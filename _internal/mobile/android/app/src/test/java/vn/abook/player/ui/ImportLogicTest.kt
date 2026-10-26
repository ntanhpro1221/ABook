package vn.abook.player.ui

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.addbook.*

class ImportLogicTest {
    private val preview = ImportPreview("Truyện", chapters = listOf(
        ImportChapter(1, "Bìa", false), ImportChapter(2, "Chương 1"), ImportChapter(3, "Chương 2"),
    ), suggestions = listOf(Suggestion(3, "Dịch: Nhóm Lục Bình")))

    @Test fun defaultsExcludeMatterAndNeverAcceptSuggestions() {
        val choice = ImportLogic.defaults(preview)
        assertEquals(setOf(2, 3), choice.picked)
        assertTrue(choice.skipped.isEmpty())
        assertFalse(choice.hideMarks)
        assertEquals("", choice.notes)
        assertFalse(choice.split)
        assertEquals(emptyList<SuggestionGroup>(), ImportLogic.accepted(preview, choice))
    }

    @Test fun picksAlwaysExplicitAndFollowSourceOrder() {
        val choice = ImportChoices(picked = setOf(3, 1), names = mapOf(2 to "Bỏ", 3 to "Khách lạ"))
        assertEquals(listOf(1 to "", 3 to "Khách lạ"), ImportLogic.picks(preview, choice))
        assertEquals(emptyList<Pair<Int, String>>(), ImportLogic.picks(preview, choice.copy(picked = emptySet())))
    }

    @Test fun suggestionsAreGroupedInFirstOccurrenceOrderAndAllMustBeSkipped() {
        val rows = listOf(Suggestion(2, "Dịch", true), Suggestion(3, "Nguồn", true), Suggestion(4, "Dịch"))
        assertEquals(listOf(SuggestionGroup("Dịch", listOf(2, 4), false), SuggestionGroup("Nguồn", listOf(3), true)), ImportLogic.groups(rows))
    }

    @Test fun acceptedSuggestionsRenumberOnlyIncludedChapters() {
        val choice = ImportLogic.defaults(preview).copy(skipped = setOf("Dịch: Nhóm Lục Bình"))
        assertEquals(listOf(SuggestionGroup("Dịch: Nhóm Lục Bình", listOf(2), true)), ImportLogic.accepted(preview, choice))
        assertTrue(ImportLogic.accepted(preview, choice.copy(picked = setOf(2))).isEmpty())
        assertEquals(listOf(1), ImportLogic.accepted(preview, choice.copy(picked = setOf(3))).single().chapters)
    }

    @Test fun rereadingFootnotesRetainsPicksAndNamesForSameRows() {
        val choice = ImportLogic.defaults(preview).copy(names = mapOf(2 to "Tên riêng"), hideMarks = true)
        assertEquals(choice, ImportLogic.retain(preview.copy(footnoteMarks = 4), preview, choice))
        val changed = preview.copy(chapters = preview.chapters.drop(1))
        assertTrue(ImportLogic.retain(changed, preview, choice).names.isEmpty())
    }

    @Test fun settlingDoesNotMutateOrReorderIncludingPackages() {
        val items = listOf(ImportItem(1, "a.abook"), ImportItem(2, "b.epub"), ImportItem(3, "c.txt"))
        val next = ImportLogic.settle(items, 2, ImportStage.Error, "Hỏng")
        assertEquals(listOf(1L, 2L, 3L), next.map { it.id })
        assertEquals(ImportStage.Waiting, items[1].stage)
        assertEquals("Hỏng", next[1].problem)
        assertEquals(1L, ImportLogic.next(next)?.id)
    }

    @Test fun queueErrorContinuesThenRetryKeepsIdentityAndOrder() = runBlocking {
        val source = FakeImportSource(preview)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val queue = ImportQueue(source, scope)
        source.fail = "bad"
        queue.enqueue(listOf("bad", "good", "third.abook"))
        assertEquals(listOf("bad", "good"), source.read)
        assertEquals(ImportStage.Error, queue.state.value.items[0].stage)
        assertEquals(2L, queue.state.value.currentId)
        queue.skip()
        assertEquals(3L, queue.state.value.currentId)
        queue.skip()
        source.fail = null
        queue.retry(1)
        assertEquals(1L, queue.state.value.currentId)
        assertEquals(listOf(1L, 2L, 3L), queue.state.value.items.map { it.id })
        scope.cancel()
    }

    @Test fun queueHasOneParsedBookAndCannotWriteUntilUserAdds() = runBlocking {
        val source = FakeImportSource(preview)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val queue = ImportQueue(source, scope)
        queue.enqueue(listOf("one", "two"))
        assertEquals(listOf("one"), source.read)
        assertEquals(listOf("one", "two"), queue.state.value.items.map { it.name })
        assertEquals(0, source.adds)
        queue.choose { it.copy(skipped = setOf("Dịch: Nhóm Lục Bình")) }
        assertEquals(0, source.adds)
        queue.add()
        assertEquals(1, source.adds)
        assertEquals(setOf("Dịch: Nhóm Lục Bình"), source.addedChoices?.skipped)
        assertEquals(listOf("one", "two"), source.read)
        scope.cancel()
    }

    @Test fun latePreviewCannotOverwriteActiveItemBecauseQueueWaitsForDecision() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val result = CompletableDeferred<PreparedImport>()
        val source = object : ImportSource by FakeImportSource(preview) {
            override suspend fun prepare(item: ImportItem) = result.await()
        }
        val queue = ImportQueue(source, scope)
        queue.enqueue(listOf("one"))
        queue.enqueue(listOf("two"))
        assertEquals(1L, queue.state.value.currentId)
        result.complete(PreparedImport("ref", "One", preview))
        assertEquals(1L, queue.state.value.currentId)
        assertEquals(ImportStage.Waiting, queue.state.value.items[1].stage)
        scope.cancel()
    }
}

internal class FakeImportSource(private val preview: ImportPreview) : ImportSource {
    var fail: String? = null
    val read = mutableListOf<String>()
    var adds = 0
    var addedChoices: ImportChoices? = null
    override suspend fun describe(item: ImportItem) = item.source
    override suspend fun prepare(item: ImportItem): PreparedImport {
        read += item.source
        if (item.source == fail) error("Bạn hãy tải lại file.")
        return PreparedImport("ref${item.id}", item.source, preview)
    }
    override suspend fun revise(ref: String, choices: ImportChoices) = preview
    override suspend fun add(ref: String, preview: ImportPreview, choices: ImportChoices): Pair<String, Boolean> {
        adds++
        addedChoices = choices
        return "book" to false
    }
    override suspend fun discard(ref: String) = Unit
}
