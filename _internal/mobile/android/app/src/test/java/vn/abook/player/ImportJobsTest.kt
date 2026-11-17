package vn.abook.player

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.nio.file.Files

/**
 * Việc nhập nền dùng chung ([ImportJobs]) với nguồn giả: tiến độ thưa lại, xong / lỗi, file của thư mục nhập chỉ bị xoá khi sách đã vào thư viện, người xem chờ
 * đúng lượt; và thư mục nhập ([ImportInbox]) chỉ nhận file sách nằm ngay trong nó.
 */
class ImportJobsTest {
    @get:Rule val temp = TemporaryFolder()
    private var clock = 0L

    /** Nguồn giả của một file 1,4 GB: bước kiểm, mỗi khối 64 MB cách nhau 30 ms đồng hồ giả. */
    private fun fakeBook(how: String = "new"): (WorkSink) -> ImportOutcome = { sink ->
        val total = 1_400L shl 20
        var done = 0L
        while (true) {
            sink(Work(WorkStep.Check, done, total))
            clock += 30
            if (done == total) break
            done = minOf(total, done + (64L shl 20))
        }
        ImportOutcome("b1", "Sách thử", how)
    }

    @Test fun a_finished_owned_file_is_removed_and_progress_is_thinned() {
        val jobs = ImportJobs(now = { clock })
        val shown = ArrayList<Work>()
        val seen = ArrayList<Work>()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        scope.async { jobs.jobs.collect { it["w1"]?.let { job -> seen += job.work } } }
        var discarded = 0
        val end = jobs.run(ImportJob("w1", "file:///import/a.abook", "a.abook", owned = true), fakeBook(), { discarded++ }, { shown += it })
        assertEquals(ImportJobState.Done, end.state)
        assertEquals("b1", end.bookId)
        assertEquals("Sách thử", end.title)
        assertEquals(1, discarded)
        // 23 khối trong 690 ms đồng hồ giả: thưa còn ~7 lời báo (10 lần/giây), lời cuối (bước xong) luôn qua.
        assertTrue("${shown.size} lời báo", shown.size in 5..10)
        assertEquals(1f, shown.last().fraction!!, 1e-6f)
        for ((before, after) in seen.mapNotNull { it.fraction }.zipWithNext()) assertTrue("thanh lùi: $before -> $after", after >= before)
        scope.cancel()
    }

    @Test fun a_failed_or_undecided_import_keeps_the_import_folder_file_for_retry() {
        val jobs = ImportJobs(now = { clock })
        var discarded = 0
        val failed = jobs.run(ImportJob("w1", "file:///import/a.abook", "a.abook", owned = true),
            { throw BookFileImport.Refused("File sách hỏng") }, { discarded++ })
        assertEquals(ImportJobState.Failed, failed.state)
        assertEquals("File sách hỏng", failed.problem)
        val older = jobs.run(ImportJob("w2", "file:///import/b.abook", "b.abook", owned = true), fakeBook("older"), { discarded++ })
        assertTrue(older.needsChoice)
        assertEquals(0, discarded)
    }

    @Test fun a_file_the_user_picked_is_never_discarded() {
        val jobs = ImportJobs(now = { clock })
        var discarded = 0
        jobs.run(ImportJob("w1", "content://docs/a", "a.abook", owned = false), fakeBook(), { discarded++ })
        assertEquals(0, discarded)
    }

    @Test fun a_scheduler_stop_is_not_a_file_failure_and_keeps_the_source_for_replay() {
        val jobs = ImportJobs(now = { clock })
        val job = ImportJob("w1", "file:///import/a.abook", "a.abook", owned = true)
        var discarded = 0
        try {
            jobs.run(job, { sink ->
                sink(Work(WorkStep.Check, 64, 128))
                throw ImportStopped()
            }, { discarded++ })
            throw AssertionError("stop was swallowed")
        } catch (_: ImportStopped) {
            assertEquals(ImportJobState.Running, jobs["w1"]!!.state)
            assertEquals("", jobs["w1"]!!.problem)
            assertEquals(0, discarded)
        }
        assertEquals(ImportJobState.Done, jobs.run(job, fakeBook(), { discarded++ }).state)
        assertEquals(1, discarded)
    }

    @Test fun a_viewer_waits_for_its_job_and_sees_its_progress() = runBlocking {
        val jobs = ImportJobs(now = { clock })
        jobs.begin(ImportJob("w1", "content://docs/a", "a.abook"))
        assertNotNull(jobs.running("content://docs/a"))
        assertNull(jobs.running("content://docs/b"))
        val seen = ArrayList<Work>()
        val waiting = async(Dispatchers.Unconfined) { jobs.await("w1") { seen += it } }
        Thread { jobs.run(ImportJob("w1", "content://docs/a", "a.abook"), fakeBook("updated"), {}) }.apply { start(); join() }
        val end = waiting.await()!!
        assertEquals(ImportJobState.Done, end.state)
        assertEquals("updated", end.how)
        assertTrue(seen.isNotEmpty())
        assertNull(jobs.running("content://docs/a"))
        assertNull(jobs.await("không có"))
    }

    @Test fun a_restarted_process_records_the_job_it_was_handed() {
        val jobs = ImportJobs(now = { clock })
        val end = jobs.run(ImportJob("w9", "file:///import/c.abook", "c.abook", owned = true), fakeBook(), {})
        assertEquals(ImportJobState.Done, end.state)
        assertEquals("c.abook", jobs["w9"]!!.name)
    }

    @Test fun only_the_latest_finished_jobs_are_kept() {
        val jobs = ImportJobs(now = { clock })
        for (i in 1..ImportJobs.KEEP + 5) jobs.run(ImportJob("w$i", "s$i", "n$i"), { ImportOutcome("b$i", "t", "new") }, {})
        jobs.begin(ImportJob("next", "s-next", "n"))
        assertEquals(ImportJobs.KEEP + 1, jobs.jobs.value.size)
        assertNull(jobs["w1"])
        assertNotNull(jobs["w${ImportJobs.KEEP + 5}"])
    }

    // ---- thư mục nhập -------------------------------------------------------------------------------------------

    private fun inbox(): File = temp.newFolder("files", ImportInbox.FOLDER)

    @Test fun the_inbox_accepts_only_book_files_directly_inside_it() {
        val inbox = inbox()
        val book = File(inbox, "Sách.abook").apply { writeText("x") }
        val project = File(inbox, "Dự án.abookproj").apply { writeText("x") }
        File(inbox, "ghi chú.txt").writeText("x")
        File(inbox, "thư mục.abook").mkdirs()
        val all = ImportInbox.resolve(inbox, null)
        assertEquals(listOf(project.canonicalFile, book.canonicalFile).sortedBy { it.name }, all.files)
        assertTrue(all.refused.isEmpty())
        assertEquals(listOf(book.canonicalFile), ImportInbox.resolve(inbox, book.absolutePath).files)
        val indirect = File(inbox, "child/../${book.name}")
        assertEquals(listOf("${indirect.path}: outside the import folder"), ImportInbox.resolve(inbox, indirect.path).refused)
    }

    @Test fun the_inbox_refuses_paths_outside_it() {
        val inbox = inbox()
        val outside = File(temp.root, "ngoài.abook").apply { writeText("x") }
        val nested = File(inbox, "con").apply { mkdirs() }.let { File(it, "sâu.abook").apply { writeText("x") } }
        val text = File(inbox, "ghi chú.txt").apply { writeText("x") }
        val cases = mapOf(
            outside.absolutePath to "outside the import folder",
            File(inbox, "../../ngoài.abook").path to "outside the import folder",
            nested.absolutePath to "outside the import folder",
            "ngoài.abook" to "not an absolute path",
            text.absolutePath to "not a .abook or .abookproj file",
            File(inbox, "không có.abook").absolutePath to "not a regular file",
            File(temp.root, "files/books/x.abook").absolutePath to "outside the import folder",
        )
        for ((path, reason) in cases) {
            val pick = ImportInbox.resolve(inbox, path)
            assertTrue("$path được nhận", pick.files.isEmpty())
            assertEquals(listOf("$path: $reason"), pick.refused)
        }
        assertTrue(outside.isFile && nested.isFile)
    }

    @Test fun the_inbox_refuses_a_symbolic_link_even_to_a_book_inside_it() {
        val inbox = inbox()
        val target = File(temp.root, "ngoài.abook").apply { writeText("x") }
        val inside = File(inbox, "thật.abook").apply { writeText("x") }
        val link = File(inbox, "liên kết.abook")
        val linkInside = File(inbox, "liên kết 2.abook")
        // Windows không có quyền tạo liên kết mềm thì bỏ qua (máy Android / Linux luôn chạy được).
        val made = runCatching { Files.createSymbolicLink(link.toPath(), target.toPath()); Files.createSymbolicLink(linkInside.toPath(), inside.toPath()) }.isSuccess
        assumeTrue("không tạo được liên kết mềm", made)
        assertEquals(listOf("${link.absolutePath}: symbolic link"), ImportInbox.resolve(inbox, link.absolutePath).refused)
        assertEquals(listOf("${linkInside.absolutePath}: symbolic link"), ImportInbox.resolve(inbox, linkInside.absolutePath).refused)
        assertEquals(listOf(inside.canonicalFile), ImportInbox.resolve(inbox, null).files)
        assertFalse(ImportInbox.resolve(inbox, null).files.any { it.name.startsWith("liên kết") })
    }
}
