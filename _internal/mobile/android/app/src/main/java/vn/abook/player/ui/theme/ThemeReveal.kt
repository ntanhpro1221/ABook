package vn.abook.player.ui.theme

import android.animation.ValueAnimator
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.PixelCopy
import android.view.View
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import vn.abook.player.ui.motion.Motion
import kotlin.math.hypot
import kotlin.math.max

/**
 * Đổi giao diện sáng / tối có chuyển động hình học: vòng tròn lan từ chỗ chạm (nút "Sáng" / "Tối") mở dần giao diện mới, giao diện cũ lùi ra ngoài vòng -
 * không mờ chéo. Cách làm: chụp khung đang thấy một lần ([PixelCopy], ảnh của chính cửa sổ, không vẽ lại cây), đổi giao diện NGAY (cả cây vẽ màu mới), rồi phủ ảnh
 * cũ lên trên và khoét một lỗ tròn lớn dần ([progress], đọc trong pha vẽ) cho tới khi hết ảnh. Không chụp được (máy < Android 8, giảm chuyển động, lỗi) thì đổi
 * thẳng.
 */
@Stable
class ThemeReveal(private val scope: CoroutineScope) {
    /** Ảnh giao diện cũ đang phủ; null = không có vòng lan nào. */
    internal var snapshot by mutableStateOf<ImageBitmap?>(null)
        private set
    private var bitmap: Bitmap? = null
    internal var center = Offset.Zero
        private set

    /** 0 = vòng chưa mở, 1 = vòng đã phủ tới góc xa nhất. */
    internal val progress = Animatable(0f)

    /** Chụp cửa sổ (do [ThemeRevealHost] gắn); null khi chưa có cửa sổ. */
    internal var capture: ((done: (Bitmap?) -> Unit) -> Unit)? = null
    private var job: Job? = null

    /**
     * Áp `apply` (đổi tuỳ chọn giao diện). `flips`: giao diện có đổi sáng <-> tối thật không (Tự động -> Sáng khi máy đang sáng thì không - đổi thẳng, không
     * lan). `from`: tâm vòng trong toạ độ gốc.
     */
    fun change(from: Offset, flips: Boolean, apply: () -> Unit) {
        val capture = capture
        if (!flips || capture == null || !from.isSpecified() || !animationsOn()) {
            finish()
            apply()
            return
        }
        finish()
        capture { shot ->
            if (shot != null) {
                bitmap = shot
                snapshot = shot.asImageBitmap()
                center = from
            }
            apply()
            if (shot != null) {
                job = scope.launch {
                    progress.snapTo(0f)
                    try {
                        progress.animateTo(1f, Motion.ThemeReveal)
                    } finally {
                        release()
                    }
                }
            }
        }
    }

    /** Đang lan dở mà có lần đổi mới: kết thúc ngay lần cũ (ảnh cũ bỏ đi). */
    private fun finish() {
        job?.cancel()
        job = null
        release()
    }

    /** Bỏ lớp phủ; trả bộ nhớ ảnh sau hai khung (khung đang vẽ có thể còn dùng nó). */
    private fun release() {
        snapshot = null
        val old = bitmap ?: return
        bitmap = null
        scope.launch {
            withFrameNanos { }
            withFrameNanos { }
            old.recycle()
        }
    }

    private fun Offset.isSpecified() = this != Offset.Unspecified

    private fun animationsOn() = Build.VERSION.SDK_INT < 26 || ValueAnimator.areAnimatorsEnabled()
}

/** Gốc của app: nội dung + lớp ảnh cũ có lỗ tròn khi đang đổi giao diện. Đặt ngoài [AbookTheme] để lớp phủ không phụ thuộc màu mới. */
@Composable
fun ThemeRevealHost(reveal: ThemeReveal, content: @Composable () -> Unit) {
    val view = LocalView.current
    DisposableEffect(view, reveal) {
        reveal.capture = { done -> captureWindow(view, done) }
        onDispose { reveal.capture = null }
    }
    Box(Modifier.fillMaxSize()) {
        content()
        val image = reveal.snapshot
        if (image != null) {
            Box(
                Modifier.fillMaxSize().testTag("theme_reveal")
                    .graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
                    .drawBehind {
                        drawImage(image)
                        val c = reveal.center
                        val far = hypot(max(c.x, size.width - c.x), max(c.y, size.height - c.y))
                        drawCircle(Color.Black, far * reveal.progress.value, c, blendMode = BlendMode.Clear)
                    },
            )
        }
    }
}

private tailrec fun Context.activity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.activity()
    else -> null
}

/** Ảnh của `view` đúng như trên màn (Android 8+: [PixelCopy] từ cửa sổ, GPU chép, luồng chính không vẽ lại gì). Lỗi / máy cũ: null. */
private fun captureWindow(view: View, done: (Bitmap?) -> Unit) {
    val window = view.context.activity()?.window
    val width = view.width
    val height = view.height
    if (Build.VERSION.SDK_INT < 26 || window == null || width == 0 || height == 0) return done(null)
    val bitmap = try {
        Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
    } catch (_: OutOfMemoryError) {
        return done(null)
    }
    val at = IntArray(2)
    view.getLocationInWindow(at)
    try {
        PixelCopy.request(window, Rect(at[0], at[1], at[0] + width, at[1] + height), bitmap, { result ->
            if (result == PixelCopy.SUCCESS) {
                done(bitmap)
            } else {
                bitmap.recycle()
                done(null)
            }
        }, Handler(Looper.getMainLooper()))
    } catch (_: IllegalArgumentException) {
        // Cửa sổ chưa có mặt vẽ (đang dựng / đã huỷ).
        bitmap.recycle()
        done(null)
    }
}
