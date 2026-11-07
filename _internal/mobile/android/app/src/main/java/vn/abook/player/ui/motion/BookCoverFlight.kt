package vn.abook.player.ui.motion

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.NavState

/** The destination artwork moves from the tapped cover using the screen's own progress.
 * No snapshot, overlay layout, extra clock, or per-frame remeasurement is needed.
 * Popping the book drives the exact same rectangle back to its library cell.
 */
@Stable
class BookCoverFlight(private val nav: NavState) {
    private val sources = mutableMapOf<String, LayoutCoordinates>()
    private var captured: Pair<String, Rect>? = null

    fun source(id: String, coordinates: LayoutCoordinates) { sources[id] = coordinates }

    fun capture(id: String) {
        captured = sources[id]?.takeIf { it.isAttached }?.let {
            val origin = it.localToRoot(Offset.Zero)
            id to Rect(origin.x, origin.y, origin.x + it.size.width, origin.y + it.size.height)
        }
    }

    fun origin(id: String): Rect? = captured?.takeIf { it.first == id }?.second
    fun active(id: String): Boolean = origin(id) != null &&
        (nav.stack.top?.destination as? Destination.Book)?.book?.id == id
    fun progress(): Float = nav.progress.value
}

val LocalBookCoverFlight = staticCompositionLocalOf<BookCoverFlight?> { null }

@Composable
fun Modifier.bookCoverSource(id: String): Modifier {
    val flight = LocalBookCoverFlight.current ?: return this
    return onGloballyPositioned { flight.source(id, it) }.drawWithContent {
        // The destination draws the same artwork at precisely this rectangle at p=0.
        if (!flight.active(id)) drawContent()
    }
}

/** A stable, untransformed wrapper supplies the target coordinates. Reading the
 * animated cover's own coordinates here would feed last frame's transform back
 * into the next frame and cause a visible jump.
 */
@Composable
fun FlyingBookCover(book: ListenBook, covers: CoverLoader, width: Dp, modifier: Modifier = Modifier) {
    val flight = LocalBookCoverFlight.current
    var destination by remember { mutableStateOf<Rect?>(null) }
    var screenWidth by remember { mutableStateOf(0f) }
    Box(modifier.onGloballyPositioned { coordinates ->
        var root = coordinates
        while (root.parentLayoutCoordinates != null) root = root.parentLayoutCoordinates!!
        screenWidth = root.size.width.toFloat()
        val origin = coordinates.localToRoot(Offset.Zero)
        // This callback runs after the parent's layer has been placed. Reading
        // localToRoot from a child's graphicsLayer can see the previous frame's
        // parent translation, so keep layout coordinates out of that phase.
        val shift = if (flight?.active(book.id) == true) ScreenGeometry.topFraction(flight.progress()) * screenWidth else 0f
        destination = Rect(origin.x - shift, origin.y, origin.x - shift + coordinates.size.width, origin.y + coordinates.size.height)
    }) {
        BookCover(book.cover, book.title, book.part, covers, width, Modifier.width(width).graphicsLayer {
            if (flight?.active(book.id) != true) return@graphicsLayer
            val target = destination ?: return@graphicsLayer
            val source = flight.origin(book.id) ?: return@graphicsLayer
            val p = flight.progress()
            val screenShift = ScreenGeometry.topFraction(p) * screenWidth
            transformOrigin = TransformOrigin(0f, 0f)
            translationX = (source.left - target.left) * (1f - p) - screenShift
            translationY = (source.top - target.top) * (1f - p)
            scaleX = source.width / size.width + (1f - source.width / size.width) * p
            scaleY = source.height / size.height + (1f - source.height / size.height) * p
        }.testTag("flying_book_cover"))
    }
}
