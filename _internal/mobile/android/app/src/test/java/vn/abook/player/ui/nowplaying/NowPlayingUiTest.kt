@file:OptIn(androidx.compose.animation.ExperimentalSharedTransitionApi::class)

package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.data.FakePrepareSource
import vn.abook.player.ui.data.PreparePlan
import vn.abook.player.ui.data.PreparedChapter
import vn.abook.player.ui.data.PrepareState
import vn.abook.player.ui.data.PrepareStatus
import kotlinx.coroutines.Dispatchers
import vn.abook.player.ui.player.MiniPlayerSlot
import vn.abook.player.ui.player.MorphingMiniPlayer
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
    private val miniCovers = CoverLoader()

    private fun show(dark: Boolean = false, expanded: Boolean = true, reading: Boolean = false,
                     playing: Boolean = false, sheet: PlayerSheet? = null, longTitles: Boolean = false, base: NowPlayingState? = null,
                     prepare: vn.abook.player.ui.data.PrepareState? = null) {
        val initial = (base ?: FakeNowPlayingModel.demoState()).copy(playing = playing,
            chapterTitle = if (longTitles) LONG_CHAPTER else FakeNowPlayingModel.demoState().chapterTitle,
            bookTitle = if (longTitles) LONG_BOOK else FakeNowPlayingModel.demoState().bookTitle)
        model = FakeNowPlayingModel(initial, prepare = prepare)
        rule.setContent {
            AbookTheme(dark) {
                scope = rememberCoroutineScope()
                window = rememberNowPlayingWindowState()
                LaunchedEffect(Unit) {
                    window.reading = reading
                    if (expanded) window.open()
                    if (sheet != null) window.openSheet(sheet)
                }
                // The real mini player (not a stand-in) over a tab-bar-sized strip, as in the shell: it is the morph source.
                NowPlayingLayer(model, window, sampleClock = false) {
                    Column(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                        Box(Modifier.weight(1f).fillMaxWidth()) { BasicText("Thư viện", style = Abook.type.screenTitle) }
                        val now by model.state.collectAsState()
                        MiniPlayerSlot(visible = true) {
                            MorphingMiniPlayer(
                                PlayerState(
                                    bookId = now.bookId, bookTitle = now.bookTitle, chapterId = now.chapterId, chapterTitle = now.chapterTitle,
                                    playing = now.playing, durationMs = now.durationMs, cover = now.cover,
                                ),
                                { model.position.milliseconds.value }, miniCovers, model::toggle, window::open,
                            )
                        }
                        Box(Modifier.fillMaxWidth().height(56.dp).background(Abook.colors.panel))
                    }
                }
            }
        }
        rule.waitForIdle()
    }
    /** The real mini player stays composed under the window (hidden from accessibility), so text of the window itself is looked up inside it. */
    private fun inWindow(matcher: SemanticsMatcher) = matcher and hasAnyAncestor(hasTestTag("now_playing"))
    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/np_$name.png")
    private fun bounds(tag: String): DpRect {
        if (tag != "now_playing") return rule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
        // The window is laid out at its final size and clipped by a rectangle that grows out of the bar (graphicsLayer only), so the container's
        // bounds are the window state's own clip rectangle, in the overlay's pixels.
        val layer = rule.onNodeWithTag("now_playing_bounds").getUnclippedBoundsInRoot()
        val clip = with(rule.density) { window.containerBounds(layer.width.toPx(), layer.height.toPx()) }
        return with(rule.density) { DpRect(clip.left.toDp(), clip.top.toDp(), clip.right.toDp(), clip.bottom.toDp()) }
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
    @Test fun longTitlesLight() { show(longTitles = true); rule.onNode(inWindow(hasText(LONG_CHAPTER))).assertIsDisplayed(); shot("long_light") }
    @Test fun longTitlesDark() { show(dark = true, longTitles = true); rule.onNode(inWindow(hasText(LONG_BOOK))).assertIsDisplayed(); shot("long_dark") }

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
        val chapter = rule.onNode(inWindow(hasText(FakeNowPlayingModel.demoState().chapterTitle)), useUnmergedTree = true).getUnclippedBoundsInRoot()
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
        // Tên sách dưới bìa (không phải chữ trang trí trên bìa tự vẽ).
        val book = rule.onAllNodes(inWindow(hasText(FakeNowPlayingModel.demoState().bookTitle)), useUnmergedTree = true)
            .filterToOne(!hasTestTag("cover_title")).getUnclippedBoundsInRoot()
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

    @Test fun moreSheetHoldsOnlyWhatThePhoneLacks() {
        show(sheet = PlayerSheet.More)
        shot("more_light")
        // Âm lượng thiết bị là việc của phím cứng; hàng "Sắp có" tắt sẵn không phải lựa chọn; "Về chỗ cũ" nằm cạnh thanh tua.
        listOf("Âm lượng", "Sắp có", "Chỗ vừa nghe").forEach {
            assertTrue("còn hàng \"$it\"", rule.onAllNodesWithText(it, substring = true).fetchSemanticsNodes().isEmpty())
        }
        // Không có nguồn nhạc (bản thử) thì không có hàng "Nhạc nền"; hàng thật và tấm của nó: MusicScreenTest.
        assertTrue(rule.onAllNodesWithText("Nhạc nền").fetchSemanticsNodes().isEmpty())
        rule.onNodeWithTag("player_sheet_more").assertIsDisplayed()
    }
    @Test fun sheetHandleReallyDragsAndCloses() {
        show(sheet = PlayerSheet.Speed)
        assertTrue("không còn nút đóng trùng Back", rule.onAllNodesWithContentDescription("Đóng").fetchSemanticsNodes().size <= 1)
        rule.onNodeWithTag("player_sheet_grip").performTouchInput { swipeDown(startY = centerY, endY = centerY + 40f, durationMillis = 300) }
        rule.onNodeWithTag("player_sheet_speed").assertIsDisplayed()
        rule.onNodeWithTag("player_sheet_grip").performTouchInput { swipeDown(startY = centerY, endY = centerY + 900f, durationMillis = 200) }
        rule.waitForIdle()
        rule.onNodeWithTag("player_sheet_speed").assertDoesNotExist()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
    }
    @Test fun returnChipAppearsAfterSeekAndNeverMovesTransport() {
        show()
        val before = bounds("transport")
        rule.onNodeWithTag("return_place").assertDoesNotExist()
        rule.runOnUiThread { model.skip(15) }
        rule.waitForIdle()
        rule.onNodeWithTag("return_place").assertIsDisplayed()
        shot("return_chip_light")
        assertBounds(before, bounds("transport"), 0.1f)
        rule.onNodeWithTag("return_place").performClick()
        assertTrue("return" in model.actions)
        rule.onNodeWithTag("return_place").assertDoesNotExist()
        assertBounds(before, bounds("transport"), 0.1f)
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
        rule.onNodeWithTag("mini_open").performClick()
        // One build frame (the window is composed and laid out hidden), then the motion starts at the bar.
        repeat(2) { rule.mainClock.advanceTimeByFrame() }
        val start = bounds("now_playing")
        shot("opening_start")
        assertBounds(mini, start, 4f)
        rule.mainClock.advanceTimeBy(1000)
        val full = bounds("now_playing")
        // Thanh phát thật rộng đúng bề ngang màn (như thanh tab): chỉ chiều cao lớn lên; cửa sổ đầy là cả màn hình.
        assertTrue("mini=$mini start=$start full=$full", full.width >= mini.width && full.height > mini.height)
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
    /** A real image file as the book's cover (a two-colour picture, so a placeholder and the artwork differ in pixels as well as in text). */
    private fun artCover(): vn.abook.player.ui.data.CoverRef {
        val file = java.io.File.createTempFile("np_cover", ".png").apply { deleteOnExit() }
        val bitmap = android.graphics.Bitmap.createBitmap(120, 180, android.graphics.Bitmap.Config.ARGB_8888)
        android.graphics.Canvas(bitmap).apply {
            drawColor(android.graphics.Color.rgb(200, 40, 40))
            drawRect(0f, 90f, 120f, 180f, android.graphics.Paint().apply { color = android.graphics.Color.rgb(30, 60, 200) })
        }
        file.outputStream().use { bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it) }
        return vn.abook.player.ui.data.CoverRef(file.path, 1)
    }

    @Test fun miniBarKeepsItsArtworkThroughOpenAndCloseAndNeverFallsBackToInitials() {
        val ref = artCover()
        show(expanded = false, base = FakeNowPlayingModel.demoState().copy(cover = ref))
        val initials = vn.abook.player.ui.data.CoverArt.label(FakeNowPlayingModel.demoState().bookTitle, null)
        val px = with(rule.density) { 36.dp.roundToPx() }
        // The art is decoded off the main thread: wait for it, then the bar must show it (no initials text) before anything opens.
        rule.waitUntil(5_000) { miniCovers.peek(miniCovers.key(ref.path, ref.stamp, px)) != null }
        rule.waitForIdle()
        rule.onAllNodesWithText(initials, useUnmergedTree = true).assertCountEquals(0)
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("mini_open").performClick()
        rule.mainClock.advanceTimeBy(1000)
        rule.onAllNodesWithText(initials, useUnmergedTree = true).assertCountEquals(0)
        rule.onNodeWithTag("collapse_player").performClick()
        // Every frame of the way back, down to the last, the bar's cover is the artwork.
        repeat(30) {
            rule.mainClock.advanceTimeByFrame()
            rule.onAllNodesWithText(initials, useUnmergedTree = true).assertCountEquals(0)
        }
        rule.mainClock.advanceTimeBy(1000)
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
        // The bar kept its decoded artwork the whole time (it is still the cached image, not re-decoded or dropped).
        assertNotNull(miniCovers.peek(miniCovers.key(ref.path, ref.stamp, px)))
        rule.onAllNodesWithText(initials, useUnmergedTree = true).assertCountEquals(0)
        rule.mainClock.autoAdvance = true
    }

    @Test fun windowIsTransparentOverTheBarAtBothEndsOfTheMotion() {
        // At progress 0 (the start of an opening, the landing of a closing) the real bar shows, untouched; the window is fully there from a few percent on.
        assertEquals(0f, windowAlpha(0f), 0f)
        assertEquals(1f, windowAlpha(1f), 0f)
        assertTrue(windowAlpha(0.02f) in 0f..1f && windowAlpha(0.02f) > 0f)
        assertEquals(1f, windowAlpha(0.2f), 0f)
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
    @Test fun scrollingAwayShowsAFollowPillInsideTheTextAndTappingItFollowsAgain() {
        show(reading = true)
        rule.onNodeWithTag("follow_sentence").assertDoesNotExist()
        rule.onNodeWithTag("read_along_text").performTouchInput {
            swipe(Offset(width * 0.5f, height * 0.7f), Offset(width * 0.5f, height * 0.3f), 300)
        }
        rule.waitForIdle()
        rule.onNodeWithTag("follow_sentence").assertIsDisplayed()
        val pill = bounds("follow_sentence")
        val text = bounds("read_along_text")
        assertTrue("pill ở trong vùng chữ: $pill / $text", pill.top >= text.top && pill.bottom <= text.bottom)
        shot("reading_follow_light")
        rule.onNodeWithTag("follow_sentence").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("follow_sentence").assertDoesNotExist()
    }

    @Test fun readerHeaderCanBeDraggedDownWithoutTakingTheTextScrollGesture() {
        show(reading = true)
        rule.onNodeWithTag("now_playing").performTouchInput {
            swipe(Offset(width * 0.5f, height * 0.035f), Offset(width * 0.5f, height * 0.6f), 400)
        }
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
    }

    private fun endedState(whole: Boolean = true) = FakeNowPlayingModel.demoState().copy(ended = true, whole = whole)

    @Test fun finishedBookSaysSoOffersRestartOtherBooksAndTheLibrary() {
        show(base = endedState())
        var home = 0
        window.toLibrary = { home++ }
        model.choices = PlayerEnd.Choices(others = listOf(
            PlayerEnd.Pick("b2", "Truyện thứ hai", "Đã nghe 40% cả cuốn · còn 3 giờ"), PlayerEnd.Pick("b3", "Truyện thứ ba", "Chưa nghe · 5 giờ")))
        // Lời đọc model.endChoices() khi `ended` hay danh sách giọng đổi: đổi số giọng để đọc lại.
        model.update(endedState().copy(voices = listOf(PlayerVoice("v", "Giọng"))))
        rule.waitForIdle()
        rule.onNodeWithText(PlayerText.ENDED_BOOK, substring = true).assertIsDisplayed()
        rule.onNodeWithTag("end_restart").assertIsDisplayed().performClick()
        assertTrue(model.actions.contains("restart"))
        rule.onNodeWithText("Nghe cuốn khác").assertIsDisplayed()
        shot("ended_light")
        rule.onNodeWithTag("end_other_b2").assertIsDisplayed().performClick()
        assertTrue(model.actions.contains("listen:b2"))
        rule.onNodeWithTag("end_library").assertIsDisplayed().performClick()
        assertEquals(1, home)
    }

    @Test fun finishedPartOffersTheNextVolumeInsteadOfRestart() {
        show(base = endedState())
        model.choices = PlayerEnd.Choices(next = PlayerEnd.Pick("t2", "Bộ truyện · Tập 2", "Chưa nghe · 6 giờ"))
        model.update(endedState().copy(bookTitle = "Bộ truyện · Tập 1", voices = listOf(PlayerVoice("v", "Giọng"))))
        rule.waitForIdle()
        rule.onNodeWithText(PlayerText.ENDED_PART).assertIsDisplayed()
        rule.onNodeWithTag("end_next").assertIsDisplayed()
        rule.onNodeWithText("Nghe tiếp Tập 2").assertIsDisplayed().performClick()
        assertTrue(model.actions.contains("listen:t2"))
        rule.onNodeWithTag("end_restart").assertDoesNotExist()
    }

    @Test fun caughtUpBookNamesWhatIsLeftAndReplacesTheBookTitleInTheSubtitle() {
        show(base = endedState(whole = false))
        rule.onNodeWithTag("end_caught_up").assertIsDisplayed()
        rule.onNodeWithText("${PlayerText.CAUGHT_UP_HEAD}. ${PlayerText.CAUGHT_UP_DETAIL}").assertIsDisplayed()
        rule.onAllNodesWithText(PlayerText.CAUGHT_UP_HEAD, substring = true, useUnmergedTree = true).assertCountEquals(2)
        shot("caught_up_light")
    }

    private fun oneChapter() = FakeNowPlayingModel.demoState().let { it.copy(chapters = it.chapters.take(1)) }

    @Test fun lastChapterButtonSaysSo() {
        show(base = oneChapter())
        rule.onNodeWithContentDescription("Đây là chương cuối").assertIsDisplayed()
    }

    @Test fun nextChapterWithoutAudioSaysWhy() {
        show(base = oneChapter().copy(moreChapters = true))
        rule.onNodeWithContentDescription("Chương sau chưa có audio").assertIsDisplayed()
    }

    @Test fun nextChapterIsPlainWhenThereIsOne() {
        show()
        rule.onNodeWithContentDescription("Chương sau").assertIsDisplayed()
    }

    @Test fun playButtonSaysWhatItWaitsFor() {
        show(base = FakeNowPlayingModel.demoState().copy(buffering = true, speaking = false), playing = true)
        rule.onNodeWithContentDescription("Đang tải âm thanh").assertIsDisplayed()
    }

    @Test fun aNoteShowsItsActionAndTappingRunsIt() {
        show()
        model.say(PlayerNote("Máy khác đã nghe tới Chương 5 · 12:04", PlayerText.ELSEWHERE_ACTION, serial = 1, lifeMs = 20_000))
        rule.waitForIdle()
        rule.onNodeWithText("Máy khác đã nghe tới Chương 5 · 12:04").assertIsDisplayed()
        shot("note_light")
        rule.onNodeWithTag("player_note_action").performClick()
        assertTrue(model.actions.contains("note"))
        rule.waitForIdle()
        rule.onNodeWithTag("player_note").assertDoesNotExist()
    }

    @Test fun moreSheetStartsWithTheWholeBookProgressLine() {
        show(sheet = PlayerSheet.More, base = FakeNowPlayingModel.demoState().copy(chapters = List(4) { vn.abook.player.ui.data.PlayerChapter(it + 1, "C${it + 1}", 600_000) }, chapterId = 1))
        rule.onNodeWithTag("book_progress").assertIsDisplayed()
        shot("more_progress_light")
    }

    @Test fun lookSheetChangesAndRemembersTheTextSizeAndLineSpacing() {
        show(sheet = PlayerSheet.Look)
        var saved: ReadLook? = null
        window.onLook = { saved = it }
        rule.onNodeWithContentDescription("Cỡ chữ 24").assertIsDisplayed().performClick()
        assertEquals(24, window.look.size)
        rule.onNodeWithContentDescription("Giãn dòng 1,9").assertIsDisplayed().performClick()
        assertEquals(1.9, window.look.leading, 0.0)
        assertEquals(ReadLook(24, 1.9), saved)
        shot("look_light")
    }

    @Test fun moreSheetOffersTheTextLookOnlyWhereThereIsTextToRead() {
        show(sheet = PlayerSheet.More)
        rule.onNodeWithContentDescription("Cỡ chữ và giãn dòng").assertIsDisplayed()
    }

    private val readingList get() = hasScrollAction() and hasAnyAncestor(hasTestTag("read_along_text"))

    @Test fun readingShowsTheHintAndTouchingATextListensFromThere() {
        show(reading = true, base = FakeNowPlayingModel.demoState().copy(voices = listOf(PlayerVoice("v", "Giọng"))))
        rule.onNode(readingList).performScrollToNode(hasTestTag("read_hint"))
        rule.onNodeWithTag("read_hint").assertIsDisplayed()
        rule.onNodeWithText(ReadHint.TAP).assertIsDisplayed()
        rule.onNodeWithTag("paragraph_0").performClick()
        assertTrue("nghe từ chữ vừa chạm: ${model.actions}", model.actions.any { it.startsWith("seek:") })
        assertTrue(window.look.tapped)
        rule.waitForIdle()
        rule.onNodeWithTag("read_hint").assertDoesNotExist()
    }

    @Test fun theEndOfTheTextOffersTheNextChapter() {
        show(reading = true)
        rule.onNode(readingList).performScrollToNode(hasTestTag("read_next_chapter"))
        rule.onNodeWithTag("read_next_chapter").assertIsDisplayed().performClick()
        assertTrue(model.actions.any { it.startsWith("jump:2") })
    }

    private fun prepareScene(): NowPlayingState = FakeNowPlayingModel.demoState().copy(
        chapterId = 1, voiceId = "vieneu:a", voices = listOf(PlayerVoice("vieneu:a", "Giọng A")),
        chapters = listOf(PlayerChapter(1, "Chương 1", 600_000), PlayerChapter(2, "Chương 2", 0, "t/2.txt"), PlayerChapter(3, "Chương 3", 0, "t/3.txt")),
    )

    @Test fun voiceSheetOffersToPrepareTheNextChaptersAndStopsWhenAsked() {
        val source = FakePrepareSource(plan = PreparePlan(2, 2, 1800, 1500))
        val prepare = PrepareState(source, CoroutineScope(Dispatchers.Unconfined))
        show(sheet = PlayerSheet.Voice, base = prepareScene(), prepare = prepare)
        rule.onNodeWithText(PrepareText.INTRO).assertIsDisplayed()
        rule.onNodeWithText("30 phút nghe · máy cần khoảng 25 phút.").assertIsDisplayed()
        rule.onNodeWithText("Làm trước 2 chương tới").assertIsDisplayed()
        rule.onNodeWithText("Chỉ khi đang sạc").assertIsDisplayed()
        shot("prepare_light")
        rule.onNodeWithText("Làm trước 2 chương tới").performClick()
        rule.waitForIdle()
        assertEquals(listOf("start vieneu:a [2, 3] 2 chương tới charging=true"), source.calls.filter { it.startsWith("start") })
        rule.onNodeWithText("Dừng làm trước").assertIsDisplayed().performClick()
        rule.waitForIdle()
        assertTrue(source.calls.contains("cancel"))
    }

    @Test fun voiceSheetShowsWhyPreparingWaitsAndWhyItFailed() {
        val source = FakePrepareSource(status = PrepareStatus("running", "vieneu:a", "2 chương tới", bookId = FakeNowPlayingModel.demoState().bookId,
            chapters = listOf(PreparedChapter(2, "Chương 2", 10, 4, false), PreparedChapter(3, "Chương 3", 10, 0, false)), waitingFor = "charging"))
        val prepare = PrepareState(source, CoroutineScope(Dispatchers.Unconfined))
        show(sheet = PlayerSheet.Voice, base = prepareScene(), prepare = prepare)
        rule.onNodeWithText("Đã sẵn sàng 0/2 chương · chờ cắm sạc").assertIsDisplayed()
        shot("prepare_waiting_light")
    }

    @Test fun deviceVoicesHaveNothingToPrepare() {
        val prepare = PrepareState(FakePrepareSource(), CoroutineScope(Dispatchers.Unconfined))
        show(sheet = PlayerSheet.Voice, base = prepareScene().copy(voiceId = "device:x"), prepare = prepare)
        rule.onNodeWithTag("prepare_block").assertDoesNotExist()
    }

    @Test fun lastChapterOffersNothingToPrepare() {
        val prepare = PrepareState(FakePrepareSource(), CoroutineScope(Dispatchers.Unconfined))
        show(sheet = PlayerSheet.Voice, base = prepareScene().copy(chapterId = 3), prepare = prepare)
        rule.onNodeWithTag("prepare_block").assertDoesNotExist()
    }

    companion object {
        const val LONG_CHAPTER = "Chương mười hai · Người lữ khách trở về qua những con đường mùa thu"
        const val LONG_BOOK = "Những ngày gió hát bên kia ngọn đồi và câu chuyện chưa kể"
    }
}
