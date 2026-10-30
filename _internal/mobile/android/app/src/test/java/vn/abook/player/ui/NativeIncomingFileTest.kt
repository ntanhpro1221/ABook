package vn.abook.player.ui

import android.content.ContentProvider
import android.content.ComponentName
import android.content.ContentValues
import android.content.Intent
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowContentResolver
import org.robolectric.shadows.ShadowToast
import vn.abook.player.AbookApplication
import vn.abook.player.IncomingFile
import java.io.File

/** "Mở bằng" / chia sẻ file tới app (bản -PnativeUi): NativeActivity đưa file vào hàng nhập sách và mở "Thêm sách", như file chọn từ bộ chọn. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NativeIncomingFileTest {
    @get:Rule val rule = createEmptyComposeRule()
    private val app get() = ApplicationProvider.getApplicationContext<AbookApplication>()

    /** Nơi gửi: tên + kiểu nội dung theo đường dẫn của địa chỉ; nội dung là byte vô nghĩa (cuộc thử không đọc sách thật). */
    class Sender : ContentProvider() {
        private val types = mapOf(
            "Truyen.abook" to "application/vnd.ngdtuanh.abook+zip",
            "la.bin" to "application/octet-stream",
        )
        override fun onCreate() = true
        override fun getType(uri: Uri): String? = types[uri.lastPathSegment]
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor =
            MatrixCursor(arrayOf(OpenableColumns.DISPLAY_NAME)).apply { addRow(arrayOf(uri.lastPathSegment)) }
        override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
            val file = File(requireNotNull(context).cacheDir, uri.lastPathSegment!!)
            file.writeBytes(ByteArray(64) { it.toByte() })
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
        }
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0
    }

    private fun sender(): String {
        val provider = Sender().also { it.attachInfo(app, ProviderInfo().apply { authority = "incoming-test" }) }
        ShadowContentResolver.registerProviderInternal("incoming-test", provider)
        return "content://incoming-test/"
    }

    private fun launch(intent: Intent): ActivityScenario<NativeActivity> {
        // Bản thường không khai báo NativeActivity trong manifest (chỉ bản -PnativeUi): khai báo cho Robolectric để cả hai bản chạy được test này.
        shadowOf(app.packageManager).addActivityIfNotPresent(ComponentName(app, NativeActivity::class.java))
        return ActivityScenario.launch(intent.setClass(app, NativeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    /**
     * Chờ có giải thích: hết hạn thì báo hàng nhập đang ra sao thay vì chỉ "timeout". Tự bơm vòng lặp chính - việc đọc file chạy ở luồng nền rồi quay về luồng chính qua Looper,
     * mà Robolectric chỉ chạy Looper khi có ai bơm (`waitUntil` của Compose không bơm khi màn đã đứng yên).
     */
    private fun until(what: String, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + 60_000
        while (!condition()) {
            if (System.currentTimeMillis() > end) throw AssertionError("Chưa thấy: $what; hàng nhập = ${app.imports.state.value.items}")
            rule.mainClock.advanceTimeByFrame()
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(10)
        }
    }

    private fun shown(tag: String) = runCatching { rule.onNodeWithTag(tag).assertIsDisplayed() }.isSuccess

    // Không đóng ActivityScenario bằng tay: đóng thì chờ Activity huỷ hẳn, mà vòng nghe máy khác của NativeActivity chạy mãi nên treo cả lượt thử; Robolectric dọn khi hết ca.
    @Test fun anAbookOpenedWithAbookEntersTheImportQueueAndShowsAddBook() {
        val uri = Uri.parse(sender() + "Truyen.abook")
        launch(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.ngdtuanh.abook+zip"))
        until("file vào hàng nhập") { app.imports.state.value.items.isNotEmpty() }
        assertEquals(uri.toString(), app.imports.state.value.items.single().source)
        until("màn Thêm sách") { shown("add_book_screen") }
        until("tên file") { app.imports.state.value.items.single().name == "Truyen.abook" }
    }

    @Test fun anUnknownSharedFileIsRefusedInTheQueueWithTheSameWords() {
        val uri = Uri.parse(sender() + "la.bin")
        launch(Intent(Intent.ACTION_SEND).setType("application/octet-stream").putExtra(Intent.EXTRA_STREAM, uri))
        until("màn Thêm sách") { shown("add_book_screen") }
        val refusal = "Không mở được file. Bạn chọn .abook, .abookproj, EPUB, Word, PDF hoặc TXT; chưa nhận loại file này."
        until("lời từ chối trong hàng") { app.imports.state.value.items.singleOrNull()?.problem == refusal }
        until("lời từ chối trên màn") { runCatching { rule.onNodeWithText(refusal).assertIsDisplayed() }.isSuccess }
    }

    @Test fun aSecondFileSentWhileOpenJoinsTheQueueWithoutAnotherScreen() {
        val base = sender()
        val first = Uri.parse(base + "Truyen.abook")
        val scenario = launch(Intent(Intent.ACTION_VIEW).setDataAndType(first, "application/vnd.ngdtuanh.abook+zip"))
        until("màn Thêm sách") { shown("add_book_screen") }
        val second = Uri.parse(base + "la.bin")
        scenario.onActivity { activity ->
            val method = NativeActivity::class.java.getDeclaredMethod("onNewIntent", Intent::class.java).apply { isAccessible = true }
            method.invoke(activity, Intent(Intent.ACTION_SEND).setType("application/octet-stream").putExtra(Intent.EXTRA_STREAM, second))
        }
        until("file thứ hai vào hàng") { app.imports.state.value.items.size == 2 }
        assertEquals(listOf(first.toString(), second.toString()), app.imports.state.value.items.map { it.source })
        assertTrue(shown("add_book_screen"))
    }

    @Test fun sharedPlainTextIsToldNotSilentlyDropped() {
        launch(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, "https://example.com"))
        assertEquals(IncomingFile.TEXT_ONLY, ShadowToast.getTextOfLatestToast())
        assertTrue(app.imports.state.value.items.isEmpty())
    }
}
