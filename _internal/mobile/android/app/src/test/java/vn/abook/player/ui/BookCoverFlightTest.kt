package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.DpRect
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.width
import androidx.compose.ui.unit.height
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.motion.*
import vn.abook.player.ui.nav.*
import vn.abook.player.ui.shell.ScreenStack
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookCoverFlightTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private lateinit var nav: NavState
    private lateinit var flight: BookCoverFlight
    private lateinit var scope: CoroutineScope
    private val book = ListenBook("b", "A book", "Author")

    private fun bounds(tag: String): DpRect {
        val r = rule.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
        return with(rule.density) { DpRect(r.left.toDp(), r.top.toDp(), r.right.toDp(), r.bottom.toDp()) }
    }
    private fun same(a: DpRect, b: DpRect) {
        assertEquals(a.left.value, b.left.value, 0.5f)
        assertEquals(a.top.value, b.top.value, 0.5f)
        assertEquals(a.width.value, b.width.value, 0.5f)
        assertEquals(a.height.value, b.height.value, 0.5f)
    }

    @Test fun coverMovesFromCellAndPredictiveBackRetracesEveryRectangle() {
        val covers = CoverLoader(1 shl 20)
        rule.setContent {
            AbookTheme(false) {
                scope = rememberCoroutineScope()
                nav = remember { NavState(scope) }
                flight = remember { BookCoverFlight(nav) }
                CompositionLocalProvider(LocalBookCoverFlight provides flight) {
                    ScreenStack(nav, root = {
                        Box(Modifier.fillMaxSize().padding(20.dp)) {
                            BookCover(book.cover, book.title, book.part, covers, 90.dp,
                                Modifier.width(90.dp).bookCoverSource(book.id).testTag("cell"))
                            // The adjacent filter page contains the same book, but it is offscreen.
                            BookCover(book.cover, book.title, book.part, covers, 90.dp,
                                Modifier.offset(x = 400.dp).width(90.dp).bookCoverSource(book.id).testTag("offscreen_cell"))
                        }
                    }, screen = {
                        Box(Modifier.fillMaxSize().padding(start = 30.dp, top = 90.dp)) {
                            FlyingBookCover(book, covers, 120.dp, Modifier.width(120.dp))
                        }
                    })
                }
            }
        }
        val source = bounds("cell")
        rule.mainClock.autoAdvance = false
        rule.runOnUiThread { flight.capture(book.id); nav.push(Destination.Book(book)) }
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeByFrame()
        same(source, bounds("flying_book_cover"))
        rule.mainClock.advanceTimeBy(400)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        rule.mainClock.autoAdvance = false
        val target = bounds("flying_book_cover")
        assertTrue(target.width > source.width)
        fun at(p: Float): DpRect {
            rule.runOnUiThread { scope.launch { nav.dragBack(1f - p) } }
            rule.mainClock.advanceTimeByFrame()
            return bounds("flying_book_cover")
        }
        val out = (0..10).map { step ->
            val p = step / 10f
            at(p).also { r ->
                assertEquals(source.left.value + (target.left.value - source.left.value) * p, r.left.value, 0.5f)
                assertEquals(source.top.value + (target.top.value - source.top.value) * p, r.top.value, 0.5f)
                assertEquals(source.width.value + (target.width.value - source.width.value) * p, r.width.value, 0.5f)
                assertEquals(source.height.value + (target.height.value - source.height.value) * p, r.height.value, 0.5f)
            }
        }
        for (step in 10 downTo 0) same(out[step], at(step / 10f))
        same(source, out.first()); same(target, out.last())
        rule.mainClock.autoAdvance = true
    }
}
