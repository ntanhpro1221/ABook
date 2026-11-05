package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Máy dò lớp lỗi "ghi file của một cuốn mà trình phát / Thư viện không biết" (lỗi ngoài đời: thay sách đang mở xong, bảng chương giữ độ dài cũ tới khi app bị giết).
 * Mọi file nguồn vừa trỏ vào thư mục của một cuốn ([Store.bookDir], [Store.file], "book.json", "chapters/"...) vừa có động tác ghi / đổi tên / xoá phải HOẶC
 * gọi [BookFiles.changed] / [BookFiles.edited] HOẶC nằm trong bảng [EXEMPT] kèm lý do vì sao chỗ ấy không đổi hàng chương, độ dài hay file đang phát.
 * Chỗ ghi mới không thuộc cả hai = test đỏ: gọi cửa [BookFiles] (hay thêm một dòng có lý do, để người duyệt đọc).
 */
class BookFilesScanTest {
    private val root = File("src/main/java")

    private val write = Regex("""writeAtomic|writeBytes|writeText|outputStream\(|FileOutputStream|renameTo|copyTo|deleteRecursively|\.delete\(\)""")
    private val bookPath = Regex("""Store\.(?:bookDir|file|contained|coverFile)\(|"(?:book|stream)\.json"|"chapters/""")
    private val routed = Regex("""BookFiles\.(?:changed|edited)\(""")

    /** Chỗ ghi đã qua cửa [BookFiles.changed] (đổi hàng chương / file audio): bỏ lời gọi này thì trình phát lại giữ bản cũ. */
    private val gate = mapOf(
        "BookFileImport.kt" to "nhập / thay file .abook, .abookproj (kể cả sách chữ tạo mới)",
        "BookDownloads.kt" to "tải / cập nhật cuốn từ máy tính hay thiết bị ghép (kể cả \"Đã cập nhật\" của Studio, chương thu lại)",
        "Streaming.kt" to "gói sách nghe thẳng (stream.json) đổi hàng chương",
    )

    /** Chỗ chạm vào thư mục sách nhưng không đổi hàng chương / độ dài / file đang phát, kèm lý do. */
    private val exempt = mapOf(
        "BookDocumentWriter.kt" to "đọc thư mục sách để ghi file xuất",
        "BookEdits.kt" to "lớp sửa edits.json / bìa của người nghe; nơi gọi báo BookFiles.edited",
        "BookMusic.kt" to "bài nhạc nền trong music/; trình phát đọc theo mốc, không đổi hàng chương",
        "EditsSync.kt" to "sổ chờ gửi phần sửa về máy tính; bản tải lại đi qua BookDownloads.downloadBook",
        "ExportHistory.kt" to "sổ các lần xuất, không phải nội dung nghe",
        "LibraryServer.kt" to "phục vụ file cho thiết bị khác (chỉ đọc sách)",
        "ListenExportWorker.kt" to "ghi file xuất ra ngoài thư mục sách",
        "M4bExportWorker.kt" to "ghi file xuất ra ngoài thư mục sách",
        "Mp3Export.kt" to "ghi file xuất ra ngoài thư mục sách",
        "Mp3ExportWorker.kt" to "ghi file xuất ra ngoài thư mục sách",
        "MusicCatalog.kt" to "kho nhạc nền chung, không phải thư mục một cuốn",
        "Peers.kt" to "bỏ ghép một máy: xoá cuốn nghe thẳng của máy ấy; Thư viện đọc lại rồi PlayerRepo.reconcile đóng cuốn không còn",
        "RemoteBooks.kt" to "phần sửa của máy giữ sách (edits.holder.json), không đổi chương",
        "SceneDevice.kt" to "nhạc cảnh của cuốn (music/), không đổi chương",
        "Store.kt" to "đổi mã thư mục (Store.adopt): cuốn đang nạp bị loại trước (BookDownloads.matchImported bỏ Playback.bookId); xoá / hoàn tác đi qua Thư viện",
        "BookSave.kt" to "ghi file lưu ra ngoài thư mục sách",
        "readaloud/ReadAloud.kt" to "đọc chữ chương; bộ nhớ đệm của chính nó",
    )

    private fun sources(): Map<String, String> = root.walkTopDown().filter { it.isFile && it.extension == "kt" }.associate { file ->
        val text = file.readText(Charsets.UTF_8).lineSequence().filterNot { line -> line.trimStart().let { it.startsWith("//") || it.startsWith("*") || it.startsWith("/*") } }.joinToString("\n")
        file.relativeTo(File(root, "vn/abook/player")).path.replace('\\', '/') to text
    }

    private fun touchesBookFiles(text: String) = write.containsMatchIn(text) && bookPath.containsMatchIn(text)

    @Test fun noCodeWritesABooksFilesWithoutTellingThePlayer() {
        val strangers = sources().filter { (name, text) -> name != "BookFiles.kt" && touchesBookFiles(text) && !routed.containsMatchIn(text) && name !in exempt }.keys
        assertTrue(
            "Các file này ghi vào thư mục sách mà không gọi BookFiles.changed / BookFiles.edited và không có trong bảng exempt (kèm lý do): $strangers",
            strangers.isEmpty(),
        )
    }

    @Test fun theGateCallsAreStillThere() {
        val all = sources()
        for ((name, why) in gate) {
            val text = all[name] ?: error("Không thấy $name ($why)")
            assertTrue("$name ($why) phải gọi BookFiles.changed( sau khi ghi xong", Regex("""BookFiles\.changed\(""").containsMatchIn(text))
        }
        val callers = all.filter { (name, text) -> name != "BookFiles.kt" && Regex("""BookFiles\.changed\(""").containsMatchIn(text) }.keys
        assertEquals("chỗ gọi BookFiles.changed( ngoài bảng gate (thêm vào bảng kèm lý do)", gate.keys, callers)
    }

    @Test fun theExemptionTableHasNoStaleRows() {
        val all = sources()
        val stale = exempt.keys.filter { name -> all[name]?.let { touchesBookFiles(it) && !routed.containsMatchIn(it) } != true }
        assertTrue("Dòng exempt không còn đúng (file đã đổi hay đã gọi BookFiles): $stale", stale.isEmpty())
    }
}
