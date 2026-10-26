package vn.abook.player

import android.content.Context

/** The same overlaid local/streamed text used by LibraryPlugin.readText, available without Capacitor.
 * Call on IO: fetching a missing small script may use the paired computer. */
object ChapterText {
    fun read(context: Context, bookId: String, path: String): String? {
        val file = Store.file(bookId, path)
        val fromPeer = !Store.streamManifest(bookId)?.optString("source").isNullOrEmpty()
        if (!file.isFile && Store.rawManifest(bookId) == null && (fromPeer || SyncLink.paired(context))) {
            Streaming.fetchSmall(context, bookId, path)
        }
        return Store.readText(bookId, path)
    }
}
