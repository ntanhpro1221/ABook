package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import androidx.compose.runtime.Immutable
import vn.abook.player.ui.components.ValuePickerLogic
import vn.abook.player.ui.components.ValueSpecs

/**
 * Dáng chữ của chế độ Đọc theo (web: ReaderScreen, `ReaderPrefs`; miền ở ValueSpecs.readSize / readLeading): cỡ chữ, giãn dòng, và người đọc đã chạm chữ để nghe từ đó lần nào chưa
 * (chưa thì lời nhắc ở đầu chữ còn hiện). Mặc định 20 / 1,7 như web.
 */
@Immutable
data class ReadLook(val size: Int = 20, val leading: Double = 1.7, val tapped: Boolean = false) {
    /** Cao một dòng, theo sp (cỡ × giãn). */
    val lineHeight: Float get() = (size * leading).toFloat()

    // Bộ chọn giá trị (DESIGN mục 6): mọi cỡ 12-40, mọi giãn dòng 1,2-2,4 bước 0,05 (ValueSpecs); giá trị ngoài miền / lệch lưới bị bỏ.
    fun sized(value: Int) = copy(size = value.takeIf { ValuePickerLogic.quantize(ValueSpecs.readSize, it.toDouble()) == it.toDouble() } ?: size)
    fun spaced(value: Double) = copy(leading = gridLeading(value) ?: leading)

    /** "20 · giãn dòng 1,7": giá trị của hàng "Cỡ chữ" ở tấm Thêm tuỳ chọn - gọi đúng tên hai mục của bảng web ("Cỡ chữ", "Giãn dòng"), không để số trần. */
    val summary: String get() = S.s_0_gian_dong_1_c148910e(size, leadingLabel(leading))

    companion object {
        /** Giãn dòng đúng lưới (cả số đọc lại từ Float của SharedPreferences, lệch chừng 1e-7); ngoài miền / lệch lưới thì null. */
        fun gridLeading(value: Double): Double? {
            val spec = ValueSpecs.readLeading
            if (value < spec.min - 0.001 || value > spec.max + 0.001) return null
            return ValuePickerLogic.quantize(spec, value).takeIf { Math.abs(it - value) < 0.001 }
        }

        /** 1,5 / 1,75 / 1,9 - dấu phẩy như web (`formatNumber`). */
        fun leadingLabel(value: Double): String = ValuePickerLogic.format(ValueSpecs.readLeading, value)
    }
}

/** Lời nhắc ở đầu chữ của Đọc theo (web: labels.ts `readerHint`); null = không nhắc. */
object ReadHint {
    const val UNTIMED = S.s_chua_co_audio_ban_van_doc_duoc_chu_6b728db5
    const val NO_VOICE = S.s_may_nay_chua_co_giong_doc_3449f846
    const val TAP = S.s_cham_36a8bd9a + S.s_chu_de_nghe_tu_do_b2d392a7

    /**
     * `speaking`: chương đọc to bằng giọng máy (chữ là nguồn, không có audio thu sẵn). `canSpeak`: máy có giọng đọc. `timed`: chữ đã có mốc theo audio.
     * `tapped`: người đọc đã chạm chữ để nghe từ đó ít nhất một lần.
     */
    fun of(speaking: Boolean, canSpeak: Boolean, timed: Boolean, tapped: Boolean): String? {
        // Sau "Nghe bằng giọng đọc." web còn nối lời sửa cách đọc (giữ chữ); điện thoại chưa sửa cách đọc ngay ở chữ nên phần ấy rỗng.
        val reading = ""
        if (speaking) {
            if (!canSpeak) return NO_VOICE
            return if (tapped) S.s_nghe_bang_giong_doc_0_7e4bfabe(reading) else TAP
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
