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
fun AudioFxPage(music: MusicState? = null, bookId: String = "", openMusic: () -> Unit = {}) {
    val context = LocalContext.current
    LaunchedEffect(context) { AudioFx.init(context) }
    val fx by AudioFx.state.collectAsState()
    val bookOnly by AudioFx.bookOnly.collectAsState()
    val update: (AudioFxSettings) -> Unit = { AudioFx.update(it) }
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("audiofx_page")) {
        val voice = fx.voiceLevel * 100
        FxSlider(S.s_giong_doc_11f2548d, voice, 0.0, AudioFxSettings.VOICE_MAX * 100, 5.0, "${voice.roundToInt()}%", tag = "audiofx_voice",
            default = 100.0) { update(fx.withVoiceLevel(it / 100)) }
        if (music != null && bookId.isNotEmpty()) MusicBlock(music, bookId, openMusic)
        Section(S.s_am_sac_8c2f4e1a)
        val tones = remember { AudioFxSettings.LABELS.indices.toList() + -1 }
        ScrollingTabs(tones, fx.tone, { update(fx.withTone(it)) },
            label = { if (it < 0) S.s_copy_e3518044ceec else AudioFxSettings.LABELS[it] }, tag = { "audiofx_tone_$it" }, rowTag = "audiofx_tones")
        Reveal(fx.tone < 0) {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                AudioFxSettings.BAND_LABELS.forEachIndexed { i, name ->
                    FxSlider(name, fx.bands[i], -12.0, 12.0, 1.0, "${fx.bands[i].roundToInt()} dB", default = 0.0) { db ->
                        update(fx.copy(preset = -1, bands = fx.bands.mapIndexed { j, v -> if (i == j) db else v }))
                    }
                }
                FxSlider(S.s_copy_eb4635c58f1d, fx.bass, 0.0, 12.0, 1.0, "${fx.bass.roundToInt()} dB") { update(fx.copy(preset = -1, bass = it)) }
            }
        }
        Spacer(Modifier.height(Dim.s8))
        SwitchRow(S.s_copy_6f00156cec07, fx.mono, { update(fx.copy(mono = it)) }, "audiofx_mono")
        FxSlider(S.s_can_bang_8b88211d, fx.balance * 100, -100.0, 100.0, 1.0, S.s_copy_45aac78838e4((fx.balance * 100).roundToInt()), default = 0.0) {
            update(fx.copy(balance = it / 100))
        }
        SwitchRow(S.s_copy_289e1cff4cbc, fx.skipSilence, { update(fx.copy(skipSilence = it)) }, "audiofx_silence", hint = S.s_copy_b09b5fb2264a)
        Reveal(fx.skipSilence) {
            Column(Modifier.fillMaxWidth()) {
                FxSlider(S.s_copy_8e18e6dd7fd9, fx.silenceDb, -80.0, -45.0, 1.0, "${fx.silenceDb.roundToInt()} dBFS") { update(fx.copy(silenceDb = it)) }
                FxSlider(S.s_copy_19adc1b298a9, fx.silenceSeconds, 2.0, 10.0, .5, "${fx.silenceSeconds} s") { update(fx.copy(silenceSeconds = it)) }
                FxSlider(S.s_copy_483cdfec9d5f, fx.keepSeconds, 1.5, minOf(3.0, fx.silenceSeconds), .1, "${fx.keepSeconds} s") { update(fx.copy(keepSeconds = it)) }
            }
        }
        SwitchRow(S.s_copy_0aedb2b2cf2b, bookOnly, AudioFx::setBookOnly, "audiofx_book")
        // Cao độ ở cuối, gọn: kéo chỉ đổi số; giọng nghe giá trị cuối khi thả tay (hay tay dừng lâu) - mỗi lần đổi cao độ, máy phát phải xả hết tiếng đang xử lý.
        FxSlider(S.s_copy_519c2d65ca4c, fx.pitch, -6.0, 6.0, 0.5, S.s_copy_e4902bd61bb7(fx.pitch), tag = "audiofx_pitch", default = 0.0,
            onMove = { AudioFx.update(fx.copy(pitch = it), AudioFx.DRAG_SETTLE_MS) }) { update(fx.copy(pitch = it)) }
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
                    FxSlider(MusicLevels.TITLE, shown, MusicLevels.MIN_DB, MusicLevels.MAX_DB, MusicLevels.STEP_DB, "${MusicLevels.percent(shown)}%",
                        enabled = !ui.busy, tag = "audiofx_music_level", default = MusicLevels.DEFAULT_DB, onMove = { moving = it }) { moving = it; music.setLevel(it) }
                    TextAction(S.s_chon_nhac_4e9b1d72, openMusic, "audiofx_music_more", align = Alignment.CenterStart)
                }
            }
        }
    }
}

@Composable
private fun Section(title: String) {
    BasicText(title, style = Abook.type.bodySmall, modifier = Modifier.padding(top = Dim.s16, bottom = Dim.s4))
}

/** Một thanh: tên trái, số phải, thanh 44 dp. `onMove` khi đang kéo (mặc định như thả tay). */
@Composable
private fun FxSlider(title: String, value: Double, min: Double, max: Double, step: Double, label: String,
                     enabled: Boolean = true, tag: String? = null, default: Double? = null,
                     onMove: ((Double) -> Unit)? = null, update: (Double) -> Unit) {
    Column(Modifier.fillMaxWidth().then(if (enabled) Modifier else Modifier.alpha(.5f)).then(if (tag != null) Modifier.testTag(tag) else Modifier)) {
        Row(Modifier.fillMaxWidth().padding(top = Dim.s8), horizontalArrangement = Arrangement.SpaceBetween) {
            BasicText(title, style = Abook.type.bodySmall)
            ClockLabel(label, style = Abook.type.bodySmall)
        }
        RangeSlider(value, min, max, step, default, title, label, enabled, onMove ?: update, update)
    }
}
