package vn.abook.player.ui.devices

import vn.abook.player.S

import androidx.activity.compose.BackHandler
import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.foundation.shape.CircleShape
import vn.abook.player.ui.nowplaying.PlayerGlyph
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.rememberPresence
import androidx.compose.foundation.lazy.rememberLazyListState

/** One entry in the playback area, rather than stacking full control bars over library content. */
@Composable
fun OtherPlayersEntry(repo: CompanionRepo, sheets: SheetHost, player: PlayerRepo) {
    val ui by repo.state.collectAsState()
    val hidden by repo.hidden.collectAsState()
    val active = ui.players.filter { it.playing && it.book.isNotEmpty() && it.chapter != null && "${it.device}:${it.book}" !in hidden }
    val names = remember { arrayOf("") }
    if (active.isNotEmpty()) names[0] = active.joinToString { it.name }
    Reveal(active.isNotEmpty()) {
        Row(Modifier.fillMaxWidth().height(36.dp).background(Abook.colors.panel)
            .pressable { sheets.show { dismiss -> OtherPlayersSheet(repo, player, dismiss) } }
            .padding(horizontal = Dim.margin).testTag("other_players"), verticalAlignment = Alignment.CenterVertically) {
            // cắt-có-chủ-ý: the requested one-line strip opens the sheet with full device names.
            BasicText(S.s_dang_phat_tren_0_62a989a1(names[0]), Modifier.weight(1f),
                // cắt-có-chủ-ý: the full names remain available in the device sheet.
                style = Abook.type.caption, maxLines = 1)
            ChevronIcon(Abook.colors.text2)
        }
    }
}

@Composable
fun OtherPlayersSheet(repo: CompanionRepo, local: PlayerRepo, dismiss: () -> Unit) {
    val ui by repo.state.collectAsState()
    val here by local.state.collectAsState()
    val scope = rememberCoroutineScope()
    var sleepFor by remember { mutableStateOf<String?>(null) }
    val players = rememberPresence(ui.players) { it.device }
    BackHandler(enabled = sleepFor != null) { sleepFor = null }
    val available = (LocalConfiguration.current.screenHeightDp * 0.8f).dp
    Column(Modifier.fillMaxWidth().heightIn(max = available).testTag("remote_players_sheet")) {
        BasicText(S.s_phat_tren_681e16e1, style = Abook.type.sectionTitle)
        Reveal(ui.opening.isNotBlank()) { Caption(ui.opening) }
        Reveal(ui.busy) { Caption(S.s_dang_gui_lenh_4c157686) }
        Reveal(ui.problem.isNotEmpty()) { Caption(ui.problem) }
        Reveal(ui.players.isEmpty()) { Caption(S.s_chua_thay_may_khac_ban_kiem_tra_ket_noi_98a81a7f) }
        val list = rememberLazyListState()
        LazyColumn(Modifier.fillMaxWidth().weight(1f, fill = false).fadeEdges(list).testTag("remote_players_list"), state = list) {
            items(players, key = { it.item.device }, contentType = { "player" }) { row ->
                AnimatedVisibility(row.visible, Modifier.animateItem(fadeInSpec = null, fadeOutSpec = null),
                    enter = expandVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) + slideInVertically(tween(MotionMs.MEDIUM)) { it / 4 },
                    exit = shrinkVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) + slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { it / 4 }) {
                val remote = row.item
                Column(Modifier.fillMaxWidth()) {
                    ListItem(
                        remote.name, tag = "remote_${remote.device}", titleStyle = Abook.type.bodyStrong,
                        hint = if (remote.book.isEmpty()) S.s_chua_phat_sach_f18215d2 else if (remote.playing) S.s_dang_phat_ac2dd0c2 else S.s_dang_dung_9b35aeb5,
                        leading = { OtherPlayerIcon(remote) },
                        below = {
                            if (remote.protocol == "gcast") Caption(S.s_google_cast_981c76f4)
                            Reveal(remote.book.isNotEmpty() && remote.chapter != null) {
                                Column {
                                    BasicText(remote.title, style = Abook.type.bodySmall)
                                    Caption("${Fmt.clock(remote.positionAfter(0.0))} · ${Fmt.clock(remote.duration)}", ticking = true)
                                    // All playback controls belong to this device's text column, including their shared centre.
                                    Row(Modifier.fillMaxWidth().testTag("remote_transport_${remote.device}"), horizontalArrangement = Arrangement.spacedBy(Dim.s8, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically) {
                                        IconAction(S.s_lui_15_giay_tren_0_ef9cea4b(remote.name), { if (!ui.busy) scope.launch { repo.send(remote, "skip", -15.0) } }, "remote_back_${remote.device}") { PlayerGlyph("↶15") }
                                        IconAction(if (remote.playing) S.s_tam_dung_tren_0_55c295eb(remote.name) else S.s_phat_tiep_tren_0_de5ffa35(remote.name),
                                            { if (!ui.busy) scope.launch { repo.send(remote, "toggle") } }, "remote_toggle_${remote.device}") {
                                            Box(Modifier.size(40.dp).background(Abook.colors.text, CircleShape), contentAlignment = Alignment.Center) {
                                                PlayPauseGlyph(remote.playing, Abook.colors.bg, 20.dp)
                                            }
                                        }
                                        IconAction(S.s_toi_15_giay_tren_0_4023d456(remote.name), { if (!ui.busy) scope.launch { repo.send(remote, "skip", 15.0) } }, "remote_forward_${remote.device}") { PlayerGlyph("15↷") }
                                    }
                                    Reveal(remote.known) {
                                        TextAction(S.s_nghe_o_day_f7f1d741, { if (!ui.busy) scope.launch { if (repo.listenHere(remote, local::playChapter)) dismiss() } }, "remote_here_${remote.device}", align = Alignment.CenterStart)
                                    }
                                    Reveal(remote.cast) {
                                        Column {
                                            TextAction(S.s_hen_gio_39d9ca26, { sleepFor = if (sleepFor == remote.device) null else remote.device }, "remote_sleep_${remote.device}", align = Alignment.CenterStart)
                                            Reveal(sleepFor == remote.device) {
                                                Column {
                                                    // Bộ chọn giá trị (DESIGN mục 6): chip tiêu biểu + chọn tự do 1-240 phút; mỗi lần đổi là hẹn lại trên máy kia.
                                                    var remoteMinutes by remember { mutableIntStateOf(30) }
                                                    ValuePicker(
                                                        ValueSpecs.sleepMinutes, remoteMinutes.toDouble(),
                                                        { minutes -> remoteMinutes = minutes.toInt(); if (!ui.busy) scope.launch { repo.send(remote, "sleep", minutes = minutes.toInt()) } },
                                                        { minutes -> S.s_0_phut_2596d212(minutes.toInt()) }, S.s_hen_gio_39d9ca26, "remote_sleep_${remote.device}_minutes",
                                                        current = remote.sleep == "minutes",
                                                    )
                                                    TextAction(S.s_tat_hen_gio_fc8af231, { if (!ui.busy) scope.launch { repo.send(remote, "sleep", minutes = 0); sleepFor = null } }, "remote_sleep_off", Modifier.fillMaxWidth(), Alignment.CenterStart)
                                                    TextAction(S.s_het_chuong_f1d590bb, { if (!ui.busy) scope.launch { repo.send(remote, "sleep", mode = "chapter"); sleepFor = null } }, "remote_sleep_chapter", Modifier.fillMaxWidth(), Alignment.CenterStart)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            val owner = Regex("^p([0-9a-f]{8})_").find(here.bookId)?.groupValues?.get(1) ?: "main"
                            Reveal(here.hasTrack && (remote.cast || remote.device == owner)) {
                                TextAction(S.s_phat_tren_0_1_757da6a7(remote.name, if (remote.protocol == "gcast") " (Google Cast)" else ""), { if (!ui.busy) scope.launch { repo.handOff(remote, here, local.positionMs() / 1000.0, local::pause) } }, "remote_load_${remote.device}", align = Alignment.CenterStart)
                            }
                            Reveal(remote.book.isNotEmpty()) { TextAction(S.s_an_9c7a6c2d, { repo.hide(remote); dismiss() }, "remote_hide_${remote.device}", align = Alignment.CenterStart) }
                        },
                    )
                    RowLine(start = Dim.s24 + Dim.s12)
                }
                }
            }
        }
        IconAction(S.s_tim_lai_thiet_bi_phat_0dc4396a, { if (!ui.busy) scope.launch { repo.findPlayers() } }, "remote_retry", Modifier.align(Alignment.End)) { RefreshIcon(Abook.colors.text) }
    }
}

/** Notices are production events, so the opt-in belongs with Studio rather than general phone playback settings. */
@Composable
fun StudioNotices(repo: CompanionRepo, askPermission: (() -> Unit) -> Unit, openSettings: () -> Unit) {
    val ui by repo.state.collectAsState()
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxWidth().testTag("studio_notices")) {
        SwitchRow(S.s_bao_tu_studio_1a19886d, ui.notices.enabled, { on ->
            val apply = { scope.launch { repo.setNotices(on) }; Unit }
            if (on) askPermission(apply) else apply()
        }, "studio_alerts", hint = if (ui.notices.enabled && !ui.notices.permitted) S.s_android_dang_chan_thong_bao_cua_abook_cc8b8e91 else S.s_sach_xong_hoac_co_viec_can_ban_2aca1fdb)
        Reveal(ui.notices.enabled && !ui.notices.permitted) {
            Column {
                Caption(S.s_bat_lai_trong_cai_dat_cua_may_ung_dung_abo_81a29820)
                TextAction(S.s_mo_cai_dat_60ab929f, openSettings, "studio_notification_settings", align = Alignment.CenterStart)
            }
        }
        Reveal(ui.problem.isNotEmpty()) { Caption(ui.problem) }
    }
}

/** The same device-kind vocabulary as RemotePlayers.tsx; Cast takes precedence over kind. */
@Composable
private fun OtherPlayerIcon(remote: OtherPlayer) {
    val ink = Abook.colors.text2
    if (remote.cast) CastIcon(ink) else when (remote.kind) {
        "computer" -> LaptopIcon(ink)
        "speaker" -> SpeakerIcon(ink)
        "tv" -> TvIcon(ink)
        "media" -> MonitorSpeakerIcon(ink)
        else -> PhoneIcon(ink)
    }
}
