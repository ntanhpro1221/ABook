package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Soát a99 V6: nơi gửi (Zalo, Drive, email) hay phát `ACTION_SEND` với `application/octet-stream` / `application/zip` cho file `.abook`; manifest phải nhận hai kiểu ấy,
 * và native kiểm tên / đầu file trước khi nhập - file không phải file sách thì báo rõ thay vì lỗi giải nén. Gradle chạy test ở mobile/android/app.
 */
class SharedBookFileTest {
    private fun zip(first: String, content: String, stored: Boolean = true): ByteArray {
        val sink = ByteArrayOutputStream()
        ZipOutputStream(sink).use { out ->
            val entry = ZipEntry(first)
            if (stored) {
                val bytes = content.toByteArray(Charsets.US_ASCII)
                entry.method = ZipEntry.STORED
                entry.size = bytes.size.toLong()
                entry.compressedSize = bytes.size.toLong()
                entry.crc = CRC32().apply { update(bytes) }.value
            }
            out.putNextEntry(entry)
            out.write(content.toByteArray(Charsets.US_ASCII))
            out.closeEntry()
        }
        return sink.toByteArray()
    }

    @Test fun theHeadOfABookFileOrProjectFileIsRecognised() {
        assertTrue(BookFileImport.looksLikeBookFile(zip("mimetype", BookFileImport.MIMETYPE)))
        assertTrue(BookFileImport.looksLikeBookFile(zip("mimetype", BookFileImport.PROJECT_MIMETYPE)))
    }

    @Test fun anyOtherZipOrJunkIsNot() {
        assertFalse(BookFileImport.looksLikeBookFile(zip("mimetype", "application/epub+zip")))
        assertFalse(BookFileImport.looksLikeBookFile(zip("nhac/01.mp3", "ID3")))
        assertFalse(BookFileImport.looksLikeBookFile(zip("mimetype", BookFileImport.MIMETYPE, stored = false)))
        assertFalse(BookFileImport.looksLikeBookFile(ByteArray(0)))
        assertFalse(BookFileImport.looksLikeBookFile("không phải zip".toByteArray()))
    }

    @Test fun aSharedGenericFileThatIsNotABookFileIsRefusedWithAReason() {
        val octet = "application/octet-stream"
        val reason = TextImports.refuseShared(octet, "nhac.zip") { zip("nhac/01.mp3", "ID3") }
        assertNotNull(reason)
        assertTrue(reason!!, reason.contains(".abook"))
        assertNotNull(TextImports.refuseShared("application/zip", "tai lieu") { ByteArray(0) })
        assertNotNull(TextImports.refuseShared(octet, null) { null })
    }

    @Test fun aBookFileIsLetThroughByNameOrByContent() {
        val octet = "application/octet-stream"
        assertNull(TextImports.refuseShared(octet, "Truyện.abook") { error("tên đã đủ - không đọc file") })
        assertNull(TextImports.refuseShared("application/zip", "Dự án.ABOOKPROJ") { error("tên đã đủ") })
        assertNull(TextImports.refuseShared(octet, "tải về (1)") { zip("mimetype", BookFileImport.MIMETYPE) })
    }

    @Test fun otherSharedFilesAreNotThisChecksBusiness() {
        assertNull(TextImports.refuseShared("application/octet-stream", "Truyện.epub") { error("EPUB đi đường xem trước") })
        assertNull(TextImports.refuseShared("application/vnd.ngdtuanh.abook+zip", "x") { error("kiểu riêng của app") })
        assertNull(TextImports.refuseShared("text/plain", "a.txt") { error("không phải kiểu chung") })
    }

    private fun filters(action: String): List<Element> {
        val file = File("src/main/AndroidManifest.xml")
        check(file.isFile) { "không thấy ${file.absolutePath}" }
        val root = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }.newDocumentBuilder().parse(file).documentElement
        val all = root.getElementsByTagName("intent-filter")
        return (0 until all.length).map { all.item(it) as Element }.filter { filter ->
            val actions = filter.getElementsByTagName("action")
            (0 until actions.length).any { (actions.item(it) as Element).getAttributeNS("http://schemas.android.com/apk/res/android", "name") == action }
        }
    }

    private fun mimes(filter: Element): Set<String> {
        val data = filter.getElementsByTagName("data")
        return (0 until data.length).map { (data.item(it) as Element).getAttributeNS("http://schemas.android.com/apk/res/android", "mimeType") }
            .filter { it.isNotEmpty() }.toSet()
    }

    @Test fun theManifestReceivesSharedZipAndOctetStreamFiles() {
        val shared = filters("android.intent.action.SEND").flatMap { mimes(it) }.toSet()
        assertTrue(shared.toString(), "application/octet-stream" in shared)
        assertTrue(shared.toString(), "application/zip" in shared)
        assertTrue(shared.toString(), "application/vnd.ngdtuanh.abook+zip" in shared)
        assertEquals("không nhận */*", false, "*/*" in shared)
    }
}
