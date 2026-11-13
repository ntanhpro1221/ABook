package vn.abook.player.ui.music.library

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
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
    Row(
        Modifier.fillMaxWidth().heightIn(min = 64.dp).pressable(onClick = onOpen).padding(vertical = Dim.s8).testTag("track_${track.link.hashCode()}"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(40.dp).then(if (canPlay) Modifier.pressable { state.togglePreview(track.link) } else Modifier.semantics { disabled() })
                .semantics { contentDescription = if (playing) S.s_dung_nghe_thu_41a2925b else S.s_nghe_thu_fa024065 }
                .testTag("preview_${track.link.hashCode()}"), contentAlignment = Alignment.Center,
        ) { LucideIcon(if (playing) LucidePaths.SQUARE else LucidePaths.PLAY, if (!canPlay) colors.text3 else if (playing) colors.accentText else colors.text) }
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
                track.duration?.let {
                    Reveal(track.creator.isNotEmpty()) { BasicText("·", style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.padding(horizontal = Dim.s4)) }
                    ClockLabel(Fmt.clock(it), Modifier.testTag("music_row_duration"), Abook.type.bodySmall.copy(color = colors.text2))
                }
            }
        }
        SwapContent(pick, contentKey = { pick -> pick != null }, layout = ContentLayout.Row) { pick ->
            if (pick != null) TextAction(S.s_dung_7927ca4e, { pick.onUse(track.link) }, "use_${track.link.hashCode()}", Modifier.padding(start = Dim.s8))
        }
        DownloadControl(track, ui, state, Modifier.padding(start = Dim.s8))
    }
}

/** Every row reserves the same download column, including tracks that have not been downloaded. */
@Composable
private fun DownloadControl(track: MusicLibrary.Track, ui: LibraryUi, state: LibraryState, modifier: Modifier = Modifier) {
    val load = ui.active[track.link]
    val downloaded = track.link in ui.downloaded
    val failed = track.link in ui.failed
    val label = when {
        load != null -> S.s_huy_tai_1a9ff73d
        downloaded -> S.s_da_tai_b7362bbf
        failed -> S.s_tai_tiep_1efbd854
        else -> S.s_tai_ve_9b5bdb44
    }
    Box(
        modifier.size(Dim.touch).then(when {
            load != null -> Modifier.pressable { state.cancel(listOf(track.link)) }
            !downloaded && ui.online -> Modifier.pressable { state.save(listOf(track.link)) }
            else -> Modifier
        }).semantics { contentDescription = label }.testTag("download_${track.link.hashCode()}"),
        contentAlignment = Alignment.Center,
    ) {
        SwapContent(load, contentKey = { load -> load != null }, layout = ContentLayout.Box) { load ->
            if (load != null) DownloadRing(load.percent, S.s_dang_tai_0_e9a97892(load.percent ?: 0), Modifier.testTag("track_loading"))
            else LucideIcon(when { downloaded -> LucidePaths.CIRCLE_CHECK; failed -> LucidePaths.CIRCLE_ALERT; else -> LucidePaths.DOWNLOAD },
            when { downloaded -> Abook.colors.success; failed -> Abook.colors.danger; !ui.online -> Abook.colors.text3; else -> Abook.colors.text2 })
        }
    }
}
