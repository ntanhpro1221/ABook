package vn.abook.player.ui.components

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.mandatorySystemGestures
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/**
 * Khoảng thở giữa thứ bấm được và vùng đáy mà hệ thống nuốt chạm (`mandatorySystemGestures`), để ngón tay không chạm sát vùng ấy.
 * Máy cử chỉ ẩn vạch (ColorOS) báo thanh điều hướng 0 nhưng vẫn nuốt chạm ở dải đáy: OPPO thật 12 px @480 dpi = 4 dp. Lỗi điện thoại thật 05-11: "Thay bằng file này" và
 * nhãn tab đáy nằm trong dải đó, bấm không trúng. Sàn cứng 24 dp trước đây chữa lỗi ấy nhưng thừa ~20 dp trên máy đó - khoảng trống đáy chủ sách chê.
 * MỌI thứ bám đáy màn (chân màn con, bảng trượt, thanh tab, thanh Hoàn tác, ghi chú) chừa đáy qua đây, không tự đọc `WindowInsets.navigationBars`: máy dò
 * [vn.abook.player.ui.BottomInsetScanTest] không cho chỗ nào ngoài file này.
 */
val GestureBreath = Dim.s8

/**
 * Chỗ chừa dưới chân của thứ bám đáy. Thanh điều hướng có mặt (3 nút 48 dp, vạch cử chỉ 24 dp) thì chừa đúng thanh ấy - cách mọi app Android đặt thanh đáy. Máy ẩn thanh
 * (inset 0) thì chừa vùng nuốt chạm + [GestureBreath]. Hàm thuần để test kiểm.
 */
fun bottomClearance(navigation: Dp, mandatoryGestures: Dp): Dp = if (navigation > 0.dp) navigation else mandatoryGestures + GestureBreath

/**
 * Đáy của chỗ đang dựng KHÔNG chạm mép màn: bên dưới còn thanh phát nhỏ / thanh tab, chính chúng đã chừa đáy (Shell.kt đặt cho lớp màn và thanh báo). Chừa lần nữa là
 * một dải trống treo giữa màn và thanh phát.
 */
val LocalBottomCovered = compositionLocalOf { false }

/** [bottomClearance] của cửa sổ hiện tại, bỏ qua [LocalBottomCovered]. */
@Composable
private fun systemClearance(): Dp {
    val density = LocalDensity.current
    val navigation = WindowInsets.navigationBars.getBottom(density)
    val mandatory = WindowInsets.mandatorySystemGestures.getBottom(density)
    return with(density) { bottomClearance(navigation.toDp(), mandatory.toDp()) }
}

/** [bottomClearance] của cửa sổ hiện tại; 0 khi bên dưới đã có thanh của khung ([LocalBottomCovered]). */
@Composable
fun navigationClearance(): Dp = if (LocalBottomCovered.current) 0.dp else systemClearance()

/**
 * Khoảng thở dưới thứ cuối cùng ở đáy (chân ghim của màn, đáy bảng trượt, hàng nút cuối của Đang nghe), tính GỘP với chỗ chừa đáy: chỗ chừa đáy đã là một khoảng tới mép,
 * nên chỉ bù phần còn thiếu cho đủ `breath`. Hàm thuần để test kiểm. Trước đây cộng `breath` lên TRÊN chỗ chừa đáy: chân "Thêm sách" có 12 dp trống thừa dưới nút cuối
 * ở mọi máy (chủ sách 15-11: "sao ở dưới đáy cứ có khoảng trống nhất định nhỉ? nhiều view cũng bị như thế").
 */
fun breathAbove(clearance: Dp, breath: Dp): Dp = (breath - clearance).coerceAtLeast(0.dp)

/**
 * [breathAbove] của cửa sổ hiện tại. Đáy đang có thanh của khung ([LocalBottomCovered]) hay bàn phím: không có chỗ chừa đáy nào ở dưới, giữ nguyên `breath` để hai mặt
 * không dính nhau. Đổi giữa hai trường hợp (bàn phím mở / đóng) thì khoảng ấy trượt, không nhảy.
 */
@Composable
fun bottomBreath(breath: Dp): Dp {
    val density = LocalDensity.current
    val clearance = systemClearance()
    val target = if (LocalBottomCovered.current || WindowInsets.ime.getBottom(density) > 0) breath else breathAbove(clearance, breath)
    return animateDpAsState(target, tween(MotionMs.MEDIUM, easing = Motion.Standard), label = "bottom-breath").value
}

/** Vùng inset đáy: `insets` (mặc định thanh điều hướng) nhưng đáy không dưới [navigationClearance]. */
@Composable
fun gestureSafe(insets: WindowInsets = WindowInsets.navigationBars): WindowInsets =
    if (LocalBottomCovered.current) WindowInsets(bottom = 0.dp) else insets.union(WindowInsets(bottom = systemClearance()))

/** Chừa đáy theo [gestureSafe]: thay cho `navigationBarsPadding()`. */
@Composable
fun Modifier.gestureBarPadding(insets: WindowInsets = WindowInsets.navigationBars): Modifier = windowInsetsPadding(gestureSafe(insets))
