package vn.abook.player.ui.music.library

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.MusicLibrary
import vn.abook.player.S
import vn.abook.player.formatSize
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.motion.ContentLayout
import vn.abook.player.ui.motion.SwapContent

/**
 * Built on IO, including joins, saved membership and byte totals. Drawing only visits visible rows.
 * Every track the book uses has a row, in listening order: catalog tracks join the library index; the rest (`local:` tracks packaged with the
 * book, or a link the catalog does not know) are [bundled] rows named from book.json - no preview, no save, never in "Lưu tất cả".
 */
data class BookMusicRows(
    val tracks: List<Pair<MusicLibrary.Track, MusicLibrary.BookTrack>>,
    val unsaved: List<String>,
    val missingBytes: Long,
    val bundled: Set<String> = emptySet(),
) {
    companion object {
        /** `index` null: the catalog is not needed (no catalog link in the book) or not loaded - every row is bundled. */
        fun build(entries: List<MusicLibrary.BookTrack>, index: LibraryIndex?, saved: List<String>, downloaded: Set<String>): BookMusicRows {
            val kept = saved.toHashSet()
            val bundled = HashSet<String>()
            val tracks = entries.map { entry ->
                (index?.byLink?.get(entry.link) ?: bundledTrack(entry).also { bundled += entry.link }) to entry
            }
            val unsaved = tracks.map { it.first }.filter { it.link !in bundled && it.link !in kept }
            return BookMusicRows(tracks, unsaved.map { it.link }, unsaved.filter { it.link !in downloaded }.sumOf { it.bytes }, bundled)
        }

        private fun bundledTrack(entry: MusicLibrary.BookTrack) =
            MusicLibrary.Track(entry.link, JSONObject().put("title", entry.title).put("creator", entry.creator))
    }
}

/** The book's Music tab contributes lazy rows, never a whole eagerly measured Column. */
@Composable
fun BookMusicSection(
    state: LibraryState,
    sheets: SheetHost,
    entries: Result<List<MusicLibrary.BookTrack>>?,
    moods: Map<String, Map<String, Double>> = emptyMap(),
    retry: () -> Unit,
): LazyListScope.() -> Unit {
    val ui by state.ui.collectAsState()
    val found = entries?.getOrNull()
    val snapshot = ui
    LaunchedEffect(state, found != null) { if (!found.isNullOrEmpty()) state.open() }
    // Only catalog links wait for (or fail with) the library index; a book of packaged tracks lists them straight away.
    val needsCatalog = found?.any { MusicLibrary.inCatalog(it.link) } == true
    val rows by produceState<BookMusicRows?>(null, found, ui.index, ui.saved, ui.downloaded) {
        val index = ui.index
        if (found != null && (index != null || !needsCatalog)) value = withContext(Dispatchers.IO) { BookMusicRows.build(found, index, snapshot.saved, snapshot.downloaded) }
    }
    val failed = entries?.isFailure == true || (needsCatalog && ui.error.isNotEmpty())
    val empty = found?.isEmpty() == true
    return {
        item(key = "book_music_heading", contentType = "heading") { SectionTitle(S.s_nhac_trong_sach_9070d53a) }
        when {
            failed -> item(key = "book_music_error", contentType = "status") {
                Column(Modifier.testTag("book_music_error")) {
                    Caption(S.s_chua_tai_duoc_kho_nhac_9577b7c7)
                    QuietButton(S.s_thu_lai_c58d068c, retry, "book_music_retry")
                }
            }
            empty -> item(key = "book_music_empty", contentType = "status") { Caption(S.s_chua_co_nhac_ed5dc66e, Modifier.testTag("book_music_empty")) }
            entries == null || (needsCatalog && ui.loading) || rows == null -> item(key = "book_music_loading", contentType = "status") { Caption(S.s_dang_tai_465b1987, Modifier.testTag("book_music_loading")) }
            else -> {
                val ready = checkNotNull(rows)
                items(ready.tracks, key = { "book_music_${it.first.link}" }, contentType = { "music_track" }) { (track, entry) ->
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            val mood = entry.scene?.let(moods::get).orEmpty()
                            SwapContent(track.link in ready.bundled, contentKey = { bundled -> bundled }, layout = ContentLayout.Column, modifier = Modifier.weight(1f)) { bundled ->
                                if (bundled) BundledTrackRow(track) { openBundledTrack(sheets, state, track, mood) }
                                else TrackRow(track, ui, state, onOpen = { openTrack(sheets, state, track.link, null, mood) })
                            }
                            Caption(S.s_0_doan_c2eb5200(entry.scenes), Modifier.padding(start = Dim.s8))
                        }
                        RowLine(start = Dim.s48)
                    }
                }
                if (ready.unsaved.isNotEmpty()) item(key = "book_music_save_all", contentType = "action") {
                    QuietButton(S.s_luu_tat_ca_0_e16e7860(formatSize(ready.missingBytes)), { state.save(ready.unsaved) }, "book_music_save_all")
                }
            }
        }
    }
}
