package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.Paragraphs
import vn.abook.player.readaloud.PreparePlan
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.readaloud.VoiceException
import java.io.File
import java.security.MessageDigest

/**
 * "Xuất sách nói" cho sách Nghe ngay (chỉ có chữ) trên điện thoại - cùng việc với máy tính (webui/listen_export.py): mỗi chương chia ĐÚNG các đoạn như trình phát
 * ([ReadAloud.parsedChapters], cùng khoá bộ đệm clip: giọng + cách đọc riêng + gốc Nhật / Hàn), mỗi đoạn qua giọng ĐÃ CHỌN của cuốn, rồi ghép thành MỘT file `.m4b` có
 * mục lục chương bằng đường mã hoá của "Xuất M4B" ([M4bExport], [Mp4Finish]). Chỉ M4B: điện thoại không có bộ mã hoá MP3 (MediaCodec của Android chỉ giải mã MP3, thêm
 * thư viện native vào APK là điều bị cấm) và mỗi chương là một MP3 độc lập thì app sách nói nào cũng mở được M4B.
 *
 * Việc NGHE đi trước: có đoạn của người nghe đang được đọc ([ReadAloud.liveJobs]) thì việc xuất đứng chờ từng đoạn một. Mỗi chương ghi xong là một file AAC riêng
 * (`<mã chương>.m4a`, đã mã hoá đúng một lần ở 64 kb/s mono như M4B của Studio) cùng dấu `.done` ghi dấu vân tay của chương (giọng + cách đọc + chữ): huỷ, lỗi hay app bị
 * giết giữa chừng rồi xuất lại thì chương nào còn dấu đúng được bỏ qua. Ghép cuối ([ListenAudio]) chép nguyên các mẫu AAC của từng chương nối nhau, không mã hoá lại.
 *
 * "Kèm nhạc nền" ([Music], như listen_export.py máy tính): chương có nhạc ghép thành bản tạm thứ hai `<mã>.music.m4a` + `.music.done` (dấu vân tay = của giọng + nhạc
 * của chương, nên đổi nhạc chỉ chương ấy làm lại). Điện thoại không giữ giọng không mất tiếng như FLAC của máy tính: giọng ghép lại từ bộ đệm clip vào `<mã>.voice.pcm`
 * (đoạn đã bị đẩy khỏi bộ đệm thì đọc lại - hộp Xuất báo trước số đoạn ấy, [Plan.rereads]), trộn, mã hoá, đo đỉnh thật (cả chương không nhạc của lượt ấy); vượt
 * trần thì hạ cộng dồn và mã hoá lại RIÊNG chương ấy, tối đa [Run.PEAK_RETRIES] lần.
 *
 * Phần này không biết gì về Android ngoài [Store]: giọng, bộ giải mã clip và nơi ghi từng chương là giao diện ([Synth], [Decoder], [Outputs]) để thử trên JVM.
 */
object ListenExport {
    /** Số lần thử lại một đoạn khi giọng trực tuyến lỗi thoáng qua khác (dịch vụ bận, bị từ chối - như máy tính), rồi mới dừng. */
    const val RETRIES = 2
    private val TRANSIENT = setOf("service", "rejected")

    /**
     * Lỗi MẠNG (mất mạng, quá giờ): lượt xuất đứng chờ mạng ("Đang chờ mạng…", `waiting` "network") thay vì dừng - nghỉ [NETWORK_WAITS_MS] (hết dãy thì giữ số cuối) tới
     * khi mất liên tục quá [OUTAGE_MS]; như `listen_export.py` máy tính (soát a62: mất mạng 3 giây là dừng cả lượt).
     */
    private val NETWORK = setOf("offline", "timeout")
    val NETWORK_WAITS_MS = longArrayOf(1000, 2000, 4000, 8000, 15000)
    const val OUTAGE_MS = 30_000L

    /** Lúc nghỉ chờ mạng vẫn hỏi "Dừng" chừng này ms một lần. */
    const val CANCEL_POLL_MS = 200L

    /** "còn khoảng ..." chỉ hiện khi đã đo đủ: chừng này đoạn đọc MỚI và chừng này ms chạy (như máy tính; soát a62: một đoạn đầu cho "còn 4 phút" khi thật còn 51 giây). */
    const val ETA_READS = 3
    const val ETA_MS = 20_000L

    /** Thư mục làm việc không ai đụng tới quá chừng này ngày bị dọn lúc mở app ([sweepFolders]). */
    const val STALE_DAYS = 7

    /** Clip trả nhanh hơn thế là từ bộ đệm: không nói gì về tốc độ giọng (như `CACHED_SECONDS` của máy tính). */
    const val CACHED_MS = 50L

    /** Sách nói giọng đọc: mono (như M4B của Studio). */
    const val CHANNELS = 1

    /** Số mẫu PCM trong một khung AAC-LC. */
    const val AAC_FRAME = 1024

    /** Một chương có chữ đọc được: tên như người nghe thấy, các đoạn đúng như trình phát, quãng lặng (ms) sau từng đoạn. */
    class Chapter(val id: Int, val title: String, val paragraphs: List<Paragraphs.Paragraph>) {
        val gaps: IntArray = Paragraphs.sceneBreakGaps(paragraphs)
        val speakable: List<Paragraphs.Paragraph> get() = paragraphs.filter { Paragraphs.isSpeakable(it.text) }
        val chars: Int get() = speakable.sumOf { it.text.length }
    }

    /** Cách đọc cuốn: giọng + gốc Nhật / Hàn + cách đọc riêng - cùng thứ người nghe dùng, nên cùng khoá bộ đệm clip. */
    class Reading(val voice: String, val origin: String?, val readings: Map<String, String>)

    /** Giọng: clip âm thanh của MỘT đoạn (từ bộ đệm hay đọc mới); null khi đoạn không có gì đọc được. Hỏng thì ném [VoiceException]. */
    fun interface Synth {
        fun clip(text: String): File?
    }

    /** Bộ giải mã clip (MP3 / WAV) ra PCM 16-bit mono. */
    interface Decoder {
        /** Tần số mẫu của clip. */
        fun rate(file: File): Int

        /** Giải mã `file` ra PCM mono ở `rate`, từng khối `write(mẫu, số mẫu)`; `stopped` đúng thì ném [Mp3Export.Stopped]. */
        fun decode(file: File, rate: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit)
    }

    /** Nơi ghi PCM mono của một chương (bộ mã hoá AAC: [M4bAudio.AacSink]). `frames`: số khung PCM đã nhận. */
    interface PcmOutput {
        val frames: Long
        fun write(pcm: ShortArray, count: Int)
        fun finish()
        fun abort()
    }

    fun interface Outputs {
        fun open(file: File, rate: Int): PcmOutput
    }

    /**
     * Dấu của một chương đã ghép: dấu vân tay, tần số, độ dài (giây). Bản kèm nhạc (`mixed`) thêm: số đoạn thiếu nhạc, dB đã hạ, đỉnh thật sau mã hoá (dBTP), và dấu
     * vân tay của riêng giọng (`voice` - đổi nhạc thì biết giọng chương này đã từng làm, cho [Plan.rereads]).
     */
    class Stamp(
        val fingerprint: String,
        val rate: Int,
        val seconds: Double,
        val mixed: Boolean = false,
        val musicMissing: Int = 0,
        val loweredDb: Double = 0.0,
        val peakDbtp: Double? = null,
        val voice: String? = null,
    )

    // ---- chương của cuốn ---------------------------------------------------------------------------------------------

    /**
     * Các chương chỉ-có-chữ của cuốn `id` như người nghe thấy (tên chương, dòng đã bỏ, cách chia đoạn) và có chữ đọc được; chương trống hay không đọc được bị bỏ.
     * `parse` đọc chữ các chương (mặc định: chính cách trình phát chia đoạn).
     */
    fun chapters(
        id: String,
        parse: (String, List<Int>) -> Map<Int, Pair<String, List<Paragraphs.Paragraph>>> = ReadAloud::parsedChapters,
    ): List<Chapter> {
        val book = Store.manifest(id) ?: throw Mp3Export.Refused("Không tìm thấy sách này trên điện thoại")
        val array = book.optJSONArray("chapters") ?: JSONArray()
        val items = (0 until array.length()).mapNotNull { array.optJSONObject(it) }.filter { it.optString("text").startsWith("texts/") }
        val parsed = parse(id, items.map { it.optInt("id") })
        return items.mapNotNull { item ->
            val paragraphs = parsed[item.optInt("id")]?.second ?: return@mapNotNull null
            val title = item.optString("fullTitle").ifEmpty { item.optString("title") }.ifEmpty { "Chương ${item.optInt("index", item.optInt("id"))}" }
            Chapter(item.optInt("id"), title, paragraphs).takeIf { it.speakable.isNotEmpty() }
        }
    }

    // ---- chương đã ghép (làm tiếp được) -------------------------------------------------------------------------------

    /**
     * Dấu vân tay của chương đã ghép: đổi giọng, cách đọc, gốc hay chữ (kể cả dòng bỏ) thì file chương cũ không dùng lại được. `music`: bản trộn nhạc của chương
     * (thêm `["music", vân tay nhạc]`, như máy tính).
     */
    fun fingerprint(chapter: Chapter, reading: Reading, music: MusicExport.ChapterMusic? = null): String {
        val data = JSONArray().put(reading.voice).put(reading.origin ?: JSONObject.NULL)
            .put(JSONArray().apply { reading.readings.entries.sortedBy { it.key }.forEach { put(JSONArray().put(it.key).put(it.value)) } })
            .put(JSONArray().apply { chapter.paragraphs.forEachIndexed { index, paragraph -> put(JSONArray().put(paragraph.text).put(chapter.gaps[index])) } })
        if (music != null) data.put(JSONArray().put("music").put(music.fingerprint()))
        return MessageDigest.getInstance("SHA-256").digest(data.toString().toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }

    fun workFolder(root: File, bookId: String): File = File(root, bookId.replace(Regex("[^A-Za-z0-9_-]"), "_"))

    /** Lần cuối có gì trong `folder` được ghi: mtime mới nhất của chính nó và mọi file trong đó. */
    private fun touched(folder: File): Long = folder.walkTopDown().maxOfOrNull { it.lastModified() } ?: folder.lastModified()

    /**
     * Dọn thư mục làm việc của các lượt xuất bỏ dở (như `sweep_work` máy tính): của sách không còn trên máy (`exists(tên thư mục)` false) hay không ai đụng tới quá
     * `maxAgeMs`. Sách đang xuất (`busy`: mã sách) không bao giờ bị đụng. Trả các thư mục đã xoá.
     */
    fun sweepFolders(root: File, exists: (String) -> Boolean, busy: Set<String>, now: Long = System.currentTimeMillis(), maxAgeMs: Long = STALE_DAYS * 86_400_000L): List<File> {
        val keep = busy.map { workFolder(root, it).name }.toSet()
        return root.listFiles().orEmpty().filter { folder ->
            folder.isDirectory && folder.name !in keep && (!exists(folder.name) || now - touched(folder) > maxAgeMs) && folder.deleteRecursively()
        }
    }

    /** File AAC tạm của chương: `<mã>.m4a`, bản kèm nhạc `<mã>.music.m4a`. */
    fun audioFile(work: File, chapter: Chapter, mixed: Boolean = false) = File(work, "${chapter.id}${if (mixed) ".music" else ""}.m4a")

    private fun doneFile(work: File, chapter: Chapter, mixed: Boolean = false) = File(work, "${chapter.id}${if (mixed) ".music" else ""}.done")

    /** Giọng của chương (PCM 16-bit mono) trong lúc làm bản kèm nhạc; xoá khi chương xong. */
    fun voiceFile(work: File, chapter: Chapter) = File(work, "${chapter.id}.voice.pcm")

    private fun readStamp(work: File, chapter: Chapter, mixed: Boolean): JSONObject? =
        runCatching { JSONObject(doneFile(work, chapter, mixed).readText(Charsets.UTF_8)) }.getOrNull()

    /** Dấu `.done` của chương (bản kèm nhạc `music` nếu có) nếu file chương còn nguyên và đúng dấu vân tay; không thì null. */
    fun ready(work: File, chapter: Chapter, reading: Reading, music: MusicExport.ChapterMusic? = null): Stamp? {
        val mixed = music != null
        val json = readStamp(work, chapter, mixed) ?: return null
        val audio = audioFile(work, chapter, mixed)
        if (json.optString("fingerprint") != fingerprint(chapter, reading, music) || !audio.isFile || audio.length() == 0L) return null
        val rate = json.optInt("rate")
        if (rate <= 0) return null
        return Stamp(json.getString("fingerprint"), rate, json.optDouble("seconds", 0.0), mixed, json.optInt("musicMissing"), json.optDouble("loweredDb", 0.0),
            json.optDouble("peakDbtp").takeIf { json.has("peakDbtp") && !it.isNaN() }, json.optString("voice").ifEmpty { null })
    }

    private fun writeStamp(work: File, chapter: Chapter, stamp: Stamp) {
        val part = File(work, "${chapter.id}${if (stamp.mixed) ".music" else ""}.done.part")
        val json = JSONObject().put("fingerprint", stamp.fingerprint).put("rate", stamp.rate).put("seconds", stamp.seconds)
        if (stamp.mixed) json.put("musicMissing", stamp.musicMissing).put("voice", stamp.voice)
        // Đã kiểm đỉnh (lượt kèm nhạc): mức đã hạ và đỉnh cuối - làm tiếp không đo lại.
        if (stamp.peakDbtp != null) {
            json.put("loweredDb", stamp.loweredDb)
            stamp.peakDbtp.takeIf { it.isFinite() }?.let { json.put("peakDbtp", it) }
        }
        part.writeBytes(json.toString().toByteArray(Charsets.UTF_8))
        val target = doneFile(work, chapter, stamp.mixed)
        target.delete()
        part.renameTo(target)
    }

    /**
     * Chương còn làm tiếp được: có dấu đúng (bản kèm nhạc với chương `music(id)` trả nhạc) và cùng tần số với chương đầu có dấu (cả cuốn phải cùng một tần số để
     * nối).
     */
    fun readyStamps(work: File, chapters: List<Chapter>, reading: Reading, music: (Int) -> MusicExport.ChapterMusic? = { null }): List<Stamp?> {
        val found = chapters.map { ready(work, it, reading, music(it.id)) }
        val rate = found.firstOrNull { it != null }?.rate ?: return found
        return found.map { it?.takeIf { stamp -> stamp.rate == rate } }
    }

    /**
     * Giọng của chương đã từng ghép xong (bản không nhạc, hay bản kèm nhạc nào đó cùng giọng + chữ): phải làm lại chương này (đổi / bật / tắt nhạc) là ghép lại giọng
     * đã đọc, chỉ đoạn bị đẩy khỏi bộ đệm clip mới phải đọc lại.
     */
    private fun voiced(work: File, chapter: Chapter, reading: Reading): Boolean {
        if (ready(work, chapter, reading) != null) return true
        val json = readStamp(work, chapter, true) ?: return false
        return json.optString("voice") == fingerprint(chapter, reading) && audioFile(work, chapter, true).isFile
    }

    // ---- ước trước khi bấm ------------------------------------------------------------------------------------------

    /**
     * Cho hộp Xuất: số chương, số chữ, thời gian nghe, ước thời gian máy làm (chỉ khi giọng đã đo tốc độ), phần đã có sẵn (`readyChapters` chương có đủ - đã ghép hay mọi đoạn
     * có clip trong bộ đệm; `readySeconds` giây nghe đã có), chỗ trống cần ở máy, và số đoạn phải đọc lại (`rereads`: chương đã có giọng nhưng phải ghép lại vì đổi nhạc, mà
     * clip đoạn ấy đã bị đẩy khỏi bộ đệm).
     */
    class Plan(val chapters: Int, val chars: Long, val audioSeconds: Long, val secondsEstimate: Long?, val readyChapters: Int, val bytes: Long, val rereads: Int = 0,
               val readySeconds: Long = 0) {
        fun toJson(): JSONObject = JSONObject().put("chapters", chapters).put("chars", chars).put("audioSeconds", audioSeconds)
            .put("secondsEstimate", secondsEstimate ?: JSONObject.NULL).put("readyChapters", readyChapters).put("bytes", bytes).put("rereads", rereads)
            .put("readySeconds", readySeconds)
    }

    /** AAC mono 64 kb/s = 8000 byte mỗi giây, dư 25% (thời lượng chỉ là ước). */
    private const val BYTES_PER_SECOND = 8000.0 * 1.25
    private const val SLACK = 16L shl 20

    /** Giọng của giọng đọc trên máy cao nhất 48 kHz: PCM 16-bit mono 96 000 byte mỗi giây ([voiceFile] của bản kèm nhạc). */
    private const val VOICE_PCM_PER_SECOND = 48_000.0 * 2

    /**
     * Chỗ trống cần ở thư mục làm việc: các chương chưa làm (AAC) + file nối trung gian cỡ cả cuốn, + `extra` (kèm nhạc: [voiceBytes] + bộ đệm bài
     * [BookMusic.pcmBytes]).
     */
    fun bytesNeeded(remainingChars: Long, totalChars: Long, extra: Long = 0): Long =
        ((remainingChars + totalChars) / PreparePlan.CHARS_PER_SECOND * BYTES_PER_SECOND).toLong() + SLACK + extra

    /** Giọng PCM tạm của chương dài nhất (bản kèm nhạc ghép giọng ra đĩa trước khi trộn, một chương một lúc). */
    fun voiceBytes(chapters: List<Chapter>): Long =
        ((chapters.maxOfOrNull { it.chars } ?: 0) / PreparePlan.CHARS_PER_SECOND * VOICE_PCM_PER_SECOND * 1.25).toLong()

    /**
     * Ước cho hộp Xuất. `music(id)`: nhạc của chương nếu xuất "Kèm nhạc nền" ([MusicExport.audible]); `cachedMs(chữ)`: độ dài (ms) clip của đoạn ấy còn trong bộ đệm,
     * null nếu chưa có (`cachedMs` null = không tra: không đếm `rereads`, không tính phần có sẵn); `extra`: chỗ trống thêm của bản kèm nhạc.
     * Thời gian nghe = độ dài thật của phần đã có (chương đã ghép + clip trong bộ đệm + quãng lặng) + phần chưa có ước theo số chữ với tốc độ ĐO trên chính các clip ấy
     * (chưa có clip nào: [PreparePlan.CHARS_PER_SECOND]) - như máy tính (soát a62: "khoảng 10 phút" cho cuốn thật 8:44). Máy chỉ phải đọc phần chưa có (`secondsEstimate`).
     */
    fun plan(chapters: List<Chapter>, reading: Reading, work: File, secondsPerChar: Double?, music: (Int) -> MusicExport.ChapterMusic? = { null },
             cachedMs: ((String) -> Long?)? = null, extra: Long = 0): Plan {
        val stamps = readyStamps(work, chapters, reading, music)
        val chars = chapters.sumOf { it.chars.toLong() }
        val remaining = chapters.filterIndexed { index, _ -> stamps[index] == null }.sumOf { it.chars.toLong() }
        val rereads = if (cachedMs == null) 0 else chapters.filterIndexed { index, chapter -> stamps[index] == null && voiced(work, chapter, reading) }
            .sumOf { chapter -> chapter.speakable.count { cachedMs(it.text) == null } }
        var heardChars = 0L
        var heardSeconds = 0.0
        var gaps = 0.0
        var open = 0L
        var ready = 0
        chapters.forEachIndexed { index, chapter ->
            val silence = chapter.gaps.sum() / 1000.0
            gaps += silence
            val stamp = stamps[index]
            if (stamp != null) {
                heardChars += chapter.chars
                heardSeconds += maxOf(0.0, stamp.seconds - silence)
                ready += 1
                return@forEachIndexed
            }
            var missing = 0L
            for (paragraph in chapter.speakable) {
                val ms = cachedMs?.invoke(paragraph.text)
                if (ms == null) {
                    missing += paragraph.text.length
                } else {
                    heardChars += paragraph.text.length
                    heardSeconds += ms / 1000.0
                }
            }
            open += missing
            if (missing == 0L) ready += 1
        }
        val rate = if (heardChars > 0 && heardSeconds > 0) heardChars / heardSeconds else PreparePlan.CHARS_PER_SECOND
        return Plan(chapters.size, chars, Math.round(heardSeconds + gaps + open / rate), secondsPerChar?.let { Math.round(open * it) },
            ready, bytesNeeded(remaining, chars, extra), rereads, Math.round(heardSeconds))
    }

    // ---- làm từng chương --------------------------------------------------------------------------------------------

    /**
     * Tiến độ: `phase` "voice" (đọc, ghép chương), "music" (trộn nhạc chương), "peaks" (kiểm đỉnh âm), "reencode" (mã hoá lại lượt `peakRound` vì `peakOver` chương
     * vượt đỉnh) hay "encode" (nối các chương thành file); `waiting` "listening" khi nhường người đang nghe, "network" khi đang chờ mạng về.
     */
    class Progress(val phase: String, val chapter: Int, val chapters: Int, val title: String, val waiting: String?, val percent: Int, val secondsLeft: Int?,
                   val peakRound: Int? = null, val peakOver: Int? = null) {
        fun toJson(): JSONObject = JSONObject().put("phase", phase).put("chapter", chapter).put("chapters", chapters).put("chapterTitle", title)
            .put("waiting", waiting ?: JSONObject.NULL).put("percent", percent).put("secondsLeft", secondsLeft ?: JSONObject.NULL).apply {
                peakRound?.let { put("peakRound", it) }
                peakOver?.let { put("peakOver", it) }
            }
    }

    /** "Kèm nhạc nền" của một lượt: bộ trộn, hằng số đo đỉnh, và cách đo đỉnh thật (dBTP) của một file chương đã mã hoá (Android: [M4bAudio.truePeak]). */
    class Music(val mixer: MusicExport.Mixer, val guard: MusicRender.Params, val peak: (File) -> Double)

    /**
     * Một lượt làm các chương. `stopped` đúng thì dừng ở chỗ an toàn kế ([Mp3Export.Stopped]; phần đã làm giữ trong `work`) - lượt đọc đang bay bị người gọi huỷ ([Synth]
     * ném CancellationException) cũng thành [Mp3Export.Stopped]; `live` đúng thì người đang nghe - nhường. `timed(số chữ, giây)` nhận các lần đọc mới (đo tốc độ giọng cho
     * lần ước sau). `music`: "Kèm nhạc nền" (null = như cũ). `cached(chữ)`: đoạn đã có clip trong bộ đệm - thời gian còn lại chỉ tính phần chưa có.
     */
    class Run(
        private val chapters: List<Chapter>,
        private val reading: Reading,
        private val work: File,
        private val synth: Synth,
        private val decoder: Decoder,
        private val outputs: Outputs,
        private val progress: (Progress) -> Unit,
        private val stopped: () -> Boolean,
        private val live: () -> Boolean = { false },
        private val timed: (Int, Double) -> Unit = { _, _ -> },
        private val sleep: (Long) -> Unit = { Thread.sleep(it) },
        private val clock: () -> Long = { System.nanoTime() / 1_000_000 },
        private val music: Music? = null,
        private val cached: (String) -> Boolean = { false },
    ) {
        private val chars = chapters.sumOf { it.chars.toLong() }
        private var doneChars = 0L
        private var timedChars = 0L
        private var timedSeconds = 0.0
        private var reads = 0 // đoạn đọc MỚI (không từ bộ đệm): đủ [ETA_READS] mới ước thời gian còn lại
        private val began = clock()
        private val open = HashSet<Pair<Int, Int>>() // (chương, số thứ tự đoạn) chưa có clip lúc bắt đầu: phần máy còn phải đọc
        private var openChars = 0L

        private fun check() {
            if (stopped()) throw Mp3Export.Stopped()
        }

        /** Ước giây còn lại: số chữ CHƯA CÓ clip còn lại / tốc độ đo trên các đoạn đọc mới; null khi chưa đo đủ ([ETA_READS] đoạn mới và [ETA_MS]). */
        internal fun secondsLeft(): Int? {
            if (reads < ETA_READS || clock() - began < ETA_MS || timedChars <= 0 || timedSeconds <= 0) return null
            return Math.round(timedSeconds / timedChars * openChars).toInt()
        }

        private fun report(index: Int, phase: String, waiting: String? = null, round: Int? = null, over: Int? = null) {
            val percent = if (chars > 0) minOf(100L, 100 * doneChars / chars).toInt() else 100
            progress(Progress(phase, index + 1, chapters.size, chapters[index].title, waiting, percent, secondsLeft(), round, over))
        }

        /** Nghỉ `ms` mà vẫn nghe "Dừng" (hỏi mỗi [CANCEL_POLL_MS]). */
        private fun pause(ms: Long) {
            val end = clock() + ms
            while (true) {
                check()
                val left = end - clock()
                if (left <= 0) return
                sleep(minOf(CANCEL_POLL_MS, left))
            }
        }

        /** Nhạc của chương nếu lượt này kèm nhạc và chương có mốc. */
        private fun variant(id: Int): MusicExport.ChapterMusic? = music?.mixer?.chapter(id)

        /**
         * Clip của một đoạn (nhường người nghe; mất mạng thì chờ mạng tới khi mất liên tục quá [OUTAGE_MS]; lỗi thoáng qua khác thử lại [RETRIES] lần); null khi đoạn không có
         * gì đọc được. Lỗi thật dừng cả lượt với lời nói rõ.
         */
        private fun clip(index: Int, text: String): File? {
            var failures = 0
            var outage: Long? = null // lúc lần lỗi mạng đầu của chuỗi lỗi liền nhau
            while (true) {
                var waiting = false
                while (live()) {
                    check()
                    if (!waiting) {
                        report(index, "voice", "listening")
                        waiting = true
                    }
                    sleep(LIVE_POLL_MS)
                }
                check()
                if (waiting || outage != null) report(index, "voice")
                val began = clock()
                try {
                    val file = synth.clip(text)
                    val spent = clock() - began
                    if (spent > CACHED_MS) {
                        timedChars += text.length
                        timedSeconds += spent / 1000.0
                        reads += 1
                        timed(text.length, spent / 1000.0)
                    }
                    return file
                } catch (cancelled: java.util.concurrent.CancellationException) {
                    check() // người dùng bấm "Dừng": lượt đọc đang bay đã bị cắt ([ClipCancel])
                    throw cancelled
                } catch (error: VoiceException) {
                    if (error.reason == "empty") return null
                    if (error.offline || error.reason in NETWORK) {
                        val now = clock()
                        val since = outage ?: now.also { outage = it }
                        if (now - since <= OUTAGE_MS) {
                            report(index, "voice", "network")
                            pause(NETWORK_WAITS_MS[minOf(failures, NETWORK_WAITS_MS.size - 1)])
                            failures += 1
                            continue
                        }
                    } else if (error.reason in TRANSIENT && failures < RETRIES) {
                        failures += 1
                        pause(failures * 1000L)
                        continue
                    }
                    throw Mp3Export.Refused("“${chapters[index].title}”: ${error.message}; giữ phần đã làm — bạn xuất lại để tiếp tục.")
                }
            }
        }

        /** Làm các chương chưa có dấu đúng; trả dấu của mọi chương theo thứ tự. */
        fun build(): List<Stamp> {
            val found = readyStamps(work, chapters, reading, ::variant)
            chapters.forEachIndexed { index, chapter ->
                if (found[index] != null) return@forEachIndexed
                chapter.paragraphs.forEachIndexed { at, paragraph ->
                    if (Paragraphs.isSpeakable(paragraph.text) && !cached(paragraph.text)) {
                        open += chapter.id to at
                        openChars += paragraph.text.length
                    }
                }
            }
            var rate = found.firstOrNull { it != null }?.rate
            val stamps = ArrayList<Stamp>()
            chapters.forEachIndexed { index, chapter ->
                check()
                val chapterMusic = variant(chapter.id)
                val have = found[index]
                if (have != null) {
                    doneChars += chapter.chars
                    report(index, "voice")
                    // Chương trộn từ lần trước: đoạn thiếu nhạc lấy từ dấu (bộ trộn không chạy lại chương này).
                    if (have.mixed) music?.mixer?.lost?.set(chapter.id, have.musicMissing)
                    stamps += have
                    return@forEachIndexed
                }
                val built = if (chapterMusic != null) buildMixed(index, chapter, chapterMusic, rate) else buildChapter(index, chapter, rate)
                rate = built.rate
                stamps += built
            }
            return stamps
        }

        /** Tần số chung của cả cuốn theo clip đầu đọc được của chương (clip đã vào bộ đệm: lần gọi sau trả ngay); clip đã lấy giữ trong `first`. */
        private fun firstRate(index: Int, chapter: Chapter, first: HashMap<Int, File?>): Int {
            for ((at, paragraph) in chapter.paragraphs.withIndex()) {
                if (!Paragraphs.isSpeakable(paragraph.text)) continue
                val file = clip(index, paragraph.text)
                first[at] = file
                if (file != null) {
                    val rate = decoder.rate(file)
                    if (rate > 0) return rate
                    break
                }
            }
            throw Mp3Export.Refused("Giọng đọc không đọc được gì ở “${chapter.title}”.")
        }

        /** Giọng của cả chương (clip từng đoạn + quãng lặng) vào `output` ở `rate`. */
        private fun speak(index: Int, chapter: Chapter, rate: Int, first: Map<Int, File?>, output: PcmOutput) {
            var heard = false
            chapter.paragraphs.forEachIndexed { at, paragraph ->
                if (Paragraphs.isSpeakable(paragraph.text)) {
                    val file = if (first.containsKey(at)) first[at] else clip(index, paragraph.text)
                    if (file != null) {
                        heard = true
                        decoder.decode(file, rate, stopped) { pcm, count -> output.write(pcm, count) }
                    }
                    doneChars += paragraph.text.length
                    if (open.remove(chapter.id to at)) openChars -= paragraph.text.length
                    report(index, "voice")
                } else if (chapter.gaps[at] > 0) {
                    silence(output, rate, chapter.gaps[at])
                }
                check()
            }
            if (!heard) throw Mp3Export.Refused("Giọng đọc không đọc được gì ở “${chapter.title}”.")
        }

        private fun publish(part: File, final: File, chapter: Chapter) {
            final.delete()
            if (!part.renameTo(final)) throw Mp3Export.Refused("Chưa ghi được file tạm của “${chapter.title}”")
        }

        /**
         * Chương không nhạc. Lượt kèm nhạc thì chương này cũng kiểm đỉnh sau mã hoá (như máy tính kiểm mọi chương của M4B); vượt thì ghép lại giọng từ clip
         * (clip còn trong bộ đệm: không đọc lại) qua [Lowered] - chương không nhạc không giữ PCM tạm. Không kèm nhạc: như trước, không đo.
         */
        private fun buildChapter(index: Int, chapter: Chapter, knownRate: Int?): Stamp {
            report(index, "voice")
            val final = audioFile(work, chapter)
            val part = File(work, "${chapter.id}.m4a.part")
            doneFile(work, chapter).delete()
            val first = HashMap<Int, File?>()
            val rate = knownRate ?: firstRate(index, chapter, first)
            try {
                var frames = 0L
                encode(part, rate) { output ->
                    speak(index, chapter, rate, first, output)
                    frames = output.frames
                    output.finish()
                }
                val (lowered, peak) = music?.let { music ->
                    guarded(index, part, music) { db ->
                        val counted = doneChars // ghép lại không phải tiến độ mới
                        encode(part, rate) { output -> Lowered(output, db).also { speak(index, chapter, rate, first, it) }.finish() }
                        doneChars = counted
                    }
                } ?: (0.0 to null)
                publish(part, final, chapter)
                val stamp = Stamp(fingerprint(chapter, reading), rate, frames.toDouble() / rate, loweredDb = lowered, peakDbtp = peak)
                writeStamp(work, chapter, stamp)
                return stamp
            } catch (error: Throwable) {
                part.delete()
                throw error
            }
        }

        /**
         * Bản kèm nhạc của chương: giọng ghép vào [voiceFile], trộn nhạc ([MusicExport.Mixer.wrap], biết độ dài chương), mã hoá `<mã>.music.m4a`, kiểm đỉnh
         * ([guarded]: trộn + mã hoá lại từ giọng đã ghép, hạ cộng dồn).
         */
        private fun buildMixed(index: Int, chapter: Chapter, chapterMusic: MusicExport.ChapterMusic, knownRate: Int?): Stamp {
            val music = music!!
            report(index, "voice")
            val final = audioFile(work, chapter, true)
            val part = File(work, "${chapter.id}.music.m4a.part")
            doneFile(work, chapter, true).delete()
            val first = HashMap<Int, File?>()
            val rate = knownRate ?: firstRate(index, chapter, first)
            val voice = voiceFile(work, chapter)
            try {
                val frames = PcmFile(voice).use { pcm ->
                    speak(index, chapter, rate, first, pcm)
                    pcm.finish()
                    pcm.frames
                }
                val seconds = frames.toDouble() / rate
                val mix = { db: Double ->
                    encode(part, rate) { output ->
                        val mixed = music.mixer.wrap(chapter.id, Lowered(output, db), rate, CHANNELS, seconds)
                        PcmFile.read(voice, stopped) { pcm, count -> mixed.write(pcm, count) }
                        mixed.finish()
                    }
                }
                report(index, "music")
                mix(0.0)
                val (lowered, peak) = guarded(index, part, music, mix)
                publish(part, final, chapter)
                val stamp = Stamp(fingerprint(chapter, reading, chapterMusic), rate, seconds, true, music.mixer.lost[chapter.id] ?: 0, lowered, peak,
                    fingerprint(chapter, reading))
                writeStamp(work, chapter, stamp)
                return stamp
            } catch (error: Throwable) {
                part.delete()
                throw error
            } finally {
                voice.delete()
            }
        }

        /** Một lần mã hoá chương vào `part`: `feed` đổ PCM vào bộ mã hoá rồi đóng nó (`finish`, có thể qua ống trộn / hạ); hỏng thì bỏ bộ mã hoá. */
        private fun encode(part: File, rate: Int, feed: (PcmOutput) -> Unit) {
            val output = outputs.open(part, rate)
            try {
                feed(output)
            } catch (error: Throwable) {
                runCatching { output.abort() }
                throw error
            }
        }

        /**
         * Đỉnh thật của chương vừa mã hoá (`part`); vượt trần thì hạ CỘNG DỒN ([AacJoin.lowerOver]) và `again(dB đã hạ)` mã hoá lại RIÊNG chương này, tối đa
         * [PEAK_RETRIES] lượt - còn vượt vẫn xong, dấu ghi đỉnh. Trả (dB đã hạ, đỉnh cuối).
         */
        private fun guarded(index: Int, part: File, music: Music, again: (Double) -> Unit): Pair<Double, Double> {
            val lowered = doubleArrayOf(0.0)
            var round = 0
            while (true) {
                check()
                report(index, "peaks", round = round)
                val peak = music.peak(part)
                if (round == PEAK_RETRIES || AacJoin.lowerOver(doubleArrayOf(peak), music.guard.ceilingDbtp, lowered).isEmpty()) return lowered[0] to peak
                round++
                report(index, "reencode", round = round, over = 1)
                again(lowered[0])
            }
        }

        private fun silence(output: PcmOutput, rate: Int, ms: Int) {
            var left = Math.round(rate.toDouble() * ms / 1000).toInt()
            val block = ShortArray(minOf(left, 16384))
            while (left > 0) {
                val take = minOf(left, block.size)
                output.write(block, take)
                left -= take
            }
        }

        companion object {
            const val LIVE_POLL_MS = 200L

            /** Số lần mã hoá lại một chương vượt đỉnh (K2_SPEC 3.2, chốt Lead: đường L theo chương, 2 lần). */
            const val PEAK_RETRIES = 2
        }
    }

    /** Ống hạ mức: mẫu qua hạ `db` dB ([TruePeak.lower], `_Lowered` của máy tính) rồi vào `sink`; 0 dB = đi thẳng. */
    private class Lowered(private val sink: PcmOutput, private val db: Double) : PcmOutput {
        override val frames: Long get() = sink.frames

        override fun write(pcm: ShortArray, count: Int) {
            if (db == 0.0) return sink.write(pcm, count)
            val copy = pcm.copyOf(count)
            TruePeak.lower(copy, db)
            sink.write(copy, count)
        }

        override fun finish() = sink.finish()
        override fun abort() = sink.abort()
    }

    /** PCM 16-bit LE mono thô trên đĩa ([voiceFile]): ghi như một [PcmOutput], đọc lại từng khối ([read]). */
    private class PcmFile(file: File) : PcmOutput, AutoCloseable {
        private val out = file.outputStream().buffered(256 * 1024)
        private val bytes = ByteArray(2 * BLOCK)
        override var frames = 0L
            private set

        override fun write(pcm: ShortArray, count: Int) {
            var at = 0
            while (at < count) {
                val take = minOf(count - at, BLOCK)
                for (i in 0 until take) {
                    val v = pcm[at + i].toInt()
                    bytes[2 * i] = v.toByte()
                    bytes[2 * i + 1] = (v shr 8).toByte()
                }
                out.write(bytes, 0, 2 * take)
                at += take
            }
            frames += count / CHANNELS
        }

        override fun finish() = out.flush()
        override fun abort() = close()
        override fun close() = out.close()

        companion object {
            private const val BLOCK = 16384

            fun read(file: File, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) {
                file.inputStream().buffered(256 * 1024).use { input ->
                    val bytes = ByteArray(2 * BLOCK)
                    val pcm = ShortArray(BLOCK)
                    var low = -1 // byte thấp còn chờ khi khối đọc dừng giữa một mẫu
                    while (true) {
                        if (stopped()) throw Mp3Export.Stopped()
                        val read = input.read(bytes)
                        if (read < 0) break
                        var count = 0
                        for (k in 0 until read) {
                            val b = bytes[k].toInt() and 0xff
                            if (low < 0) {
                                low = b
                            } else {
                                pcm[count++] = ((b shl 8) or low).toShort()
                                low = -1
                            }
                        }
                        if (count > 0) write(pcm, count)
                    }
                }
            }
        }
    }

    // ---- ghép cuối ---------------------------------------------------------------------------------------------------

    /** Tiến độ bước nối các chương thành file (mọi chương đã có; `done` chương đã nối). Thanh vẫn dừng ở 99% tới khi file xong. */
    fun encodeProgress(chapters: List<Chapter>, done: Int, total: Int): Progress =
        Progress("encode", minOf(done + 1, total), total, chapters[minOf(done, chapters.size - 1)].title, null, 99, null)

    /** Việc cho [M4bExport.run]: mỗi chương là file AAC của nó (bản kèm nhạc nếu dấu là bản ấy), độ dài thật từ dấu. */
    fun exportPlan(book: JSONObject, id: String, chapters: List<Chapter>, stamps: List<Stamp>, work: File, cover: Id3Tag.Cover?, coverName: String): Mp3Export.Plan =
        Mp3Export.Plan(
            title = book.optString("title").ifEmpty { id },
            narrator = book.optString("author"),
            chapters = chapters.mapIndexed { index, chapter ->
                Mp3Export.Chapter(index + 1, chapter.title, stamps[index].seconds, audioFile(work, chapter, stamps[index].mixed))
            },
            numbered = chapters.size,
            chaptersTotal = book.optInt("chaptersTotal", chapters.size),
            cover = cover,
            coverName = coverName,
        )
}
