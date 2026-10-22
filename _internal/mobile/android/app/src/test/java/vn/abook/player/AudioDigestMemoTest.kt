package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/** Mã băm audio đã tải được nhớ theo (cỡ, mtime): có bản ghi thì không băm lại, file đổi thì băm lại. */
class AudioDigestMemoTest {
    private lateinit var root: File

    @Before fun fresh() {
        root = Files.createTempDirectory("digest-memo").toFile()
        BookEditsFixtures.useStoreRoot(root)
    }

    private fun chapter(text: String, age: Long = 60_000): File {
        val file = File(root, "books/b1/chapters/1.mp3")
        file.parentFile.mkdirs()
        file.writeText(text)
        file.setLastModified(System.currentTimeMillis() - age)
        return file
    }

    private fun recorded() = Store.chapterPrints("b1").optJSONObject("chapters/1.mp3")

    @Test fun a_recorded_chapter_is_not_hashed_again() {
        val file = chapter("old")
        val real = AudioRevision.sha256(file)
        assertEquals(real, Store.audioSha256(file))
        assertEquals(3L, recorded()!!.getLong("size"))
        assertEquals(file.lastModified(), recorded()!!.getLong("modified"))
        // Cùng cỡ, cùng mtime, byte khác: chỉ có bản ghi mới nói được mã băm cũ - tức là file không bị đọc lại.
        val modified = file.lastModified()
        file.writeText("new")
        file.setLastModified(modified)
        assertEquals(real, Store.audioSha256(file))
        assertTrue(AudioRevision.matches(file, 3, real))
    }

    @Test fun a_changed_file_is_hashed_again() {
        val file = chapter("old")
        val first = Store.audioSha256(file)
        file.writeText("longer")
        file.setLastModified(System.currentTimeMillis() - 60_000)
        val bigger = Store.audioSha256(file)
        assertEquals(AudioRevision.sha256(file), bigger)
        assertNotEquals(first, bigger)
        file.writeText("LONGER") // cùng cỡ, mtime khác
        file.setLastModified(System.currentTimeMillis() - 30_000)
        assertEquals(AudioRevision.sha256(file), Store.audioSha256(file))
        assertFalse(AudioRevision.matches(file, 6, bigger))
    }

    @Test fun a_file_written_a_moment_ago_is_not_trusted_yet() {
        val file = chapter("old", age = 0)
        Store.audioSha256(file)
        assertNull(recorded())
        file.writeText("new")
        assertEquals(AudioRevision.sha256(file), Store.audioSha256(file))
    }

    @Test fun a_finished_download_is_recorded_without_hashing_it_again() {
        val file = chapter("audio")
        val real = AudioRevision.sha256(file)
        Store.rememberDigest("b1", "chapters/1.mp3", file, real)
        val modified = file.lastModified()
        file.writeText("AUDIO")
        file.setLastModified(modified)
        assertEquals("bản ghi lúc tải xong được tin khi cỡ + mtime khớp", real, Store.audioSha256(file))
    }

    @Test fun import_stamps_the_files_it_just_verified() {
        val file = chapter("audio")
        val real = AudioRevision.sha256(file)
        Store.rememberChapters("b1", org.json.JSONObject().put("chapters/1.mp3", org.json.JSONObject().put("size", 5).put("sha256", real)), imported = true)
        assertEquals(file.lastModified(), recorded()!!.getLong("modified"))
    }

    @Test fun partial_and_foreign_files_leave_no_record() {
        val part = File(root, "books/b1/chapters/1.mp3.part").apply { parentFile.mkdirs(); writeText("half"); setLastModified(System.currentTimeMillis() - 60_000) }
        val outside = File(root, "elsewhere.mp3").apply { writeText("x"); setLastModified(System.currentTimeMillis() - 60_000) }
        Store.audioSha256(part)
        Store.audioSha256(outside)
        assertEquals(0, Store.chapterPrints("b1").length())
        assertFalse(File(root, "prints.json").isFile)
    }

    @Test fun a_whole_book_is_read_and_recorded_in_one_pass() {
        val files = (1..3).map { number ->
            File(root, "books/b1/chapters/$number.mp3").apply { parentFile.mkdirs(); writeText("audio-$number"); setLastModified(System.currentTimeMillis() - 60_000) }
        }
        assertEquals(files.map { AudioRevision.sha256(it) }, Store.audioSha256s(files))
        assertEquals(3, Store.chapterPrints("b1").length())
        assertEquals(files.map { AudioRevision.sha256(it) }, Store.audioSha256s(files))
    }
}
