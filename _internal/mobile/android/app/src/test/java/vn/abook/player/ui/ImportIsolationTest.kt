package vn.abook.player.ui

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.abook.player.WorkSink
import vn.abook.player.ui.addbook.ImportChapter
import vn.abook.player.ui.addbook.ImportChoices
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportPreview
import vn.abook.player.ui.addbook.ImportQueue
import vn.abook.player.ui.addbook.ImportSource
import vn.abook.player.ui.addbook.ImportStage
import vn.abook.player.ui.addbook.PackageReview
import vn.abook.player.ui.addbook.PreparedImport

/**
 * Mỗi lượt của hàng đợi có trạng thái riêng: bản tạm (ref), kiểu file (bản xem trước hay gói cần chọn), lời lỗi. Lượt trước lỗi hay bị bỏ không bao giờ để lại
 * thứ gì mà lượt sau dùng nhầm - bản bench 15-11 (.abook hỏng rồi TXT báo "Đây không phải file sách của app.").
 */
class ImportIsolationTest {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
    @After fun close() = scope.cancel()

    /** Nguồn giả theo tên file: `.abook` hỏng / tốt, `.txt` hỏng / tốt. Ghi lại ref mà mỗi lần thêm / bỏ nhận. */
    private class Fake : ImportSource {
        val added = ArrayList<String>()
        val discarded = ArrayList<String>()
        override suspend fun prepare(item: ImportItem, progress: WorkSink): PreparedImport = when (item.source) {
            "bad.abook" -> throw IllegalStateException("Đây không phải file sách của app.")
            "bad.txt" -> throw IllegalStateException("File “bad.txt” hỏng chữ.")
            "older.abook" -> PreparedImport(null, item.source, packageReview = PackageReview("b-old", "Cũ", "Mới", "older"))
            "good.abook" -> PreparedImport(null, item.source, bookId = "b-pack", notice = "Đã thêm “Gói”")
            else -> PreparedImport("ref-" + item.source, item.source, preview = ImportPreview("Sách thử", chapters = listOf(ImportChapter(1, "Chương 1"))))
        }
        override suspend fun revise(ref: String, choices: ImportChoices) = error("không dùng")
        override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean> { added += ref; return "b-$ref" to false }
        override suspend fun discard(ref: String) { discarded += ref }
        override suspend fun replace(item: ImportItem, progress: WorkSink): PreparedImport = error("lượt này không phải gói: ${item.source}")
    }

    @Test fun a_broken_book_file_then_a_valid_txt_adds_the_txt_with_its_own_staging() {
        val fake = Fake()
        val queue = ImportQueue(fake, scope)
        queue.enqueue(listOf("bad.abook"))
        assertEquals(ImportStage.Error, queue.state.value.items[0].stage)
        queue.enqueue(listOf("good.txt"))
        val review = queue.state.value
        assertEquals(ImportStage.Review, review.items[1].stage)
        assertNull(review.packageReview)
        assertEquals("", review.problem)
        queue.add()
        assertEquals(listOf("ref-good.txt"), fake.added)
        assertEquals(ImportStage.Added, queue.state.value.items[1].stage)
        assertEquals("", queue.state.value.problem)
    }

    @Test fun a_broken_txt_then_a_valid_book_file_adds_the_book() {
        val fake = Fake()
        val queue = ImportQueue(fake, scope)
        queue.enqueue(listOf("bad.txt"))
        assertEquals(ImportStage.Error, queue.state.value.items[0].stage)
        queue.enqueue(listOf("good.abook"))
        val done = queue.state.value
        assertEquals(ImportStage.Added, done.items[1].stage)
        assertEquals("b-pack", done.items[1].bookId)
        assertNull(done.preview)
        assertEquals("", done.problem)
    }

    @Test fun a_book_file_waiting_for_a_choice_never_makes_the_next_txt_a_replacement() {
        val fake = Fake()
        val queue = ImportQueue(fake, scope)
        queue.enqueue(listOf("older.abook", "good.txt"))
        assertEquals("older", queue.state.value.packageReview?.how)
        queue.keepPackage()
        val review = queue.state.value
        assertEquals(ImportStage.Existing, review.items[0].stage)
        assertNull(review.packageReview)
        assertEquals(ImportStage.Review, review.items[1].stage)
        // "Thêm" của TXT thêm TXT bằng bản tạm của chính nó - không đi đường "Thay bằng file này" của gói trước.
        queue.add()
        assertEquals(listOf("ref-good.txt"), fake.added)
        assertEquals(ImportStage.Added, queue.state.value.items[1].stage)
    }

    @Test fun skipping_a_txt_discards_only_its_own_staging() {
        val fake = Fake()
        val queue = ImportQueue(fake, scope)
        queue.enqueue(listOf("one.txt", "bad.abook", "two.txt"))
        queue.skip()
        assertEquals(listOf("ref-one.txt"), fake.discarded)
        assertEquals(ImportStage.Error, queue.state.value.items[1].stage)
        assertEquals(ImportStage.Review, queue.state.value.items[2].stage)
        queue.add()
        assertEquals(listOf("ref-two.txt"), fake.added)
    }
}
