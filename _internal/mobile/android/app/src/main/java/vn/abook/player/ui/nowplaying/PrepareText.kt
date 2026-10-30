package vn.abook.player.ui.nowplaying

import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PreparePlan
import vn.abook.player.ui.data.PrepareStatus
import vn.abook.player.ui.data.dotJoin

/**
 * Chữ của "Làm trước" (web: listen/prepareAhead.ts): câu mời, ước trước khi bấm, tiến độ - nói theo cái người nghe cần biết (còn bao lâu, đang chờ gì).
 * Hàm thuần - thử trên JVM (PrepareTextTest). Giọng trực tuyến nói rõ chữ sẽ được gửi tới đâu trước khi bạn bắt đầu.
 */
object PrepareText {
    /** Tối đa bao nhiêu chương tới được làm trước một lần (như web). */
    const val LIMIT = 5

    /** Cái lợi khi làm trước bằng giọng chạy trên máy. */
    private const val GAIN = "nghe liền mạch, không cần chờ"

    const val INTRO = "Máy đọc chậm? Làm trước để nghe liền mạch."
    const val OTHER_JOB = "Đang làm trước cho một cuốn hay giọng khác - làm ở đây thì việc ấy dừng."

    /** Giọng nào có "Làm trước": giọng tải về đọc trên máy (VieNeu, Supertonic - chậm hơn tốc độ nghe trên máy yếu). Giọng của máy đã đọc nhanh. */
    fun canPrepare(voiceId: String): Boolean = voiceId.startsWith("vieneu:") || voiceId.startsWith("supertonic:") ||
        vn.abook.player.ui.voice.VoiceText.isOnline(voiceId.substringBefore(':'))

    fun intro(voiceId: String): String {
        val provider = voiceId.substringBefore(':')
        if (!vn.abook.player.ui.voice.VoiceText.isOnline(provider)) return INTRO
        val destination = "; chữ sẽ được gửi tới ${vn.abook.player.ui.voice.VoiceText.destination(provider)}"
        return "Làm trước để nghe khi không có mạng$destination."
    }

    /** Các chương chỉ-có-chữ ngay sau chương đang nghe (tối đa [limit]). */
    fun upcoming(chapters: List<PlayerChapter>, currentId: Int?, limit: Int = LIMIT): List<PlayerChapter> {
        val at = chapters.indexOfFirst { it.id == currentId }
        return chapters.drop(at + 1).filter { it.textPath.isNotEmpty() }.take(limit)
    }

    /** Tên việc gửi cho lõi: một chương thì tên chương, nhiều thì "N chương tới". */
    fun jobLabel(upcoming: List<PlayerChapter>): String = if (upcoming.size == 1) upcoming[0].title else "${upcoming.size} chương tới"

    /** Nút bắt đầu: "Làm trước chương sau" / "Làm trước N chương". */
    fun startLabel(count: Int): String = if (count == 1) "Làm trước chương sau" else "Làm trước $count chương"

    /** "khoảng 1 giờ 20 phút", "khoảng 12 phút", "dưới 1 phút". */
    fun spokenDuration(seconds: Long): String {
        val minutes = Math.round(seconds / 60.0)
        if (minutes < 1) return "dưới 1 phút"
        if (minutes < 60) return "khoảng $minutes phút"
        val hours = minutes / 60
        val rest = minutes % 60
        return "khoảng $hours giờ" + if (rest > 0) " $rest phút" else ""
    }

    /** Câu ước trước khi bấm: "Khoảng 2 giờ nghe · máy cần khoảng 1 giờ 50 phút." (rỗng khi không chương nào nhận). */
    fun planLabel(plan: PreparePlan): String {
        if (plan.chapters == 0) return ""
        val listen = spokenDuration(plan.audioSeconds).removePrefix("khoảng ") + " nghe"
        val machine = plan.secondsEstimate?.let { " · máy cần " + spokenDuration(it) }.orEmpty()
        val fits = if (plan.chapters < plan.offered) "Vừa chỗ trống cho ${plan.chapters} chương: " else ""
        return (fits + listen + machine + ".").replaceFirstChar { it.uppercase() }
    }

    /** Vì sao việc chưa chạy lúc này. */
    fun waiting(reason: String): String = when (reason) {
        "charging" -> "chờ cắm sạc"
        "wifi" -> "chờ Wi-Fi"
        "battery" -> "chờ pin đầy hơn"
        "listening" -> "nhường cho chương đang nghe"
        else -> ""
    }

    /** Câu nói tiến độ của việc đang có (rỗng khi chưa có việc nào). */
    fun label(status: PrepareStatus): String {
        val what = status.label.ifEmpty { "các chương tới" }
        val listen = if (status.audioSeconds > 0) " (" + spokenDuration(status.audioSeconds).removePrefix("khoảng ") + " nghe)" else ""
        val chapters = status.chapters
        val ready = chapters?.let { "Đã sẵn sàng ${it.count { chapter -> chapter.ready }}/${it.size} chương" }.orEmpty()
        return when (status.state) {
            "running" -> {
                if (chapters != null) {
                    dotJoin(ready, status.waitingFor?.let { waiting(it) } ?: status.secondsLeft?.let { "còn " + spokenDuration(it) })
                } else {
                    val left = status.secondsLeft?.let { ", còn " + spokenDuration(it) }.orEmpty()
                    "Đang làm trước $what$listen: ${status.done}/${status.total} đoạn$left."
                }
            }
            "done" -> {
                val partial = if (status.offered > status.total) " - phần còn lại làm tiếp khi bạn nghe tới" else ""
                if (chapters != null && chapters.any { !it.ready }) "$ready - phần còn lại làm tiếp khi bạn nghe tới."
                else "Đã làm trước $what$listen: ${if (status.online) "nghe được cả khi không có mạng" else GAIN}$partial."
            }
            "error" -> status.error.ifEmpty { "Làm trước bị dừng." }
            "cancelled" -> if (chapters != null) "Đã dừng làm trước (${ready.take(1).lowercase()}${ready.drop(1)})." else "Đã dừng làm trước."
            else -> ""
        }
    }

    /** Việc đang có là của cuốn + giọng này (web: `mine`). */
    fun mine(status: PrepareStatus, voiceId: String, bookId: String?): Boolean =
        status.state != "idle" && status.voice == voiceId && (status.bookId.isEmpty() || status.bookId == bookId)
}
