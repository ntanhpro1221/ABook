package vn.abook.player

import java.io.File
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test

/**
 * Chỉ chạy trên máy có kho truyện thật (không bao giờ có trong repo): đọc từng thư mục TXT / file sách bằng [BookImport] và ghi kết quả -
 * tên sách, tên + sha256 của chữ từng chương ([BookImport.chapterSource]), ghi chú - ra `ABOOK_IMPORT_DUMP/<tên>.json`, để so với
 * `abook/importers.py` chạy trên cùng các đường dẫn. `ABOOK_IMPORT_CORPUS` = các đường dẫn cách nhau bằng `File.pathSeparator`; thiếu thì bỏ qua.
 */
class BookImportCorpusTest {
    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    @Test
    fun dumps_every_corpus_folder_for_the_desktop_diff() {
        val corpus = System.getenv("ABOOK_IMPORT_CORPUS").orEmpty()
        val out = System.getenv("ABOOK_IMPORT_DUMP").orEmpty()
        assumeTrue("ABOOK_IMPORT_CORPUS / ABOOK_IMPORT_DUMP chưa đặt", corpus.isNotEmpty() && out.isNotEmpty())
        val target = File(out).also { it.mkdirs() }
        val withText = System.getenv("ABOOK_IMPORT_TEXT") == "1" // kèm chữ từng chương để xem chỗ lệch
        for (path in corpus.split(File.pathSeparator).filter { it.isNotEmpty() }) {
            val folder = File(path)
            // PDF: các dòng pdf.js đã lấy (`<file>.pdf.pages.json` của pdfPages.corpus.test.ts) qua lớp luật.
            val name = folder.name.removeSuffix(".pages.json")
            val row = JSONObject().put("folder", name)
            val started = System.nanoTime()
            try {
                val book = if (name == folder.name) BookImport.importFile(folder) else {
                    val raw = JSONObject(folder.readText(Charsets.UTF_8))
                    val all = raw.getJSONArray("pages")
                    val pages = (0 until all.length()).map { page -> all.getJSONArray(page).let { lines -> (0 until lines.length()).map(lines::getString) } }
                    BookImport.fromPdfPages(name.substringBeforeLast('.'), pages, raw.getString("title"), raw.getString("author"))
                }
                val chapters = JSONArray()
                for (chapter in book.chapters) {
                    val source = BookImport.chapterSource(book, chapter)
                    val row = JSONObject().put("title", chapter.title).put("sha", sha256(source.toByteArray(Charsets.UTF_8)))
                    if (withText) row.put("text", source)
                    chapters.put(row)
                }
                row.put("title", book.title).put("chapters", chapters).put("notes", JSONArray(book.notes))
            } catch (error: BookImport.Failed) {
                row.put("error", error.message)
            }
            row.put("secs", (System.nanoTime() - started) / 1e9)
            File(target, "$name.json").writeBytes(row.toString(1).toByteArray(Charsets.UTF_8))
        }
    }
}
