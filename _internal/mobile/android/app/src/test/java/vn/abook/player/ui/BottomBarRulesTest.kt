package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import java.io.File

/**
 * Nội dung nằm TRÊN thanh nút đáy, không bao giờ dưới nó; bàn phím mở thì cả ô nhập lẫn nút nằm trên bàn phím (soát điện thoại thật 02-11: "Chưa có tệp nào" bị nút "Tiếp" che khi
 * bàn phím mở). Hai chỗ chung lo việc ấy: [vn.abook.player.ui.addbook.BookForm] (màn con có chân) và bảng trượt ([vn.abook.player.ui.components.SheetLayer]) đều `imePadding()`.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h420dp-xxhdpi")
class BottomBarRulesTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun theFormContentEndsWhereTheFooterBeginsEvenOnAShortWindow() {
        rule.setContent {
            AbookTheme {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    BookForm("Tên", {}, "form", footer = { PrimaryButton("Tiếp", {}, Modifier.fillMaxWidth().testTag("footer_button")) }) {
                        Box(Modifier.fillMaxSize().testTag("form_content"))
                    }
                }
            }
        }
        rule.waitForIdle()
        val content = rule.onNodeWithTag("form_content").getUnclippedBoundsInRoot()
        val button = rule.onNodeWithTag("footer_button").getUnclippedBoundsInRoot()
        assertTrue("nội dung ($content) đè lên nút đáy ($button)", content.bottom <= button.top)
        assertTrue("nút đáy phải nằm trong cửa sổ: $button", button.bottom <= 420.dp)
    }

    private val root = File("src/main/java/vn/abook/player/ui")

    @Test fun theSharedBottomContainersLiftThemselvesAboveTheKeyboard() {
        for (path in listOf("addbook/BookForms.kt", "components/Sheet.kt")) {
            val text = File(root, path).readText()
            assertTrue("$path mất imePadding(): màn / bảng có ô nhập sẽ bị bàn phím che", Regex("""(?m)^[^/*\n]*\.imePadding\(\)""").containsMatchIn(text))
        }
    }

    /** Màn con có ô nhập mà KHÔNG dùng BookForm thì phải tự imePadding(); không thì bàn phím che nó. */
    @Test fun everyScreenWithATextFieldEitherUsesTheFormOrLiftsItselfAboveTheKeyboard() {
        val offenders = root.walkTopDown().filter { it.isFile && it.extension == "kt" }.filter { file ->
            val text = file.readText()
            // LibraryChrome: ô tìm kiếm ở ĐẦU Thư viện (trên bàn phím sẵn), không có chân. *Sheets.kt: nội dung bảng trượt, SheetLayer đã imePadding.
            file.name != "LibraryChrome.kt" && !file.name.endsWith("Sheets.kt") && Regex("""\b(BookField|BasicTextField)\(""").containsMatchIn(text) && file.name != "BookForms.kt" &&
                !text.contains("BookForm(") && !text.contains("imePadding()") && !text.contains("sheets.show") && !text.contains("SheetHost")
        }.map { it.name }.toList()
        assertTrue("ô nhập không nằm trong BookForm / bảng trượt / imePadding: $offenders", offenders.isEmpty())
    }
}
