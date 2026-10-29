package vn.abook.player.ui.nowplaying

import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.PlayerChapter

/**
 * Chữ của Đang nghe ngoài nhãn nút (web: listen/labels.ts `toggleLabel`, `nextChapterLabel`, `bookProgressText`, `bookHeardBase`, `caughtUpDetail`).
 * Hàm thuần - thử trên JVM (PlayerTextTest). Nói theo cái người nghe nhận ra (đang chờ gì, chương sau có chưa), không theo trạng thái bên trong.
 */
object PlayerText {
    /** Đang chờ giọng máy đọc xong đoạn đầu (nhãn nút phát). */
    const val PREPARING_VOICE = "Đang chuẩn bị giọng đọc"

    /** Chờ giọng ngắn hơn mức này thì không nói gì (chỉ vòng quay ở nút phát). */
    const val PREPARING_AFTER_MS = 1500L

    const val CAUGHT_UP_HEAD = "Đã nghe hết phần đã có"

    /** Điện thoại không có máy nào làm sách tiếp, nên chỉ nói điều chắc chắn: các chương sau chưa có audio. */
    const val CAUGHT_UP_DETAIL = "Các chương sau chưa có audio."
    const val ENDED_PART = "Đã nghe hết cuốn này."
    const val ENDED_BOOK = "Đã nghe hết sách."
    const val FINISHED = "Đã nghe hết cả cuốn"

    /** Nhãn đọc màn hình của nút phát: đang chờ thì nói đang chờ gì - không nói "Tạm dừng" khi chưa có tiếng nào. */
    fun toggleLabel(playing: Boolean, buffering: Boolean, speaking: Boolean): String = when {
        playing && buffering -> if (speaking) PREPARING_VOICE else "Đang tải âm thanh"
        playing -> "Tạm dừng"
        else -> "Phát"
    }

    /** Nút "Chương sau": chương cuối thì nói đó là chương cuối (nút mờ); chương sau có mà chưa nghe được thì nói vì sao. */
    fun nextLabel(hasNext: Boolean, hasLater: Boolean): String = when {
        !hasLater -> "Đây là chương cuối"
        hasNext -> "Chương sau"
        else -> "Chương sau chưa có audio"
    }

    fun hasNext(chapters: List<PlayerChapter>, chapterId: Int?): Boolean {
        val at = chapters.indexOfFirst { it.id == chapterId }
        return at >= 0 && at < chapters.lastIndex
    }

    /** Phần audio của cả cuốn trước chương đang nghe và tổng phần audio đã có (giây); `inside`: chương đang nghe là một phần của tổng ấy. */
    class HeardBase(val before: Double, val total: Double, val inside: Boolean)

    /** Chương chỉ có chữ (giọng máy đọc) không có audio riêng: đồng hồ của nó không cộng vào tổng; chương đang nghe được tìm TRƯỚC khi bỏ nó. */
    fun heardBase(chapters: List<PlayerChapter>, chapterId: Int?): HeardBase {
        var before = 0.0
        var total = 0.0
        var reached = false
        var inside = false
        for (chapter in chapters) {
            val audio = chapter.textPath.isEmpty()
            if (chapter.id == chapterId) { reached = true; inside = audio }
            if (!audio) continue
            val seconds = chapter.durationMs / 1000.0
            if (!reached) before += seconds
            total += seconds
        }
        return HeardBase(before, total, inside)
    }

    /** "<1%" / "42%" / "99%" - như formatPercent của web. */
    fun percent(fraction: Double): String {
        val value = fraction.coerceIn(0.0, 1.0) * 100
        return when {
            value > 0 && value < 1 -> "<1%"
            value < 100 && value > 99 -> "99%"
            else -> "${value.toInt()}%"
        }
    }

    /**
     * Dòng tiến độ cả cuốn: "Đã nghe 10% phần đã có · còn khoảng 27 phút ở tốc độ 1,5×" (tốc độ thường: "còn 41 phút").
     * `whole`: sách đủ chương ("cả cuốn") hay mới có một phần. `finished`: phát hết chương cuối của sách đủ chương.
     */
    fun bookProgress(whole: Boolean, heard: Double, total: Double, rate: Double, finished: Boolean): String {
        if (finished) return FINISHED
        val left = (total - heard).coerceAtLeast(0.0)
        val scope = if (whole) "cả cuốn" else "phần đã có"
        val remaining = if (rate != 1.0 && left > 60) "còn khoảng ${Fmt.length(left / rate)} ở tốc độ ${PlayerLabels.rate(rate)}" else "còn ${Fmt.length(left)}"
        return "Đã nghe ${percent(if (total > 0) heard / total else 0.0)} $scope · $remaining"
    }

    /** Lệch (giây) từ đó chỗ nghe của máy khác mới là "chỗ khác" - ít hơn là cùng chỗ (lưu chậm vài giây). */
    const val ELSEWHERE_SECONDS = 30.0

    /**
     * Chỗ nghe thư viện giữ (`lastAt` giây epoch) được ghi SAU lần cuối máy này nạp cuốn (`loadedMs`) - tức của máy khác - và xa chỗ máy này đang đứng:
     * nghe tiếp ở đây phải hỏi, đừng phát chỗ cũ rồi lưu đè chỗ mới hơn (web: model.ts `newerElsewhere`).
     */
    fun newerElsewhere(lastChapter: Int, lastSeconds: Double, lastAt: Double, loadedMs: Long, hereChapter: Int?, hereSeconds: Double): Boolean {
        if (!(lastAt * 1000 > loadedMs + 1000)) return false
        return !(lastChapter == hereChapter && Math.abs(lastSeconds - hereSeconds) < ELSEWHERE_SECONDS)
    }

    fun elsewhereLine(chapterTitle: String, seconds: Double): String = "Máy khác đã nghe tới $chapterTitle · ${Fmt.clock(seconds)}"

    const val ELSEWHERE_ACTION = "Nghe tiếp từ đó"
    fun continueLine(title: String): String = "Nghe tiếp ${PlayerEnd.nextLabel(title)}"
}
