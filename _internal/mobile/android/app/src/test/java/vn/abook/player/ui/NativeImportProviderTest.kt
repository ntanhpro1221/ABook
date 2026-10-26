package vn.abook.player.ui

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportRepo
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class NativeImportProviderTest {
    @Test fun folderPickerUsesDocumentMetadataAndImportsAllDirectTxtChildren() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val provider = FolderProvider()
        provider.attachInfo(context, ProviderInfo().apply { authority = "native-import-test" })
        ShadowContentResolver.registerProviderInternal("native-import-test", provider)
        val repo = ImportRepo(context)
        val tree = DocumentsContract.buildTreeDocumentUri("native-import-test", "books")
        val item = ImportItem(1, tree.toString(), folder = true)
        assertEquals("Thư mục thử", repo.describe(item))
        val prepared = repo.prepare(item)
        assertEquals("Thư mục thử", prepared.name)
        assertEquals(2, prepared.preview?.chapters?.size)
        repo.discard(requireNotNull(prepared.ref))
    }

    /** A real provider may reject metadata queries on a tree URI; the selected document URI is required. */
    class FolderProvider : ContentProvider() {
        override fun onCreate() = true
        override fun getType(uri: Uri): String {
            require(uri.pathSegments.contains("document")) { "Tree URI does not have document metadata" }
            return if (uri.lastPathSegment == "books") DocumentsContract.Document.MIME_TYPE_DIR else "text/plain"
        }
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor {
            require(uri.pathSegments.contains("document")) { "Tree URI does not have document metadata" }
            val columns = projection ?: arrayOf(OpenableColumns.DISPLAY_NAME)
            val rows = if (uri.lastPathSegment == "children") listOf("2.txt", "1.txt") else listOf("Thư mục thử")
            return MatrixCursor(columns).apply {
                for (name in rows) addRow(columns.map { column -> when (column) {
                    DocumentsContract.Document.COLUMN_DOCUMENT_ID -> "books/$name"
                    DocumentsContract.Document.COLUMN_MIME_TYPE -> "text/plain"
                    else -> name
                } }.toTypedArray())
            }
        }
        override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
            val file = File(requireNotNull(context).cacheDir, uri.lastPathSegment!!.substringAfterLast('/'))
            file.writeText("Một người khách đang chờ chuyến phà cuối ngày. Bạn vẫn nghe thấy tiếng gió bên kia sông.\n")
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
        }
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0
    }
}
