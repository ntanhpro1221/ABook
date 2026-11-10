package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
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
    val bookOnly by AudioFx.bookOnly.collectAsState()
    val fx = value ?: saved
    val update = change ?: AudioFx::update
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        BasicText(S.s_copy_d05a51c01f29, style = Abook.type.bodySmall)
        SwitchRow(S.s_copy_0aedb2b2cf2b, bookOnly, AudioFx::setBookOnly, "audiofx_book")
        FxSlider(S.s_am_luong_5dafca26, ValueSpecs.volume, (fx.volume * 100).roundToInt().toDouble(), "audiofx_volume", { "${it.roundToInt()}%" }) { update(fx.copy(volume = it / 100)) }
        FxSlider(S.s_copy_c77e16da718e, ValueSpecs.boost, fx.boost, "audiofx_boost", { "${it.roundToInt()} dB" }) { update(fx.copy(boost = it)) }
        FxSlider(S.s_copy_519c2d65ca4c, ValueSpecs.pitch, fx.pitch, "audiofx_pitch", { S.s_copy_e4902bd61bb7(ValuePickerLogic.format(ValueSpecs.pitch, it)) }) { update(fx.copy(pitch = it)) }
        TextAction(S.s_ve_mac_dinh_4eb6b300, { update(fx.copy(pitch = 0.0)) }, "audiofx_pitch_reset", align = androidx.compose.ui.Alignment.CenterStart)
        SwitchRow(S.s_copy_6f00156cec07, fx.mono, { update(fx.copy(mono = it)) }, "audiofx_mono")
        FxSlider(S.s_can_bang_8b88211d, ValueSpecs.balance, (fx.balance * 100).roundToInt().toDouble(), "audiofx_balance", { vn.abook.player.UiNumber.balance(it) }) { update(fx.copy(balance = it / 100)) }
        SwitchRow(S.s_copy_289e1cff4cbc, fx.skipSilence, { update(fx.copy(skipSilence = it)) }, "audiofx_silence")
        BasicText(S.s_copy_b09b5fb2264a, style = Abook.type.bodySmall)
        FxSlider(S.s_copy_8e18e6dd7fd9, ValueSpecs.silenceDb, fx.silenceDb, "audiofx_silence_db", { "${it.roundToInt()} dBFS" }, fx.skipSilence) { update(fx.copy(silenceDb = it)) }
        FxSlider(S.s_copy_19adc1b298a9, ValueSpecs.silenceSeconds, fx.silenceSeconds, "audiofx_silence_seconds", { "${ValuePickerLogic.format(ValueSpecs.silenceSeconds, it)} s" }, fx.skipSilence) { update(fx.copy(silenceSeconds = it)) }
        // "Giữ khoảng nghỉ" không quá "Dài tối thiểu".
        val keep = ValueSpecs.keepSeconds.cappedAt(fx.silenceSeconds)
        FxSlider(S.s_copy_483cdfec9d5f, keep, fx.keepSeconds, "audiofx_keep_seconds", { "${ValuePickerLogic.format(keep, it)} s" }, fx.skipSilence) { update(fx.copy(keepSeconds = it)) }
        SwitchRow(S.s_copy_71255f2b6855, fx.enabled, { update(fx.copy(enabled = it)) }, "audiofx_enabled")
        BasicText(S.s_copy_7252e7ce0085, style = Abook.type.bodySmall)
        val choices = remember { AudioFxSettings.LABELS.mapIndexed { i, label -> FxChoice(i, label) } + FxChoice(-1, S.s_copy_e3518044ceec) }
        ChoiceRow(choices, choices.first { it.index == fx.preset }, { selected, _ ->
            update(if (selected.index < 0) fx.copy(enabled = true, preset = -1) else fx.withPreset(selected.index).copy(enabled = true))
        }, Modifier.fillMaxWidth(), "audiofx_presets")
        AudioFxSettings.BAND_LABELS.forEachIndexed { i, name ->
            FxSlider(name, ValueSpecs.eqBand, fx.bands[i], "audiofx_band_$i", { "${it.roundToInt()} dB" }, fx.enabled) { db ->
                update(fx.copy(preset = -1, bands = fx.bands.mapIndexed { j, v -> if (i == j) db else v }))
            }
        }
        FxSlider(S.s_copy_eb4635c58f1d, ValueSpecs.bass, fx.bass, "audiofx_bass", { "${it.roundToInt()} dB" }, fx.enabled) { update(fx.copy(preset = -1, bass = it)) }
    }
}
private data class FxChoice(val index: Int, override val label: String) : Choice { override val key = index.toString() }

/** Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6; web AudioFxPanel FxSlider): tên + giá trị (chạm để gõ), thước giữa -/+, chip tiêu biểu.
 *  Kéo là nghe ngay (`onPreview`). */
@Composable
private fun FxSlider(title: String, spec: ValueSpec, value: Double, tag: String, format: (Double) -> String,
                     enabled: Boolean = true, update: (Double) -> Unit) {
    ValuePicker(spec, value, update, format, title, tag, Modifier, enabled = enabled, dense = true,
        chipLabel = { ValuePickerLogic.format(spec, it) }, onPreview = update)
}
