package vn.abook.player.ui

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ImportJob
import vn.abook.player.ImportJobState
import vn.abook.player.ImportJobs
import vn.abook.player.ImportOutcome
import vn.abook.player.Work
import vn.abook.player.WorkSink
import vn.abook.player.WorkStep
import vn.abook.player.ui.addbook.ImportChoices
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportLogic
import vn.abook.player.ui.addbook.ImportPreview
import vn.abook.player.ui.addbook.ImportQueue
import vn.abook.player.ui.addbook.ImportSource
import vn.abook.player.ui.addbook.ImportStage
import vn.abook.player.ui.addbook.PreparedImport

/**
 * Màn "Thêm sách" chỉ là MỘT người xem của việc nhập nền ([ImportJobs]): lượt màn không xếp (lệnh adb, nút trên thông báo) hiện thành hàng với đúng bước và
 * byte, xong thì "Đã thêm", lỗi thì "Thử lại" (xếp lại lượt nền, không đọc lại bằng hàng đợi); lượt của chính hàng đợi không thành hàng thứ hai; đóng màn không
 * hỏi về lượt nền vì nó không mất.
 */
class ImportBackgroundTest {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
    private var clock = 0L

    @After fun close() = scope.cancel()

    private object Unused : ImportSource {
        override suspend fun prepare(item: ImportItem, progress: WorkSink): PreparedImport = error("không dùng")
        override suspend fun revise(ref: String, choices: ImportChoices): ImportPreview = error("không dùng")
        override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean> = error("không dùng")
        override suspend fun discard(ref: String) = Unit
    }

    @Test fun a_background_job_shows_its_real_progress_and_ends_as_added() {
        val jobs = ImportJobs(now = { clock })
        var refreshed = 0
        val queue = ImportQueue(Unused, scope, now = { clock }, changed = { refreshed++ }, background = jobs.jobs)
        val source = "file:///sdcard/Android/data/com.ngdtuanh.abook/files/import/To.abook"
        jobs.begin(ImportJob("w1", source, "To.abook", owned = true))
        val row = queue.state.value.items.single()
        assertEquals("To.abook", row.name)
        assertEquals(ImportStage.Reading, row.stage)
        assertTrue(row.background)
        assertEquals(0, ImportLogic.unfinished(queue.state.value.items))
        val total = 1_400L shl 20
        jobs.report("w1", Work(WorkStep.Check, total / 2, total))
        assertEquals(0.5f, queue.progress(row.id).value.fraction!!, 1e-6f)
        assertEquals("Đang kiểm tra · 700\u00a0MB / 1,4\u00a0GB", ImportLogic.workLabel(queue.progress(row.id).value))
        jobs.finish("w1", ImportOutcome("b1", "To", "new"))
        val done = queue.state.value.items.single()
        assertEquals(ImportStage.Added, done.stage)
        assertEquals("b1", done.bookId)
        assertEquals("Đã thêm “To”", queue.state.value.notice)
        assertEquals(1f, queue.progress(row.id).value.fraction!!, 1e-6f)
        assertEquals(1, refreshed)
    }

    @Test fun reopening_the_screen_mid_import_shows_the_running_job_at_its_current_step() {
        val jobs = ImportJobs(now = { clock })
        jobs.begin(ImportJob("w1", "file:///import/A.abook", "A.abook", owned = true))
        jobs.report("w1", Work(WorkStep.Check, 30, 100))
        // Hàng đợi (người xem) dựng SAU khi lượt đã chạy: thấy ngay bước và phần đã làm, không bắt đầu lại từ "Đang đọc".
        val queue = ImportQueue(Unused, scope, now = { clock }, background = jobs.jobs)
        val row = queue.state.value.items.single()
        assertEquals(ImportStage.Reading, row.stage)
        assertEquals(0.3f, queue.progress(row.id).value.fraction!!, 1e-6f)
        // Lượt đã xong trước khi màn thấy nó: không thêm hàng (nằm ở Thư viện và thông báo).
        jobs.begin(ImportJob("w0", "file:///import/B.abook", "B.abook"))
        jobs.finish("w0", ImportOutcome("b0", "B", "new"))
        val late = ImportQueue(Unused, scope, now = { clock }, background = jobs.jobs)
        assertEquals(listOf("A.abook"), late.state.value.items.map { it.name })
    }

    @Test fun retry_on_a_failed_background_row_requeues_the_job_in_the_same_row() {
        val jobs = ImportJobs(now = { clock })
        val retried = ArrayList<String>()
        val queue = ImportQueue(Unused, scope, now = { clock }, background = jobs.jobs, retryJob = { retried += it })
        jobs.begin(ImportJob("w1", "file:///import/A.abook", "A.abook", owned = true))
        jobs.fail("w1", "File sách hỏng")
        val failed = queue.state.value.items.single()
        assertEquals(ImportStage.Error, failed.stage)
        assertEquals("File sách hỏng", failed.problem)
        queue.retry(failed.id)
        assertEquals(listOf("w1"), retried)
        jobs.begin(ImportJob("w2", "file:///import/A.abook", "A.abook", owned = true))
        val again = queue.state.value.items.single()
        assertEquals(failed.id, again.id)
        assertEquals(ImportStage.Reading, again.stage)
        jobs.finish("w2", ImportOutcome("b1", "A", "updated"))
        assertEquals(ImportStage.Added, queue.state.value.items.single().stage)
        assertEquals("Đã cập nhật “A”", queue.state.value.notice)
    }

    @Test fun the_queues_own_file_does_not_get_a_second_row() {
        val jobs = ImportJobs(now = { clock })
        val gate = CompletableDeferred<Unit>()
        val source = object : ImportSource {
            override suspend fun prepare(item: ImportItem, progress: WorkSink): PreparedImport {
                // Như ImportRepo: file sách đi qua việc nền và màn chờ nó; hàng của màn đang "Đang đọc" cùng file ấy.
                jobs.begin(ImportJob("own", item.source, "Của tôi.abook"))
                jobs.report("own", Work(WorkStep.Copy, 10, 100))
                gate.await()
                jobs.finish("own", ImportOutcome("b9", "Của tôi", "new"))
                return PreparedImport(null, "Của tôi.abook", bookId = "b9")
            }
            override suspend fun revise(ref: String, choices: ImportChoices): ImportPreview = error("không dùng")
            override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean> = error("không dùng")
            override suspend fun discard(ref: String) = Unit
        }
        val queue = ImportQueue(source, scope, now = { clock }, background = jobs.jobs)
        queue.enqueue(listOf("content://docs/mine"))
        // Lượt nền đang chạy (người xem đã thấy nó) mà vẫn chỉ một hàng - hàng của chính màn.
        assertEquals(ImportJobState.Running, jobs["own"]!!.state)
        assertEquals(listOf(ImportStage.Reading), queue.state.value.items.map { it.stage })
        gate.complete(Unit)
        val rows = queue.state.value.items
        assertEquals(1, rows.size)
        assertEquals(ImportStage.Added, rows.single().stage)
        assertTrue(!rows.single().background)
    }

    @Test fun an_existing_or_undecided_book_ends_as_already_in_the_library() {
        val jobs = ImportJobs(now = { clock })
        val queue = ImportQueue(Unused, scope, now = { clock }, background = jobs.jobs)
        jobs.begin(ImportJob("w1", "file:///import/A.abook", "A.abook", owned = true))
        jobs.finish("w1", ImportOutcome("b1", "A", "older"))
        assertEquals(ImportStage.Existing, queue.state.value.items.single().stage)
        assertEquals("b1", queue.state.value.items.single().bookId)
    }
}
