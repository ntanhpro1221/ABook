package vn.abook.player.ui.addbook

import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ImportRepoFileTest {
    private val context get() = ApplicationProvider.getApplicationContext<vn.abook.player.AbookApplication>()
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
