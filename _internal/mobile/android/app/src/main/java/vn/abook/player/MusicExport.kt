package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * Bộ trộn nhạc nền của MỘT lượt xuất trên điện thoại - port `music_export.ChapterMusic` / `Mixer` / `MixSink` của máy tính. Bài lấy từ
 * [TrackPcmCache] (trên đĩa, có bù gộp một kênh), dòng thời gian từ [MusicTimeline], âm thanh từ [MusicRender] (bus + bộ chặn + int16).
 */
object MusicExport {
    /** Nhạc của chương `id` nếu có gì để trộn (còn mốc); không thì null - chương ấy xuất y như không kèm nhạc. Chung cho [Mixer] và bản ước
     *  của hộp "Xuất sách nói" (chưa dựng bộ trộn). */
    fun audible(music: Map<Int, ChapterMusic>, id: Int): ChapterMusic? = music[id]?.takeIf { it.cues.isNotEmpty() }

    /**
     * Nhạc của một chương: mốc ([MusicCues.Cue], `track` là khoá vào `files`), file từng bài, và số mốc của kế hoạch bị bỏ vì không lấy
     * được bài nào (`musicMissing`).
     */
    class ChapterMusic(val cues: List<MusicCues.Cue>, val files: Map<String, File>, val dropped: Int = 0) {
        /** Đổi mốc, mức hay bài (kể cả bài tải lại khác cỡ) thì đổi - bản tạm chương trộn sẵn không dùng lại được. Chỉ cần ổn định trên máy này. */
        fun fingerprint(): String {
            val cues = JSONArray(cues.map(::cueJson))
            val files = JSONObject()
            for (name in this.files.keys.sorted()) {
                val file = this.files.getValue(name)
                files.put(name, JSONArray().put(file.name).put(if (file.isFile) file.length() else JSONObject.NULL))
            }
            val text = JSONArray().put(cues).put(files).put(dropped).toString()
            return MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        }

        private fun cueJson(cue: MusicCues.Cue): JSONObject = JSONObject().apply {
            put("start", cue.start)
            put("end", cue.end)
            put("track", cue.track)
            put("gainDb", cue.gainDb ?: JSONObject.NULL)
            put("steps", JSONArray(cue.steps.map { JSONArray().put(it.at).put(it.db) }))
            put("sibling", cue.sibling)
            put("tail", cue.tail)
            put("audibleStart", cue.audibleStart ?: JSONObject.NULL)
            put("audibleEnd", cue.audibleEnd ?: JSONObject.NULL)
        }
    }

    /**
     * Đứng thay bộ mã hoá cho MỘT chương: `write(PCM giọng 16-bit)` -> PCM đã trộn vào `sink`; [finish] xả phần bộ chặn còn giữ (ra đúng
     * bằng số khung giọng) rồi `sink.finish()`. Chỗ không có nhạc: từng mẫu y hệt giọng.
     */
    class MixOutput(
        private val sink: ListenExport.PcmOutput,
        private val rate: Int,
        private val channels: Int,
        private val timeline: List<MusicRender.Element>,
        private val pcm: Map<String, MusicRender.Pcm?>,
        params: MusicRender.Params,
    ) : ListenExport.PcmOutput {
        private val stream = MusicRender.GuardStream(rate, channels, params)
        private var position = 0L

        override val frames: Long get() = position

        override fun write(pcm: ShortArray, count: Int) {
            require(count % channels == 0) { "khối không trọn khung" }
            val n = count / channels
            if (n == 0) return
            val voice = DoubleArray(count) { pcm[it] / 32768.0 }
            val bus = MusicRender.renderBus(timeline, n, rate, channels, { this.pcm[it] }, start = position.toInt())
            position += n
            out(stream.feed(voice, bus.data))
        }

        override fun finish() {
            out(stream.finish())
            sink.finish()
        }

        override fun abort() = sink.abort()

        private fun out(mixed: DoubleArray) {
            if (mixed.isEmpty()) return
            sink.write(ShortArray(mixed.size) { MusicRender.toInt16(mixed[it]) }, mixed.size)
        }
    }

    /**
     * dB bù gộp một kênh của bài `file` (PCM đã gộp `pcm` ở `rate`) đo trên đoạn phát [start, end) giây ([playedSpan]) - Android:
     * [M4bAudio.foldOffset], `music_export.mono_offset_db`. Bài một kênh / không đo được -> 0.
     */
    fun interface FoldOffset {
        fun db(file: File, pcm: MusicRender.Pcm, rate: Int, start: Int, end: Int): Double
    }

    /**
     * `music_export.played_span`: khoảng phát (giây trong bài, đầu làm tròn xuống, cuối làm tròn lên) của MỘT bài trong một chương =
     * bao các phần tử của bài ấy: thường [position, position + (to - from)], `loop` cả bài, `to` vô hạn tới hết bài; kẹp [0, `seconds`].
     */
    fun playedSpan(elements: List<MusicRender.Element>, seconds: Double): Pair<Int, Int> {
        var lo = Double.POSITIVE_INFINITY
        var hi = Double.NEGATIVE_INFINITY
        for (element in elements) {
            val start = if (element.loop) 0.0 else element.position
            val end = if (element.loop || element.to.isInfinite()) seconds else start + element.to - element.from
            lo = minOf(lo, start)
            hi = maxOf(hi, end)
        }
        if (lo > hi) return 0 to Math.ceil(seconds).toInt()
        return Math.floor(maxOf(0.0, lo)).toInt() to Math.ceil(minOf(seconds, hi)).toInt()
    }

    /**
     * Bộ trộn của một lượt xuất: nhạc từng chương, bộ đệm bài, và số đoạn thiếu nhạc theo chương ([lost]). `fold`: bù gộp cho chương một
     * kênh (null = không bù).
     */
    class Mixer(
        private val music: Map<Int, ChapterMusic>,
        private val cache: TrackPcmCache,
        private val params: MusicRender.Params,
        private val fold: FoldOffset? = null,
    ) {
        /** chương -> số đoạn thiếu nhạc (bài không lấy / không giải mã được) + mốc bị bỏ. */
        val lost = HashMap<Int, Int>()

        /** Nhạc của chương nếu có gì để trộn; không thì null - chương ấy xuất y như không kèm nhạc. */
        fun chapter(id: Int): ChapterMusic? = audible(music, id)

        fun has(id: Int): Boolean = chapter(id) != null

        /** [MixOutput] cho chương `id` (đã [has]). `seconds`: độ dài chương nếu biết (mốc cuối kẹp như trình phát). */
        fun wrap(id: Int, sink: ListenExport.PcmOutput, rate: Int, channels: Int, seconds: Double?): MixOutput {
            val chapter = music.getValue(id)
            val pcm = chapter.files.mapValues { (_, file) -> cache.get(file.absolutePath, rate, channels) }
            val info = HashMap<String, MusicTimeline.TrackInfo>()
            for ((name, data) in pcm) if (data != null) info[name] = MusicTimeline.TrackInfo(data.frames.toDouble() / rate)
            for (cue in chapter.cues) { // đoạn nghe được của bài (A, E) đi theo mốc trong gói
                val known = info[cue.track] ?: continue
                if (cue.audibleEnd != null) info[cue.track] = MusicTimeline.TrackInfo(known.seconds, cue.audibleStart, cue.audibleEnd)
            }
            val timeline = MusicTimeline.build(chapter.cues, seconds, info)
            lost[id] = timeline.filter { pcm[it.element.track] == null }.map { it.cue }.toSet().size + chapter.dropped
            var elements = timeline.map { it.element }
            if (channels == 1 && fold != null) elements = folded(elements, chapter.files, pcm, rate, fold)
            return MixOutput(sink, rate, channels, elements, pcm, params)
        }

        /** Cộng dB bù gộp của từng bài (đo trên [playedSpan] của bài trong chương) vào mọi điểm gain của các phần tử của bài; điểm câm giữ. */
        private fun folded(
            elements: List<MusicRender.Element>,
            files: Map<String, File>,
            pcm: Map<String, MusicRender.Pcm?>,
            rate: Int,
            fold: FoldOffset,
        ): List<MusicRender.Element> {
            val offsets = HashMap<String, Double>()
            return elements.map { element ->
                val data = pcm[element.track] ?: return@map element
                val db = offsets.getOrPut(element.track) {
                    val (start, end) = playedSpan(elements.filter { it.track == element.track }, data.frames.toDouble() / rate)
                    fold.db(files.getValue(element.track), data, rate, start, end)
                }
                if (db == 0.0) element else MusicRender.Element(
                    element.track, element.from, element.to, element.position, element.gainAt,
                    Array(element.gainDb.size) { element.gainDb[it]?.plus(db) }, element.loop,
                )
            }
        }

        /** Số đoạn thiếu nhạc của các chương đã xuất (kể cả chương mọi bài đều hỏng) - `musicMissing` của kết quả; 0 = không báo. */
        fun missing(ids: Iterable<Int>): Int = ids.sumOf { lost[it] ?: music[it]?.dropped ?: 0 }
    }
}
