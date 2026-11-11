package vn.abook.player.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextOverflow
import vn.abook.player.ui.theme.Abook

/** Self-updating time, percentage, size and count: replace in place, with equal-width digits. */
@Composable
fun ClockLabel(text: String, modifier: Modifier = Modifier, style: TextStyle = Abook.type.body, maxLines: Int = Int.MAX_VALUE) {
    // cắt-có-chủ-ý: mặc định không cắt; nơi gọi tự đặt maxLines khi cần một dòng cố định (dòng phụ ô lưới) - chữ dài thì "…".
    BasicText(text, modifier, style = style.merge(TextStyle(fontFeatureSettings = "tnum")), maxLines = maxLines, overflow = if (maxLines == Int.MAX_VALUE) TextOverflow.Clip else TextOverflow.Ellipsis)
}
