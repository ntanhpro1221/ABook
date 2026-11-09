package vn.abook.player.ui

import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.AndroidComposeTestRule
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.core.graphics.Insets
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import vn.abook.player.ui.components.bottomClearance

/**
 * Inset đáy của các máy đã đo bằng `dumpsys window` (px ở mật độ của máy ấy, chỉ đọc):
 * OPPO thật 10-11 (cử chỉ, vạch ẩn): thanh điều hướng 0, vùng nuốt chạm [0,2388][1080,2400] = 12 px @480 dpi;
 * emulator cử chỉ: thanh 63 px, vùng nuốt 84 px @420 dpi; emulator 3 nút: thanh 126 px, vùng nuốt 126 px.
 */
data class BottomInsets(val name: String, val navigationPx: Int, val mandatoryPx: Int) {
    /** Chỗ chừa đáy mà luật chung (components/Insets.kt) cho máy này ở mật độ [density]. */
    fun clearance(density: Float): Dp = bottomClearance((navigationPx / density).dp, (mandatoryPx / density).dp)
}

val OppoHiddenBar = BottomInsets("OPPO cử chỉ ẩn vạch", navigationPx = 0, mandatoryPx = 12)
val EmulatorGesture = BottomInsets("emulator cử chỉ", navigationPx = 63, mandatoryPx = 84)
val EmulatorThreeButton = BottomInsets("emulator 3 nút", navigationPx = 126, mandatoryPx = 126)

/** Đưa [insets] tới khung Compose như hệ thống gửi (navigationBars + mandatorySystemGestures + systemGestures đáy). Gọi sau `setContent`. */
fun <A : ComponentActivity> AndroidComposeTestRule<*, A>.applyBottomInsets(insets: BottomInsets) {
    val built = WindowInsetsCompat.Builder()
        .setInsets(WindowInsetsCompat.Type.navigationBars(), Insets.of(0, 0, 0, insets.navigationPx))
        .setInsets(WindowInsetsCompat.Type.mandatorySystemGestures(), Insets.of(0, 0, 0, insets.mandatoryPx))
        .setInsets(WindowInsetsCompat.Type.systemGestures(), Insets.of(0, 0, 0, insets.mandatoryPx))
        .build()
    runOnUiThread {
        val content = activity.findViewById<ViewGroup>(android.R.id.content)
        ViewCompat.dispatchApplyWindowInsets(content.getChildAt(0), built)
    }
    waitForIdle()
}
