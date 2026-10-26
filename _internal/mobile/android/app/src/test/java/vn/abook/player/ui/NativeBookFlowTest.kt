package vn.abook.player.ui

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.addbook.*
import vn.abook.player.ui.data.*
import vn.abook.player.ui.editbook.*
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme
import java.io.File

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NativeBookFlowTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val book = ListenBook("b", "Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", chaptersTotal = 2, textOnly = true)
    private val snapshot = EditSnapshot("b", book.title, book.author, listOf(EditChapter(1, "Chương 1"), EditChapter(2, "Chương 2")))

    @Test fun oneFileAutomaticallyPreviewsAfterTheSlideAndOpensBookAfterAdding() {
        lateinit var queue: ImportQueue
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                val shell = remember { ShellState(scope) }
                val player = remember { PlayerRepo(FakePlaybackCore(playerSnapshot(chapter = null)), scope, Dispatchers.Unconfined, { null }, { null }) }
                val source = remember { object : ImportSource by FakeImportSource(ImportPreview(book.title, chapters = listOf(ImportChapter(1, "Chương 1")))) {
                    override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices) = "b" to false
                } }
                queue = remember { ImportQueue(source, scope) }
                AppShell(shell, LibraryState.Ready(listOf(book)), player, CoverLoader(), imports = queue, autoPick = true)
            }
        }
        rule.runOnIdle { queue.enqueue(listOf("Truyện.epub")) }
        rule.onNodeWithTag("add_book").performClick()
        rule.onNodeWithTag("import_review_screen").assertIsDisplayed()
        rule.onNodeWithTag("confirm_import").performClick()
        rule.onNodeWithTag("book_screen").assertIsDisplayed()
        back()
        rule.onNodeWithTag("add_book_screen").assertIsDisplayed()
        rule.onNodeWithTag("book_screen").assertDoesNotExist()
    }

    @Test fun libraryAddAndNestedChapterBackUseTheRealShellStack() {
        lateinit var shell: ShellState
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                val player = remember { PlayerRepo(FakePlaybackCore(playerSnapshot(chapter = null)), scope, Dispatchers.Unconfined, { null }, { null }) }
                val imports = remember { ImportQueue(FakeImportSource(ImportPreview("Sách", chapters = emptyList())), scope) }
                val editors = remember { EditBooks(FakeEditSource(snapshot), scope) }
                AppShell(shell, LibraryState.Ready(listOf(book)), player, CoverLoader(), imports = imports, editors = editors)
            }
        }
        rule.onNodeWithTag("add_book").performClick()
        rule.onNodeWithTag("add_book_screen").assertIsDisplayed()
        back()
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
        rule.onNodeWithTag("book_cell").performClick()
        rule.onNodeWithTag("edit_book").performClick()
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("edit_chapter_1"))
        rule.onNodeWithTag("edit_chapter_1").performClick()
        rule.onNodeWithTag("chapter_title").performTextReplacement("Khách qua sông")
        rule.runOnIdle { assertEquals(3, shell.nav.stack.size) }
        back()
        rule.onNodeWithTag("edit_book_screen").assertIsDisplayed()
        rule.runOnIdle { assertEquals(2, shell.nav.stack.size) }
        rule.onNodeWithText("Khách qua sông").assertIsDisplayed()
        back()
        rule.onNodeWithTag("book_screen").assertIsDisplayed()
        back()
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
    }

    @Test fun chapterLight() = chapter(false, "edit_chapter_light")
    @Test fun chapterDark() = chapter(true, "edit_chapter_dark")
    private fun chapter(dark: Boolean, name: String) {
        rule.setContent { AbookTheme(dark) {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", FakeEditSource(snapshot), scope) }
            EditChapterRoute(editor, 1) {}
        } }
        rule.onNodeWithTag("chapter_title").assertIsDisplayed()
        shot(name)
    }

    @Test fun footnotesLight() = footnotes(false, "add_footnotes_light")
    @Test fun footnotesDark() = footnotes(true, "add_footnotes_dark")
    private fun footnotes(dark: Boolean, name: String) {
        val preview = ImportPreview("Chuyến phà cuối ngày", chapters = listOf(ImportChapter(1, "Chương 1")),
            footnoteCount = 12, footnoteMarks = 12, footnoteExample = "hàng cây²\nLời chú về cây bên sông.")
        var state by mutableStateOf(ImportState(preview = preview, choices = ImportLogic.defaults(preview)))
        rule.setContent { AbookTheme(dark) { ImportReviewScreen(state, {}, {}, { state = state.copy(choices = it(state.choices)) }, {}, {}) } }
        rule.onNodeWithText("Bỏ số gọi").performClick()
        assertTrue(state.choices.hideMarks)
        rule.onNodeWithText("Bỏ số gọi").performClick()
        assertFalse(state.choices.hideMarks)
        shot(name)
    }

    @Test fun cropLight() = crop(false, "edit_crop_light")
    @Test fun cropDark() = crop(true, "edit_crop_dark")
    private fun crop(dark: Boolean, name: String) {
        val image = File(rule.activity.cacheDir, "$name.png")
        val bitmap = Bitmap.createBitmap(960, 1440, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply { color = Color.rgb(70, 90, 75) }
        canvas.drawRect(0f, 0f, 960f, 1440f, paint)
        paint.color = Color.rgb(230, 202, 140)
        canvas.drawCircle(480f, 500f, 250f, paint)
        paint.color = Color.rgb(40, 50, 45)
        canvas.drawRect(0f, 1050f, 960f, 1440f, paint)
        assertEquals(Color.rgb(230, 202, 140), bitmap.getPixel(480, 500))
        image.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
        rule.setContent { AbookTheme(dark) {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", FakeEditSource(snapshot), scope) }
            CoverCropRoute(editor, Uri.fromFile(image).toString()) {}
        } }
        rule.waitUntil(10_000) { rule.onAllNodesWithTag("cover_crop_canvas").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("cover_crop_canvas").assertIsDisplayed()
        rule.onNodeWithText("Phóng to").performClick()
        rule.onNodeWithText("Đặt lại").performClick()
        shot(name)
        runBlocking {
            val decoded = CoverCrop.load(rule.activity, Uri.fromFile(image), 600)
            assertTrue(maxOf(decoded.width, decoded.height) <= 600)
            assertEquals(Color.rgb(230, 202, 140), decoded.getPixel(decoded.width / 2, decoded.height * 500 / 1440))
            val bytes = CoverCrop.jpeg(decoded, CropChoice(2f, 1f, -1f))
            val cropped = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            assertEquals(1.5f, cropped.height.toFloat() / cropped.width, 0.02f)
        }
    }

    private fun shot(name: String) {
        rule.mainClock.advanceTimeBy(64)
        rule.waitForIdle()
        rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }

    private fun back() {
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
    }
}
