package vn.abook.player.ui.addbook

import android.net.Uri
import android.content.ContentProvider
import android.content.ContentValues
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver
import org.json.JSONObject
import vn.abook.player.BookFileImport
import vn.abook.player.Store
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ImportRepoFileTest {
    private val context get() = ApplicationProvider.getApplicationContext<vn.abook.player.AbookApplication>()

    @Test fun viewStyleFileAndContentUrisApplyCoverAndScriptUpdatesAndKeepListening() = runBlocking {
        val provider = PackageProvider()
        provider.attachInfo(context, ProviderInfo().apply { authority = "metaupd-package" })
        ShadowContentResolver.registerProviderInternal("metaupd-package", provider)
        val repo = ImportRepo(context)
        for (contentUri in listOf(false, true)) {
            val base = File("../../../tests/fixtures/book_edits/base")
            val book = JSONObject(File(base, "book.json").readText())
            val content = book.getJSONObject("package").getJSONObject("files").keys().asSequence()
                .associateWith { File(base, it).readBytes() }.toMutableMap()
            // Independent books for the two VIEW URI schemes.
            val audio = content.keys.first { it.startsWith("chapters/") }
            content[audio] = content.getValue(audio) + contentUri.toString().toByteArray()
            suspend fun prepare(): PreparedImport {
                val files = JSONObject()
                for ((name, bytes) in content) files.put(name, JSONObject().put("size", bytes.size)
                    .put("sha256", java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }))
                book.getJSONObject("package").put("files", files)
                val file = File(context.cacheDir, "Bản cập nhật.abook")
                ZipOutputStream(file.outputStream()).use { zip ->
                    val mime = BookFileImport.MIMETYPE.toByteArray()
                    zip.putNextEntry(ZipEntry("mimetype").apply {
                        method = ZipEntry.STORED; size = mime.size.toLong(); compressedSize = size
                        crc = java.util.zip.CRC32().apply { update(mime) }.value
                    })
                    zip.write(mime); zip.closeEntry()
                    for ((name, bytes) in content + ("book.json" to book.toString().toByteArray())) {
                        zip.putNextEntry(ZipEntry(name)); zip.write(bytes); zip.closeEntry()
                    }
                }
                provider.file = file
                val uri = if (contentUri) Uri.parse("content://metaupd-package/book") else Uri.fromFile(file)
                return repo.prepare(ImportItem(1, uri.toString()))
            }
            val first = prepare()
            val id = requireNotNull(first.bookId)
            Store.progress(id, 1, 4.5, 120.0)
            Store.setRate(id, 1.25)
            Store.setChapterDone(id, 1, true)
            val state = Store.state(id).toString()
            val cover = "new base cover".toByteArray()
            content["cover.jpg"] = cover
            book.put("cover", JSONObject().put("file", "cover.jpg").put("width", 12).put("height", 24))
            val covered = prepare()
            assertEquals(id, covered.bookId)
            assertFalse(covered.existing)
            assertEquals("Đã cập nhật “${Store.manifest(id)!!.getString("title")}”", covered.notice)
            assertArrayEquals(cover, File(Store.bookDir(id), "cover.jpg").readBytes())
            val script = "{\"text\":\"script-only update\"}".toByteArray()
            content["scripts/1.json"] = script
            val scripted = prepare()
            assertEquals(id, scripted.bookId)
            assertFalse(scripted.existing)
            assertArrayEquals(script, File(Store.bookDir(id), "scripts/1.json").readBytes())
            assertTrue(prepare().existing)
            assertEquals(state, Store.state(id).toString())
        }
    }

    class PackageProvider : ContentProvider() {
        lateinit var file: File
        override fun onCreate() = true
        override fun getType(uri: Uri) = BookFileImport.MIMETYPE
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor =
            MatrixCursor(projection ?: arrayOf(OpenableColumns.DISPLAY_NAME)).apply {
                addRow(columnNames.map<String, Any> { if (it == OpenableColumns.SIZE) file.length() else file.name }.toTypedArray())
            }
        override fun openFile(uri: Uri, mode: String) = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0
    }
    @Test fun fileUriKeepsItsVietnameseNameAndExtensionWithoutAProvider() = runBlocking {
        val file = File(context.cacheDir, "Sách của bạn.abook")
        assertEquals(file.name, ImportRepo(context).describe(ImportItem(1, Uri.fromFile(file).toString())))
    }
    @Test fun anActualFixturePackageCanBeOpenedFromAFileUri() = runBlocking {
        val base = File("../../../tests/fixtures/book_edits/base")
        assertTrue(base.isDirectory)
        val book = org.json.JSONObject(File(base,"book.json").readText())
        val names = listOf("book.json") + book.getJSONObject("package").getJSONObject("files").keys().asSequence().toList()
        val file = File(context.cacheDir, "Sách thử.abook")
        ZipOutputStream(file.outputStream()).use { zip ->
            val mime = vn.abook.player.BookFileImport.MIMETYPE.toByteArray()
            val entry = ZipEntry("mimetype").apply {
                method = ZipEntry.STORED; size = mime.size.toLong(); compressedSize = size
                crc = java.util.zip.CRC32().apply { update(mime) }.value
            }
            zip.putNextEntry(entry); zip.write(mime); zip.closeEntry()
            names.forEach { name -> zip.putNextEntry(ZipEntry(name)); zip.write(File(base,name).readBytes()); zip.closeEntry() }
        }
        val prepared = ImportRepo(context).prepare(ImportItem(1,Uri.fromFile(file).toString()))
        assertEquals(file.name, prepared.name)
        assertNotNull(prepared.bookId)
        assertNull(prepared.preview)
    }
}
