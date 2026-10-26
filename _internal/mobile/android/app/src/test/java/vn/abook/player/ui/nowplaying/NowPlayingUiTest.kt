@file:OptIn(androidx.compose.animation.ExperimentalSharedTransitionApi::class)

package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.unit.DpRect
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.width
import androidx.compose.ui.unit.height
import androidx.compose.ui.geometry.Offset
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NowPlayingUiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private lateinit var window: NowPlayingWindowState
    private lateinit var model: FakeNowPlayingModel
    private lateinit var scope: CoroutineScope

    private fun show(dark: Boolean = false, expanded: Boolean = true, reading: Boolean = false,
                     playing: Boolean = false, sheet: PlayerSheet? = null, longTitles: Boolean = false) {
        val initial = FakeNowPlayingModel.demoState().copy(playing = playing,
            chapterTitle = if (longTitles) LONG_CHAPTER else FakeNowPlayingModel.demoState().chapterTitle,
            bookTitle = if (longTitles) LONG_BOOK else FakeNowPlayingModel.demoState().bookTitle)
        model = FakeNowPlayingModel(initial)
        rule.setContent {
            AbookTheme(dark) {
                scope = rememberCoroutineScope()
                window = rememberNowPlayingWindowState()
                LaunchedEffect(Unit) {
                    window.reading = reading
                    if (expanded) window.open()
                    if (sheet != null) window.openSheet(sheet)
                }
                NowPlayingHost(model, window, sampleClock = false) {
                    Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { BasicText("Thư viện", style = Abook.type.screenTitle) }
                }
            }
        }
        rule.waitForIdle()
    }
    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/np_$name.png")
    private fun bounds(tag: String): DpRect {
        val content = rule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
        if (tag != "now_playing") return content
        // Compose exposes the shared overlay's translated origin on the content, and its animated size
        // on the placeholder (ScaleToBounds keeps content at final size). Inspect both actual UI nodes.
        val placeholder = rule.onNodeWithTag("now_playing_bounds").getUnclippedBoundsInRoot()
        return DpRect(content.left, content.top, content.left + placeholder.width, content.top + placeholder.height)
    }
    private fun assertBounds(a: DpRect, b: DpRect, tolerance: Float = 1f) {
        assertEquals("left", a.left.value, b.left.value, tolerance)
        assertEquals("top", a.top.value, b.top.value, tolerance)
        assertEquals("width", a.width.value, b.width.value, tolerance)
        assertEquals("height", a.height.value, b.height.value, tolerance)
    }

    @Test fun playingLight() { show(playing = true); shot("playing_light") }
    @Test fun playingDark() { show(dark = true, playing = true); shot("playing_dark") }
    @Test fun pausedLight() { show(); shot("paused_light") }
    @Test fun pausedDark() { show(dark = true); shot("paused_dark") }
    @Test fun readingLight() { show(reading = true); shot("reading_light") }
    @Test fun readingDark() { show(dark = true, reading = true); shot("reading_dark") }
    @Test fun speedLight() { show(sheet = PlayerSheet.Speed); shot("speed_light") }
    @Test fun speedDark() { show(dark = true, sheet = PlayerSheet.Speed); shot("speed_dark") }
    @Test fun sleepLight() { show(sheet = PlayerSheet.Sleep); shot("sleep_light") }
    @Test fun sleepDark() { show(dark = true, sheet = PlayerSheet.Sleep); shot("sleep_dark") }
    @Test fun chaptersLight() { show(sheet = PlayerSheet.Chapters); shot("chapters_light") }
    @Test fun chaptersDark() { show(dark = true, sheet = PlayerSheet.Chapters); shot("chapters_dark") }
    @Test fun longTitlesLight() { show(longTitles = true); rule.onNodeWithText(LONG_CHAPTER).assertIsDisplayed(); shot("long_light") }
    @Test fun longTitlesDark() { show(dark = true, longTitles = true); rule.onNodeWithText(LONG_BOOK).assertIsDisplayed(); shot("long_dark") }

    @Test fun secondaryActionsShareOneLabelLineAndEqualColumns() {
        show()
        val labels = listOf("Tốc độ", "Hẹn giờ", "Chương").map { rule.onNodeWithText(it, useUnmergedTree = true).getUnclippedBoundsInRoot() }
        // Nhãn dưới cùng một đường dù ô trên là chữ ("1×") hay icon.
        labels.forEach { assertEquals("đáy nhãn lệch: $labels", labels[0].bottom.value, it.bottom.value, 0.5f) }
        // Ba cột bằng nhau: khoảng giữa các tâm bằng nhau.
        val centers = labels.map { (it.left.value + it.right.value) / 2 }
        assertEquals("tâm không cách đều: $centers", centers[1] - centers[0], centers[2] - centers[1], 1f)
    }

    @Test fun readingHeaderKeepsCoverAndTitlesBesideEachOtherAboveTheText() {
        show(reading = true)
        val cover = bounds("player_cover_small")
        val chapter = rule.onNodeWithText(FakeNowPlayingModel.demoState().chapterTitle, useUnmergedTree = true).getUnclippedBoundsInRoot()
        val text = bounds("read_along_text")
        assertEquals("ô bìa nhỏ 48 dp", 48f, cover.width.value, 0.5f)
        assertTrue("tên chương đứng cạnh bìa nhỏ: $cover / $chapter", chapter.left >= cover.right)
        assertTrue("tên chương nằm trên vùng chữ: $chapter / $text", chapter.bottom <= text.top + 0.5.dp)
        assertTrue("không còn nút đáy kiểu cũ", rule.onAllNodesWithText("Đóng đọc theo").fetchSemanticsNodes().isEmpty())
    }
    @Test fun readingModeMidTransition() {
        show()
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("mode_read").performClick()
        rule.mainClock.advanceTimeBy(160)
        shot("reading_mid")
        // Giữa chuyển cảnh, chữ chương luôn nằm dưới mép bìa và khối tên đang thu lại - không đè lên nhau.
        val cover = rule.onNodeWithTag("player_cover").getUnclippedBoundsInRoot()
        val book = rule.onNodeWithText(FakeNowPlayingModel.demoState().bookTitle, useUnmergedTree = true).getUnclippedBoundsInRoot()
        val text = rule.onNodeWithTag("read_along_text").getUnclippedBoundsInRoot()
        assertTrue("chữ đè tên: $book / $text", text.top >= book.bottom - 0.5.dp)
        assertTrue("chữ đè bìa: $cover / $text", text.top >= cover.top)
    }
    @Test fun tappingTheCoverSwitchesModeBothWays() {
        show()
        rule.onNodeWithTag("player_cover").performClick()
        rule.onNodeWithTag("read_along_text").assertIsDisplayed()
        rule.onNodeWithTag("mode_read").assertIsSelected()
        // Chạm vào chữ khi đang đọc không được đưa về chế độ nghe.
        rule.onNodeWithTag("read_along_text").performClick()
        rule.onNodeWithTag("mode_read").assertIsSelected()
        rule.onNodeWithTag("player_cover_small").performClick()
        rule.onNodeWithTag("read_along_text").assertDoesNotExist()
        rule.onNodeWithTag("mode_listen").assertIsSelected()
    }

    @Test fun readingModeKeepsTransportAtExactlyTheSameCoordinates() {
        show()
        val before = bounds("transport")
        rule.onNodeWithTag("mode_read").performClick()
        rule.onNodeWithTag("read_along_text").assertIsDisplayed()
        assertBounds(before, bounds("transport"), 0.1f)
        rule.onNodeWithTag("mode_listen").performClick()
        rule.onNodeWithTag("read_along_text").assertDoesNotExist()
        assertBounds(before, bounds("transport"), 0.1f)
    }
    @Test fun sheetNeverMovesOrShrinksTheScreenAndBackClosesOnlyTheSheet() {
        show()
        val before = bounds("transport")
        rule.onNodeWithTag("player_speed").performClick()
        assertBounds(before, bounds("transport"), 0.1f)
        rule.onNodeWithTag("player_sheet_speed").assertIsDisplayed()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.onNodeWithTag("player_sheet_speed").assertDoesNotExist()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        assertBounds(before, bounds("transport"), 0.1f)
    }
    @Test fun sharedContainerStartsAtMiniBoundsAndReturnsThere() {
        show(expanded = false)
        val mini = bounds("mini_player")
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("mini_player").performClick()
        rule.mainClock.advanceTimeByFrame()
        val start = bounds("now_playing")
        shot("opening_start")
        assertBounds(mini, start, 4f)
        rule.mainClock.advanceTimeBy(1000)
        val full = bounds("now_playing")
        assertTrue(full.width > mini.width); assertTrue(full.height > mini.height)
        rule.runOnUiThread { scope.launch { window.dragClose(0.5f) } }
        rule.mainClock.advanceTimeByFrame()
        val half = bounds("now_playing")
        assertTrue(half.height > mini.height && half.height < full.height)
        rule.runOnUiThread { scope.launch { window.settleClose(commit = false) } }
        rule.mainClock.advanceTimeBy(1000)
        assertBounds(full, bounds("now_playing"), 1f)
        rule.onNodeWithTag("collapse_player").performClick()
        rule.mainClock.advanceTimeBy(1000)
        assertBounds(mini, bounds("mini_player"), 1f)
        rule.mainClock.autoAdvance = true
    }
    @Test fun controlsUseRealModelActionsAndChoiceClosesSheet() {
        show()
        rule.onNodeWithContentDescription("Tới 15 giây").performClick()
        assertTrue(model.actions.contains("skip:15"))
        rule.onNodeWithTag("player_speed").performClick()
        rule.onNodeWithText("1,5×").performClick()
        assertEquals(1.5, model.state.value.rate, 0.0)
        rule.onNodeWithTag("player_sheet_speed").assertDoesNotExist()
        rule.onNodeWithTag("player_sleep").performClick()
        rule.onNodeWithText("15 phút").performClick()
        assertEquals(SleepKind.Minutes, model.state.value.sleep.kind)
        rule.onNodeWithTag("player_chapters").performClick()
        rule.onNodeWithText("Chương 2 · Trên con đường").performClick()
        assertEquals(2, model.state.value.chapterId)
    }
    @Test fun positionTicksDoNotRecomposeTheHost() {
        show(reading = true)
        val before = Recomposer.runningRecomposers.value.sumOf { it.changeCount }
        rule.runOnIdle { repeat(60) { model.setPosition(12_000 + it * 16L) } }
        rule.waitForIdle()
        assertEquals(before, Recomposer.runningRecomposers.value.sumOf { it.changeCount })
    }
    @Test fun swipeDownClosesThroughTheSharedContainer() {
        show()
        rule.onNodeWithTag("now_playing").performTouchInput {
            swipe(Offset(width * 0.5f, height * 0.2f), Offset(width * 0.5f, height * 0.8f), 400)
        }
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
    }
    @Test fun readerHeaderCanBeDraggedDownWithoutTakingTheTextScrollGesture() {
        show(reading = true)
        rule.onNodeWithTag("now_playing").performTouchInput {
            swipe(Offset(width * 0.5f, height * 0.035f), Offset(width * 0.5f, height * 0.6f), 400)
        }
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
    }

    companion object {
        const val LONG_CHAPTER = "Chương mười hai · Người lữ khách trở về qua những con đường mùa thu"
        const val LONG_BOOK = "Những ngày gió hát bên kia ngọn đồi và câu chuyện chưa kể"
    }
}
