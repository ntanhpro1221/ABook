package vn.abook.player.ui.nowplaying

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.BookActions
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.ui.data.PlayerChapter

/** Read-along text and voices from the core, never on the main thread except the engine's own snapshot call (the caller's context, as the engine expects). */
class AndroidReadAlongSource(context: Context) : ReadAlongSource {
    private val app = context.applicationContext

    override suspend fun paragraphs(bookId: String, chapter: PlayerChapter): List<ReadParagraph> {
        if (chapter.textPath.isNotEmpty()) {
            // Active chapter: use the engine's exact loaded paragraphs and virtual timeline, including live tail clips.
            val active = ReadAloud.script(bookId, chapter.id)
            return withContext(Dispatchers.Default) { ReadAlongLookup.parse(active) }
        }
        return withContext(Dispatchers.IO) {
            val raw = BookActions.text(app, bookId, "scripts/${chapter.id}.json") ?: error("Bạn cần tải chữ của chương.")
            ReadAlongLookup.parse(JSONObject(raw))
        }
    }

    override suspend fun voices(): List<PlayerVoice> =
        // Online voices stay with the existing consent / settings flow; the picker lists the installed ones.
        withContext(Dispatchers.IO) {
            ReadAloud.voices(app).filter { !it.optBoolean("online") }.map { PlayerVoice(it.optString("id"), it.optString("name")) }
        }
}
