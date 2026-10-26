package vn.abook.player.ui.editbook

import kotlinx.coroutines.CoroutineScope
import vn.abook.player.ui.data.ListenBook

class EditBooks(private val source: EditSource, private val scope: CoroutineScope) {
    private val sessions = LinkedHashMap<String, BookEditor>()
    fun refresh(id: String) { sessions[id]?.reload() }
    fun session(book: ListenBook, demo: Boolean = false): BookEditor = sessions.getOrPut(book.id) {
        BookEditor(book.id, if (demo) DemoEdits(book) else source, scope)
    }
}

/** Explicit benchmark library has no disk writes, matching the existing demo Library/Player path. */
private class DemoEdits(book: ListenBook) : EditSource {
    private var saved = EditSnapshot(book.id, book.title, book.author,
        (1..book.chaptersTotal).map { EditChapter(it.toLong(), "Chương $it") }, book.cover, book.textOnly)
    override suspend fun load(id: String) = saved
    override suspend fun save(id: String, diff: EditDiff): EditSnapshot {
        saved = saved.copy(title = diff.title ?: saved.title, author = diff.author ?: saved.author,
            chapters = saved.chapters.map { row -> diff.chapters.firstOrNull { it.id == row.id } ?: row })
        return saved
    }
    override suspend fun cover(id: String, image: ByteArray?) = saved
    override suspend fun revertChapter(id: String, chapterId: Long) = saved
    override suspend fun send(id: String) = saved
}
