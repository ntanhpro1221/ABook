package vn.abook.player.ui.addbook

import android.app.Activity
import android.content.ContentProvider
import android.content.ContentValues
import android.content.Intent
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.TestTime
import java.io.File

/**
 * Chủ sách, 0.4.173: một lần thêm sách hỏng, sau đó (app đã khởi động lại, quyền tạm của hộp chọn file đã hết) bấm "Thử lại" và thẻ hiện
 * nguyên chữ "Permission Denial ... ACTION_OPEN_DOCUMENT". Ở đây nhà cung cấp file ném đúng SecurityException ấy khi mở file:
 * hàng phải nói một câu tiếng Việt, và "Thử lại" phải mở lại hộp chọn file ở chỗ của file cũ.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ExpiredGrantRetryTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val context get() = ApplicationProvider.getApplicationContext<vn.abook.player.AbookApplication>()
    private val expired = Uri.parse("content://$AUTHORITY/expired/Sach.txt")
    private val fresh = Uri.parse("content://$AUTHORITY/fresh/Sach.txt")

    private fun provider() = GrantProvider().also {
        it.attachInfo(context, ProviderInfo().apply { authority = AUTHORITY })
        ShadowContentResolver.registerProviderInternal(AUTHORITY, it)
    }

    /** The import reads on Dispatchers.IO: poll through the shared scaled helper, running the main looper between checks. */
    private fun waitFor(what: String, check: () -> Boolean) =
        TestTime.eventually(what, limitMs = 3_000, pollMs = 20) { check().also { if (!it) shadowOf(android.os.Looper.getMainLooper()).idle() } }

    @Test fun expiredGrantShowsVietnameseAndRetryAsksForThePickerThenReadsTheNewFile() {
        provider()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val queue = ImportQueue(ImportRepo(context), scope)
            queue.enqueue(listOf(expired.toString()))
            waitFor("error row") { queue.state.value.items.single().stage == ImportStage.Error }
            val row = queue.state.value.items.single()
            assertEquals(ImportLogic.LOST_ACCESS, row.problem)
            assertTrue(row.lostAccess)
            assertFalse(row.problem, row.problem.contains("Permission") || row.problem.contains("ACTION_OPEN_DOCUMENT") || row.problem.contains("Exception"))

            queue.retry(row.id)
            waitFor("repick request") { queue.state.value.repick == row.id }
            assertEquals(row.id, queue.takeRepick())
            assertNull(queue.takeRepick())

            // Người dùng đóng hộp chọn file: hàng vẫn lỗi với câu tiếng Việt, không đọc lại vô ích.
            queue.repicked(row.id, null)
            assertEquals(ImportStage.Error, queue.state.value.items.single().stage)
            assertEquals(ImportLogic.LOST_ACCESS, queue.state.value.items.single().problem)

            queue.repicked(row.id, fresh.toString())
            waitFor("review") { queue.state.value.items.single().stage == ImportStage.Review }
            val read = queue.state.value.items.single()
            assertEquals(row.id, read.id)
            assertEquals(fresh.toString(), read.source)
            assertFalse(read.lostAccess)
            assertNotNull(queue.state.value.preview)
        } finally { scope.cancel() }
    }

    @Test fun tappingRetryOnAnExpiredGrantOpensTheSystemPickerAtTheOldFile() {
        provider()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val queue = ImportQueue(ImportRepo(context), scope)
            rule.setContent { AbookTheme(false) { AddBookRoute(queue, {}, {}, {}) } }
            rule.runOnIdle { queue.enqueue(listOf(expired.toString())) }
            rule.waitUntil(15_000) { queue.state.value.items.singleOrNull()?.stage == ImportStage.Error }
            val id = queue.state.value.items.single().id
            rule.onNodeWithTag("retry_$id").performClick()
            rule.waitUntil(15_000) { shadowOf(rule.activity).peekNextStartedActivityForResult() != null }
            val started = shadowOf(rule.activity).nextStartedActivityForResult
            assertEquals(Intent.ACTION_OPEN_DOCUMENT, started.intent.action)
            assertEquals(expired, started.intent.getParcelableExtra(DocumentsContract.EXTRA_INITIAL_URI, Uri::class.java))
            shadowOf(rule.activity).receiveResult(started.intent, Activity.RESULT_OK, Intent().setData(fresh))
            rule.waitUntil(15_000) { queue.state.value.items.single().stage == ImportStage.Review }
            assertEquals(fresh.toString(), queue.state.value.items.single().source)
        } finally { scope.cancel() }
    }

    /** `expired/...`: quyền đã hết - mở file ném SecurityException như Android thật. `fresh/...`: file vừa chọn lại, đọc được. */
    class GrantProvider : ContentProvider() {
        override fun onCreate() = true
        override fun getType(uri: Uri) = "text/plain"
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor {
            val columns = projection ?: arrayOf(OpenableColumns.DISPLAY_NAME)
            return MatrixCursor(columns).apply { addRow(columns.map<String, Any> { if (it == OpenableColumns.SIZE) TEXT.toByteArray().size.toLong() else "Sách.txt" }.toTypedArray()) }
        }
        override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
            if (uri.pathSegments.first() == "expired") throw SecurityException(
                "Permission Denial: reading com.android.externalstorage.ExternalStorageProvider uri $uri from pid=4242, uid=10123 requires " +
                    "android.permission.MANAGE_DOCUMENTS, or grantUriPermission(); you could obtain access using ACTION_OPEN_DOCUMENT or related APIs")
            val file = File.createTempFile("grant", ".txt").apply { writeText(TEXT); deleteOnExit() }
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
        }
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0
    }

    private companion object {
        const val AUTHORITY = "expired-grant-test"
        const val TEXT = "Sách thử\n\nChương 1\nMột dòng để đọc.\n\nChương 2\nMột dòng khác để đọc.\n"
    }
}
