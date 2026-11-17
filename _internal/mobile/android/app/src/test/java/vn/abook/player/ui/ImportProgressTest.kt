package vn.abook.player.ui

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.Work
import vn.abook.player.WorkSink
import vn.abook.player.WorkStep
import vn.abook.player.WorkThrottle
import vn.abook.player.ui.addbook.ImportChoices
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportLogic
import vn.abook.player.ui.addbook.ImportPreview
import vn.abook.player.ui.addbook.ImportQueue
import vn.abook.player.ui.addbook.ImportSource
import vn.abook.player.ui.addbook.ImportStage
import vn.abook.player.ui.addbook.PreparedImport

/**
 * Thanh tiến độ của "Thêm sách" chạy theo việc thật (chủ sách 11-11: "thanh tiến độ ở đây chả chạy bao giờ" - trước đây gán cứng 0.2 rồi 0.55):
 * byte giả của bước chép rồi bước kiểm đẩy thanh đi lên đều, tới 1 khi xong; chưa có lời báo nào thì thanh chạy liên tục, không là số đứng yên.
 */
class ImportProgressTest {
    private var clock = 0L

    /** Nguồn giả của một file .abook 1,5 GB: chép rồi kiểm, mỗi khối 64 MB cách nhau 30 ms đồng hồ giả. */
    private inner class BigBook(private val seen: MutableList<Work>, private val queue: () -> ImportQueue) : ImportSource {
        override suspend fun prepare(item: ImportItem, progress: WorkSink): PreparedImport {
            seen += queue().progress(item.id).value
            val total = 1_500L shl 20
            for (step in listOf(WorkStep.Copy, WorkStep.Check)) {
                var done = 0L
                while (true) {
                    progress(Work(step, done, total))
                    seen += queue().progress(item.id).value
                    clock += 30
                    if (done == total) break
                    done = minOf(total, done + (64L shl 20))
                }
            }
            return PreparedImport(null, "To.abook", bookId = "big")
        }
        override suspend fun revise(ref: String, choices: ImportChoices): ImportPreview = error("không dùng")
        override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean> = error("không dùng")
        override suspend fun discard(ref: String) = Unit
    }

    @Test fun the_bar_follows_fake_bytes_upward_without_standing_still_and_ends_at_one() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val seen = ArrayList<Work>()
        lateinit var queue: ImportQueue
        queue = ImportQueue(BigBook(seen) { queue }, scope, now = { clock })
        queue.enqueue(listOf("content://big"))
        // Trước lời báo đầu tiên: "Đang đọc", thanh chạy liên tục (không có phần trăm nào để đứng yên).
        assertEquals(WorkStep.Read, seen.first().step)
        assertNull(seen.first().fraction)
        // Thanh theo BƯỚC đang hiện: trong mỗi bước chỉ đi lên, từ 0 tới đầy; sang bước mới (chữ đổi "Đang chép" -> "Đang kiểm tra") thì bắt đầu lại.
        val reports = seen.drop(1)
        for (step in listOf(WorkStep.Copy, WorkStep.Check)) {
            val fractions = reports.filter { it.step == step }.map { it.fraction!! }
            for ((before, after) in fractions.zipWithNext()) assertTrue("thanh lùi giữa bước $step: $before -> $after", after >= before)
            // Chạy thật: nhiều nấc khác nhau trong cả hai bước, không phải mốc gán cứng.
            assertTrue("bước $step chỉ ${fractions.distinct().size} nấc", fractions.distinct().size >= 5)
            assertEquals(0f, fractions.first(), 1e-6f)
            assertEquals(1f, fractions.last(), 1e-6f)
        }
        assertEquals(ImportStage.Added, queue.state.value.items.single().stage)
        assertEquals(1f, queue.progress(1).value.fraction!!, 1e-6f)
        scope.cancel()
    }

    @Test fun reports_are_thinned_to_ten_a_second_but_step_changes_and_step_ends_always_pass() {
        var now = 0L
        val out = ArrayList<Work>()
        val throttle = WorkThrottle({ out += it }, now = { now })
        for (done in 0L..100L) { throttle(Work(WorkStep.Copy, done, 100)); now += 10 } // 1 giây, 101 lời báo
        assertTrue("${out.size} lời báo trong 1 giây", out.size in 10..12)
        assertEquals(100L, out.last().done) // bước xong luôn đi qua
        throttle(Work(WorkStep.Check, 0, 100))
        assertEquals(WorkStep.Check, out.last().step) // đổi bước đi qua ngay dù chưa đủ 100 ms
    }

    @Test fun a_stale_system_size_turns_the_bar_continuous_instead_of_standing_at_full() {
        // Máy ảo 11-11: MediaStore báo 918 MB cho file 1,46 GB; thanh đứng "918 MB / 918 MB" mấy giây trong khi vẫn chép.
        val total = 918L shl 20
        assertEquals(0.5f, vn.abook.player.copyWork(total / 2, total).fraction!!, 1e-6f)
        assertEquals(1f, vn.abook.player.copyWork(total, total).fraction!!, 1e-6f)
        val over = vn.abook.player.copyWork(total + 1, total)
        assertNull(over.fraction)
        assertEquals("Đang chép", ImportLogic.workLabel(over))
    }

    @Test fun the_bar_and_the_words_say_the_same_number() {
        // Ảnh OPPO 15-11 (0.4.172): "Đang chép · 1,3 GB / 1,4 GB" mà thanh mới ~47 % (thanh là cả việc chép + kiểm, chữ chỉ nói bước chép).
        val total = 1_400L * 1_000_000
        for (step in listOf(WorkStep.Copy, WorkStep.Check, WorkStep.Read)) {
            for (done in listOf(0L, total / 3, total * 13 / 14, total)) {
                val work = Work(step, done, total)
                assertEquals("$step $done", done.toFloat() / total, work.fraction!!, 1e-6f)
            }
        }
        val owner = Work(WorkStep.Copy, 1_300L * 1_000_000, total)
        assertTrue(ImportLogic.workLabel(owner), ImportLogic.workLabel(owner).startsWith("Đang chép · "))
        assertTrue("thanh ${owner.fraction}", owner.fraction!! > 0.9f)
        // Số trang / số file cũng vậy: "Đang đọc · 3/12" là một phần tư thanh.
        assertEquals(0.25f, Work(WorkStep.Read, 3, 12, bytes = false).fraction!!, 1e-6f)
    }

    @Test fun the_row_says_the_real_step_and_how_much_is_done() {
        val copying = ImportLogic.workLabel(Work(WorkStep.Copy, 512L shl 20, 1536L shl 20))
        assertTrue(copying, copying.startsWith("Đang chép · ") && copying.contains(" / "))
        assertEquals("Đang kiểm tra", ImportLogic.workLabel(Work(WorkStep.Check)))
        assertEquals("Đang chép · 2/5", ImportLogic.workLabel(Work(WorkStep.Copy, 2, 5, bytes = false)))
        assertEquals("Đang đọc", ImportLogic.workLabel(Work(WorkStep.Read)))
    }
}
