package vn.abook.player.ui.pip

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.GeneratedCover
import vn.abook.player.ui.components.shapeForWrap
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Nội dung của cửa sổ nhỏ (PiP), cùng năm thứ với cửa sổ mini của bản máy tính (`MiniPlayer.qml`, docs/DESIGN.md "Khay hệ thống và cửa sổ mini"), cùng thứ tự đọc:
 * bìa phủ kín (khung 2:3 = tỉ lệ bìa, [PipParams.RATIO_WIDTH]), tên sách, tên chương (chữ trắng trên lớp nền tối dần ở đáy bìa), dải tiến độ chương mảnh ở đáy, và ba nút
 * lùi / phát / tới là nút hệ thống của PiP ([PipParams]; app không vẽ nút giả vào đây). Khác bản máy tính vì giới hạn nền tảng: PiP không nhận chạm vào nội dung nên dải
 * tiến độ chỉ để xem. Chữ của người dùng không bao giờ bị cắt: chữ dài XUỐNG DÒNG như `MiniPlayer.qml`, không "…", không maxLines.
 *
 * Dòng nào hiện là do ĐO, không đoán bằng số ký tự ([planPipText]): dàn từng tên ở bề rộng thật của khung (trừ hai lề) rồi cộng lề trên (chỗ nền mờ dần), khe giữa hai dòng,
 * lề dưới và dải tiến độ. (1) Tên sách + tên chương vừa chiều cao khung: hiện cả hai. (2) Không vừa: chỉ hiện tên chương - tên sách đã nằm trên bìa tự vẽ. (3) Tên chương
 * một mình vẫn không vừa: nền tối dần mọc lên hết chiều cao bìa (lề trên thu về [Dim.s8]), chữ vẫn đủ và dồn xuống đáy; không bao giờ để chữ tràn khỏi khung.
 * Không có tên chương thì tên sách luôn hiện (không còn gì khác để nhường chỗ). `position`: vị trí trong chương (ms), chỉ đọc trong pha vẽ của dải tiến độ.
 */
@Composable
fun PipContent(player: PlayerState, position: () -> Long, covers: CoverLoader, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val titleStyle = Abook.type.body.copy(fontWeight = FontWeight.Bold, color = Color.White)
    val chapterStyle = Abook.type.caption.copy(color = Color.White.copy(alpha = CHAPTER_ALPHA))
    val measurer = rememberTextMeasurer()
    val density = LocalDensity.current
    BoxWithConstraints(
        modifier.fillMaxSize().background(colors.bgSunken).testTag("pip_content")
            .semantics { contentDescription = player.bookTitle },
    ) {
        PipCover(player, covers, maxWidthPx = with(LocalDensity.current) { maxWidth.roundToPx() }, Modifier.fillMaxSize())
        val plan = remember(player.bookTitle, player.chapterTitle, titleStyle, chapterStyle, density, constraints.maxWidth, constraints.maxHeight) {
            planPipText(player.bookTitle, player.chapterTitle, titleStyle, chapterStyle, measurer, density, constraints.maxWidth, constraints.maxHeight)
        }
        if (plan.showBook || plan.showChapter) {
            Column(
                Modifier.align(Alignment.BottomStart).fillMaxWidth().then(if (plan.full) Modifier.fillMaxHeight() else Modifier).background(SCRIM)
                    .padding(start = Dim.s12, end = Dim.s12, top = if (plan.full) Dim.s8 else Dim.s24, bottom = PROGRESS_HEIGHT + Dim.s8),
                verticalArrangement = Arrangement.spacedBy(Dim.s4, if (plan.full) Alignment.Bottom else Alignment.Top),
            ) {
                if (plan.showBook) BasicText(player.bookTitle, Modifier.testTag("pip_book_title"), style = titleStyle)
                if (plan.showChapter) BasicText(player.chapterTitle, Modifier.testTag("pip_chapter_title"), style = chapterStyle)
            }
        }
        Box(
            Modifier.align(Alignment.BottomStart).fillMaxWidth().height(PROGRESS_HEIGHT).testTag("pip_progress").drawBehind {
                drawRect(TRACK)
                val fraction = if (player.durationMs > 0) (position().toFloat() / player.durationMs).coerceIn(0f, 1f) else 0f
                drawRect(colors.accent, size = Size(size.width * fraction, size.height))
            },
        )
    }
}

/** Dòng nào hiện ([showBook], [showChapter]) và nền tối dần có phải mọc hết chiều cao bìa không ([full]). Xem KDoc của [PipContent]. */
internal data class PipTextPlan(val showBook: Boolean, val showChapter: Boolean, val full: Boolean)

/** Đo thật bằng chính kiểu chữ và chính chữ đã chỉnh xuống dòng ([shapeForWrap]) mà [BasicText] sẽ vẽ; `widthPx` / `heightPx` là khung PiP. */
internal fun planPipText(
    book: String, chapter: String, titleStyle: TextStyle, chapterStyle: TextStyle,
    measurer: TextMeasurer, density: Density, widthPx: Int, heightPx: Int,
): PipTextPlan = with(density) {
    val textWidth = (widthPx - 2 * Dim.s12.roundToPx()).coerceAtLeast(0)
    fun height(text: String, style: TextStyle) =
        if (text.isEmpty()) 0 else measurer.measure(shapeForWrap(text), style, constraints = Constraints(maxWidth = textWidth)).size.height
    val gap = Dim.s4.roundToPx()
    val below = (PROGRESS_HEIGHT + Dim.s8).roundToPx()
    val fade = Dim.s24.roundToPx()
    val bookHeight = height(book, titleStyle)
    val chapterHeight = height(chapter, chapterStyle)
    val both = book.isNotEmpty() && chapter.isNotEmpty()
    val showBook = book.isNotEmpty() && (chapter.isEmpty() || fade + below + bookHeight + gap + chapterHeight <= heightPx)
    val shown = (if (showBook) bookHeight else 0) + chapterHeight + (if (showBook && both) gap else 0)
    PipTextPlan(showBook, chapter.isNotEmpty(), full = fade + below + shown > heightPx)
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

/** Nền tối dần ở đáy bìa cho hai dòng chữ: tối vừa đủ để chữ trắng đọc được trên mọi bìa, sáng hay tối. */
private val SCRIM = Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.72f)))

/** Tên chương là chữ phụ so với tên sách (như `Theme.text2` ở bản máy tính). */
private const val CHAPTER_ALPHA = 0.78f

