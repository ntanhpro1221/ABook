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
 * Phần này không biết gì về Android ngoài [Store]: giọng, bộ giải mã clip và nơi ghi từng chương là giao diện ([Synth], [Decoder], [Outputs]) để thử trên JVM.
 */
object ListenExport {
    /** Số lần thử lại một đoạn khi giọng trực tuyến lỗi thoáng qua (như trình phát và máy tính), rồi mới dừng. */
    const val RETRIES = 2
    private val TRANSIENT = setOf("offline", "timeout", "service", "rejected")

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

    /** Dấu của một chương đã ghép: dấu vân tay, tần số, độ dài (giây). */
    class Stamp(val fingerprint: String, val rate: Int, val seconds: Double)

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

    /** Dấu vân tay của chương đã ghép: đổi giọng, cách đọc, gốc hay chữ (kể cả dòng bỏ) thì file chương cũ không dùng lại được. */
    fun fingerprint(chapter: Chapter, reading: Reading): String {
        val data = JSONArray().put(reading.voice).put(reading.origin ?: JSONObject.NULL)
            .put(JSONArray().apply { reading.readings.entries.sortedBy { it.key }.forEach { put(JSONArray().put(it.key).put(it.value)) } })
            .put(JSONArray().apply { chapter.paragraphs.forEachIndexed { index, paragraph -> put(JSONArray().put(paragraph.text).put(chapter.gaps[index])) } })
        return MessageDigest.getInstance("SHA-256").digest(data.toString().toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }

    fun workFolder(root: File, bookId: String): File = File(root, bookId.replace(Regex("[^A-Za-z0-9_-]"), "_"))

    fun audioFile(work: File, chapter: Chapter) = File(work, "${chapter.id}.m4a")

    private fun doneFile(work: File, chapter: Chapter) = File(work, "${chapter.id}.done")

    /** Dấu `.done` của chương nếu file chương còn nguyên và đúng dấu vân tay; không thì null. */
    fun ready(work: File, chapter: Chapter, reading: Reading): Stamp? {
        val json = runCatching { JSONObject(doneFile(work, chapter).readText(Charsets.UTF_8)) }.getOrNull() ?: return null
        val audio = audioFile(work, chapter)
        if (json.optString("fingerprint") != fingerprint(chapter, reading) || !audio.isFile || audio.length() == 0L) return null
        val rate = json.optInt("rate")
        return if (rate > 0) Stamp(json.getString("fingerprint"), rate, json.optDouble("seconds", 0.0)) else null
    }

    private fun writeStamp(work: File, chapter: Chapter, stamp: Stamp) {
        val part = File(work, "${chapter.id}.done.part")
        part.writeBytes(JSONObject().put("fingerprint", stamp.fingerprint).put("rate", stamp.rate).put("seconds", stamp.seconds).toString().toByteArray(Charsets.UTF_8))
        val target = doneFile(work, chapter)
        target.delete()
        part.renameTo(target)
    }

    /** Chương còn làm tiếp được: có dấu đúng và cùng tần số với chương đầu có dấu (cả cuốn phải cùng một tần số để nối). */
    fun readyStamps(work: File, chapters: List<Chapter>, reading: Reading): List<Stamp?> {
        val found = chapters.map { ready(work, it, reading) }
        val rate = found.firstOrNull { it != null }?.rate ?: return found
        return found.map { it?.takeIf { stamp -> stamp.rate == rate } }
    }

    // ---- ước trước khi bấm ------------------------------------------------------------------------------------------

    /** Cho hộp Xuất: số chương, số chữ, thời gian nghe, ước thời gian máy làm (chỉ khi giọng đã đo tốc độ), số chương đã làm sẵn từ lần trước, và chỗ trống cần ở máy. */
    class Plan(val chapters: Int, val chars: Long, val audioSeconds: Long, val secondsEstimate: Long?, val readyChapters: Int, val bytes: Long) {
        fun toJson(): JSONObject = JSONObject().put("chapters", chapters).put("chars", chars).put("audioSeconds", audioSeconds)
            .put("secondsEstimate", secondsEstimate ?: JSONObject.NULL).put("readyChapters", readyChapters).put("bytes", bytes)
    }

    /** AAC mono 64 kb/s = 8000 byte mỗi giây, dư 25% (thời lượng chỉ là ước). */
    private const val BYTES_PER_SECOND = 8000.0 * 1.25
    private const val SLACK = 16L shl 20

    /** Chỗ trống cần ở thư mục làm việc: các chương chưa làm (AAC) + file nối trung gian cỡ cả cuốn. */
    fun bytesNeeded(remainingChars: Long, totalChars: Long): Long =
        ((remainingChars + totalChars) / PreparePlan.CHARS_PER_SECOND * BYTES_PER_SECOND).toLong() + SLACK

    fun plan(chapters: List<Chapter>, reading: Reading, work: File, secondsPerChar: Double?): Plan {
        val stamps = readyStamps(work, chapters, reading)
        val chars = chapters.sumOf { it.chars.toLong() }
        val remaining = chapters.filterIndexed { index, _ -> stamps[index] == null }.sumOf { it.chars.toLong() }
        return Plan(chapters.size, chars, Math.round(chars / PreparePlan.CHARS_PER_SECOND), secondsPerChar?.let { Math.round(remaining * it) },
            stamps.count { it != null }, bytesNeeded(remaining, chars))
    }

    // ---- làm từng chương --------------------------------------------------------------------------------------------

    /** Tiến độ: `phase` "voice" (đọc, ghép chương) hay "encode" (nối các chương thành file); `waiting` "listening" khi nhường người đang nghe. */
    class Progress(val phase: String, val chapter: Int, val chapters: Int, val title: String, val waiting: String?, val percent: Int, val secondsLeft: Int?) {
        fun toJson(): JSONObject = JSONObject().put("phase", phase).put("chapter", chapter).put("chapters", chapters).put("chapterTitle", title)
            .put("waiting", waiting ?: JSONObject.NULL).put("percent", percent).put("secondsLeft", secondsLeft ?: JSONObject.NULL)
    }

    /**
     * Một lượt làm các chương. `stopped` đúng thì dừng ở chỗ an toàn kế ([Mp3Export.Stopped]; phần đã làm giữ trong `work`); `live` đúng thì người đang nghe - nhường.
     * `timed(số chữ, giây)` nhận các lần đọc mới (đo tốc độ giọng cho lần ước sau).
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
    ) {
        private val chars = chapters.sumOf { it.chars.toLong() }
        private var doneChars = 0L
        private var timedChars = 0L
        private var timedSeconds = 0.0

        private fun check() {
            if (stopped()) throw Mp3Export.Stopped()
        }

        private fun report(index: Int, phase: String, waiting: String? = null) {
            val left = if (timedChars > 0 && timedSeconds > 0) Math.round(timedSeconds / timedChars * (chars - doneChars)).toInt() else null
            val percent = if (chars > 0) minOf(100L, 100 * doneChars / chars).toInt() else 100
            progress(Progress(phase, index + 1, chapters.size, chapters[index].title, waiting, percent, left))
        }

        /** Clip của một đoạn (nhường người nghe, thử lại lỗi thoáng qua); null khi đoạn không có gì đọc được. Lỗi thật dừng cả lượt với lời nói rõ. */
        private fun clip(index: Int, text: String): File? {
            var failures = 0
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
                if (waiting) report(index, "voice")
                val began = clock()
                try {
                    val file = synth.clip(text)
                    val spent = clock() - began
                    if (spent > CACHED_MS) {
                        timedChars += text.length
                        timedSeconds += spent / 1000.0
                        timed(text.length, spent / 1000.0)
                    }
                    return file
                } catch (error: VoiceException) {
                    if (error.reason == "empty") return null
                    if (error.reason in TRANSIENT && failures < RETRIES) {
                        failures += 1
                        sleep(failures * 1000L)
                        continue
                    }
                    throw Mp3Export.Refused("Giọng đọc không đọc được một đoạn ở “${chapters[index].title}”: ${error.message} Phần đã làm được giữ - bấm xuất lại để làm tiếp.")
                }
            }
        }

        /** Làm các chương chưa có dấu đúng; trả dấu của mọi chương theo thứ tự. */
        fun build(): List<Stamp> {
            val found = readyStamps(work, chapters, reading)
            var rate = found.firstOrNull { it != null }?.rate
            val stamps = ArrayList<Stamp>()
            chapters.forEachIndexed { index, chapter ->
                check()
                val have = found[index]
                if (have != null) {
                    doneChars += chapter.chars
                    report(index, "voice")
                    stamps += have
                    return@forEachIndexed
                }
                val built = buildChapter(index, chapter, rate)
                rate = built.rate
                stamps += built
            }
            return stamps
        }

        private fun buildChapter(index: Int, chapter: Chapter, knownRate: Int?): Stamp {
            report(index, "voice")
            val final = audioFile(work, chapter)
            val part = File(work, "${chapter.id}.m4a.part")
            doneFile(work, chapter).delete()
            // Tần số chung của cả cuốn theo clip đầu đọc được của chương đầu tiên (clip đã vào bộ đệm: lần gọi sau trả ngay).
            val first = HashMap<Int, File?>()
            var rate = knownRate
            if (rate == null) {
                for ((at, paragraph) in chapter.paragraphs.withIndex()) {
                    if (!Paragraphs.isSpeakable(paragraph.text)) continue
                    val file = clip(index, paragraph.text)
                    first[at] = file
                    if (file != null) {
                        rate = decoder.rate(file)
                        break
                    }
                }
            }
            if (rate == null || rate <= 0) throw Mp3Export.Refused("Giọng đọc không đọc được gì ở “${chapter.title}”.")
            val output = outputs.open(part, rate)
            try {
                var heard = false
                chapter.paragraphs.forEachIndexed { at, paragraph ->
                    if (Paragraphs.isSpeakable(paragraph.text)) {
                        val file = if (first.containsKey(at)) first[at] else clip(index, paragraph.text)
                        if (file != null) {
                            heard = true
                            decoder.decode(file, rate, stopped) { pcm, count -> output.write(pcm, count) }
                        }
                        doneChars += paragraph.text.length
                        report(index, "voice")
                    } else if (chapter.gaps[at] > 0) {
                        silence(output, rate, chapter.gaps[at])
                    }
                    check()
                }
                if (!heard) throw Mp3Export.Refused("Giọng đọc không đọc được gì ở “${chapter.title}”.")
                val frames = output.frames
                output.finish()
                final.delete()
                if (!part.renameTo(final)) throw Mp3Export.Refused("Không ghi được file tạm của “${chapter.title}”")
                val stamp = Stamp(fingerprint(chapter, reading), rate, frames.toDouble() / rate)
                writeStamp(work, chapter, stamp)
                return stamp
            } catch (error: Throwable) {
                runCatching { output.abort() }
                part.delete()
                throw error
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
        }
    }

    // ---- ghép cuối ---------------------------------------------------------------------------------------------------

    /** Tiến độ bước nối các chương thành file (mọi chương đã có; `done` chương đã nối). Thanh vẫn dừng ở 99% tới khi file xong. */
    fun encodeProgress(chapters: List<Chapter>, done: Int, total: Int): Progress =
        Progress("encode", minOf(done + 1, total), total, chapters[minOf(done, chapters.size - 1)].title, null, 99, null)

    /** Việc cho [M4bExport.run]: mỗi chương là file AAC của nó, độ dài thật từ dấu. */
    fun exportPlan(book: JSONObject, id: String, chapters: List<Chapter>, stamps: List<Stamp>, work: File, cover: Id3Tag.Cover?, coverName: String): Mp3Export.Plan =
        Mp3Export.Plan(
            title = book.optString("title").ifEmpty { id },
            narrator = book.optString("author"),
            chapters = chapters.mapIndexed { index, chapter -> Mp3Export.Chapter(index + 1, chapter.title, stamps[index].seconds, audioFile(work, chapter)) },
            numbered = chapters.size,
            chaptersTotal = book.optInt("chaptersTotal", chapters.size),
            cover = cover,
            coverName = coverName,
        )
}
