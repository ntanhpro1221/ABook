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
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertTrue
import java.io.File
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

    /**
     * Dán chữ nhiều dòng trong cửa sổ thấp (bàn phím mở): ô nhập cao thêm, "Thêm chữ này" đứng dưới ô. Nó phải thấy TRỌN và nằm trên chân trang ghim
     * ("Chưa có tệp nào" + Tiếp), không bị chân trang đè (soát điện thoại thật 02-11).
     */
    @Test fun theAddTextButtonStaysAboveThePinnedFooterWhenThePastedTextRunsLong() {
        val hub = StudioHub(FakeStudioSource(listOf(studioBook())), CoroutineScope(Dispatchers.Unconfined))
        val state = StudioNewState(hub.session(""), "Tải lên")
        rule.setContent { AbookTheme(true) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { StudioNewScreen(state, {}, {}, true) } } }
        rule.waitForIdle()
        rule.onNodeWithTag("studio_new_paste").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("studio_new_paste_field").performClick()
        rule.onNodeWithTag("studio_new_paste_field").performTextInput("Dòng một của đoạn dán.\nDòng hai của đoạn dán.\nDòng ba của đoạn dán.\nDòng bốn của đoạn dán.")
        rule.waitForIdle()
        rule.onNodeWithTag("studio_new_paste_add").assertIsDisplayed()
        val add = rule.onNodeWithTag("studio_new_paste_add").getUnclippedBoundsInRoot()
        val none = rule.onNodeWithTag("studio_new_none").getUnclippedBoundsInRoot()
        val next = rule.onNodeWithTag("studio_new_next").getUnclippedBoundsInRoot()
        assertTrue("nút Thêm chữ này ($add) nằm trên dòng trạng thái ($none) và nút Tiếp ($next)", add.bottom <= none.top && add.bottom <= next.top)
        rule.onRoot().captureRoboImage("src/test/snapshots/studio_new_paste_long_dark.png")
    }

    /** Ô nhập có việc nằm dưới nó (BookField) phải đứng trong [FieldGroup], nếu không bàn phím + chân trang ghim che việc ấy: quét nguồn. */
    @Test fun everyScreenWithAFieldAndAnActionBelowItWrapsThemInAFieldGroup() {
        val root = File("src/main/java/vn/abook/player/ui")
        val bad = root.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "BookForms.kt" }
            .filter { f -> val t = f.readText(); t.contains("BookField(") && !Regex("""FieldGroup\s*[({]""").containsMatchIn(t) }
            .map { it.name }.toList()
        // Màn có ô nhập mà KHÔNG có nút nào ngay dưới ô: AddBookScreen (tên rồi dòng thông tin), PairScreen (việc ghép nằm ở chân trang), CoverSearchScreen (nút Tìm nằm trong ô).
        val alone = setOf("AddBookScreen.kt", "PairScreen.kt", "CoverSearchScreen.kt")
        assertTrue("file có BookField mà không có FieldGroup: ${bad - alone}", (bad - alone).isEmpty())
    }
}
