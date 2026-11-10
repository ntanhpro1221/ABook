package vn.abook.player.ui.motion

import androidx.compose.foundation.layout.Box
import androidx.compose.animation.SharedTransitionScope
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
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
 * The shared overlay uses that same clock without per-frame remeasurement.
 * Popping the book drives the exact same rectangle back to its library cell.
 */
@Stable
class BookCoverFlight(private val nav: NavState) {
    private val sources = mutableMapOf<String, MutableList<LayoutCoordinates>>()
    private var captured by mutableStateOf<Pair<String, Rect>?>(null)

    fun source(id: String, coordinates: LayoutCoordinates) {
        sources.getOrPut(id) { mutableListOf() }.apply {
            removeAll { !it.isAttached || it === coordinates }
            add(coordinates)
        }
    }

    fun capture(id: String) {
        // Adjacent resident pager pages may contain the same book. Only the
        // visible instance may become the source; never the last laid-out one.
        val candidates = sources[id].orEmpty().filter { it.isAttached }.map { coordinates ->
            val origin = coordinates.localToRoot(Offset.Zero)
            val end = coordinates.localToRoot(Offset(coordinates.size.width.toFloat(), coordinates.size.height.toFloat()))
            val rect = Rect(origin.x, origin.y, end.x, end.y)
            var root = coordinates
            while (root.parentLayoutCoordinates != null) root = root.parentLayoutCoordinates!!
            val visible = rect.intersect(Rect(0f, 0f, root.size.width.toFloat(), root.size.height.toFloat()))
            rect to (visible.width.coerceAtLeast(0f) * visible.height.coerceAtLeast(0f))
        }
        captured = candidates.maxByOrNull { it.second }?.takeIf { it.second > 0 }?.let { id to it.first }
    }

    fun origin(id: String): Rect? = captured?.takeIf { it.first == id }?.second
    fun clear() { captured = null }
    fun active(id: String): Boolean = origin(id) != null &&
        (nav.stack.top?.destination as? Destination.Book)?.book?.id == id
    fun progress(): Float = nav.progress.value
}

val LocalBookCoverFlight = staticCompositionLocalOf<BookCoverFlight?> { null }
val LocalCoverOverlay = staticCompositionLocalOf<SharedTransitionScope?> { null }

@Composable
fun Modifier.bookCoverSource(id: String): Modifier {
    val flight = LocalBookCoverFlight.current ?: return this
    // Keep the source pixels until the incoming page covers them. A missing or
    // delayed destination must never leave an empty hole in the library.
    return onGloballyPositioned { flight.source(id, it) }
}

/** A stable, untransformed wrapper supplies the target coordinates. Reading the
 * animated cover's own coordinates here would feed last frame's transform back
 * into the next frame and cause a visible jump.
 */
@Composable
fun FlyingBookCover(book: ListenBook, covers: CoverLoader, width: Dp, modifier: Modifier = Modifier) {
    val flight = LocalBookCoverFlight.current
    val overlay = LocalCoverOverlay.current
    var destination by remember { mutableStateOf<Rect?>(null) }
    Box(modifier.onGloballyPositioned { coordinates ->
        val origin = coordinates.localToRoot(Offset.Zero)
        destination = Rect(origin.x, origin.y, origin.x + coordinates.size.width, origin.y + coordinates.size.height)
    }) {
        val shared = if (overlay == null) Modifier else with(overlay) {
            Modifier.renderInSharedTransitionScopeOverlay(renderInOverlay = { flight?.active(book.id) == true && flight.progress() < 1f })
        }
        BookCover(book.cover, book.title, book.part, covers, width, Modifier.width(width).then(shared).graphicsLayer {
            if (flight?.active(book.id) != true) return@graphicsLayer
            val target = destination ?: return@graphicsLayer
            val source = flight.origin(book.id) ?: return@graphicsLayer
            val p = flight.progress()
            transformOrigin = TransformOrigin(0f, 0f)
            translationX = (source.left - target.left) * (1f - p)
            translationY = (source.top - target.top) * (1f - p)
            scaleX = source.width / size.width + (1f - source.width / size.width) * p
            scaleY = scaleX
        }.testTag("flying_book_cover"))
    }
}
