package vn.abook.player.ui.pip

import android.content.Context
import android.util.Rational
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.Playback
import vn.abook.player.PlayerWidget

/**
 * Params của cửa sổ nhỏ (PiP) dựng từ trạng thái phát: tỉ lệ bìa 2:3, ba nút đúng thứ tự + nhãn, nút giữa đổi Phát / Tạm dừng, tự vào PiP chỉ khi có sách mở
 * VÀ công tắc bật, icon vẽ ra thật. Phần thuần ([PipParams.plan]) không cần Android; phần dựng [android.app.PictureInPictureParams] chạy ở Robolectric.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class PipParamsTest {
    private val context: Context get() = ApplicationProvider.getApplicationContext()

    @Test
    fun theThreeButtonsAreBackToggleForwardWithTheLabelsOfThePlayer() {
        val plan = PipParams.plan(playing = false, hasBook = true, switchOn = true)
        assertEquals(listOf(PipKind.Back, PipKind.Toggle, PipKind.Forward), plan.buttons.map { it.kind })
        assertEquals(listOf("Lùi 15 giây", "Phát", "Tới 15 giây"), plan.buttons.map { it.label })
        assertEquals("số 15 là của lõi, không viết cứng", 15, Playback.SKIP_SECONDS)
    }

    @Test
    fun theMiddleButtonFollowsThePlayState() {
        assertEquals("Phát", PipParams.plan(playing = false, hasBook = true, switchOn = true).buttons[1].label)
        assertEquals("Tạm dừng", PipParams.plan(playing = true, hasBook = true, switchOn = true).buttons[1].label)
    }

    @Test
    fun theButtonsGoTheSameWayAsTheWidgetButtons() {
        val actions = PipParams.plan(playing = true, hasBook = true, switchOn = true).buttons.map { it.action }
        assertEquals(listOf(PlayerWidget.ACTION_BACK, PlayerWidget.ACTION_TOGGLE, PlayerWidget.ACTION_FORWARD), actions)
    }

    @Test
    fun noBookMeansNoButtonsAndNoAutoEnter() {
        val plan = PipParams.plan(playing = false, hasBook = false, switchOn = true)
        assertTrue(plan.buttons.isEmpty())
        assertFalse(plan.autoEnter)
    }

    @Test
    fun autoEnterNeedsABookAndTheSwitch() {
        assertTrue(PipParams.autoEnter(hasBook = true, switchOn = true))
        assertFalse(PipParams.autoEnter(hasBook = true, switchOn = false))
        assertFalse(PipParams.autoEnter(hasBook = false, switchOn = true))
        // Đang phát hay tạm dừng đều được, miễn có sách mở.
        assertTrue(PipParams.plan(playing = false, hasBook = true, switchOn = true).autoEnter)
        assertTrue(PipParams.plan(playing = true, hasBook = true, switchOn = true).autoEnter)
    }

    @Test
    fun builtParamsCarryTheCoverRatioTheActionsAndAutoEnter() {
        val params = PipParams.build(context, PipParams.plan(playing = true, hasBook = true, switchOn = true))
        assertEquals(Rational(2, 3), params.aspectRatio)
        assertEquals(listOf("Lùi 15 giây", "Tạm dừng", "Tới 15 giây"), params.actions.map { it.title.toString() })
        assertEquals(params.actions.map { it.title.toString() }, params.actions.map { it.contentDescription.toString() })
        val sent = params.actions.map { shadowOf(it.actionIntent) }
        assertTrue(sent.all { it.isBroadcastIntent })
        assertEquals(listOf(PlayerWidget.ACTION_BACK, PlayerWidget.ACTION_TOGGLE, PlayerWidget.ACTION_FORWARD), sent.map { it.savedIntent.action })
        assertTrue(params.isAutoEnterEnabled)
    }

    @Test
    fun autoEnterIsOffInTheParamsWhenTheSwitchIsOff() {
        assertFalse(PipParams.build(context, PipParams.plan(playing = true, hasBook = true, switchOn = false)).isAutoEnterEnabled)
        assertFalse(PipParams.build(context, PipParams.plan(playing = true, hasBook = false, switchOn = true)).isAutoEnterEnabled)
    }

    @Test
    fun theToggleActionSwapsWithThePlayState() {
        val paused = PipParams.build(context, PipParams.plan(playing = false, hasBook = true, switchOn = true))
        val playing = PipParams.build(context, PipParams.plan(playing = true, hasBook = true, switchOn = true))
        assertEquals("Phát", paused.actions[1].title.toString())
        assertEquals("Tạm dừng", playing.actions[1].title.toString())
        // Cùng lệnh phát sóng (bật / tắt) - việc đổi nhãn không đổi đường đi.
        assertEquals(paused.actions[1].actionIntent, playing.actions[1].actionIntent)
    }

    @Test
    fun everyIconHasInkAndPlayDiffersFromPause() {
        val cases = listOf(
            Triple(PipKind.Back, false, "back"), Triple(PipKind.Forward, false, "forward"),
            Triple(PipKind.Toggle, false, "play"), Triple(PipKind.Toggle, true, "pause"),
        )
        val inked = cases.map { (kind, playing, name) ->
            val bitmap = PipIcons.bitmap(context, kind, playing)
            val side = (24 * context.resources.displayMetrics.density).toInt()
            assertEquals("$name: ô 24 dp", side, bitmap.width)
            val pixels = IntArray(bitmap.width * bitmap.height).also { bitmap.getPixels(it, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height) }
            assertTrue("$name phải có mực", pixels.any { (it ushr 24) > 0 })
            pixels.toList()
        }
        assertTrue("phát và dừng là hai hình khác nhau", inked[2] != inked[3])
        assertTrue("lùi và tới là hai hình khác nhau", inked[0] != inked[1])
    }

    @Test
    fun pipIsAllowedOnlyOnAndroid8WithTheFeatureAndTheAppOp() {
        assertTrue(PipSupport.allowed(26, hasFeature = true, appOpAllowed = true))
        assertFalse(PipSupport.allowed(25, hasFeature = true, appOpAllowed = true))
        assertFalse(PipSupport.allowed(34, hasFeature = false, appOpAllowed = true))
        assertFalse(PipSupport.allowed(34, hasFeature = true, appOpAllowed = false))
    }
}
