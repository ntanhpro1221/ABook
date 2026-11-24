package vn.abook.player.ui.music.library

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import vn.abook.player.MusicLibrary
import vn.abook.player.S
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Shared by the library, saved tracks and book music. Details retain the full title and style. */
@Composable
fun TrackRow(track: MusicLibrary.Track, ui: LibraryUi, state: LibraryState, pick: PickTarget? = null, onOpen: () -> Unit) {
    val colors = Abook.colors
    val playing = ui.previewing == track.link
    val canPlay = ui.online || track.link in ui.downloaded
    Column(Modifier.fillMaxWidth()) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 64.dp).pressable(onClick = onOpen).padding(vertical = Dim.s8).testTag("track_${track.link.hashCode()}"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        MusicArt(track)
        Spacer(Modifier.width(Dim.s8))
        Box(
            Modifier.size(40.dp).then(if (canPlay) Modifier.pressable { state.togglePreview(track.link) } else Modifier.semantics { disabled() })
                .semantics { contentDescription = if (playing && ui.previewLoading) S.s_buffering else if (playing && !ui.previewPaused) S.s_tam_dung_67635815 else S.s_nghe_thu_fa024065 }
                .testTag("preview_${track.link.hashCode()}"), contentAlignment = Alignment.Center,
        ) { PendingIndicator(playing && ui.previewLoading) {
            LucideIcon(if (playing && !ui.previewPaused) LucidePaths.PAUSE else LucidePaths.PLAY, if (!canPlay) colors.text3 else if (playing) colors.accentText else colors.text)
        } }
        Spacer(Modifier.width(Dim.s8))
        Column(Modifier.weight(1f)) {
            // cắt-có-chủ-ý: owner requests at most two title lines in music rows; the sheet shows the full title.
            BasicText(track.title.ifEmpty { track.link.substringAfterLast('/') }, style = Abook.type.bodyStrong, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.testTag("music_row_title"))
            Spacer(Modifier.height(2.dp))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                SwapContent(track, contentKey = { track -> track.creator.isNotEmpty() }, layout = ContentLayout.Row, modifier = Modifier.weight(1f, fill = false)) { track ->
                    if (track.creator.isNotEmpty()) {
                        // cắt-có-chủ-ý: only the creator yields space to the duration; the entire metadata line stays on one line.
                        BasicText(track.creator, style = Abook.type.bodySmall.copy(color = colors.text2), maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis, modifier = Modifier.testTag("music_row_creator"))
                    }
                }
                (ui.active[track.link]?.percent?.let { S.s_dang_tai_0_e9a97892(it) } ?: if (track.link in ui.failed) S.s_chua_tai_xong_b257419d else track.duration?.let(Fmt::clock))?.let {
                    Reveal(track.creator.isNotEmpty()) { BasicText("·", style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.padding(horizontal = Dim.s8)) }
                    ClockLabel(it, Modifier.testTag("music_row_duration"), Abook.type.bodySmall.copy(color = if (track.link in ui.failed) colors.danger else colors.text2))
                }
            }
        }
        ChevronIcon(colors.text3)
        SwapContent(pick, contentKey = { pick -> pick != null }, layout = ContentLayout.Row) { pick ->
            if (pick != null) TextAction(S.s_dung_7927ca4e, { pick.onUse(track.link) }, "use_${track.link.hashCode()}", Modifier.padding(start = Dim.s8))
        }
        DownloadControl(track, ui, state, Modifier.padding(start = Dim.s8))
    }
    // The listening bar starts under the preview button (art 40 + gap 8), as on web and Qt.
    Reveal(playing) { ListeningProgress(ui, state, Modifier.padding(start = Dim.s48, bottom = Dim.s8)) }
    }
}

/** Every row reserves the same download column, including tracks that have not been downloaded. Download, stop and retry
 * are actions; "downloaded" is a status (no click): removing a download is "Xoá bản tải" in the track sheet, behind the confirmation. */
@Composable
private fun DownloadControl(track: MusicLibrary.Track, ui: LibraryUi, state: LibraryState, modifier: Modifier = Modifier) {
    val load = ui.active[track.link]
    val downloaded = track.link in ui.downloaded
    val failed = track.link in ui.failed
    // A removal runs (and shows its wait) in the track sheet's confirmation; the row only waits for its own download request.
    val pending = track.link in ui.pendingLinks && !downloaded
    val label = when {
        pending -> S.s_dang_tai_465b1987
        load != null -> S.s_stop_download
        downloaded -> S.s_da_tai_b7362bbf
        failed -> S.s_thu_lai_c58d068c
        else -> S.s_tai_ve_9b5bdb44
    }
    Box(
        modifier.size(Dim.touch).then(when {
            pending -> Modifier.semantics { disabled() }
            load != null -> Modifier.pressable { state.cancel(listOf(track.link)) }
            downloaded -> Modifier
            ui.online -> Modifier.pressable { state.save(listOf(track.link)) }
            else -> Modifier
        }).semantics { contentDescription = label }.testTag("download_${track.link.hashCode()}"),
        contentAlignment = Alignment.Center,
    ) {
        val waiting = pendingVisible(pending)
        StateIcon(when { waiting -> "pending"; load != null -> "loading"; downloaded -> "downloaded"; failed -> "failed"; else -> "download" }) { shown ->
            when (shown) {
                "pending" -> BusyRing()
                "loading" -> DownloadRing(load?.percent, load?.percent?.let { S.s_dang_tai_0_e9a97892(it) } ?: S.s_dang_tai_465b1987, Modifier.testTag("track_loading"))
                "downloaded" -> DownloadedIcon()
                else -> LucideIcon(LucidePaths.DOWNLOAD,
                    if (shown == "failed") Abook.colors.danger else if (!ui.online) Abook.colors.text3 else Abook.colors.text2)
            }
        }
    }
}

/**
 * "Nhạc trong sách": a track the catalog does not have (`local:` packaged with the book). The text column starts where [TrackRow]'s does so a mixed
 * list stays aligned: the preview slot carries a quiet book mark (nothing to preview or save), the creator line says "Đi kèm sách". There is
 * no download column: its width goes to the creator, which "Đi kèm sách" would otherwise squeeze. The row opens the bundled sheet (name, creator, the first scene's mood).
 */
@Composable
fun BundledTrackRow(track: MusicLibrary.Track, onOpen: () -> Unit) {
    val colors = Abook.colors
    Row(
        Modifier.fillMaxWidth().heightIn(min = 64.dp).pressable(onClick = onOpen).padding(vertical = Dim.s8).testTag("bundled_${track.link.hashCode()}"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        MusicArt(track)
        Spacer(Modifier.width(Dim.s8))
        Box(Modifier.size(40.dp), contentAlignment = Alignment.Center) { LucideIcon(LucidePaths.BOOK_AUDIO, colors.text3) }
        Spacer(Modifier.width(Dim.s8))
        Column(Modifier.weight(1f)) {
            // Book text is never cut in a new place (TextCutScanTest): a packaged track's title wraps in full.
            BasicText(track.title.ifEmpty { S.s_bai_nay_d9683a01 }, style = Abook.type.bodyStrong, modifier = Modifier.testTag("music_row_title"))
            Spacer(Modifier.height(2.dp))
            val small = Abook.type.bodySmall.copy(color = colors.text2)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                SwapContent(track, contentKey = { track -> track.creator.isNotEmpty() }, layout = ContentLayout.Row, modifier = Modifier.weight(1f, fill = false)) { track ->
                    if (track.creator.isNotEmpty()) {
                        // cắt-có-chủ-ý: only the creator yields space to "Đi kèm sách", as it does to the duration in TrackRow; the sheet shows it in full.
                        BasicText(track.creator, style = small, maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis, modifier = Modifier.testTag("music_row_creator"))
                    }
                }
                Reveal(track.creator.isNotEmpty()) { BasicText("·", style = small, modifier = Modifier.padding(horizontal = Dim.s8)) }
                // cắt-có-chủ-ý: short fixed app label kept on the creator line; it never truncates (no ellipsis), the creator yields instead.
                BasicText(S.s_bundled_track, style = small, maxLines = 1, softWrap = false, modifier = Modifier.testTag("music_row_bundled"))
            }
        }
        ChevronIcon(colors.text3)
    }
}
