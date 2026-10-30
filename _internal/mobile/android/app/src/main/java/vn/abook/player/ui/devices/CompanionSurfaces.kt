package vn.abook.player.ui.devices

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
    val local by player.state.collectAsState()
    val hidden by repo.hidden.collectAsState()
    val active = ui.players.filter { it.book.isNotEmpty() && it.chapter != null && "${it.device}:${it.book}" !in hidden }
    Reveal(ui.players.isNotEmpty() || local.hasTrack) {
        Column(Modifier.fillMaxWidth().background(Abook.colors.panel).padding(horizontal = Dim.margin)) {
            DisclosureRow("Phát trên", { sheets.show { dismiss -> OtherPlayersSheet(repo, player, dismiss) } }, "other_players",
                summary = if (active.isEmpty()) "Chọn nơi phát" else active.joinToString { it.name })
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
        BasicText("Phát trên", style = Abook.type.sectionTitle)
        Reveal(ui.opening.isNotBlank()) { Caption(ui.opening) }
        Reveal(ui.busy) { Caption("Đang gửi lệnh") }
        Reveal(ui.problem.isNotEmpty()) { Caption(ui.problem) }
        Reveal(ui.players.isEmpty()) { Caption("Chưa thấy máy khác. Bạn kiểm tra kết nối.") }
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
                        hint = if (remote.book.isEmpty()) "Chưa phát sách" else if (remote.playing) "Đang phát" else "Đang dừng",
                        leading = { OtherPlayerIcon(remote) },
                        below = {
                            if (remote.protocol == "gcast") Caption("Google Cast")
                            Reveal(remote.book.isNotEmpty() && remote.chapter != null) {
                                Column {
                                    BasicText(remote.title, style = Abook.type.bodySmall)
                                    Caption("${Fmt.clock(remote.positionAfter(0.0))} · ${Fmt.clock(remote.duration)}", ticking = true)
                                    // All playback controls belong to this device's text column, including their shared centre.
                                    Row(Modifier.fillMaxWidth().testTag("remote_transport_${remote.device}"), horizontalArrangement = Arrangement.spacedBy(Dim.s8, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically) {
                                        IconAction("Lùi 15 giây trên ${remote.name}", { if (!ui.busy) scope.launch { repo.send(remote, "skip", -15.0) } }, "remote_back_${remote.device}") { PlayerGlyph("↶15") }
                                        IconAction(if (remote.playing) "Tạm dừng trên ${remote.name}" else "Phát tiếp trên ${remote.name}",
                                            { if (!ui.busy) scope.launch { repo.send(remote, "toggle") } }, "remote_toggle_${remote.device}") {
                                            Box(Modifier.size(40.dp).background(Abook.colors.text, CircleShape), contentAlignment = Alignment.Center) {
                                                PlayPauseGlyph(remote.playing, Abook.colors.bg, 20.dp)
                                            }
                                        }
                                        IconAction("Tới 15 giây trên ${remote.name}", { if (!ui.busy) scope.launch { repo.send(remote, "skip", 15.0) } }, "remote_forward_${remote.device}") { PlayerGlyph("15↷") }
                                    }
                                    Reveal(remote.known) {
                                        TextAction("Nghe ở đây", { if (!ui.busy) scope.launch { if (repo.listenHere(remote, local::playChapter)) dismiss() } }, "remote_here_${remote.device}", align = Alignment.CenterStart)
                                    }
                                    Reveal(remote.cast) {
                                        Column {
                                            TextAction("Hẹn giờ", { sleepFor = if (sleepFor == remote.device) null else remote.device }, "remote_sleep_${remote.device}", align = Alignment.CenterStart)
                                            Reveal(sleepFor == remote.device) {
                                                Column {
                                                    for (minutes in listOf(15, 30, 45, 60)) {
                                                        TextAction("$minutes phút", {
                                                            if (!ui.busy) scope.launch { repo.send(remote, "sleep", minutes = minutes); sleepFor = null }
                                                        }, "remote_sleep_${remote.device}_$minutes", Modifier.fillMaxWidth(), Alignment.CenterStart)
                                                    }
                                                    TextAction("Tắt hẹn giờ", { if (!ui.busy) scope.launch { repo.send(remote, "sleep", minutes = 0); sleepFor = null } }, "remote_sleep_off", Modifier.fillMaxWidth(), Alignment.CenterStart)
                                                    TextAction("Hết chương", { if (!ui.busy) scope.launch { repo.send(remote, "sleep", mode = "chapter"); sleepFor = null } }, "remote_sleep_chapter", Modifier.fillMaxWidth(), Alignment.CenterStart)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            val owner = Regex("^p([0-9a-f]{8})_").find(here.bookId)?.groupValues?.get(1) ?: "main"
                            Reveal(here.hasTrack && (remote.cast || remote.device == owner)) {
                                TextAction("Phát trên ${remote.name}${if (remote.protocol == "gcast") " (Google Cast)" else ""}", { if (!ui.busy) scope.launch { repo.handOff(remote, here, local.positionMs() / 1000.0, local::pause) } }, "remote_load_${remote.device}", align = Alignment.CenterStart)
                            }
                            Reveal(remote.book.isNotEmpty()) { TextAction("Ẩn", { repo.hide(remote); dismiss() }, "remote_hide_${remote.device}", align = Alignment.CenterStart) }
                        },
                    )
                    RowLine(start = Dim.s24 + Dim.s12)
                }
                }
            }
        }
        IconAction("Tìm lại thiết bị phát", { if (!ui.busy) scope.launch { repo.findPlayers() } }, "remote_retry", Modifier.align(Alignment.End)) { RefreshIcon(Abook.colors.text) }
    }
}

/** Notices are production events, so the opt-in belongs with Studio rather than general phone playback settings. */
@Composable
fun StudioNotices(repo: CompanionRepo, askPermission: (() -> Unit) -> Unit, openSettings: () -> Unit) {
    val ui by repo.state.collectAsState()
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxWidth().testTag("studio_notices")) {
        SwitchRow("Báo từ Studio", ui.notices.enabled, { on ->
            val apply = { scope.launch { repo.setNotices(on) }; Unit }
            if (on) askPermission(apply) else apply()
        }, "studio_alerts", hint = if (ui.notices.enabled && !ui.notices.permitted) "Android đang chặn thông báo của ABook." else "Sách xong hoặc có việc cần bạn.")
        Reveal(ui.notices.enabled && !ui.notices.permitted) {
            Column {
                Caption("Bật lại trong Cài đặt của máy > Ứng dụng > ABook > Thông báo.")
                TextAction("Mở cài đặt", openSettings, "studio_notification_settings", align = Alignment.CenterStart)
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
