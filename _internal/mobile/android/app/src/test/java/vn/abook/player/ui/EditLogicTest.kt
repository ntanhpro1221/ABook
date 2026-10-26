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

    // ---- Bỏ mọi thay đổi ----

    @Test fun discardAllDropsTypedTextAndReturnsToThePackagedBook() = runBlocking {
        val source = FakeEditSource(saved.copy(title = "Tên đã sửa", edits = 2))
        source.original = saved
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        editor.change { it.copy(author = "Đang gõ dở") }
        var result: String? = "chưa gọi"
        editor.discardAll { result = it }
        assertNull(result)
        assertEquals(1, source.discards)
        assertEquals(saved, editor.state.value.saved)
        assertEquals(EditLogic.draft(saved), editor.state.value.draft)
        // Lần gõ dở đã bị bỏ: hết hạn chờ cũng không ghi lại nó.
        delay(600)
        assertEquals(emptyList<EditDiff>(), source.saves)
        scope.cancel()
    }

    @Test fun discardAllFailureKeepsTheBookAndSaysSo() = runBlocking {
        val edited = saved.copy(title = "Tên đã sửa", edits = 1)
        val source = FakeEditSource(edited)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        source.fail = true
        var result: String? = null
        editor.discardAll { result = it }
        assertEquals("Chưa bỏ được thay đổi", result)
        assertEquals(edited, editor.state.value.saved)
        scope.cancel()
    }

    // ---- Cách đọc tên ----

    @Test fun spokenTextIsCleanedLikeTheWebAndSaveNeedsARealChange() {
        assertEquals("Ha-ru-tô Sa", ReadingText.spoken("  Ha-ru-tô \t  Sa \n"))
        assertFalse(ReadingText.canSave("Haruto", "", "   "))
        assertFalse(ReadingText.canSave("Haruto", "Ha-ru-tô", " Ha-ru-tô "))
        assertFalse(ReadingText.canSave("Haruto", "", "Haruto"))
        assertTrue(ReadingText.canSave("Haruto", "Ha-ru-tô", "Ha-ru-to"))
        assertEquals("“Haruto” sẽ đọc là “Ha-ru-tô” từ đoạn sau", ReadingText.saved("Haruto", "Ha-ru-tô"))
        assertEquals("“Haruto” đọc lại như chữ trong sách từ đoạn sau", ReadingText.saved("Haruto", ""))
    }

    @Test fun readingsLoadSaveAndRemoveThroughTheSource() = runBlocking {
        val source = FakeEditSource(saved)
        source.words["Haruto"] = "Ha-ru-tô"
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        assertFalse(editor.readings.value.loaded)
        editor.loadReadings()
        assertEquals(listOf(WordReading("Haruto", "Ha-ru-tô")), editor.readings.value.list)
        var closed = 0
        editor.setReading("Hạ Vy", "  Hạ   Vi ") { closed++ }
        assertEquals("Hạ Vy" to "Hạ Vi", source.readingCalls.last())
        assertEquals(1, closed)
        assertEquals("“Hạ Vy” sẽ đọc là “Hạ Vi” từ đoạn sau", editor.readings.value.notice)
        // Số thay đổi của sách đọc lại sau mỗi lần lưu ("Bỏ mọi thay đổi (N)").
        assertEquals(2, editor.state.value.saved?.edits)
        editor.setReading("Haruto", "")
        assertEquals(listOf(WordReading("Hạ Vy", "Hạ Vi")), editor.readings.value.list)
        scope.cancel()
    }

    @Test fun readingFailuresAreNamedByWhatWasAttempted() = runBlocking {
        val source = FakeEditSource(saved)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        source.fail = true
        editor.loadReadings()
        assertEquals("Bạn hãy thử tải lại danh sách cách đọc.", editor.readings.value.problem)
        assertFalse(editor.readings.value.loaded)
        var closed = 0
        editor.setReading("Haruto", "Ha-ru-tô") { closed++ }
        assertEquals("Chưa lưu được cách đọc", editor.readings.value.failed)
        editor.setReading("Haruto", "")
        assertEquals("Chưa bỏ được cách đọc", editor.readings.value.failed)
        assertEquals(0, closed)
        assertFalse(editor.readings.value.saving)
        scope.cancel()
    }

    // ---- Tìm ảnh bìa ----

    private val found = listOf(
        FoundCover("Open Library", "Tắt đèn", "Ngô Tất Tố", "https://covers.openlibrary.org/b/id/1-M.jpg", "https://covers.openlibrary.org/b/id/1-L.jpg"),
        FoundCover("Google Books", "Tắt đèn (bản in lại)", "", "https://books.google.com/t2", "https://books.google.com/f2"),
    )

    @Test fun openingTheSearchAsksWithTheBookNameAndALaterSearchReplacesIt() = runBlocking {
        val source = FakeEditSource(saved)
        source.covers = CoverResults("", found)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        editor.openCoverSearch("Tắt đèn")
        assertEquals(listOf("Tắt đèn"), source.queries)
        assertEquals(found, editor.covers.value.shown)
        assertFalse(editor.covers.value.nothing)
        editor.setCoverQuery("Tat den")
        source.covers = CoverResults("", emptyList())
        editor.searchCovers()
        assertEquals("Tat den", source.queries.last())
        // Không ảnh nào mà mọi nguồn đã trả lời: mời chọn ảnh trên máy.
        assertTrue(editor.covers.value.nothing)
        source.covers = CoverResults("", emptyList(), failed = listOf("google_books"))
        editor.searchCovers()
        assertFalse(editor.covers.value.nothing)
        source.coverFail = true
        editor.searchCovers()
        assertTrue(editor.covers.value.error)
        assertFalse(editor.covers.value.nothing)
        scope.cancel()
    }

    @Test fun choosingACoverSetsItAndAFailureOffersTheSameCoverAgain() = runBlocking {
        val source = FakeEditSource(saved)
        source.covers = CoverResults("", found)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        editor.openCoverSearch("Tắt đèn")
        source.coverFail = true
        var done = 0
        editor.chooseCover(found[0]) { done++ }
        assertEquals(found[0], editor.covers.value.unset)
        assertNull(editor.covers.value.choosing)
        assertEquals(0, done)
        source.coverFail = false
        editor.chooseCover(found[0]) { done++ }
        assertEquals(listOf(found[0].url), source.chosen)
        assertEquals(1, done)
        assertNull(editor.covers.value.unset)
        assertNotNull(editor.state.value.saved?.cover)
        scope.cancel()
    }

    @Test fun aThumbnailThatDoesNotLoadLeavesTheGrid() = runBlocking {
        val source = FakeEditSource(saved)
        source.covers = CoverResults("", found)
        // JVM thuần (không Robolectric): không dựng ảnh thật; ảnh tải được thì giữ ô (BookFormsTest vẽ lưới có ảnh).
        source.thumbs = { null }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val editor = BookEditor("b", source, scope)
        editor.openCoverSearch("Tắt đèn")
        assertNull(editor.thumbnail(found[1].thumb))
        assertEquals(listOf(found[0]), editor.covers.value.shown)
        // Lượt tìm mới thì ảnh hỏng lần trước được thử lại.
        editor.searchCovers()
        assertEquals(found, editor.covers.value.shown)
        scope.cancel()
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

    // "Bỏ mọi thay đổi", "Cách đọc tên", "Tìm ảnh bìa": cùng lõi giả, ghi lại lời gọi để test so.
    var original: EditSnapshot = snapshot
    var discards = 0
    override suspend fun discardAll(id: String): EditSnapshot {
        if (fail) error("Không ghi được file")
        discards++
        snapshot = original
        words.clear()
        return snapshot
    }

    val words = linkedMapOf<String, String>()
    val readingCalls = mutableListOf<Pair<String, String>>()
    override suspend fun readings(id: String): List<WordReading> {
        if (fail) error("Không đọc được")
        return words.map { (surface, spoken) -> WordReading(surface, spoken) }
    }
    override suspend fun setReading(id: String, surface: String, spoken: String): List<WordReading> {
        if (fail) error("Không ghi được file")
        readingCalls += surface to spoken
        if (spoken.isEmpty()) words.remove(surface) else words[surface] = spoken
        snapshot = snapshot.copy(edits = words.size)
        return readings(id)
    }

    var covers = CoverResults("", emptyList())
    var coverFail = false
    val queries = mutableListOf<String>()
    val chosen = mutableListOf<String>()
    var thumbs: (String) -> androidx.compose.ui.graphics.ImageBitmap? = { androidx.compose.ui.graphics.ImageBitmap(2, 3) }
    override suspend fun findCovers(id: String, query: String): CoverResults {
        queries += query
        if (coverFail) error("Mất mạng")
        return covers.copy(query = query)
    }
    override suspend fun coverFromUrl(id: String, url: String): EditSnapshot {
        if (coverFail) error("Mất mạng")
        chosen += url
        snapshot = snapshot.copy(cover = vn.abook.player.ui.data.CoverRef("edits/cover.jpg", chosen.size.toLong()), edits = snapshot.edits + 1)
        return snapshot
    }
    override suspend fun thumbnail(url: String) = thumbs(url)
}
