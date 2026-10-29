package vn.abook.player.ui.nowplaying

import androidx.compose.runtime.Immutable
import java.math.BigDecimal

/**
 * Dáng chữ của chế độ Đọc theo (web: ReaderScreen `SIZES`, `LEADINGS`, `ReaderPrefs`): cỡ chữ, giãn dòng, và người đọc đã chạm chữ để nghe từ đó lần nào chưa
 * (chưa thì lời nhắc ở đầu chữ còn hiện). Mặc định 20 / 1,7 như web.
 */
@Immutable
data class ReadLook(val size: Int = 20, val leading: Double = 1.7, val tapped: Boolean = false) {
    /** Cao một dòng, theo sp (cỡ × giãn). */
    val lineHeight: Float get() = (size * leading).toFloat()

    fun sized(value: Int) = copy(size = value.takeIf { it in SIZES } ?: size)
    fun spaced(value: Double) = copy(leading = value.takeIf { it in LEADINGS } ?: leading)

    /** "20 · 1,7": giá trị của hàng "Cỡ chữ" ở tấm Thêm tuỳ chọn. */
    val summary: String get() = "$size · ${leadingLabel(leading)}"

    companion object {
        val SIZES = listOf(16, 18, 20, 22, 24)
        val LEADINGS = listOf(1.5, 1.7, 1.9)

        /** 1,5 / 1,7 / 1,9 - dấu phẩy như web (`toLocaleString("vi-VN")`). */
        fun leadingLabel(value: Double): String = BigDecimal.valueOf(value).stripTrailingZeros().toPlainString().replace('.', ',')
    }
}

/** Lời nhắc ở đầu chữ của Đọc theo (web: labels.ts `readerHint`); null = không nhắc. */
object ReadHint {
    const val UNTIMED = "Chưa có audio; bạn vẫn đọc được chữ."
    const val NO_VOICE = "Máy này chưa có giọng đọc."
    const val TAP = "Chạm" + " chữ để nghe từ đó."

    /**
     * `speaking`: chương đọc to bằng giọng máy (chữ là nguồn, không có audio thu sẵn). `canSpeak`: máy có giọng đọc. `timed`: chữ đã có mốc theo audio.
     * `tapped`: người đọc đã chạm chữ để nghe từ đó ít nhất một lần.
     */
    fun of(speaking: Boolean, canSpeak: Boolean, timed: Boolean, tapped: Boolean): String? {
        // Sau "Nghe bằng giọng đọc." web còn nối lời sửa cách đọc (giữ chữ); điện thoại chưa sửa cách đọc ngay ở chữ nên phần ấy rỗng.
        val reading = ""
        if (speaking) {
            if (!canSpeak) return NO_VOICE
            return if (tapped) "Nghe bằng giọng đọc.$reading" else TAP
        }
        if (!timed) return UNTIMED
        return if (tapped) null else TAP
    }
}

/** Chữ nào người đọc vừa chạm: nghe từ đó. */
object ReadTap {
    /** Mốc (ms) để nghe từ chỗ chạm `offset` (vị trí ký tự trong đoạn): đầu từ chứa nó, hay đầu từ kế nếu chạm vào khoảng trắng; không có từ nào thì đầu đoạn. */
    fun startAt(paragraph: ReadParagraph, offset: Int): Long {
        if (paragraph.words.isEmpty()) return paragraph.startMs
        val hit = paragraph.words.firstOrNull { offset >= it.from && offset < it.until }
            ?: paragraph.words.firstOrNull { it.from >= offset }
            ?: paragraph.words.last()
        return hit.startMs
    }
}
