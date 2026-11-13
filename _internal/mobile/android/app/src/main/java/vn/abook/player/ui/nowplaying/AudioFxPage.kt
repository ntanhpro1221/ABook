package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.unit.dp
import vn.abook.player.AudioFx
import vn.abook.player.AudioFxSettings
import vn.abook.player.ui.components.*
import vn.abook.player.ui.music.MusicKind
import vn.abook.player.ui.music.MusicLevels
import vn.abook.player.ui.music.MusicState
import vn.abook.player.ui.music.MusicText
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.roundToInt

/**
 * Trang Âm thanh (DESIGN.md §9.6): Giọng đọc (một thanh 0-200 %, 100 % = gốc), Nhạc nền ngay dưới (công tắc + mức), Âm sắc (một hàng cuộn ngang;
 * dải tần chỉ hiện khi Tự chỉnh), các tuỳ chọn tai nghe, Cao độ ở cuối, rồi Về mặc định - đưa MỌI thứ ở trang này về gốc và nghe ngay.
 */
@Composable
fun AudioFxPage(music: MusicState? = null, bookId: String = "", openMusic: () -> Unit = {}, openTone: () -> Unit = {}) {
    val context = LocalContext.current
    LaunchedEffect(context) { AudioFx.init(context) }
    val fx by AudioFx.state.collectAsState()
    val bookOnly by AudioFx.bookOnly.collectAsState()
    val update: (AudioFxSettings) -> Unit = { AudioFx.update(it) }
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("audiofx_page")) {
        FxSlider(S.s_giong_doc_11f2548d, ValueSpecs.voice, (fx.voiceLevel * 100).roundToInt().toDouble(), "audiofx_voice", { "${it.roundToInt()}%" }) {
            update(fx.withVoiceLevel(it / 100))
        }
        if (music != null && bookId.isNotEmpty()) MusicBlock(music, bookId, openMusic)
        val toneRevision by AudioFx.toneChanges.collectAsState()
        val tones = remember(toneRevision) { AudioFx.tones }
        ListRow(S.s_am_sac_8c2f4e1a, Modifier.pressable(onClick = openTone).testTag("audiofx_tones")) {
            Column(Modifier.widthIn(max = 180.dp), horizontalAlignment = Alignment.End) {
                BasicText(tones.name, style = Abook.type.bodySmall.copy(color = Abook.colors.text2))
                Reveal(tones.scoped) { RowHint(S.s_copy_0aedb2b2cf2b) }
            }
        }
        Spacer(Modifier.height(Dim.s8))
        SwitchRow(S.s_copy_6f00156cec07, fx.mono, { update(fx.copy(mono = it)) }, "audiofx_mono")
        FxSlider(S.s_can_bang_8b88211d, ValueSpecs.balance, (fx.balance * 100).roundToInt().toDouble(), "audiofx_balance", { vn.abook.player.UiNumber.balance(it) }) {
            update(fx.copy(balance = it / 100))
        }
        SwitchRow(S.s_copy_289e1cff4cbc, fx.skipSilence, { update(fx.copy(skipSilence = it)) }, "audiofx_silence", hint = S.s_copy_b09b5fb2264a)
        Reveal(fx.skipSilence) {
            Column(Modifier.fillMaxWidth()) {
                // Thanh hai phía (ngưỡng dBFS, Cao độ): số có dấu, dấu trừ thật.
                FxSlider(S.s_copy_8e18e6dd7fd9, ValueSpecs.silenceDb, fx.silenceDb, "audiofx_silence_db", { "${PlayerLabels.signed(it)} dBFS" }) { update(fx.copy(silenceDb = it)) }
                FxSlider(S.s_copy_19adc1b298a9, ValueSpecs.silenceSeconds, fx.silenceSeconds, "audiofx_silence_seconds", { "${ValuePickerLogic.format(ValueSpecs.silenceSeconds, it)} s" }) { update(fx.copy(silenceSeconds = it)) }
                // "Giữ khoảng nghỉ" không quá "Dài tối thiểu".
                val keep = ValueSpecs.keepSeconds.cappedAt(fx.silenceSeconds)
                FxSlider(S.s_copy_483cdfec9d5f, keep, fx.keepSeconds, "audiofx_keep_seconds", { "${ValuePickerLogic.format(keep, it)} s" }) { update(fx.copy(keepSeconds = it)) }
            }
        }
        SwitchRow(S.s_copy_0aedb2b2cf2b, bookOnly, AudioFx::setBookOnly, "audiofx_book")
        // Cao độ ở cuối, gọn: kéo chỉ đổi số; giọng nghe giá trị cuối khi thả tay (hay tay dừng lâu) - mỗi lần đổi cao độ, máy phát phải xả hết tiếng đang xử lý.
        FxSlider(S.s_copy_519c2d65ca4c, ValueSpecs.pitch, fx.pitch, "audiofx_pitch", { S.s_copy_e4902bd61bb7(PlayerLabels.signed(it)) },
            onPreview = { AudioFx.update(fx.copy(pitch = it), AudioFx.DRAG_SETTLE_MS) }) { update(fx.copy(pitch = it)) }
        TextAction(S.s_ve_mac_dinh_4eb6b300, {
            AudioFx.reset()
            if (music != null && bookId.isNotEmpty()) music.setLevel(MusicLevels.DEFAULT_DB)
        }, "audiofx_reset", align = Alignment.CenterStart)
    }
}

/** Nhạc nền của cuốn đang nghe, ngay dưới Giọng đọc: công tắc (+ "Theo cảnh" khi máy dựng được), mức 0-100 %, và lối vào chọn bài / ghi công. */
@Composable
private fun MusicBlock(music: MusicState, bookId: String, openMusic: () -> Unit) {
    LaunchedEffect(music, bookId) { music.open(bookId) }
    val all by music.ui.collectAsState()
    val ui = all.takeIf { it.bookId == bookId } ?: vn.abook.player.ui.music.BookMusicUi(bookId = bookId)
    val book = ui?.book
    Reveal(book != null && book.kind != MusicKind.None) {
        if (book == null) return@Reveal
        val on = MusicText.playing(book)
        val playlist = book.kind == MusicKind.Playlist
        val scene = playlist && ui.menu?.scene == true
        Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("audiofx_music")) {
            ListRow(S.s_nhac_nen_271fb292, Modifier.pressable(Role.Switch) {
                if (ui.busy) return@pressable
                if (playlist) music.choose(if (on) MusicText.OFF else null) else music.setEnabled(!on)
            }.testTag("audiofx_music_switch")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (scene) {
                        val byScene = book.playlist == MusicText.SCENE && !book.playlistAuto
                        Box(Modifier.heightIn(min = Dim.s48).pressable(Role.Checkbox) { if (!ui.busy) music.choose(if (byScene) null else MusicText.SCENE) }
                            .semantics { selected = byScene }.padding(horizontal = Dim.s8).testTag("audiofx_music_scene"), contentAlignment = Alignment.Center) {
                            BasicText(MusicText.SCENE_LABEL, style = Abook.type.label.copy(color = if (byScene) Abook.colors.accentText else Abook.colors.text2))
                        }
                    }
                    Switch(on)
                }
            }
            Reveal(on) {
                Column(Modifier.fillMaxWidth()) {
                    var moving by remember(book.levelDb) { mutableStateOf<Double?>(null) }
                    val shown = moving ?: MusicLevels.clamp(book.levelDb)
                    LevelSlider(MusicLevels.TITLE, shown, MusicLevels.MIN_DB, MusicLevels.MAX_DB, MusicLevels.STEP_DB, "${MusicLevels.percent(shown)}%",
                        enabled = !ui.busy, tag = "audiofx_music_level", default = MusicLevels.DEFAULT_DB, onMove = { moving = it }) { moving = it; music.setLevel(it) }
                    TextAction(S.s_chon_nhac_4e9b1d72, openMusic, "audiofx_music_more", align = Alignment.CenterStart)
                }
            }
        }
    }
}

/** Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6; web AudioFxPanel FxSlider): tên + giá trị (chạm để gõ), thước giữa -/+, chip tiêu biểu.
 *  Kéo là nghe ngay (`onPreview`). */
@Composable
private fun FxSlider(title: String, spec: ValueSpec, value: Double, tag: String, format: (Double) -> String,
                     onPreview: ((Double) -> Unit)? = null, update: (Double) -> Unit) {
    ValuePicker(spec, value, update, format, title, tag, Modifier.padding(top = Dim.s8), dense = true,
        chipLabel = { ValuePickerLogic.format(spec, it) }, onPreview = onPreview ?: update)
}

/** Mức nhạc nền (dB, hiện %): thanh trượt như MusicLevelSlider của web / Qt - tên trái, số phải, thanh 44 dp. `onMove` khi đang kéo. */
@Composable
private fun LevelSlider(title: String, value: Double, min: Double, max: Double, step: Double, label: String,
                        enabled: Boolean, tag: String, default: Double, onMove: (Double) -> Unit, update: (Double) -> Unit) {
    Column(Modifier.fillMaxWidth().then(if (enabled) Modifier else Modifier.alpha(.5f)).testTag(tag)) {
        Row(Modifier.fillMaxWidth().padding(top = Dim.s8), horizontalArrangement = Arrangement.SpaceBetween) {
            BasicText(title, style = Abook.type.bodySmall)
            ClockLabel(label, style = Abook.type.bodySmall)
        }
        RangeSlider(value, min, max, step, default, title, label, enabled, onMove, update)
    }
}
