package vn.abook.player.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.theme.Abook
import kotlin.math.round

/** Same canvas track, thumb and 44dp touch target as the player's seek control. */
@Composable
fun RangeSlider(value: Double, min: Double, max: Double, step: Double, default: Double?,
                title: String, description: String, enabled: Boolean,
                onMove: (Double) -> Unit, onCommit: (Double) -> Unit, modifier: Modifier = Modifier,
                readValue: () -> Double = { value }, onCancel: () -> Unit = {}) {
    val colors = Abook.colors
    val move by rememberUpdatedState(onMove)
    val commit by rememberUpdatedState(onCommit)
    var dragged by remember { mutableDoubleStateOf(value) }
    fun snap(v: Double) = (min + round((v - min) / step) * step).coerceIn(min, max)
    Canvas(modifier.fillMaxWidth().height(44.dp)
        .semantics {
            contentDescription = title
            stateDescription = description
            progressBarRangeInfo = ProgressBarRangeInfo(value.toFloat(), min.toFloat()..max.toFloat())
            if (!enabled) disabled()
            setProgress { if (enabled) { commit(snap(it.toDouble())); true } else false }
        }
        .pointerInput(min, max, step, enabled) {
            if (enabled) detectTapGestures { commit(snap(min + (it.x / size.width).coerceIn(0f, 1f) * (max - min))) }
        }
        .pointerInput(min, max, step, enabled) {
            if (enabled) detectDragGestures(
                onDragStart = { dragged = snap(min + (it.x / size.width).coerceIn(0f, 1f) * (max - min)); move(dragged) },
                onDrag = { change, _ -> change.consume(); dragged = snap(min + (change.position.x / size.width).coerceIn(0f, 1f) * (max - min)); move(dragged) },
                onDragEnd = { commit(dragged) },
                onDragCancel = { move(value); onCancel() },
            )
        }) {
        drawRangeTrack(readValue(), min, max, default, colors)
    }
}
