package vn.abook.player.readaloud

import kotlin.math.ceil

/** Giây máy cho MỖI khúc: hai hệ số đo từ [VoiceSpeeds], không suy chi phí cố định từ một giọng hay một máy khác. */
data class VoiceWork(val perUnit: Double, val perChar: Double) {
    fun seconds(chars: Int, units: Int = 1): Double = perUnit * units + perChar * chars
}

/** Cùng các khúc thật của [LocalLive.unitsOf]. [chars] tính giây tiếng của cả đoạn; ngăn cảnh chỉ có [silenceMs], không có việc đọc. */
data class OpeningParagraph(val units: List<Int>, val chars: Int = units.sum(), val cached: Boolean = false, val silenceMs: Long = 0L)

/** Lịch đọc tuần tự tính từ khi clip đầu ĐÃ xong. Không đổi cách cắt, seed, mẫu tiếng hay luật nhả luồng của [LocalLive]. */
object OpeningSchedule {
    const val HORIZON_SECONDS = 60.0
    const val MARGIN_MS = 200L
    /** dev/gap [21], OPPO CPH2121, Supertonic nhanh: đầu sách A làm 16,1 s cho 13,2 s tiếng, rồi khúc đầu đoạn 5 cần 5,4 s khi chỉ còn 2,28 s tiếng.
     *  Trần cũ 1,5 s không đủ; cho phép dời tối đa 6 s vào lúc mở. Đây là lịch dự đoán, chưa đo bản sửa trên máy thật. */
    const val MAX_HOLD_MS = 6_000L

    /** H = max(0, max_i(sẵn sàng đoạn i - lúc nghe tới i) + biên), chặn [MAX_HOLD_MS]. Đoạn phát luồng sẵn sàng ở khúc đầu (như [LocalLive.charsBeforeStart] khi nhả theo `reach`):
     *  [LocalLive] có thể giữ khúc đầu tới `reach`, nên dự đoán sẵn trước hạn là đủ, không cần đợi xong cả đoạn. Công việc các khúc sau vẫn cộng vào trước đoạn kế. RTF toàn chương >= 1: phát ngay.
     *  [paragraphs] gồm phần CÒN LẠI của chương; bộ đệm không tốn việc nhưng vẫn có tiếng. [firstMs] là tiếng clip đầu còn nghe, ở tốc độ gốc. */
    fun holdMs(firstMs: Long, paragraphs: List<OpeningParagraph>, work: VoiceWork, audioPerChar: Double, speed: Double = 1.0, firstUnits: List<Int> = emptyList()): Long {
        val rate = maxOf(speed, 0.1)
        if (!audioPerChar.isFinite() || audioPerChar <= 0 || paragraphs.isEmpty()) return 0L
        val sound = (firstMs / 1000.0 + paragraphs.sumOf { it.chars * audioPerChar + it.silenceMs / 1000.0 }) / rate
        // RTF toàn chương kể cả clip đầu; không lấy riêng cửa sổ có nhiều câu ngắn hay tốc độ lấy từ bộ đệm để kết luận máy nhanh/chậm kéo dài.
        val totalWork = work.seconds(firstUnits.sum(), firstUnits.size) + paragraphs.sumOf { it.units.sumOf { chars -> work.seconds(chars) } }
        if (sound <= 0 || totalWork >= sound) return 0L
        var heard = firstMs.coerceAtLeast(0) / 1000.0 / rate
        var made = 0.0
        var deficit = Double.NEGATIVE_INFINITY
        for (paragraph in paragraphs) {
            val duration = paragraph.chars * audioPerChar / rate
            if (heard >= HORIZON_SECONDS) break
            if (paragraph.units.isNotEmpty() && !paragraph.cached) {
                deficit = maxOf(deficit, made + work.seconds(paragraph.units.first()) - heard)
                made += work.seconds(paragraph.units.sum(), paragraph.units.size)
            }
            heard += duration + paragraph.silenceMs / 1000.0 / rate
        }
        val wait = deficit * 1000 + MARGIN_MS
        return if (wait <= 0) 0L else minOf(MAX_HOLD_MS, ceil(wait - 1e-7).toLong()) // bỏ nhiễu dấu phẩy động ở ranh mili-giây nguyên
    }

    /**
     * [holdMs] cho clip đầu là đoạn [segment] của một chương ([paragraphs] cả chương, [gaps] quãng lặng của dòng ngăn cảnh, [isBreak]). MỘT bộ cắt cho cả ghi số đo và dự đoán
     * ([LocalLive.unitsOf]); [cached] tra bộ đệm từng đoạn. Cắt cả chương và tra bộ đệm tốn vài chục ms trở lên (JVM máy tính, chương 12 nghìn ký tự): [ReadAloud] gọi ở luồng nền.
     */
    fun forChapter(
        voice: String, paragraphs: List<String>, isBreak: (Int) -> Boolean, gaps: IntArray, segment: Int, firstMs: Long, work: VoiceWork, audioPerChar: Double, speed: Double,
        origin: String?, readings: Map<String, String>?, cached: (String) -> Boolean,
    ): Long {
        val shapes = paragraphs.mapIndexed { index, paragraph ->
            if (isBreak(index)) OpeningParagraph(emptyList(), silenceMs = gaps[index].toLong()) else {
                val (tokens, units) = LocalLive.unitsOf(voice, paragraph, origin, readings) ?: error("Giọng không đọc theo khúc")
                OpeningParagraph(units.map { it.text(tokens).length }, paragraph.length, cached(paragraph))
            }
        }
        return holdMs(firstMs, shapes.drop(segment + 1), work, audioPerChar, speed, shapes[segment].units)
    }
}

/** Các mục sẵn sàng trong lúc giữ đầu: lịch nhiều đoạn không được nhả sớm chỉ vì ĐOẠN KẾ đã xong (luật cũ). Dùng cả cho clip thường và clip phát luồng. */
class OpeningQueue<T>(first: T, val scheduled: Boolean) {
    val items = arrayListOf(first)
    fun releases(ready: Boolean): Boolean = !scheduled || !ready
    /** Bỏ mục chưa phát khớp [match] (mục phát luồng hỏng trong lúc giữ): chưa ai nghe gì của nó, kết quả của lượt đọc thay vào đúng một lần. True = đã bỏ. */
    fun withdraw(match: (T) -> Boolean): Boolean = items.subList(1, items.size).removeAll(match)
}

/**
 * Tính lịch giữ đầu chương ở luồng nền: một luồng RIÊNG (không xếp sau các lượt đọc không huỷ được của bể `worker` - tua nhanh nhiều lần thì lịch mới không chờ lịch cũ), lần tính đã cũ
 * ([current] false lúc tới lượt) thì bỏ không tính. Giữ CPU ([FetchWake], không Wi-Fi) suốt lúc tính: ExoPlayer chưa có gì nên không giữ khoá nào, vé của lượt đọc clip đầu đã nhả.
 */
class OpeningPlanner(name: String) {
    private val executor = java.util.concurrent.Executors.newSingleThreadExecutor { Thread(it, name).apply { isDaemon = true } }

    /** [compute] ở luồng tính lịch (lỗi -> null), rồi [then] với kết quả, vẫn ở luồng ấy (người gọi tự chuyển về luồng chính). */
    fun <T> plan(current: () -> Boolean, compute: () -> T, then: (T?) -> Unit) {
        val ticket = FetchWake.hold(network = false)
        executor.execute {
            try {
                if (current()) then(runCatching(compute).getOrNull())
            } finally {
                FetchWake.release(ticket)
            }
        }
    }
}
