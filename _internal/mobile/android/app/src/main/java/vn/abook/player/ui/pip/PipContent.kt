package vn.abook.player.ui.pip

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.GeneratedCover
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.theme.Abook

/**
 * Nội dung của cửa sổ nhỏ (PiP): bìa phủ kín (khung 2:3 = tỉ lệ bìa, [PipParams.RATIO_WIDTH]) và dải tiến độ chương mảnh ở đáy - không thêm chữ nào ngoài bìa (bìa tự vẽ giữ tên sách: đó là chính cái bìa, bỏ đi thì không nhận ra cuốn nào).
 * Mọi điều khiển là nút hệ thống của PiP ([PipParams]). `position`: vị trí trong chương (ms), chỉ đọc trong pha vẽ của dải tiến độ.
 */
@Composable
fun PipContent(player: PlayerState, position: () -> Long, covers: CoverLoader, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    BoxWithConstraints(
        modifier.fillMaxSize().background(colors.bgSunken).testTag("pip_content")
            .semantics { contentDescription = player.bookTitle },
    ) {
        PipCover(player, covers, maxWidthPx = with(LocalDensity.current) { maxWidth.roundToPx() }, Modifier.fillMaxSize())
        Box(
            Modifier.align(Alignment.BottomStart).fillMaxWidth().height(PROGRESS_HEIGHT).testTag("pip_progress").drawBehind {
                drawRect(TRACK)
                val fraction = if (player.durationMs > 0) (position().toFloat() / player.durationMs).coerceIn(0f, 1f) else 0f
                drawRect(colors.accent, size = Size(size.width * fraction, size.height))
            },
        )
    }
}

@Composable
private fun PipCover(player: PlayerState, covers: CoverLoader, maxWidthPx: Int, modifier: Modifier) {
    val ref = player.cover
    if (ref == null) {
        GeneratedCover(player.bookTitle, null, with(LocalDensity.current) { maxWidthPx.toDp() }, modifier)
        return
    }
    val key = remember(ref.path, ref.stamp, maxWidthPx) { covers.key(ref.path, ref.stamp, maxWidthPx) }
    val image = remember(key) { mutableStateOf(covers.peek(key)) }
    if (image.value == null) LaunchedEffect(key) { image.value = covers.load(key, ref.path, maxWidthPx, maxWidthPx * 3 / 2) }
    image.value?.let { Image(it, null, modifier, contentScale = ContentScale.Crop) }
}

private val PROGRESS_HEIGHT = 3.dp

/** Nền dải tiến độ: tối vừa đủ nổi trên mọi bìa, sáng hay tối. */
private val TRACK = Color.Black.copy(alpha = 0.45f)
