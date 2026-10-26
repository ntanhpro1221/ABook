package vn.abook.player.ui.pip

import android.content.Context
import android.graphics.Bitmap
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Canvas
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.drawscope.CanvasDrawScope
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.font.createFontFamilyResolver
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import vn.abook.player.ui.components.PlayPauseGeometry
import vn.abook.player.ui.components.drawPlayPause
import vn.abook.player.ui.nowplaying.drawSkip
import vn.abook.player.ui.nowplaying.skipNumberLayout

/**
 * Icon của ba nút hệ thống trong PiP: ảnh vẽ bằng CHÍNH các hàm vẽ của trình phát ([drawSkip] cho lùi / tới 15 giây, [drawPlayPause] cho phát / dừng) vào một ImageBitmap
 * 24 dp - nút trong cửa sổ nhỏ và nút trong Đang nghe là một hình. Trắng, vì thanh nút của PiP luôn nền tối.
 */
internal object PipIcons {
    private const val SIZE_DP = 24

    fun bitmap(context: Context, kind: PipKind, playing: Boolean): Bitmap {
        val density = Density(context)
        val side = (SIZE_DP * density.density).toInt().coerceAtLeast(1)
        val image = ImageBitmap(side, side)
        val ink = Color.White
        val path = Path()
        CanvasDrawScope().draw(density, LayoutDirection.Ltr, Canvas(image), Size(side.toFloat(), side.toFloat())) {
            when (kind) {
                // Đang phát thì nút làm việc kế là Tạm dừng: vẽ hai thanh (t = 1); đang dừng thì vẽ tam giác phát (t = 0).
                PipKind.Toggle -> drawPlayPause(if (playing) 1f else 0f, ink, FloatArray(PlayPauseGeometry.POINTS), path)
                PipKind.Back, PipKind.Forward -> {
                    val measurer = TextMeasurer(createFontFamilyResolver(context), density, LayoutDirection.Ltr, cacheSize = 1)
                    drawSkip(kind == PipKind.Forward, ink, path, skipNumberLayout(measurer, density, ink))
                }
            }
        }
        return image.asAndroidBitmap()
    }
}
