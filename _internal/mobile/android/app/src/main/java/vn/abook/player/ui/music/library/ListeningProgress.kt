package vn.abook.player.ui.music.library

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.S
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.theme.Abook

/** Same track geometry, touch and accessibility as the book seek control. */
@Composable
fun ListeningProgress(ui: LibraryUi, state: LibraryState, modifier: Modifier = Modifier) {
    var dragging by remember(ui.previewing) { mutableStateOf<Double?>(null) }
    val value = dragging ?: ui.previewPosition
    Column(modifier.fillMaxWidth().testTag("music_listening_progress")) {
        RangeSlider(value, 0.0, ui.previewDuration.coerceAtLeast(1.0), 0.1, null,
            S.s_music_seek, "${Fmt.clock(value)} / ${Fmt.clock(ui.previewDuration)}", ui.previewDuration > 0,
            onMove = { dragging = it }, onCommit = { state.seekPreview(it); dragging = null }, onCancel = { dragging = null })
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            ClockLabel(Fmt.clock(value), style = Abook.type.caption)
            ClockLabel(Fmt.clock(ui.previewDuration), style = Abook.type.caption)
        }
    }
}
