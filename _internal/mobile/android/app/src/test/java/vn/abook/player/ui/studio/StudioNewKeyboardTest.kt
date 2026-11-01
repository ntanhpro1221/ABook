package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** "Sách mới" bước Nguồn trong cửa sổ thấp (như khi bàn phím mở): "Chưa có tệp nào" nằm ngay trên nút "Tiếp", thấy trọn, không bị danh sách cuộn cắt. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h440dp-xxhdpi")
class StudioNewKeyboardTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun theReasonTheNextButtonIsOffStaysVisibleAboveItOnAShortWindow() {
        val hub = StudioHub(FakeStudioSource(listOf(studioBook())), CoroutineScope(Dispatchers.Unconfined))
        val state = StudioNewState(hub.session(""), "Tải lên")
        rule.setContent { AbookTheme(true) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { StudioNewScreen(state, {}, {}, true) } } }
        rule.waitForIdle()
        rule.onNodeWithTag("studio_new_none").assertIsDisplayed()
        val none = rule.onNodeWithTag("studio_new_none").getUnclippedBoundsInRoot()
        val next = rule.onNodeWithTag("studio_new_next").getUnclippedBoundsInRoot()
        val list = rule.onNodeWithTag("studio_new_source").getUnclippedBoundsInRoot()
        assertTrue("dòng trạng thái ($none) nằm trên nút Tiếp ($next)", none.bottom <= next.top)
        assertTrue("danh sách ($list) không đè dòng trạng thái ($none)", list.bottom <= none.top)
        rule.onRoot().captureRoboImage("src/test/snapshots/studio_new_short_dark.png")
    }
}
