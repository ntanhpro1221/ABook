package vn.abook.player.ui.music.library

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.MusicLibrary
import vn.abook.player.S
import vn.abook.player.formatSize
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.theme.Dim

/**
 * Phần "Nhạc trong sách" của trang sách: các bài của danh mục cuốn này dùng (gộp trùng, số đoạn mỗi bài) + "Lưu tất cả (X)" - lưu = ghim + tải
 * về máy, nghe không mạng. Chạm bài mở chi tiết. `scenes`: (khoá đoạn, link) theo thứ tự nghe. Không có bài nào của danh mục thì không hiện gì.
 */
@Composable
fun BookMusicSection(state: LibraryState, sheets: SheetHost, scenes: List<Pair<String?, String>>, modifier: Modifier = Modifier) {
    val ui by state.ui.collectAsState()
    LaunchedEffect(state) { state.open() }
    val entries = remember(scenes) { MusicLibrary.bookTracks(scenes) }
    val index = ui.index ?: return
    val tracks = entries.mapNotNull { entry -> index.byLink[entry.link]?.let { it to entry } }
    if (tracks.isEmpty()) return
    val unsaved = tracks.map { it.first }.filter { it.link !in ui.savedSet }
    Column(modifier.fillMaxWidth().testTag("book_music")) {
        SectionTitle(S.s_nhac_trong_sach_9070d53a)
        for ((track, entry) in tracks) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { TrackRow(track, ui, state, onOpen = { openTrack(sheets, state, track.link, null) }) }
                Caption(S.s_0_doan_c2eb5200(entry.scenes), Modifier.padding(start = Dim.s8))
            }
            RowLine(start = Dim.s48)
        }
        if (unsaved.isNotEmpty()) {
            QuietButton(S.s_luu_tat_ca_0_e16e7860(formatSize(ui.missingBytes(unsaved))), { state.save(unsaved.map { it.link }) }, "book_music_save_all")
        }
    }
}
