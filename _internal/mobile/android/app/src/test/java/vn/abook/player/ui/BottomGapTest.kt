package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.addbook.AddBookScreen
import vn.abook.player.ui.addbook.ImportChapter
import vn.abook.player.ui.addbook.ImportLogic
import vn.abook.player.ui.addbook.ImportPreview
import vn.abook.player.ui.addbook.ImportReviewScreen
import vn.abook.player.ui.addbook.ImportState
import vn.abook.player.ui.components.LocalBottomCovered
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.breathAbove
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * Máy dò "dải trống cố định ở đáy" (chủ sách 15-11, ảnh OPPO màn Thêm sách: "sao ở dưới đáy cứ có khoảng trống nhất định nhỉ? nhiều view cũng bị như thế").
 * Gốc: các khối bám đáy (chân ghim của màn khung [vn.abook.player.ui.addbook.BookForm], đáy bảng trượt, hàng cuối Đang nghe) cộng khoảng thở của mình LÊN TRÊN chỗ
 * chừa đáy của hệ thống - chân Thêm sách dư 12 dp dưới nút cuối trên mọi máy. Luật chung (components/Insets.kt `bottomBreath`): khoảng dưới thứ cuối cùng =
 * max(chỗ chừa đáy, khoảng thở), không phải tổng. Đo trên inset thật của ba máy ([SystemInsets.kt]): đáy hộp chạm của thứ thấp nhất cách mép đúng chừng ấy.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BottomGapTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun show(insets: BottomInsets, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
        rule.applyBottomInsets(insets)
    }

    /**
     * Khoảng từ đáy thứ thấp nhất đang vẽ tới mép dưới cửa sổ: mọi nút ngữ nghĩa có cỡ (hộp chạm của nút, hàng, chữ), trừ khung chiếm quá nửa chiều cao (màn,
     * danh sách) - khung chạm mép là chuyện của nó, cái cần đo là thứ cuối cùng người dùng thấy / bấm.
     */
    private fun lowest(): Pair<SemanticsNode, SemanticsNode> {
        val root = rule.onRoot(useUnmergedTree = true).fetchSemanticsNode()
        fun all(node: SemanticsNode): List<SemanticsNode> = listOf(node) + node.children.flatMap(::all)
        val height = root.boundsInRoot.height
        return root to all(root).filter { it.size.height > 0 && it.size.width > 0 && it.boundsInRoot.height < height / 2 }.maxBy { it.boundsInRoot.bottom }
    }

    private fun lowestGap(): Float {
        val (root, node) = lowest()
        return with(rule.density) { (root.boundsInRoot.bottom - node.boundsInRoot.bottom).toDp().value }
    }

    /** Thứ thấp nhất (để lời báo lỗi nói nó là gì). */
    private fun lowestNode(): String = lowest().second.let { "nút thấp nhất: ${it.config} ${it.boundsInRoot}" }

    private fun clearance(insets: BottomInsets): Dp = insets.clearance(rule.density.density)

    @Test fun breathMergesWithTheClearanceInsteadOfStackingOnIt() {
        assertEquals(0f, breathAbove(12.dp, 12.dp).value, 0f)
        assertEquals(0f, breathAbove(48.dp, 12.dp).value, 0f)
        assertEquals(4f, breathAbove(12.dp, 16.dp).value, 0f)
        assertEquals(16f, breathAbove(0.dp, 16.dp).value, 0f)
    }

    private fun addBook(insets: BottomInsets) {
        show(insets) { AddBookScreen(ImportState(), {}, {}, {}, {}, {}, {}) }
        // Thứ thấp nhất là hộp chạm 48 dp của "Chọn thư mục TXT": đáy nó chạm đúng chỗ chừa đáy, không dư dải nào (trước 15-11: chỗ chừa đáy + 12 dp).
        val folder = rule.onNodeWithTag("pick_folder").getUnclippedBoundsInRoot()
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        assertEquals("${insets.name}: đáy Chọn thư mục TXT", clearance(insets).value, (root.bottom - folder.bottom).value, 0.5f)
        assertEquals("${insets.name}: khoảng trống đáy, ${lowestNode()}", clearance(insets).value, lowestGap(), 0.5f)
    }

    @Test fun addBookOppo() = addBook(OppoHiddenBar)
    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi") fun addBookGesture() = addBook(EmulatorGesture)
    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi") fun addBookThreeButton() = addBook(EmulatorThreeButton)

    private fun review(insets: BottomInsets) {
        val preview = ImportPreview("Sách thử", "", listOf(ImportChapter(1, "Chương 1"), ImportChapter(2, "Chương 2")))
        val state = ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview))
        show(insets) { ImportReviewScreen(state, {}, {}, {}, {}, {}) }
        // Thứ thấp nhất là nút chính "Thêm vào thư viện".
        assertEquals("${insets.name}: khoảng trống đáy Xem trước, ${lowestNode()}", clearance(insets).value, lowestGap(), 0.5f)
    }

    @Test fun reviewOppo() = review(OppoHiddenBar)
    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi") fun reviewGesture() = review(EmulatorGesture)
    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi") fun reviewThreeButton() = review(EmulatorThreeButton)

    @Test fun aFooterAboveTheShellBarsKeepsItsBreath() {
        // Màn khung nằm trên thanh phát nhỏ / thanh tab (LocalBottomCovered): không có chỗ chừa đáy ở dưới, giữ 12 dp để nút không dính vào thanh.
        show(OppoHiddenBar) {
            CompositionLocalProvider(LocalBottomCovered provides true) { AddBookScreen(ImportState(), {}, {}, {}, {}, {}, {}) }
        }
        val folder = rule.onNodeWithTag("pick_folder").getUnclippedBoundsInRoot()
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        assertEquals(lowestNode(), 12f, (root.bottom - folder.bottom).value, 0.5f)
    }

    private fun sheet(insets: BottomInsets) {
        val host = SheetHost()
        host.show {
            Column(Modifier.fillMaxWidth()) {
                Box(Modifier.fillMaxWidth().height(120.dp))
                TextAction("Xong", {}, "sheet_last", Modifier.fillMaxWidth())
            }
        }
        // Bảng đã mở TRƯỚC khi inset tới: Compose chỉ nghe inset khi đã có ai đọc nó (bảng đóng thì không ai đọc).
        show(insets) { SheetLayer(host) }
        val last = rule.onNodeWithTag("sheet_last").getUnclippedBoundsInRoot()
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        // Dưới hàng cuối: max(chỗ chừa đáy, 16 dp) - không phải tổng hai số (trước 15-11: 16 dp + chỗ chừa đáy).
        val expected = maxOf(clearance(insets), 16.dp).value
        assertEquals("${insets.name}: đáy bảng", expected, (root.bottom - last.bottom).value, 0.5f)
        // Phần cuộn của bảng xuống tới chỗ chừa đáy: khoảng thở nằm TRONG phần cuộn, không phải dải chết dưới nó.
        val scroll = rule.onNodeWithTag("sheet_scroll").getUnclippedBoundsInRoot()
        assertEquals("${insets.name}: đáy phần cuộn", clearance(insets).value, (root.bottom - scroll.bottom).value, 0.5f)
    }

    @Test fun sheetOppo() = sheet(OppoHiddenBar)
    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi") fun sheetGesture() = sheet(EmulatorGesture)
    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi") fun sheetThreeButton() = sheet(EmulatorThreeButton)
}
