package vn.abook.player.ui.music.library

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import vn.abook.player.MusicLibrary
import vn.abook.player.S
import vn.abook.player.formatSize
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.CloseIcon
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.LucideIcon
import vn.abook.player.ui.components.LucidePaths
import vn.abook.player.ui.components.PageHeader
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.ScreenHeader
import vn.abook.player.ui.components.ScrollingTabs
import vn.abook.player.ui.components.SearchIcon
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.navigationClearance
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.dotJoined
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.insetSurface
import vn.abook.player.ui.theme.hover
import vn.abook.player.ui.components.Reveal

/** Hai phần của màn Nhạc: bài đã lưu (+ "Nhạc của tôi") và cả kho. */
enum class MusicPart(val label: String, val tag: String) {
    Saved(S.s_da_luu_6379aeba, "music_part_saved"),
    Library(S.s_kho_nhac_94affa81, "music_part_library"),
}

/** Chế độ chọn (mở từ "Đổi bài" › "Xem cả kho"): mỗi bài có nút "Dùng"; chọn xong quay lại màn trước, lưu qua cùng đường với gợi ý sẵn có. */
class PickTarget(val onUse: (String) -> Unit, val onBan: ((String) -> Unit)? = null)

/**
 * Màn "Nhạc" (tab đáy, DESIGN.md §7 "Nhạc"): "Đã lưu" (bài đã lưu, đã tải để nghe không mạng + lối sang "Nhạc của tôi") và "Kho nhạc"
 * (tìm, lọc theo danh sách phát / phong cách / cảm xúc / nhịp / độ dài / đã tải, đếm số bài, danh sách cuộn ảo). Chạm bài mở chi tiết.
 * `pick` khác null: chế độ chọn bài cho một đoạn (chỉ có Kho nhạc, có nút quay lại). Rời màn thì dừng nghe thử.
 */
@Composable
fun MusicScreen(
    state: LibraryState,
    sheets: SheetHost,
    modifier: Modifier = Modifier,
    pick: PickTarget? = null,
    onBack: (() -> Unit)? = null,
    onMyMusic: (() -> Unit)? = null,
    initialPart: MusicPart = MusicPart.Saved,
    initialQuery: String = "",
) {
    val ui by state.ui.collectAsState()
    LaunchedEffect(state) {
        state.open()
        if (initialQuery.isNotEmpty()) state.setQuery(initialQuery)
    }
    DisposableEffect(state) { onDispose { state.stopPreview() } }
    var part by rememberSaveable { mutableStateOf(if (pick != null) MusicPart.Library else initialPart) }
    LaunchedEffect(ui.libraryRequest) { if (ui.libraryRequest > 0) part = MusicPart.Library }
    Box(modifier.fillMaxSize().testTag("music_screen")) {
        Column(Modifier.fillMaxSize()) {
            // Đầu màn cố định, danh sách cuộn nằm DƯỚI nó (không chạy dưới thanh trạng thái): chừa thanh trạng thái ở đây
            Column(Modifier.statusBarsPadding().padding(horizontal = Dim.margin)) {
                SwapContent(pick, onBack, contentKey = { pick, onBack -> pick != null || onBack != null }, layout = ContentLayout.Column) { pick, onBack ->
                    if (pick != null || onBack != null) {
                        PageHeader(if (pick != null) S.s_chon_bai_cho_doan_840afc40 else S.s_nhac_0e4413e9, onBack ?: {})
                    } else {
                        ScreenHeader(S.s_nhac_0e4413e9, bottomGap = Dim.s8)
                    }
                }
                SwapContent(pick, contentKey = { pick -> pick == null }, layout = ContentLayout.Column) { pick ->
                    if (pick == null) {
                        ScrollingTabs(MusicPart.entries, part, { part = it }, { it.label }, { it.tag }, "music_parts")
                        Spacer(Modifier.height(Dim.s12))
                    }
                }
            }
            when {
                ui.loading -> Caption(S.s_dang_tai_465b1987, Modifier.padding(horizontal = Dim.margin).testTag("music_loading"))
                ui.error.isNotEmpty() -> InlineProblem(ui.error, state::open, "music_error", Modifier.padding(horizontal = Dim.margin))
                part == MusicPart.Saved -> SavedPart(ui, state, sheets, onMyMusic)
                else -> LibraryPart(ui, state, sheets, pick)
            }
        }
        PreviewBar(ui, state, Modifier.align(Alignment.BottomCenter))
        if (ui.meteredAsk.isNotEmpty()) {
            LaunchedEffect(ui.meteredAsk) {
                val links = ui.meteredAsk
                val bytes = ui.missingBytes(links.mapNotNull { ui.index?.byLink?.get(it) })
                sheets.show { dismiss -> MeteredAsk(bytes, { dismiss(); state.save(links, confirmed = true) }) { dismiss(); state.dismissMetered() } }
            }
        }
    }
}

@Composable
private fun SavedPart(ui: LibraryUi, state: LibraryState, sheets: SheetHost, onMyMusic: (() -> Unit)?) {
    val tracks = ui.savedTracks()
    val (count, bytes) = ui.savedOnDevice()
    val list = rememberLazyListState()
    LazyColumn(
        Modifier.fillMaxSize().testTag("music_saved").fadeEdges(list),
        state = list,
        contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, bottom = navigationClearance() + Dim.s48 + Dim.s48),
    ) {
        item(key = "summary") {
            Caption(S.s_da_tai_0_bai_1_3cac202f(count, formatSize(bytes)), Modifier.testTag("music_saved_summary").padding(bottom = Dim.s8))
            Reveal(!ui.online) { Caption(S.s_bai_da_tai_nghe_duoc_khi_khong_co_mang_ca12f3db, Modifier.padding(bottom = Dim.s8)) }
        }
        if (tracks.isEmpty()) {
            item(key = "empty") { Caption(S.s_chua_luu_bai_nao_6e7558df, Modifier.padding(vertical = Dim.s16).testTag("music_saved_empty")) }
        }
        items(tracks, key = { it.link }) { track ->
            TrackRow(track, ui, state, onOpen = { openTrack(sheets, state, track.link, null) })
            RowLine(start = ROW_TEXT_START)
        }
        if (onMyMusic != null) {
            item(key = "mine") {
                Spacer(Modifier.height(Dim.s24))
                ListItem(
                    S.s_nhac_cua_toi_f65b7ac6, onClick = onMyMusic, tag = "music_mine", chevron = true,
                    leading = { LucideIcon(LucidePaths.LIST_MUSIC, Abook.colors.text2) },
                )
            }
        }
    }
}

@Composable
private fun LibraryPart(ui: LibraryUi, state: LibraryState, sheets: SheetHost, pick: PickTarget?) {
    val index = ui.index ?: return
    val list = rememberLazyListState()
    val filters = ui.filters
    Column(Modifier.fillMaxSize()) {
        SearchField(filters.q, state::setQuery, Modifier.padding(horizontal = Dim.margin))
        Spacer(Modifier.height(Dim.s8))
        FilterChips(ui, index, state, sheets)
        Row(Modifier.fillMaxWidth().padding(horizontal = Dim.margin).heightIn(min = Dim.touch), verticalAlignment = Alignment.CenterVertically) {
            Caption(S.s_0_bai_1e392237(ui.shown.size), Modifier.weight(1f).testTag("music_count"))
            Reveal(filters.filtering) { TextAction(S.s_bo_loc_74de0064, state::clearFilters, "music_clear") }
        }
        if (filters.playlist.isNotEmpty()) {
            val missing = ui.shown.filter { it.link !in ui.downloaded }
            Reveal(missing.isNotEmpty()) {
                QuietButton(S.s_tai_ca_danh_sach_0_63e52378(formatSize(ui.missingBytes(missing))), { state.save(missing.map { it.link }) }, "music_save_playlist",
                    Modifier.padding(horizontal = Dim.margin).padding(bottom = Dim.s8))
            }
        }
        Reveal(!ui.online) { Caption(S.s_mat_mang_chi_nghe_thu_duoc_bai_da_tai_cab0d6f8, Modifier.padding(horizontal = Dim.margin).padding(bottom = Dim.s8)) }
        LazyColumn(
            Modifier.fillMaxSize().testTag("music_list").fadeEdges(list),
            state = list,
            contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, bottom = navigationClearance() + Dim.s48 + Dim.s48),
        ) {
            if (ui.shown.isEmpty()) item(key = "empty") { Caption(S.s_khong_co_bai_nao_hop_5b5b11b5, Modifier.padding(vertical = Dim.s16).testTag("music_empty")) }
            items(ui.shown, key = { it.link }) { track ->
                TrackRow(track, ui, state, pick = pick, onOpen = { openTrack(sheets, state, track.link, pick) })
                RowLine(start = ROW_TEXT_START)
            }
        }
    }
}

private val ROW_TEXT_START = 52.dp

/** Mở sheet chi tiết bài (cùng một bảng trượt cho Kho nhạc, Đã lưu, trang sách). */
fun openTrack(sheets: SheetHost, state: LibraryState, link: String, pick: PickTarget?, scene: Map<String, Double> = emptyMap()) {
    sheets.show { dismiss -> TrackSheet(state, link, dismiss, pick = pick, scene = scene) }
}

@Composable
private fun SearchField(query: String, onChange: (String) -> Unit, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val keyboard = LocalSoftwareKeyboardController.current
    Row(
        modifier.fillMaxWidth().height(Dim.touch).insetSurface(colors).padding(start = Dim.s12),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SearchIcon(colors.text2)
        Spacer(Modifier.width(Dim.s8))
        BasicTextField(
            value = query,
            onValueChange = onChange,
            modifier = Modifier.weight(1f).semantics { contentDescription = S.s_tim_trong_kho_nhac_b9972ac9 }.testTag("music_search"),
            singleLine = true,
            textStyle = Abook.type.body,
            cursorBrush = SolidColor(colors.accent),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { keyboard?.hide() }),
            decorationBox = { inner ->
                Box(contentAlignment = Alignment.CenterStart) {
                    Reveal(query.isEmpty()) { BasicText(S.s_tim_ten_bai_nguoi_sang_tac_fdee04f4, style = Abook.type.body.copy(color = colors.text3)) }
                    inner()
                }
            },
        )
        Reveal(query.isNotEmpty()) {
            Box(
                Modifier.size(Dim.touch).pressable { onChange("") }.semantics { contentDescription = S.s_xoa_o_tim_0bafa7ad }.testTag("music_search_clear"),
                contentAlignment = Alignment.Center,
            ) { CloseIcon(colors.text2, size = 18.dp) }
        }
    }
}

/** Một bộ lọc dạng chip: chữ là tên bộ lọc (hay lựa chọn đang bật), chạm mở bảng chọn "Tất cả" + các lựa chọn. */
private class ChipSpec(val tag: String, val title: String, val value: String, val options: List<Label>, val set: (String) -> MusicLibrary.Filters)

@Composable
private fun FilterChips(ui: LibraryUi, index: LibraryIndex, state: LibraryState, sheets: SheetHost) {
    val f = ui.filters
    val tempos = MusicLibrary.TEMPOS.zip(listOf(S.s_cham_6ddeaddc, S.s_vua_8af1c03b, S.s_nhanh_c2385879), ::Label)
    val lengths = MusicLibrary.LENGTHS.zip(listOf(S.s_duoi_2_phut_c8f6f04e, S.s_2_5_phut_29244d26, S.s_tren_5_phut_42aafebc), ::Label)
    val specs = listOf(
        ChipSpec("chip_playlist", S.s_danh_sach_phat_26862e10, f.playlist, index.playlists.map { Label(it.id, it.name) }) { f.copy(playlist = it) },
        ChipSpec("chip_style", S.s_phong_cach_d80ae8d9, f.style, index.styles) { f.copy(style = it) },
        ChipSpec("chip_emotion", S.s_cam_xuc_05c1aee0, f.emotion, index.emotions) { f.copy(emotion = it) },
        ChipSpec("chip_tempo", S.s_nhip_8a75919d, f.tempo, tempos) { f.copy(tempo = it) },
        ChipSpec("chip_length", S.s_do_dai_5e055f59, f.length, lengths) { f.copy(length = it) },
    )
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = Dim.margin).testTag("music_chips")
            .semantics { contentDescription = S.s_loc_kho_nhac_6c590fb5 },
        horizontalArrangement = Arrangement.spacedBy(Dim.s8),
    ) {
        for (spec in specs) {
            val chosen = spec.options.firstOrNull { it.id == spec.value }
            Chip(chosen?.label ?: spec.title, chosen != null, spec.tag, chevron = true) {
                sheets.show { dismiss -> ChipOptions(spec.title, spec.options, spec.value) { id -> dismiss(); state.setFilters(spec.set(id)) } }
            }
        }
        Chip(S.s_da_tai_b7362bbf, f.downloaded, "chip_downloaded", chevron = false) { state.setFilters(f.copy(downloaded = !f.downloaded)) }
    }
}

@Composable
private fun Chip(label: String, on: Boolean, tag: String, chevron: Boolean, onClick: () -> Unit) {
    val colors = Abook.colors
    val shape = RoundedCornerShape(Dim.radiusControl)
    Box(Modifier.heightIn(min = Dim.touch).pressable(onClick = onClick).testTag(tag), contentAlignment = Alignment.Center) {
        Row(
            Modifier.height(36.dp).clip(shape).background(if (on) colors.accentSoft else colors.hover).padding(horizontal = Dim.s12),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Reveal(on && !chevron) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CheckIcon(colors.accentText, size = 16.dp)
                    Spacer(Modifier.width(Dim.s4))
                }
            }
            BasicText(label, style = Abook.type.label.copy(color = if (on) colors.accentText else colors.text))
            Reveal(chevron) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Spacer(Modifier.width(Dim.s4))
                    LucideIcon(LucidePaths.CHEVRON_DOWN, if (on) colors.accentText else colors.text2, size = 16.dp)
                }
            }
        }
    }
}

@Composable
private fun ChipOptions(title: String, options: List<Label>, value: String, onPick: (String) -> Unit) {
    val list = rememberLazyListState()
    Column(Modifier.testTag("chip_options")) {
        BasicText(title, style = Abook.type.sectionTitle, modifier = Modifier.padding(bottom = Dim.s8))
        LazyColumn(Modifier.heightIn(max = 460.dp).fadeEdges(list), state = list) {
            items(listOf(Label("", S.s_tat_ca_49c73a31)) + options, key = { it.id }) { option ->
                val on = option.id == value
                ListItem(
                    option.label, onClick = { onPick(option.id) }, tag = "option_${option.id.ifEmpty { "all" }}",
                    titleColor = if (on) Abook.colors.accentText else Abook.colors.text,
                    trailing = if (on) ({ CheckIcon(Abook.colors.accentText) }) else null,
                )
            }
        }
    }
}

/** Thanh "Đang nghe thử · tên · ■" ở đáy màn (nổi trên danh sách). */
@Composable
private fun PreviewBar(ui: LibraryUi, state: LibraryState, modifier: Modifier = Modifier) {
    val link = ui.previewing ?: return
    val track = ui.index?.byLink?.get(link) ?: return
    val colors = Abook.colors
    Row(
        modifier.padding(horizontal = Dim.margin).padding(bottom = navigationClearance() + Dim.s8).fillMaxWidth()
            .clip(RoundedCornerShape(Dim.radiusControl)).background(colors.panel).border(1.dp, colors.line, RoundedCornerShape(Dim.radiusControl))
            .padding(start = Dim.s16).testTag("preview_bar"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BasicText(listOf(S.s_dang_nghe_thu_f1fb4cba, track.title).dotJoined(), style = Abook.type.label, modifier = Modifier.weight(1f).padding(vertical = Dim.s12))
        Box(
            Modifier.size(Dim.touch).pressable { state.stopPreview() }.semantics { contentDescription = S.s_dung_nghe_f20939be }.testTag("preview_stop"),
            contentAlignment = Alignment.Center,
        ) { LucideIcon(LucidePaths.SQUARE, colors.text, size = 18.dp) }
    }
}

@Composable
private fun MeteredAsk(bytes: Long, onGo: () -> Unit, onLater: () -> Unit) {
    Column(Modifier.testTag("music_metered")) {
        BasicText(S.s_tai_qua_mang_tinh_phi_8d46c411, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        BasicText(S.s_tai_0_qua_du_lieu_di_dong_1a67cb08(formatSize(bytes)), style = Abook.type.body.copy(color = Abook.colors.text2))
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(S.s_van_tai_b166c8ee, onGo, Modifier.fillMaxWidth().testTag("metered_go"))
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_de_sau_9be0a7ab, onLater, "metered_later", Modifier.fillMaxWidth())
    }
}
