package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.addbook.AddBookScreen
import vn.abook.player.ui.addbook.ImportChapter
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportLogic
import vn.abook.player.ui.addbook.ImportPreview
import vn.abook.player.ui.addbook.ImportReviewScreen
import vn.abook.player.ui.addbook.ImportStage
import vn.abook.player.ui.addbook.ImportState
import vn.abook.player.ui.addbook.PackageReview
import vn.abook.player.ui.addbook.PackageReviewScreen
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.editbook.EditChapter
import vn.abook.player.ui.editbook.EditBookScreen
import vn.abook.player.ui.editbook.EditLogic
import vn.abook.player.ui.editbook.EditSnapshot
import vn.abook.player.ui.editbook.EditState
import vn.abook.player.ui.player.MiniPlayer
import vn.abook.player.ui.shell.TabBar
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * Hộp chạm của mọi việc bám đáy màn (lỗi điện thoại thật 05-11, OPPO cử chỉ ẩn vạch: inset đáy 0, "Thay bằng file này" và nhãn tab đáy vẽ ở 36 dp trên mép - bấm không trúng, app bị đẩy ra nền):
 * cao >= 48 dp, chữ con nằm gọn trong hộp, hộp nằm trên vạch cử chỉ 24 dp. Cửa sổ Robolectric không có thanh điều hướng = đúng ca inset 0 của máy ấy.
 * Màn nào có chân / thanh đáy phải vào danh sách dưới đây.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BottomTouchBoxTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val report = StringBuilder()
    private val problems = ArrayList<String>()

    /** Dựng MỘT màn rồi soát; đếm nút để máy dò không "xanh vì mù". */
    private fun check(screen: String, minimum: Int = 1, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
        rule.waitForIdle()
        val result = rule.touchBoxProblems(screen)
        println("TOUCHBOX $screen: ${result.checked} nút bấm được")
        assertTrue("$screen: chỉ thấy ${result.checked} nút (< $minimum), máy dò mù", result.checked >= minimum)
        assertTrue("Hộp chạm sai:\n" + result.problems.joinToString("\n"), result.problems.isEmpty())
    }

    private val chapters = listOf(ImportChapter(1, "Lời nói đầu", included = false, note = "Ngắn"), ImportChapter(2, "Chương 1"))
    private val preview = ImportPreview("Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", chapters)
    private val queue = ImportState(items = listOf(
        ImportItem(1, "a", "Chuyến phà cuối ngày.epub", stage = ImportStage.Added, bookId = "a"),
        ImportItem(3, "c", "Những ngày thơ ấu.docx", stage = ImportStage.Review),
        ImportItem(5, "e", "Sách tải dở.epub", stage = ImportStage.Error, problem = "File EPUB hỏng."),
    ))
    private val edit = EditSnapshot("b", "Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", listOf(EditChapter(1, "Chương 1")), sendable = true, pending = 2)

    @Test fun addBookEmpty() = check("Thêm sách (trống)", 2) { AddBookScreen(ImportState(), {}, {}, {}, {}, {}, {}) }

    @Test fun addBookQueue() = check("Thêm sách (hàng đợi)", 3) { AddBookScreen(queue, {}, {}, {}, {}, {}, {}) }

    @Test fun addBookAskingBeforeLeaving() = check("Thêm sách (hỏi trước khi đóng)", 2) { AddBookScreen(queue, {}, {}, {}, {}, {}, {}, leaving = 2) }

    @Test fun packageReviewFooter() = check("Mở sách (file có bản thu khác)", 3) {
        PackageReviewScreen(ImportState(packageReview = PackageReview("b", "Your Story", "Your Story 2", "older")), {}, {}, {})
    }

    @Test fun importReviewFooter() = check("Xem sách thêm", 2) {
        ImportReviewScreen(ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview)), {}, {}, {}, {}, {})
    }

    @Test fun editBook() = check("Sửa sách", 2) {
        EditBookScreen(EditState(edit, EditLogic.draft(edit), loading = false), CoverLoader(), {}, {}, {}, {}, {}, {})
    }

    @Test fun tabBar() = check("Thanh tab đáy", 3) {
        val tabs = remember { TabState(CoroutineScope(Dispatchers.Unconfined)) }
        Column(Modifier.fillMaxSize()) { Box(Modifier.weight(1f)); TabBar(tabs) }
    }

    @Test fun miniPlayerOverTabBar() = check("Thanh phát nhỏ trên thanh tab", 5) {
        val tabs = remember { TabState(CoroutineScope(Dispatchers.Unconfined)) }
        val playing = PlayerState(bookId = "b1", bookTitle = "Dế Mèn phiêu lưu ký", chapterId = 4, chapterTitle = "Chương 4", playing = true, durationMs = 600_000)
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f))
            MiniPlayer(playing, { 150_000L }, CoverLoader(1 shl 20), {}, {})
            TabBar(tabs)
        }
    }

    /** Máy dò không "xanh vì mù": đòi vạch cử chỉ cao hơn chân màn thật (60 dp) thì phải bắt được "Thay bằng file này", và đòi hộp cao 200 dp thì bắt hết. */
    @Test fun theDetectorFlagsAFooterInsideTheStrip() {
        rule.setContent { AbookTheme { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { PackageReviewScreen(ImportState(packageReview = PackageReview("b", "A", "B", "older")), {}, {}, {}) } } }
        rule.waitForIdle()
        val strip = rule.touchBoxProblems("dải 60 dp", gestureBarDp = 60f)
        assertTrue("dải 60 dp phải bắt được chân màn: ${strip.problems}", strip.problems.any { "vạch cử chỉ" in it })
        val tall = rule.touchBoxProblems("hộp 200 dp", minDp = 200f)
        assertTrue("hộp 200 dp phải bắt được mọi nút", tall.problems.size >= tall.checked)
    }
}
