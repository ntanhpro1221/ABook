package vn.abook.player.ui.music.library

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import vn.abook.player.MusicLibrary
import vn.abook.player.MusicCredits
import vn.abook.player.ui.components.DownloadRing
import vn.abook.player.ui.components.LinearProgress
import vn.abook.player.ui.components.OutlineButton
import vn.abook.player.ui.components.LucideIcon
import vn.abook.player.ui.components.LucidePaths
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.S
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.dotJoined
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.insetSurface
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.Reveal

/** Sheet "Bài đang phát" (chạm dòng Nhạc nền của trình phát): Lưu / Bỏ lưu, Xem trong kho, Đổi bài. */
class PlayingActions(val onOpenLibrary: (title: String) -> Unit, val onSwap: (() -> Unit)? = null)

/**
 * Chi tiết một bài (DESIGN.md §7 "Nhạc"): tên · người sáng tác, các nút (Dùng ở chế độ chọn; Nghe thử; Tải về / Huỷ tải % / Tải tiếp / Xoá bản tải;
 * Không tự chọn bài này), "Vì sao bài này" (cảm xúc của đoạn cạnh cảm xúc của bài, 3 cảm xúc khớp nhất - ẩn khi đoạn không có cảm xúc),
 * 13 cảm xúc thành thanh ngang 0-100 % (giảm dần, nhãn tiếng Việt của danh mục), năng lượng, nhịp, phong cách, độ dài, có lời, giấy phép / ghi công /
 * nguồn, các danh sách phát có bài. `playing` khác null: sheet "Bài đang phát".
 */
@Composable
fun TrackSheet(
    state: LibraryState,
    link: String,
    dismiss: () -> Unit,
    pick: PickTarget? = null,
    scene: Map<String, Double> = emptyMap(),
    playing: PlayingActions? = null,
) {
    val ui by state.ui.collectAsState()
    val index = ui.index
    val track = index?.byLink?.get(link)
    val colors = Abook.colors
    val scroll = rememberScrollState()
    Column(Modifier.heightIn(max = 640.dp).fadeEdges(scroll).verticalScroll(scroll).testTag("track_sheet")) {
        SwapContent(track, index, contentKey = { track, index -> track == null || index == null }, layout = ContentLayout.Column) { track, index ->
            if (track == null || index == null) {
                Caption(if (ui.loading) S.s_dang_tai_465b1987 else S.s_chua_tai_duoc_bai_nay_d66f95b6, Modifier.padding(vertical = Dim.s16))
            } else {
                SwapContent(playing, contentKey = { playing -> playing != null }, layout = ContentLayout.Column) { playing ->
                    if (playing != null) Caption(S.s_bai_dang_phat_3c20c832, Modifier.padding(bottom = Dim.s4).testTag("track_playing"))
                }
                BasicText(track.title, style = Abook.type.sectionTitle, modifier = Modifier.testTag("track_title"))
                Reveal(track.creator.isNotEmpty()) { BasicText(track.creator, style = Abook.type.body.copy(color = colors.text2)) }
                Spacer(Modifier.height(Dim.s16))
                Actions(ui, state, track, dismiss, pick, playing)
                val why = MusicLibrary.why(scene, track.emotions)
                SwapContent(why, contentKey = { why -> why != null }, layout = ContentLayout.Column) { why ->
                    if (why != null) {
                        Section(S.s_vi_sao_bai_nay_f681e004)
                        Reveal(why.matches.isNotEmpty()) { Caption(S.s_doan_va_bai_cung_0_music(index.emotionLabel(why.matches.first().id)), Modifier.testTag("track_fit")) }
                        Row(horizontalArrangement = Arrangement.spacedBy(Dim.s16)) {
                            Legend(S.s_doan_nay_82d01522, colors.text3)
                            Legend(S.s_bai_nay_d9683a01, colors.accent)
                        }
                        Spacer(Modifier.height(Dim.s8))
                        for (match in why.matches) {
                            Row(Modifier.fillMaxWidth().heightIn(min = 28.dp), verticalAlignment = Alignment.CenterVertically) {
                                BasicText(index.emotionLabel(match.id), style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.width(104.dp))
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    LinearProgress(Modifier.height(4.dp), ink = colors.text3) { match.scene.toFloat() }
                                    LinearProgress(Modifier.height(4.dp)) { match.track.toFloat() }
                                }
                            }
                        }
                    }
                }
                val ranked = track.rankedEmotions()
                Reveal(ranked.isNotEmpty()) {
                    Section(S.s_cam_xuc_05c1aee0)
                    for ((id, score) in ranked) Bar(index.emotionLabel(id), score, Modifier.testTag("emotion_$id"))
                }
                Section(S.s_thong_tin_4aa16c92)
                Facts(track, index)
                Credit(track.info)
            }
        }
    }
}

@Composable
private fun Actions(ui: LibraryUi, state: LibraryState, track: MusicLibrary.Track, dismiss: () -> Unit, pick: PickTarget?, playing: PlayingActions?) {
    val link = track.link
    val load = ui.active[link]
    val downloaded = link in ui.downloaded
    val saved = link in ui.savedSet
    Column {
        SwapContent(playing, contentKey = { playing -> playing != null }, layout = ContentLayout.Column) { playing ->
            if (playing != null) {
                SwapContent(saved, contentKey = { saved -> saved }, layout = ContentLayout.Column) { saved ->
                    if (saved) QuietButton(S.s_bo_luu_2fd51455, { state.unsave(listOf(link)) }, "track_unsave")
                    else PrimaryButton(S.s_luu_e91f26c0, { state.save(listOf(link)) }, Modifier.fillMaxWidth().testTag("track_save"))
                }
                QuietButton(S.s_xem_trong_kho_2a139d05, { dismiss(); playing.onOpenLibrary(track.title) }, "track_open_library")
                playing.onSwap?.let { swap -> QuietButton(S.s_doi_bai_7b81488f, { dismiss(); swap() }, "track_swap") }
            } else {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s8)) {
                    PrimaryButton(
                    if (ui.previewing == link) S.s_dung_nghe_f20939be else S.s_nghe_thu_fa024065,
                    { state.togglePreview(link) }, Modifier.weight(1f).testTag("track_preview"), enabled = ui.online || downloaded, compact = true,
                    icon = { ink -> LucideIcon(if (ui.previewing == link) LucidePaths.SQUARE else LucidePaths.PLAY, ink) },
                    )
                    OutlineButton(
                    when { load != null -> S.s_huy_tai_1a9ff73d; downloaded -> S.s_xoa_ban_tai_4b461f4a; link in ui.failed -> S.s_tai_tiep_1efbd854; else -> S.s_tai_ve_9b5bdb44 },
                    { when { load != null -> state.cancel(listOf(link)); downloaded -> state.forget(link); else -> state.save(listOf(link)) } },
                    Modifier.weight(1f).testTag(when { load != null -> "track_cancel"; downloaded -> "track_forget"; else -> "track_download" }),
                    enabled = load != null || downloaded || ui.online,
                    icon = { ink -> if (load != null) DownloadRing(load.percent, S.s_dang_tai_0_e9a97892(load.percent ?: 0)) else LucideIcon(if (downloaded) LucidePaths.TRASH_2 else LucidePaths.DOWNLOAD, ink) },
                    )
                }
                Reveal(link in ui.failed) { Caption(S.s_chua_tai_xong_b257419d, Modifier.testTag("track_failed"), color = Abook.colors.danger) }
                SwapContent(pick, contentKey = { pick -> pick != null }, layout = ContentLayout.Column) { pick ->
                    if (pick != null) {
                        Spacer(Modifier.height(Dim.s8))
                        QuietButton(S.s_dung_7927ca4e, { dismiss(); pick.onUse(link) }, "track_use")
                    }
                }
                SwapContent(pick, contentKey = { pick -> pick?.onBan != null }, layout = ContentLayout.Column) { pick ->
                    if (pick?.onBan != null) {
                        QuietButton(S.s_khong_tu_chon_02ae1742, { dismiss(); pick.onBan.invoke(link) }, "track_ban")
                    }
                }
            }
        }
    }
}

@Composable
private fun Section(title: String) {
    SwapContent(title, contentKey = { title -> title.isEmpty() }, layout = ContentLayout.Column) { title ->
        if (title.isEmpty()) {
            Spacer(Modifier.height(Dim.s16))
            RowLine()
            Spacer(Modifier.height(Dim.s8))
        } else {
            Spacer(Modifier.height(Dim.s24))
            BasicText(title, style = Abook.type.bodyStrong, modifier = Modifier.padding(bottom = Dim.s8))
        }
    }
}

/** Thanh ngang 0-100 %: nhãn · thanh · số phần trăm (chữ số đều). Thanh vẽ trong pha vẽ. */
@Composable
private fun Bar(label: String, score: Double, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val fraction = score.coerceIn(0.0, 1.0).toFloat()
    Row(modifier.fillMaxWidth().heightIn(min = 28.dp), verticalAlignment = Alignment.CenterVertically) {
        BasicText(label, style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.width(104.dp))
        LinearProgress(Modifier.weight(1f).height(6.dp)) { fraction }
        ClockLabel("${MusicLibrary.percent(score)} %", style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.width(48.dp).padding(start = Dim.s8))
    }
}

@Composable
private fun Facts(track: MusicLibrary.Track, index: LibraryIndex) {
    val info = track.info
    val playlists = index.playlists.filter { track.link in it.links }.map { it.name }
    val vocals = (info.opt("vocals") as? Number)?.toDouble() ?: 0.0
    val rows: List<Pair<String, String?>> = listOfNotNull(
        MusicLibrary.energyPercent(track.arousal)?.let { S.s_nang_luong_1b9cc9af to "$it %" },
        track.bpm?.takeIf { it > 0 }?.let { S.s_nhip_8a75919d to S.s_0_nhip_phut_3c154e09(Math.round(it)) },
        track.style.takeIf { it.isNotEmpty() }?.let { S.s_phong_cach_d80ae8d9 to index.styleLabel(it) },
        track.duration?.let { S.s_do_dai_5e055f59 to Fmt.clock(it) },
        if (vocals >= 0.5) S.s_co_loi_4b381f10 to null else null,
        info.optString("license").takeIf { it.isNotEmpty() && !info.isNull("license") }?.let { S.s_giay_phep_b609ade1 to MusicCredits.licenseLabel(it, info.optString("licenseUrl")) },
        playlists.takeIf { it.isNotEmpty() }?.let { S.s_co_trong_1312af9f to it.joinToString(", ") },
    )
    for ((label, value) in rows) Fact(label) {
        SwapContent(value, contentKey = { value -> value != null }, layout = ContentLayout.Box) { value ->
            if (value != null) BasicText(value, style = Abook.type.bodySmall) else CheckIcon(Abook.colors.success)
        }
    }
}

@Composable
private fun Fact(label: String, content: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = Dim.s4).testTag("fact"), verticalAlignment = Alignment.Top) {
        BasicText(label, style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.width(104.dp))
        Column(Modifier.weight(1f)) { content() }
    }
}

@Composable
private fun Legend(label: String, ink: androidx.compose.ui.graphics.Color) {
    Row(Modifier.padding(vertical = Dim.s4), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.width(16.dp).height(4.dp).background(ink))
        Spacer(Modifier.width(Dim.s4))
        Caption(label)
    }
}

@Composable
private fun Credit(info: JSONObject) {
    val uri = LocalUriHandler.current
    val attribution = info.optString("attribution").takeIf { it.isNotEmpty() && !info.isNull("attribution") }
    val landing = info.optString("landing").takeIf { it.startsWith("https://") }
    SwapContent(attribution, contentKey = { attribution -> attribution != null }, layout = ContentLayout.Box) { attribution ->
        if (attribution != null) Fact(S.s_ghi_cong_9c291f64) {
            BasicText(attribution, style = Abook.type.bodySmall, modifier = Modifier.testTag("track_credit"))
        }
    }
    SwapContent(landing, contentKey = { landing -> landing != null }, layout = ContentLayout.Box) { landing ->
        if (landing != null) Fact(S.s_nguon_c76d57b3) {
            TextAction(S.s_mo_trang_nguon_af980960, { runCatching { uri.openUri(landing) } }, "track_source", align = Alignment.CenterStart)
        }
    }
}
