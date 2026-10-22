package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Test

/** Tải tiếp file dở chỉ khi chắc nó cùng phiên bản - cùng luật với `remote_books._resume_point` / `_save` (tests/test_remote_download_and_edits.py). */
class PartResumeTest {
    private lateinit var dir: File
    private val partial get() = File(dir, "1.mp3.part")

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("abook-partresume").toFile()
    }

    @After
    fun tearDown() {
        dir.deleteRecursively()
    }

    @Test
    fun a_part_with_no_recorded_version_is_not_resumed() {
        partial.writeBytes(ByteArray(300))
        assertEquals(0L to "", PartResume.point(partial, 1000))
    }

    @Test
    fun a_part_resumes_with_the_version_it_started_with() {
        partial.writeBytes(ByteArray(300))
        PartResume.stamp(partial, "\"v1\"")
        assertEquals(300L to "\"v1\"", PartResume.point(partial, 1000))
        assertEquals("whole or oversized parts start over", 0L to "", PartResume.point(partial, 300))
        PartResume.stamp(partial, null)
        assertEquals("a server with no ETag leaves nothing to trust", 0L to "", PartResume.point(partial, 1000))
    }

    @Test
    fun only_a_matching_206_is_appended() {
        val tag = "\"v1\""
        assertEquals(PartResume.Answer.RESUME, PartResume.answer(206, "bytes 300-999/1000", tag, 300, tag))
        assertEquals("the file changed: the whole new file came back", PartResume.Answer.WHOLE, PartResume.answer(200, null, "\"v2\"", 300, tag))
        assertEquals("a server that ignored If-Range sent a foreign tail", PartResume.Answer.STALE_TAIL, PartResume.answer(206, "bytes 300-999/1000", "\"v2\"", 300, tag))
        assertEquals(PartResume.Answer.STALE_TAIL, PartResume.answer(206, "bytes 301-999/1000", tag, 300, tag))
        assertEquals("no ETag on the tail is not a match", PartResume.Answer.STALE_TAIL, PartResume.answer(206, "bytes 300-999/1000", null, 300, tag))
    }

    @Test
    fun discarding_removes_the_part_and_its_note() {
        partial.writeBytes(ByteArray(10))
        PartResume.stamp(partial, "\"v1\"")
        PartResume.discard(partial)
        assertFalse(partial.exists() || PartResume.tagFile(partial).exists())
    }
}
