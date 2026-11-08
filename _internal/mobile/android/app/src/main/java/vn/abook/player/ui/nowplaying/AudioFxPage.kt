package vn.abook.player.ui.nowplaying

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import vn.abook.player.AudioFx
import vn.abook.player.AudioFxSettings
import vn.abook.player.ui.components.*
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.data.Choice
import kotlin.math.roundToInt

@Composable
fun AudioFxPage(value: AudioFxSettings? = null, change: ((AudioFxSettings) -> Unit)? = null) {
    val context = LocalContext.current
    LaunchedEffect(context) { AudioFx.init(context) }
    val saved by AudioFx.state.collectAsState()
    val fx = value ?: saved
    val update = change ?: AudioFx::update
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        BasicText("Lưu cho toàn app. Chỉ chỉnh giọng đọc; nhạc nền có mức riêng.", style = Abook.type.bodySmall)
        FxSlider("Âm lượng", fx.volume * 100, 0.0, 100.0, 1.0, "${(fx.volume * 100).roundToInt()}%") { update(fx.copy(volume = it / 100)) }
        FxSlider("Tăng âm", fx.boost, 0.0, 12.0, 1.0, "${fx.boost.roundToInt()} dB") { update(fx.copy(boost = it)) }
        FxSlider("Cao độ", fx.pitch, -6.0, 6.0, 0.5, "${fx.pitch} bán âm") { update(fx.copy(pitch = it)) }
        TextAction("Về mặc định", { update(fx.copy(pitch = 0.0)) }, "audiofx_pitch_reset", align = androidx.compose.ui.Alignment.CenterStart)
        SwitchRow("Equalizer", fx.enabled, { update(fx.copy(enabled = it)) }, "audiofx_enabled")
        BasicText("Preset", style = Abook.type.bodySmall)
        val choices = remember { AudioFxSettings.LABELS.mapIndexed { i, label -> FxChoice(i, label) } + FxChoice(-1, "Tự chỉnh") }
        ChoiceRow(choices, choices.first { it.index == fx.preset }, { selected, _ ->
            update(if (selected.index < 0) fx.copy(enabled = true, preset = -1) else fx.withPreset(selected.index).copy(enabled = true))
        }, Modifier.fillMaxWidth(), "audiofx_presets")
        AudioFxSettings.BAND_LABELS.forEachIndexed { i, name ->
            FxSlider(name, fx.bands[i], -12.0, 12.0, 1.0, "${fx.bands[i].roundToInt()} dB", fx.enabled) { db ->
                update(fx.copy(preset = -1, bands = fx.bands.mapIndexed { j, v -> if (i == j) db else v }))
            }
        }
        FxSlider("Tăng trầm", fx.bass, 0.0, 12.0, 1.0, "${fx.bass.roundToInt()} dB", fx.enabled) { update(fx.copy(preset = -1, bass = it)) }
    }
}
private data class FxChoice(val index: Int, override val label: String) : Choice { override val key = index.toString() }

@Composable
private fun FxSlider(title: String, value: Double, min: Double, max: Double, step: Double, label: String,
                     enabled: Boolean = true, update: (Double) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        BasicText(title, style = Abook.type.bodySmall)
        ClockLabel(label, style = Abook.type.bodySmall)
    }
    RangeSlider(value, min, max, step, if (min < 0) 0.0 else null, title, label, enabled, update, update)
}
