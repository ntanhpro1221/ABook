package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.unit.DpRect
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.width
import androidx.compose.ui.unit.height
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.asCoroutineDispatcher
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
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.PlayerClock
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.BookScreenActions
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

    @Test fun entryWaitsForADelayedCoverLayoutInsteadOfSpendingItsAnimationOffscreen() {
        val covers = CoverLoader(1 shl 20)
        rule.setContent {
            AbookTheme(false) {
                scope = rememberCoroutineScope()
                nav = remember { NavState(scope) }
                flight = remember { BookCoverFlight(nav) }
                CompositionLocalProvider(LocalBookCoverFlight provides flight) {
                    ScreenStack(nav, root = {
                        Box(Modifier.fillMaxSize().padding(start = 20.dp, top = 300.dp)) {
                            BookCover(book.cover, book.title, book.part, covers, 90.dp,
                                Modifier.width(90.dp).bookCoverSource(book.id).testTag("cell"))
                        }
                    }, screen = {
                        var ready by remember { mutableStateOf(false) }
                        LaunchedEffect(Unit) { delay(600); ready = true }
                        Box(Modifier.fillMaxSize().padding(start = 30.dp, top = 90.dp)) {
                            if (ready) FlyingBookCover(book, covers, 120.dp, Modifier.width(120.dp))
                        }
                    })
                }
            }
        }
        rule.mainClock.autoAdvance = false
        rule.runOnUiThread { flight.capture(book.id); nav.push(Destination.Book(book)) }
        rule.mainClock.advanceTimeBy(400)
        rule.runOnUiThread { assertEquals("layout is not ready", 0f, nav.progress.value, 0f) }
        rule.mainClock.advanceTimeBy(250)
        rule.mainClock.advanceTimeBy(400)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        assertEquals(1f, nav.progress.value, 0f)
        assertTrue(bounds("flying_book_cover").top.value < 100f)
    }

    @Test fun aBookRemovedAfterTheTapDoesNotWaitForeverForMissingArtwork() {
        val covers = CoverLoader(1 shl 20)
        rule.setContent {
            AbookTheme(false) {
                scope = rememberCoroutineScope()
                nav = remember { NavState(scope) }
                flight = remember { BookCoverFlight(nav) }
                val sheets = remember { SheetHost() }
                CompositionLocalProvider(LocalBookCoverFlight provides flight) {
                    ScreenStack(nav, root = {
                        BookCover(book.cover, book.title, book.part, covers, 90.dp,
                            Modifier.width(90.dp).bookCoverSource(book.id).testTag("cell"))
                    }, screen = {
                        BookScreen(book, LibraryState.Ready(emptyList()), PlayerState.Empty, PlayerClock(), covers,
                            BookSource.None, sheets, BookScreenActions(nav::pop, {}, {}, { _, _, _ -> }, {}, edit = {}))
                    })
                }
            }
        }
        rule.runOnUiThread { flight.capture(book.id); nav.push(Destination.Book(book)) }
        rule.waitForIdle()
        rule.onNodeWithTag("book_gone").assertIsDisplayed()
        assertEquals(1f, nav.progress.value, 0f)
    }

    // A page that never lays the cover out (a future screen state, a crash in its header) must not freeze navigation.
    @Test fun aPageThatNeverPlacesItsCoverStillSlidesIn() {
        val covers = CoverLoader(1 shl 20)
        rule.setContent {
            AbookTheme(false) {
                scope = rememberCoroutineScope()
                nav = remember { NavState(scope) }
                flight = remember { BookCoverFlight(nav) }
                CompositionLocalProvider(LocalBookCoverFlight provides flight) {
                    ScreenStack(nav, root = {
                        BookCover(book.cover, book.title, book.part, covers, 90.dp,
                            Modifier.width(90.dp).bookCoverSource(book.id).testTag("cell"))
                    }, screen = { Box(Modifier.fillMaxSize()) })
                }
            }
        }
        rule.mainClock.autoAdvance = false
        rule.runOnUiThread { flight.capture(book.id); nav.push(Destination.Book(book)) }
        rule.mainClock.advanceTimeBy(1_000)
        rule.runOnUiThread { assertEquals("still waiting for the cover", 0f, nav.progress.value, 0f) }
        rule.mainClock.advanceTimeBy(2_000)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        assertEquals(1f, nav.progress.value, 0f)
        assertTrue(!nav.busy)
    }

    private fun artworkStage(cover: CoverRef, covers: CoverLoader): ListenBook {
        val art = ListenBook("art", "Art", "Author", cover = cover)
        rule.setContent {
            AbookTheme(false) {
                scope = rememberCoroutineScope()
                nav = remember { NavState(scope) }
                flight = remember { BookCoverFlight(nav) }
                CompositionLocalProvider(LocalBookCoverFlight provides flight) {
                    ScreenStack(nav, root = {
                        Box(Modifier.fillMaxSize().padding(start = 20.dp, top = 300.dp)) {
                            Box(Modifier.width(90.dp).height(135.dp).bookCoverSource(art.id).testTag("cell"))
                        }
                    }, screen = {
                        Box(Modifier.fillMaxSize().padding(start = 30.dp, top = 90.dp)) {
                            FlyingBookCover(art, covers, 120.dp, Modifier.width(120.dp))
                        }
                    })
                }
            }
        }
        return art
    }

    // A memory trim (app hidden) empties the cover cache while the library cell keeps its own bitmap.
    // The page decodes again at its size: the flight must not carry the blank placeholder over the cell.
    @Test fun anEvictedCoverDecodesBeforeTheFlightLeavesTheCell() {
        val file = java.io.File.createTempFile("cover", ".png").apply { deleteOnExit() }
        android.graphics.Bitmap.createBitmap(400, 600, android.graphics.Bitmap.Config.ARGB_8888).apply {
            eraseColor(android.graphics.Color.rgb(200, 40, 40))
            file.outputStream().use { compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it) }
        }
        val gate = java.util.concurrent.CountDownLatch(1)
        val pool = java.util.concurrent.Executors.newSingleThreadExecutor()
        pool.execute { gate.await() } // the decoder thread is busy: the decode stays pending
        try {
            val covers = CoverLoader(8 shl 20, pool.asCoroutineDispatcher())
            val art = artworkStage(CoverRef(file.absolutePath, 1L), covers)
            rule.runOnUiThread { flight.capture(art.id); nav.push(Destination.Book(art)) }
            rule.mainClock.advanceTimeBy(1_000)
            rule.waitForIdle()
            rule.runOnUiThread { assertEquals("placeholder must not fly", 0f, nav.progress.value, 0f) }
            gate.countDown()
            rule.waitUntil(10_000) { nav.progress.value == 1f && !nav.busy }
            assertTrue(covers.peek(file.absolutePath, 1L) != null)
        } finally {
            gate.countDown(); pool.shutdown()
        }
    }

    @Test fun anUnreadableCoverStillOpensTheBook() {
        val art = artworkStage(CoverRef(java.nio.file.Files.createTempDirectory("abook-missing-cover").resolve("cover.png").toString(), 1L), CoverLoader(1 shl 20))
        rule.runOnUiThread { flight.capture(art.id); nav.push(Destination.Book(art)) }
        rule.waitUntil(10_000) { nav.progress.value == 1f && !nav.busy }
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
