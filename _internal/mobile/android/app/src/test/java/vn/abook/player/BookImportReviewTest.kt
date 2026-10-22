package vn.abook.player

import java.io.File
import java.io.InputStream
import java.lang.reflect.InvocationTargetException
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import java.nio.file.Files
import java.security.MessageDigest
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test

class BookImportReviewTest {
    private val dir = File("../../../tests/fixtures/import")
    private fun cases(name: String) = JSONArray(File(dir, "expected/$name.json").readText(Charsets.UTF_8))

    @Test
    fun merge_5000_parts_within_budget() {
        val case = JSONObject(File(dir, "expected/many_parts.json").readText(Charsets.UTF_8))
        val started = System.nanoTime()
        val book = BookImport.importFile(File(dir, "many_parts.epub"))
        val elapsed = (System.nanoTime() - started) / 1e9
        assertEquals(1, book.chapters.size)
        val chapter = book.chapters.first()
        assertEquals(case.getString("title"), chapter.title)
        assertEquals(case.getInt("length"), chapter.text.length)
        val digest = MessageDigest.getInstance("SHA-256").digest(chapter.text.toByteArray()).joinToString("") { "%02x".format(it) }
        assertEquals(case.getString("sha256"), digest)
        println("5000 parts: ${elapsed}s")
        assertTrue("5000 parts: ${elapsed}s", elapsed < case.getDouble("max_seconds"))
    }

    @Test
    fun strict_xml_rejects_malformed_documents() {
        val cases = cases("malformed_xml_cases")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val hex = case.getString("hex")
            val raw = ByteArray(hex.length / 2) { hex.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
            val got = try { BookImport.Markup.parse(raw, "EPUB", strict = true).allText() } catch (error: BookImport.Failed) { error.message }
            assertEquals(case.getString("case"), case.optString("text", case.optString("error")), got)
        }
    }

    @Test
    fun package_xml_is_strict() {
        for (part in listOf("META-INF/container.xml", "OEBPS/content.opf", "word/document.xml")) {
            val source = if (part.startsWith("word/")) "headings.docx" else "epub3.epub"
            val path = Files.createTempFile("abook-xml", source).toFile()
            try {
                ZipFile(File(dir, source)).use { input ->
                    ZipOutputStream(path.outputStream()).use { output ->
                        for (entry in input.entries()) {
                            output.putNextEntry(ZipEntry(entry.name))
                            output.write(input.getInputStream(entry).use { it.readBytes() })
                            if (entry.name == part) output.write("<extra/>".toByteArray())
                            output.closeEntry()
                        }
                    }
                }
                try { BookImport.importFile(path); fail(part) } catch (_: BookImport.Failed) { }
            } finally { path.delete() }
        }
    }

    @Test
    fun markup_aliases_in_chapters_and_drm() {
        checkMarkup("markup_alias_cases")
    }

    @Test
    fun bomless_utf16_in_chapters_and_drm() {
        checkMarkup("markup_utf16_cases")
    }

    private fun checkMarkup(name: String) {
        val cases = cases(name)
        val drm = BookImport::class.java.getDeclaredMethod("looksEncrypted", ByteArray::class.java).apply { isAccessible = true }
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val hex = case.getString("hex")
            val raw = ByteArray(hex.length / 2) { hex.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
            assertEquals(case.getString("case"), case.getString("text"), BookImport.markupText(raw))
            assertEquals(false, drm.invoke(BookImport, raw))
        }
    }

    @Test
    fun controls_are_removed_before_extract_decode_round_trip() {
        for (name in listOf("review_nul", "review_controls")) {
            val book = BookImport.importFile(File(dir, "$name.epub"))
            assertEquals(File(dir, "expected/$name.json").readText(Charsets.UTF_8), StrictJson.dumps(BookImport.toMap(book)) + "\n")
            val source = BookImport.chapterSource(book, book.chapters.first())
            assertEquals(source, BookImport.decodeText(source.toByteArray(Charsets.UTF_8)).first)
        }
    }

    @Test
    fun zip_counts_actual_bytes_not_declared_size() {
        val cases = cases("zip_stream_cases")
        val read = BookImport::class.java.getDeclaredMethod("read", ZipFile::class.java, String::class.java, String::class.java).apply { isAccessible = true }
        val cover = BookImport::class.java.getDeclaredMethod("epubCover", ZipFile::class.java, BookImport.Markup.Node::class.java, Map::class.java).apply { isAccessible = true }
        val item = BookImport::class.java.declaredClasses.first { it.simpleName == "ManifestItem" }
            .getDeclaredConstructor(String::class.java, String::class.java, String::class.java).apply { isAccessible = true }
            .newInstance("cover.png", "image/png", "cover-image")
        val opf = BookImport.Markup.parse("<package/>".toByteArray(), "EPUB", strict = true)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            var size = 0
            val zip = object : ZipFile(File(dir, "epub3.epub")) {
                override fun getEntry(name: String) = ZipEntry(name).apply { this.size = 1 }
                override fun getInputStream(entry: ZipEntry): InputStream = object : InputStream() {
                    var remaining = size
                    override fun read(): Int = if (remaining-- > 0) 120 else -1
                    override fun read(bytes: ByteArray, off: Int, len: Int): Int {
                        if (remaining <= 0) return -1
                        val n = minOf(len, remaining)
                        bytes.fill(120, off, off + n)
                        remaining -= n
                        return n
                    }
                }
            }
            zip.use {
                try {
                    val sizes = case.getJSONArray("sizes")
                    for (at in 0 until sizes.length()) {
                        size = sizes.getInt(at)
                        if (case.getBoolean("cover")) cover.invoke(BookImport, zip, opf, mapOf("cover" to item))
                        else read.invoke(BookImport, zip, "part$at", "EPUB")
                    }
                    fail(case.getString("case"))
                } catch (error: InvocationTargetException) {
                    assertEquals(case.getString("error"), error.cause?.message)
                }
            }
        }
    }
}
