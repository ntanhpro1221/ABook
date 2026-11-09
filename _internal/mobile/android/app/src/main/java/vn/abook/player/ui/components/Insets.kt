package vn.abook.player.ui.components

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.theme.Dim

/**
 * Vạch cử chỉ của hệ thống: thanh điều hướng kiểu cử chỉ cao 24 dp (AOSP). Máy cử chỉ ẩn vạch (ColorOS: inset đáy ~0) báo inset 0, nhưng vùng vuốt của hệ thống vẫn chiếm dải
 * đáy ấy - chạm vào chữ nằm trong dải đó bị hệ thống nuốt (soát điện thoại thật 05-11: "Thay bằng file này" và nhãn tab đáy nằm ở 36 dp trên mép, bấm không trúng).
 * MỌI thứ bám đáy màn (chân màn con, bảng trượt, thanh tab, thanh Hoàn tác, ghi chú) chừa đáy qua đây, không tự đọc `WindowInsets.navigationBars`: máy dò
 * [vn.abook.player.ui.BottomInsetScanTest] không cho chỗ nào ngoài file này.
 */
val GestureBar = Dim.s24

/** Chỗ chừa dưới chân của thứ bám đáy: thanh điều hướng chiếm bao nhiêu thì chừa bấy nhiêu, nhưng KHÔNG BAO GIỜ dưới [floor]. Hàm thuần để test kiểm. */
fun bottomClearance(inset: Dp, floor: Dp = GestureBar): Dp = if (inset > floor) inset else floor

/**
 * Đáy của chỗ đang dựng KHÔNG chạm mép màn: bên dưới còn thanh phát nhỏ / thanh tab, chính chúng đã chừa vạch cử chỉ (Shell.kt đặt cho lớp màn và thanh báo). Chừa lần nữa là
 * một dải trống 24 dp treo giữa màn và thanh phát.
 */
val LocalBottomCovered = compositionLocalOf { false }

/** [bottomClearance] của thanh điều hướng hiện tại; 0 khi bên dưới đã có thanh của khung ([LocalBottomCovered]). */
@Composable
fun navigationClearance(): Dp = if (LocalBottomCovered.current) 0.dp else bottomClearance(WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding())

/** Vùng inset đáy: `insets` (mặc định thanh điều hướng) nhưng đáy không dưới [GestureBar]. */
@Composable
fun gestureSafe(insets: WindowInsets = WindowInsets.navigationBars): WindowInsets = if (LocalBottomCovered.current) WindowInsets(bottom = 0.dp) else insets.union(WindowInsets(bottom = GestureBar))

/** Chừa đáy theo [gestureSafe]: thay cho `navigationBarsPadding()`. */
@Composable
fun Modifier.gestureBarPadding(insets: WindowInsets = WindowInsets.navigationBars): Modifier = windowInsetsPadding(gestureSafe(insets))
