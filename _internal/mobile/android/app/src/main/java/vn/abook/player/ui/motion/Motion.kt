package vn.abook.player.ui.motion

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.tween
import vn.abook.player.ui.theme.Bezier
import vn.abook.player.ui.theme.MotionMs

/**
 * Chuyển động (DESIGN.md §5.2, NATIVE_PHONE_UI.md §4). Thời lượng / đường cong là token sinh từ DESIGN.md ([MotionMs], [Bezier]); vào chậm hơn ra.
 * Không chuyển cảnh nào chỉ có alpha: mọi cái ở đây là dịch chuyển / đổi cỡ.
 */
object Motion {
    val Standard: Easing = CubicBezierEasing(Bezier.STANDARD_X1, Bezier.STANDARD_Y1, Bezier.STANDARD_X2, Bezier.STANDARD_Y2)
    val Decelerate: Easing = CubicBezierEasing(Bezier.DECELERATE_X1, Bezier.DECELERATE_Y1, Bezier.DECELERATE_X2, Bezier.DECELERATE_Y2)
    val Accelerate: Easing = CubicBezierEasing(Bezier.ACCELERATE_X1, Bezier.ACCELERATE_Y1, Bezier.ACCELERATE_X2, Bezier.ACCELERATE_Y2)

    /** Màn con vào: trượt từ phải, chậm (300 ms, giảm tốc). */
    val PushIn: FiniteAnimationSpec<Float> = tween(MotionMs.SLOW, easing = Decelerate)

    /** Tab đổi chỗ: trượt ngang, vừa (220 ms, chuẩn). */
    val TabSlide: FiniteAnimationSpec<Float> = tween(MotionMs.MEDIUM, easing = Standard)

    /** Back xong sau khi kéo dở: thời lượng ra (200 ms) theo phần đường còn lại, không ngắn hơn 90 ms. */
    fun popOut(fromProgress: Float): FiniteAnimationSpec<Float> =
        tween((MotionMs.SLOW_OUT * fromProgress).toInt().coerceAtLeast(MotionMs.FAST_OUT), easing = Accelerate)

    /** Nội dung lưới ra (90 ms, tăng tốc) rồi vào (220 ms, giảm tốc) cùng chiều với bộ lọc - chỉ dịch ngang, không mờ. */
    val SlideOut: FiniteAnimationSpec<Float> = tween(MotionMs.FAST_OUT, easing = Accelerate)
    val SlideIn: FiniteAnimationSpec<Float> = tween(MotionMs.MEDIUM, easing = Decelerate)

    /** Ô tìm nở ra / thu lại, thanh phát nhỏ hiện lên: vừa (220 ms vào, 150 ms ra). */
    val Expand: FiniteAnimationSpec<Float> = tween(MotionMs.MEDIUM, easing = Standard)
    val Collapse: FiniteAnimationSpec<Float> = tween(MotionMs.MEDIUM_OUT, easing = Standard)

    /** Bảng trượt từ đáy: vào 300 ms giảm tốc, ra 200 ms tăng tốc. */
    val SheetIn: FiniteAnimationSpec<Float> = tween(MotionMs.SLOW, easing = Decelerate)
    val SheetOut: FiniteAnimationSpec<Float> = tween(MotionMs.SLOW_OUT, easing = Accelerate)

    /** Menu nhỏ bật ra / đóng lại: nhanh (120 ms / 90 ms). */
    val MenuIn: FiniteAnimationSpec<Float> = tween(MotionMs.FAST, easing = Decelerate)
    val MenuOut: FiniteAnimationSpec<Float> = tween(MotionMs.FAST_OUT, easing = Accelerate)

    /** Nút phát <-> dừng: biến hình nét vẽ, không mờ chéo (120 ms). */
    val GlyphMorph: FiniteAnimationSpec<Float> = tween(MotionMs.FAST, easing = Standard)

    /** Nhấn thu 0,97 trong 90 ms, thả về trong 120 ms (§5.2). */
    const val PRESS_SCALE = 0.97f
    val PressDown: FiniteAnimationSpec<Float> = tween(MotionMs.FAST_OUT, easing = Standard)
    val PressUp: FiniteAnimationSpec<Float> = tween(MotionMs.FAST, easing = Standard)
}

/**
 * Hình học một chuyển cảnh màn con theo MỘT tiến trình `p` của màn trên cùng (0 = chưa vào, 1 = đã vào hẳn): màn trên ở `(1 - p)` bề rộng bên phải,
 * màn dưới lùi trái [BELOW_SHIFT] bề rộng. Vào (push) chạy p 0 -> 1, Back chạy p 1 -> 0 qua ĐÚNG hai hàm này - nên Back là đường ngược lại của vào, kể cả
 * khi Back dự đoán kéo dở ([forBack]); không có hàm riêng cho Back để lệch.
 */
object ScreenGeometry {
    const val BELOW_SHIFT = 0.3f

    /** Dịch ngang của màn trên cùng, theo tỉ lệ bề rộng (dương = sang phải). */
    fun topFraction(p: Float): Float = 1f - p

    /** Dịch ngang của màn bên dưới (âm = sang trái). */
    fun belowFraction(p: Float): Float = -BELOW_SHIFT * p

    /** Tiến trình p ứng với cử chỉ Back đã kéo `back` (0..1): kéo hết = màn trên ra khỏi hẳn. */
    fun forBack(back: Float): Float = 1f - back.coerceIn(0f, 1f)
}
