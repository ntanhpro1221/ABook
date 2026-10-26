package vn.abook.player.ui.player

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.PlayPauseGlyph
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.nowplaying.NowPlayingPart
import vn.abook.player.ui.nowplaying.NowPlayingSource
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.roundToInt

/** Chiều cao TỐI THIỂU của thanh phát nhỏ (token khoảng cách 64); tên dài thì thanh cao thêm theo số dòng, không cắt chữ. */
val MiniPlayerHeight: Dp = 64.dp

/**
 * Thanh phát nhỏ (DESIGN.md §6): bìa · tên chương / tên sách · nút phát; vạch tiến độ 2 dp ở mép trên. Không giữ trạng thái - mọi thứ vào qua tham số.
 *
 * - `state`: bất biến, đổi khi có gì đổi thật (không đổi mỗi nhịp).
 * - `positionMs`: vị trí chạy theo nhịp, CHỈ đọc trong pha vẽ của vạch tiến độ (truyền `{ clock.positionMs.value }`) nên mỗi nhịp không dựng lại gì.
 * - `onToggle`: nút phát / dừng; `onOpenNowPlaying`: chạm vào phần còn lại của thanh.
 * - `modifier`: đặt NGOÀI CÙNG của thanh - cửa sổ Đang nghe đưa vào khung chung (`sharedBounds`) để thanh nở thành cả màn.
 * - `sharedModifier(part)`: móc cho chuyển phần tử chung. Cửa sổ Đang nghe trả về Modifier (`Modifier.sharedElement(...)`) cho từng [NowPlayingPart]
 *   (Cover, Chapter, Book, Play); mặc định không thêm gì. Hàm là @Composable để dùng được `rememberSharedContentState`. Modifier đặt NGOÀI CÙNG của mỗi phần
 *   (bìa 36 dp, hai dòng chữ, nút phát 44 dp).
 *
 * Nút phát <-> dừng biến hình nét vẽ ([PlayPauseGlyph]), không mờ chéo.
 */
@Composable
fun MiniPlayer(
    state: PlayerState,
    positionMs: () -> Long,
    covers: CoverLoader,
    onToggle: () -> Unit,
    onOpenNowPlaying: () -> Unit,
    modifier: Modifier = Modifier,
    sharedModifier: @Composable (NowPlayingPart) -> Modifier = { Modifier },
) {
    val colors = Abook.colors
    val durationMs = state.durationMs
    val title = state.chapterTitle.ifEmpty { state.bookTitle }
    Row(
        modifier.fillMaxWidth().heightIn(min = MiniPlayerHeight)
            .drawBehind {
                // Bóng nhẹ phía trên (lớp nổi) rồi nền, cuối cùng vạch tiến độ.
                val lift = 8.dp.toPx()
                drawRect(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = if (colors.dark) 0.32f else 0.08f)), -lift, 0f), Offset(0f, -lift), Size(size.width, lift))
                drawRect(colors.panel)
                val thick = 2.dp.toPx()
                drawRect(colors.line, Offset.Zero, Size(size.width, thick))
                if (durationMs > 0) {
                    val fraction = (positionMs().toFloat() / durationMs).coerceIn(0f, 1f)
                    drawRect(colors.accent, Offset.Zero, Size(size.width * fraction, thick))
                }
            }
            .testTag("mini_player"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            Modifier.weight(1f).heightIn(min = MiniPlayerHeight).pressable { onOpenNowPlaying() }.padding(start = Dim.s12, top = Dim.s4, bottom = Dim.s4).testTag("mini_open"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BookCover(state.cover, state.bookTitle, null, covers, 36.dp, sharedModifier(NowPlayingPart.Cover).width(36.dp), small = true)
            Spacer(Modifier.width(Dim.s12))
            Column(Modifier.weight(1f)) {
                BasicText(title, sharedModifier(NowPlayingPart.Chapter), Abook.type.label)
                BasicText(state.bookTitle, sharedModifier(NowPlayingPart.Book), Abook.type.caption)
            }
        }
        Box(Modifier.padding(horizontal = Dim.s12)) {
            Box(
                sharedModifier(NowPlayingPart.Play).size(Dim.touch).pressable { onToggle() }.clip(CircleShape).background(colors.accent)
                    .semantics { contentDescription = if (state.playing) "Tạm dừng" else "Phát" }.testTag("mini_play"),
                contentAlignment = Alignment.Center,
            ) {
                PlayPauseGlyph(state.playing, colors.accentInk, 22.dp)
            }
        }
    }
}

/**
 * Thanh phát nhỏ THẬT làm nguồn của chuyển động nở thành cửa sổ Đang nghe: cùng [MiniPlayer], gói vào khung chung và bốn phần bay riêng của cửa sổ
 * ([NowPlayingSource]). Không có lớp cửa sổ ở trên (xem trước, ảnh chụp riêng thanh) thì nó là [MiniPlayer] thường.
 */
@Composable
fun MorphingMiniPlayer(
    state: PlayerState,
    positionMs: () -> Long,
    covers: CoverLoader,
    onToggle: () -> Unit,
    onOpenNowPlaying: () -> Unit,
    modifier: Modifier = Modifier,
) {
    NowPlayingSource { bounds, part ->
        MiniPlayer(state, positionMs, covers, onToggle, onOpenNowPlaying, modifier.then(bounds), part)
    }
}

/**
 * Chỗ của thanh phát nhỏ trong cột gốc: cao dần từ 0 tới thanh đầy khi có bài (220 ms), thu về 0 khi hết - nội dung nằm yên ở đỉnh ô còn thanh tab đè lên phần chưa lộ,
 * nên thanh như trồi lên từ thanh tab. Chiều cao chỉ đọc trong pha dàn trang.
 */
@Composable
fun MiniPlayerSlot(visible: Boolean, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val reveal = remember { Animatable(if (visible) 1f else 0f) }
    LaunchedEffect(visible) { reveal.animateTo(if (visible) 1f else 0f, if (visible) Motion.Expand else Motion.Collapse) }
    // Khi cửa sổ Đang nghe mở, thanh nhỏ rời cây (nó nở thành cửa sổ) và đo ra 0: giữ chỗ cũ để nội dung bên dưới không nhảy theo.
    val kept = remember { intArrayOf(0) }
    Layout(content = content, modifier = modifier) { measurables, constraints ->
        val placeables = measurables.map { it.measure(constraints.copy(minHeight = 0)) }
        val measured = placeables.maxOfOrNull { it.height } ?: 0
        if (measured > 0) kept[0] = measured
        val full = if (visible) kept[0] else measured
        val width = placeables.maxOfOrNull { it.width } ?: constraints.minWidth
        val height = (full * reveal.value).roundToInt()
        layout(width, height) { placeables.forEach { it.place(0, 0) } }
    }
}
