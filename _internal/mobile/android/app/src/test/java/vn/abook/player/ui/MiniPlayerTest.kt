package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertHeightIsEqualTo
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.nowplaying.NowPlayingPart
import vn.abook.player.ui.player.MiniPlayer
import vn.abook.player.ui.player.MiniPlayerHeight
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Thanh phát nhỏ: ảnh chụp phát / dừng sáng / tối, bấm thật, móc phần tử chung. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class MiniPlayerTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val state = PlayerState(
        bookId = "b1", bookTitle = "Dế Mèn phiêu lưu ký", chapterId = 4, chapterTitle = "Chương 4: Bài học đầu tiên của chú Dế Mèn",
        playing = true, durationMs = 600_000,
    )
    private var toggled = 0
    private var opened = 0
    private val requested = HashSet<NowPlayingPart>()
    private var position = 150_000L

    private fun show(player: PlayerState, dark: Boolean = false, shared: @Composable (NowPlayingPart) -> Modifier = { Modifier }) {
        rule.setContent {
            AbookTheme(dark) {
                Column(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    Box(Modifier.weight(1f).fillMaxWidth())
                    MiniPlayer(player, { position }, CoverLoader(1 shl 20), { toggled++ }, { opened++ }, sharedModifier = shared)
                    Box(Modifier.fillMaxWidth().height(56.dp).background(Abook.colors.panel), contentAlignment = Alignment.Center) {}
                }
            }
        }
    }

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")

    @Test
    fun playingLight() {
        show(state)
        rule.onNodeWithTag("mini_player").assertIsDisplayed().assertHeightIsAtLeast(MiniPlayerHeight)
        shot("mini_playing_light")
    }

    @Test
    fun shortTitleKeepsMinimumHeight() {
        show(state.copy(chapterTitle = "Chương 4", bookTitle = "Dế Mèn"))
        rule.onNodeWithTag("mini_player").assertHeightIsEqualTo(MiniPlayerHeight)
    }

    @Test
    fun longTitleWrapsInsteadOfCutting() {
        val long = "Chương 128: Trận chiến cuối cùng trên đỉnh núi tuyết, nơi mọi lời thề cũ được nhắc lại lần nữa"
        show(state.copy(chapterTitle = long))
        rule.onNodeWithText(long).assertIsDisplayed()
        val bar = rule.onNodeWithTag("mini_player").fetchSemanticsNode().size.height
        val min = with(rule.density) { MiniPlayerHeight.roundToPx() }
        assertTrue("thanh phải cao thêm để chứa tên dài: $bar <= $min", bar > min)
        shot("mini_long_title_light")
    }

    @Test
    fun playingDark() {
        show(state, dark = true)
        shot("mini_playing_dark")
    }

    @Test
    fun pausedLight() {
        show(state.copy(playing = false))
        shot("mini_paused_light")
    }

    @Test
    fun pausedDark() {
        show(state.copy(playing = false), dark = true)
        shot("mini_paused_dark")
    }

    @Test
    fun shortTitlesAndNoChapterFallBackToTheBookTitle() {
        show(PlayerState(bookId = "b2", bookTitle = "Chí Phèo", chapterId = 1, chapterTitle = "", playing = false, durationMs = 0))
        rule.onNodeWithTag("mini_open").assertIsDisplayed()
        shot("mini_short_light")
    }

    @Test
    fun theButtonTogglesAndTheRestOpensTheFullPlayer() {
        show(state)
        rule.onNodeWithTag("mini_play").performClick()
        assertEquals(1, toggled)
        assertEquals(0, opened)
        rule.onNodeWithTag("mini_open").performClick()
        assertEquals(1, opened)
        assertEquals(1, toggled)
    }

    @Test
    fun theButtonSaysWhatItWillDo() {
        show(state)
        rule.onNodeWithContentDescription("Tạm dừng").assertExists()
    }

    @Test
    fun everyPartAsksTheSharedElementHook() {
        show(state, shared = { part -> requested += part; Modifier.testTag("shared_${part.name}") })
        // Khung chung (Container) do cửa sổ đặt lên cả thanh; bốn phần còn lại là việc của thanh.
        val parts = NowPlayingPart.entries - NowPlayingPart.Container
        for (part in parts) rule.onNodeWithTag("shared_${part.name}", useUnmergedTree = true).assertExists()
        assertTrue(requested.containsAll(parts))
    }
}
