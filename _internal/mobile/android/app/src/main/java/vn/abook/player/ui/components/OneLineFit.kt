package vn.abook.player.ui.components

import androidx.compose.foundation.text.TextAutoSize
import androidx.compose.foundation.text.modifiers.TextAutoSizeLayoutScope
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.sp

/**
 * Một dòng mà không cắt chữ (luật TextCutScanTest: không "…", không cắt im lặng): chữ thu cỡ dần từ [maxSize] tới [minSize] cho tới khi nằm gọn một dòng.
 * Thu tới đáy vẫn không vừa thì trả về cỡ gốc và xuống dòng như mọi hàng (chữ nhỏ mà vẫn hai dòng thì khó đọc, khoảng dòng giữ theo cỡ gốc) - chữ luôn đọc trọn.
 * Dùng với `softWrap = true` (mặc định của [BasicText]); tên ngắn chỉ dàn một lần.
 */
data class OneLineFit(val maxSize: TextUnit, val minSize: TextUnit, val step: TextUnit = 0.5.sp) : TextAutoSize {
    override fun TextAutoSizeLayoutScope.getFontSize(constraints: Constraints, text: AnnotatedString): TextUnit {
        var size = maxSize.value
        while (size >= minSize.value) {
            if (performLayout(constraints, text, size.sp).lineCount <= 1) return size.sp
            size -= step.value
        }
        return maxSize
    }

    companion object {
        /** Đáy thu cỡ: ba phần tư cỡ gốc (chữ thân 16 -> 12, vẫn trên cỡ chú thích nhỏ nhất). */
        const val MIN_SCALE = 0.75f

        fun of(style: TextStyle) = OneLineFit(style.fontSize, style.fontSize * MIN_SCALE)
    }
}
