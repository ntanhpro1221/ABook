package vn.abook.player.ui

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.editbook.*

class EditLogicTest {
    private val saved = EditSnapshot("b", "Tên sách", "Nguyễn Nhật Ánh", listOf(EditChapter(1, "Chương 1", "Mở đầu")))

    @Test fun authorWhitespaceIsNoChangeAsInWebCases() {
        assertTrue(EditLogic.diff(saved, EditLogic.draft(saved).copy(author = "  Nguyễn   Nhật Ánh ")).empty)
        assertEquals("", EditLogic.diff(saved, EditLogic.draft(saved).copy(author = "")).author)
        assertTrue(EditLogic.diff(saved.copy(author = ""), EditLogic.draft(saved).copy(author = "   ")).empty)
    }

    @Test fun titleAndChapterDiffsIgnoreWhitespaceButKeepTypedText() {
        val draft = EditLogic.draft(saved).copy(title = "Tên mới", chapters = listOf(EditChapter(1, " Chương 1 ", "Mưa")))
        val diff = EditLogic.diff(saved, draft)
        assertEquals("Tên mới", diff.title)
        assertNull(diff.author)
        assertEquals(listOf(EditChapter(1, " Chương 1 ", "Mưa")), diff.chapters)
        assertEquals("Tên sách", saved.title)
    }

    @Test fun syncRefreshKeepsUnwrittenFieldsAndTakesOtherFieldsFromHolder() {
        val draft = EditLogic.draft(saved).copy(author = "Đang gõ")
        val latest = saved.copy(title = "Tên ở máy tính", chapters = listOf(EditChapter(1, "Chương một", "Mưa")))
        val rebased = EditLogic.rebase(saved, draft, latest)
        assertEquals("Đang gõ", rebased.author)
        assertEquals("Tên ở máy tính", rebased.title)
        assertEquals(latest.chapters, rebased.chapters)
        assertEquals(EditDiff(author = "Đang gõ"), EditLogic.diff(latest, rebased))
    }

    @Test fun invalidNamesAreReportedWithoutTruncating() {
        assertNotNull(EditLogic.validate(EditDiff(title = " ")))
        assertNotNull(EditLogic.validate(EditDiff(title = "a".repeat(161))))
        assertNull(EditLogic.validate(EditDiff(author = "")))
        assertNull(EditLogic.validate(EditDiff(title = "a".repeat(160))))
    }

    @Test fun cropIsTwoByThreeAndNeverLeavesImageAtEveryEdge() {
        for ((width, height) in listOf(3000 to 500, 500 to 3000, 800 to 1200, 1 to 1)) {
            for (zoom in listOf(0.2f, 1f, 2f, 8f)) for (pan in listOf(-5f, 0f, 5f)) {
                val rect = CropLogic.rect(width, height, CropChoice(zoom, pan, pan))
                assertTrue(rect.left >= 0 && rect.top >= 0)
                assertTrue(rect.left + rect.width <= width && rect.top + rect.height <= height)
                if (rect.width > 1) assertEquals(1.5f, rect.height.toFloat() / rect.width, 0.04f)
            }
        }
    }

    @Test fun immediateBackCanFlushBeforeDebounceAndDoesNotLoseOtherFields() = runBlocking {
        val source = FakeEditSource(saved)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        editor.change { it.copy(title = "Tên mới", author = "") }
        assertTrue(editor.flush())
        assertEquals("Tên mới", source.snapshot.title)
        assertEquals("", source.snapshot.author)
        scope.cancel()
    }

    @Test fun typingDuringWriteIsKeptAndNextWriteSavesIt() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        val source = FakeEditSource(saved)
        val blocking = object : EditSource by source {
            override suspend fun save(id: String, diff: EditDiff): EditSnapshot { gate.await(); return source.save(id, diff) }
        }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", blocking, scope)
        editor.change { it.copy(title = "A") }
        val writing = scope.launch { editor.flush() }
        editor.change { it.copy(title = "B") }
        gate.complete(Unit)
        writing.join()
        assertEquals("B", editor.state.value.draft?.title)
        editor.flush()
        assertEquals("B", source.snapshot.title)
        scope.cancel()
    }

    @Test fun onlyChangedFieldsAreSaved() = runBlocking {
        val source = FakeEditSource(saved)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        // Khoảng trắng đổi chứ chữ không đổi: không ghi gì.
        editor.change { it.copy(author = "  Nguyễn  Nhật Ánh ", title = " Tên sách") }
        assertTrue(editor.flush())
        assertEquals(emptyList<EditDiff>(), source.saves)
        // Chỉ tên đổi: chỉ tên được ghi, tác giả và chương không có mặt trong lần ghi.
        editor.change { it.copy(title = "Tên mới") }
        assertTrue(editor.flush())
        assertEquals(listOf(EditDiff(title = "Tên mới")), source.saves)
        scope.cancel()
    }

    @Test fun cropGestureKeepsTheWindowCenterAndStaysInsideTheImage() {
        val start = CropChoice(1f, 0f, 0f)
        val before = CropLogic.rect(3000, 500, start)
        val zoomed = CropLogic.transform(3000, 500, start, 0f, 0f, 2f)
        val after = CropLogic.rect(3000, 500, zoomed)
        assertEquals(2f, zoomed.zoom, 0f)
        assertEquals(before.left + before.width / 2f, after.left + after.width / 2f, 2f)
        val dragged = CropLogic.transform(3000, 500, zoomed, 100000f, -100000f, 1f)
        val far = CropLogic.rect(3000, 500, dragged)
        assertTrue(far.left + far.width <= 3000 && far.top >= 0)
        assertEquals(1f, CropLogic.transform(800, 1200, start, 5f, 5f, 0.1f).zoom, 0f)
    }

    @Test fun failedSaveKeepsDraftAndRetrySendsExactDiff() = runBlocking {
        val source = FakeEditSource(saved)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        source.fail = true
        editor.change { it.copy(author = "Nam Cao") }
        assertFalse(editor.flush())
        assertEquals("Nam Cao", editor.state.value.draft?.author)
        source.fail = false
        assertTrue(editor.flush())
        assertEquals("Nam Cao", source.snapshot.author)
        scope.cancel()
    }
}

internal class FakeEditSource(var snapshot: EditSnapshot) : EditSource {
    var fail = false
    val saves = mutableListOf<EditDiff>()
    override suspend fun load(id: String) = snapshot
    override suspend fun save(id: String, diff: EditDiff): EditSnapshot {
        if (fail) error("Không ghi được file")
        saves += diff
        snapshot = snapshot.copy(title = diff.title ?: snapshot.title, author = diff.author ?: snapshot.author,
            chapters = snapshot.chapters.map { old -> diff.chapters.firstOrNull { it.id == old.id } ?: old })
        return snapshot
    }
    override suspend fun cover(id: String, image: ByteArray?) = snapshot
    override suspend fun revertChapter(id: String, chapterId: Long) = snapshot
    override suspend fun send(id: String) = snapshot
}
