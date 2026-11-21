package vn.abook.player.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Màn / mục "chưa có gì, chưa vào được" (DESIGN §2: một câu + một nút dẫn tới việc tạo nội dung) - cùng thành phần với web `EmptyState`
 * (shared/ui.tsx) và Qt `EmptyState.qml`: ô icon 56 bo bìa nền nhấn nhạt, tiêu đề 16 đậm vừa, lời mực phụ tối đa 448, việc bên dưới; mọi thứ
 * căn giữa. Khe theo thang: icon -> tiêu đề 16, tiêu đề -> lời 8, lời -> việc 24.
 *
 * [fillHeight] > 0: trạng thái là CẢ MÀN (web `fill`, Qt `fillHeight`) - khối đứng giữa vùng cao chừng ấy, không dính góc trên rồi để trống quá
 * nửa màn bên dưới (design_lint R10). Trống trong một mục / bảng thì để 0: đệm 64 trên dưới như web py-16.
 */
@Composable
fun EmptyState(
    icon: String,
    title: String,
    modifier: Modifier = Modifier,
    text: String? = null,
    fillHeight: Dp = 0.dp,
    /** Chỗ gọi đã cho khối chiều cao (Modifier.weight / fillMaxHeight của cột chứa): không đệm, khối đứng giữa chiều cao ấy. */
    fill: Boolean = false,
    actions: (@Composable ColumnScope.() -> Unit)? = null,
) {
    Column(
        modifier.fillMaxWidth()
            .then(if (fillHeight > 0.dp) Modifier.heightIn(min = fillHeight) else if (fill) Modifier else Modifier.padding(vertical = 64.dp)),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(Modifier.size(56.dp).clip(RoundedCornerShape(Dim.radiusCover)).background(Abook.colors.accentSoft), contentAlignment = Alignment.Center) {
            LucideIcon(icon, Abook.colors.accentText, size = 28.dp)
        }
        Spacer(Modifier.height(Dim.s16))
        BasicText(title, style = Abook.type.bodyStrong.copy(textAlign = TextAlign.Center))
        // Lời và việc theo THAM SỐ của chỗ gọi: tham số đổi (có lời <-> không lời, có nút <-> không nút) thì khối mới mờ vào trên khối cũ, không bật cứng.
        // SwapContent giữ chính giá trị cũ cho khối đang đi ra (lời cũ, nút cũ) tới hết nhịp.
        SwapContent(text, contentKey = { text -> !text.isNullOrEmpty() }) { text ->
            if (!text.isNullOrEmpty()) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(text, Modifier.widthIn(max = 448.dp), style = Abook.type.bodySmall.copy(textAlign = TextAlign.Center))
                }
            }
        }
        SwapContent(actions, contentKey = { actions -> actions != null }) { actions ->
            if (actions != null) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Spacer(Modifier.height(Dim.s24))
                    actions()
                }
            }
        }
    }
}
