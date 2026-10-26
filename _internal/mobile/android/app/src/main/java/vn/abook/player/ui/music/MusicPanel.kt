package vn.abook.player.ui.music

import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.expandHorizontally
import androidx.compose.animation.shrinkHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.BiasAlignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import kotlinx.coroutines.delay
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import vn.abook.player.MusicImport
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.ChevronIcon
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.PinIcon
import vn.abook.player.ui.components.PlusIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.ShuffleIcon
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.components.fadeEdges

/**
 * Nhạc nền của một cuốn - MỘT bảng cho "…" của Đang nghe và bảng "Thêm" của trang sách (cùng lựa chọn, lưu vào lớp sửa nên đi theo sách).
 * Sách chỉ có chữ: danh sách chọn (dấu tích đầu dòng, chọn là đổi ngay - bảng vẫn mở để thấy mức), "Thêm nhạc của bạn" mở hộp chọn file và chọn luôn
 * Nhạc của tôi. Sách gắn nhạc sẵn (như Sửa sách > Nhạc nền của web): công tắc "Nhạc nền: Bật", mức nhạc, rồi từng đoạn nhạc - chạm một đoạn thì trượt
 * sang trang của đoạn ấy (Im lặng / Có nhạc, Về bài gốc, Đổi bài). Lời báo chỉ khi có điều cần biết; bài đang phát (ghi công CC BY) trước danh sách đoạn.
 * `player`: nhạc của trình phát khi cuốn này đang nạp (null ở trang của cuốn khác).
 */
@Composable
fun MusicPanel(music: MusicState, bookId: String, player: PlayerMusic?, modifier: Modifier = Modifier) {
    LaunchedEffect(music, bookId) { music.open(bookId) }
    val all by music.ui.collectAsState()
    val ui = all.takeIf { it.bookId == bookId } ?: BookMusicUi(bookId = bookId)
    val book = ui.book
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris -> music.importMine(uris.map(Uri::toString)) }
    val add = { picker.launch(MusicImport.MIME_TYPES) }
    // Trang của một đoạn: khoá đoạn ("" = trang chính). Back: khép "Đổi bài" trước, rồi về trang chính.
    var cueKey by rememberSaveable(bookId) { mutableStateOf("") }
    val cue = book?.cues?.firstOrNull { it.key == cueKey }
    BackHandler(enabled = cue != null) {
        if (ui.swapKey.isNotEmpty()) music.swap("") else cueKey = ""
    }
    Box(modifier.fillMaxWidth().testTag("music_panel_pages")) {
        SheetPages(cue?.key ?: "", { if (it.isEmpty()) 0 else 1 }, "music_pages") { shown ->
            val page = book?.cues?.firstOrNull { it.key == shown }
            if (page == null) MainPage(music, ui, player, add) { key -> cueKey = key }
            else CuePage(music, ui, page, add)
        }
    }
}

@Composable
private fun MainPage(music: MusicState, ui: BookMusicUi, player: PlayerMusic?, onAdd: () -> Unit, onCue: (String) -> Unit) {
    val book = ui.book
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("music_panel")) {
        val stage = when {
            book != null -> book.kind
            ui.failed -> null
            else -> MusicKind.None
        }
        // Khung chờ -> nội dung thật: trượt lên ngắn, chiều cao đổi dần (không thay cứng).
        AnimatedContent(
            targetState = stage to (book == null),
            transitionSpec = {
                (slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 8 } + fadeIn(tween(MotionMs.MEDIUM)))
                    .togetherWith(slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it / 8 } + fadeOut(tween(MotionMs.FAST_OUT)))
                    .using(SizeTransform(clip = false))
            },
            label = "music-panel",
        ) { (kind, waiting) ->
            when {
                kind == null -> InlineProblem(MusicText.LOAD_FAILED, music::retry, "music_load_problem")
                waiting -> MusicSkeleton()
                kind == MusicKind.Playlist -> PlaylistChoices(music, ui, onAdd)
                kind == MusicKind.Packaged -> {
                    val on = book?.enabled == true
                    SwitchRow(MusicText.switchLabel(on), on, music::setEnabled, "music_enabled")
                }
                else -> Caption(MusicText.NONE, Modifier.padding(vertical = Dim.s12).testTag("music_none"))
            }
        }
        if (book != null && book.kind != MusicKind.None) {
            Reveal(MusicText.playing(book)) { LevelMeter(book.levelDb, enabled = !ui.busy, music::setLevel) }
            InlineProblem(ui.problem, tag = "music_problem")
            val note = MusicText.note(book, ui.menu, player)
            var lastNote by remember { mutableStateOf(note) }
            if (note.isNotEmpty()) lastNote = note
            Reveal(note.isNotEmpty()) { Caption(lastNote, Modifier.padding(top = Dim.s12).testTag("music_note")) }
        }
        MusicCreditBlock(player?.credit)
        if (book != null && book.kind == MusicKind.Packaged && book.cues.isNotEmpty()) CueList(book, enabled = !ui.busy, onCue)
    }
}

/**
 * Các đoạn nhạc gắn sẵn, như danh sách của web: tên bài (im lặng thì mờ + gạch ngang), dưới là chương · giờ · tác giả · "bài của bạn". Nhạc nền đang tắt
 * thì cả danh sách mờ đi (vẫn sửa được - bật lại là có).
 */
@Composable
private fun CueList(book: BookMusic, enabled: Boolean, onCue: (String) -> Unit) {
    val colors = Abook.colors
    // Như opacity-50 của web khi tắt, nhưng bằng mực: tên và dòng phụ chuyển sang mực nhạt nhất (không làm mờ cả khối bằng alpha).
    val hintInk by animateColorAsState(if (book.enabled) colors.text2 else colors.text3, tween(MotionMs.MEDIUM), label = "cues-hint")
    Column(Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("music_cues")) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(colors.line))
        book.cues.forEachIndexed { index, cue ->
            key(cue.key) {
                val ink by animateColorAsState(if (cue.silenced || !book.enabled) colors.text3 else colors.text, tween(MotionMs.FAST), label = "cue-ink")
                ListItem(
                    MusicText.cueTitle(cue), Modifier, if (enabled) ({ onCue(cue.key) }) else null, "music_cue_$index",
                    hint = MusicText.cueLine(cue),
                    hintColor = hintInk,
                    titleColor = ink,
                    titleStyle = Abook.type.body.copy(textDecoration = if (cue.silenced) TextDecoration.LineThrough else null),
                    chevron = true,
                )
            }
        }
    }
}

/**
 * Trang của một đoạn: tên bài + dòng chương · giờ, rồi đúng ba nút của web theo đúng thứ tự - Về bài gốc (khi đã đổi), Đổi bài (icon Shuffle, mở danh
 * sách bài bên dưới), Im lặng / Có nhạc. Nút chữ hổ phách như nút chữ khác của app, mực nút đầu thẳng mép chữ; hẹp thì xuống hàng.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CuePage(music: MusicState, ui: BookMusicUi, cue: MusicCue, onAdd: () -> Unit) {
    val colors = Abook.colors
    val enabled = !ui.busy
    val open = ui.swapKey == cue.key
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("music_cue_page")) {
        BasicText(
            MusicText.cueTitle(cue),
            style = Abook.type.sectionTitle.copy(
                color = if (cue.silenced) colors.text3 else colors.text,
                textDecoration = if (cue.silenced) TextDecoration.LineThrough else null,
            ),
            modifier = Modifier.padding(top = Dim.s4).testTag("music_cue_title"),
        )
        Caption(MusicText.cueLine(cue), Modifier.padding(top = Dim.s4))
        FlowRow(Modifier.fillMaxWidth().padding(vertical = Dim.s4), horizontalArrangement = Arrangement.spacedBy(Dim.s24)) {
            AnimatedVisibility(
                cue.pinned,
                enter = expandHorizontally(tween(MotionMs.MEDIUM, easing = Motion.Decelerate), Alignment.Start) + fadeIn(tween(MotionMs.MEDIUM)),
                exit = shrinkHorizontally(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate), Alignment.Start) + fadeOut(tween(MotionMs.FAST_OUT)),
            ) {
                CueAction(MusicText.ORIGINAL_LABEL, enabled, "music_cue_original") { music.pin(cue.key, null) }
            }
            CueAction(MusicText.SWAP_LABEL, enabled, "music_cue_swap", icon = { ShuffleIcon(it, size = 16.dp) }, expanded = open) {
                music.swap(if (open) "" else cue.key)
            }
            CueAction(if (cue.silenced) MusicText.UNSILENCE_LABEL else MusicText.SILENCE_LABEL, enabled, "music_cue_silence") {
                music.silence(cue.key, !cue.silenced)
            }
        }
        Reveal(open) { SwapList(music, ui, onAdd) }
        InlineProblem(ui.problem, tag = "music_problem")
    }
}

/** Nút chữ của một đoạn (nút ghost của web): cao 48, icon 16 trước chữ nếu có; đang lưu thì nhạt và không bấm được. */
@Composable
private fun CueAction(
    label: String,
    enabled: Boolean,
    tag: String,
    icon: (@Composable (Color) -> Unit)? = null,
    expanded: Boolean? = null,
    onClick: () -> Unit,
) {
    val colors = Abook.colors
    val ink by animateColorAsState(if (enabled) colors.accentText else colors.text3, tween(MotionMs.FAST), label = "cue-action")
    Row(
        Modifier.heightIn(min = Dim.s48)
            .then(if (enabled) Modifier.pressable(onClick = onClick) else Modifier.semantics { disabled() })
            .semantics { if (expanded != null) stateDescription = if (expanded) "Đang mở" else "Đang đóng" }
            .testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            icon(ink)
            Spacer(Modifier.size(Dim.s8))
        }
        BasicText(label, style = Abook.type.bodyStrong.copy(color = ink))
    }
}

/** "Đổi bài" (MyMusic.tsx SwapTrack): các bài trong Nhạc của tôi - tên, nghệ sĩ · độ dài, chú thích, "Chọn" có ghim. Trống thì mời thêm nhạc. */
@Composable
private fun SwapList(music: MusicState, ui: BookMusicUi, onAdd: () -> Unit) {
    val colors = Abook.colors
    val mine = ui.mine
    val stage = when {
        ui.swapFailed && mine == null -> 0
        mine == null -> 1
        mine.isEmpty() -> 2
        else -> 3
    }
    AnimatedContent(
        targetState = stage,
        transitionSpec = {
            (slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 8 } + fadeIn(tween(MotionMs.MEDIUM)))
                .togetherWith(slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it / 8 } + fadeOut(tween(MotionMs.FAST_OUT)))
                .using(SizeTransform(clip = false))
        },
        label = "swap-list",
        modifier = Modifier.fillMaxWidth().testTag("music_swap"),
    ) { shown ->
        Column(Modifier.fillMaxWidth()) {
            Box(Modifier.fillMaxWidth().height(1.dp).background(colors.line))
            when (shown) {
                0 -> InlineProblem(MusicText.SWAP_FAILED, music::retrySwap, "music_swap_problem")
                1 -> MusicSkeleton(rows = 2)
                2 -> {
                    Caption(MusicText.NO_MINE, Modifier.padding(vertical = Dim.s8).testTag("music_swap_empty"))
                    AddRow(ui, onAdd)
                }
                else -> ui.mine.orEmpty().forEachIndexed { index, track -> key(track.link) {
                    val note = MusicText.mineNote(track)
                    val choosing = ui.choosing == track.link
                    ListItem(
                        track.title, Modifier, if (!ui.busy) ({ music.pin(ui.swapKey, track.link) }) else null, "music_mine_$index",
                        hint = MusicText.mineLine(track).ifEmpty { null },
                        trailing = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                PinIcon(if (choosing) colors.text3 else colors.accentText, size = 16.dp)
                                Spacer(Modifier.size(Dim.s4))
                                BasicText(MusicText.CHOOSE_LABEL, style = Abook.type.bodySmall.copy(color = if (choosing) colors.text3 else colors.accentText))
                            }
                        },
                        below = if (note.isNotEmpty()) ({ Caption(note) }) else null,
                    )
                } }
            }
        }
    }
}

/** Hàng "Thêm nhạc của bạn": tiến độ (xong / tổng) chạy ngay hàng này. */
@Composable
private fun AddRow(ui: BookMusicUi, onAdd: () -> Unit) {
    val colors = Abook.colors
    ListItem(
        if (ui.importing) "Đang thêm ${ui.done}/${ui.total}" else MusicText.ADD_LABEL, Modifier,
        if (ui.importing) null else onAdd, "music_add",
        titleColor = if (ui.importing) colors.text else colors.accentText,
        leading = { PlusIcon(if (ui.importing) colors.text2 else colors.accentText) },
        below = if (ui.importing) ({ StageProgress { if (ui.total > 0) ui.done.toFloat() / ui.total else 0f } }) else null,
    )
    Reveal(ui.notice.isNotEmpty() && !ui.importing) { Caption(ui.notice, Modifier.testTag("music_notice")) }
}

@Composable
private fun PlaylistChoices(music: MusicState, ui: BookMusicUi, onAdd: () -> Unit) {
    val book = ui.book ?: return
    val chosen = MusicText.chosen(book)
    val colors = Abook.colors
    // Danh mục tải xong thì thêm hàng: khung giãn dần, không nhảy.
    Column(Modifier.fillMaxWidth().animateContentSize(tween(MotionMs.MEDIUM, easing = Motion.Standard))) {
        for (option in MusicText.options(ui.menu, book)) {
            key(option.id ?: "auto") { OptionRow(option, option.id == chosen, enabled = !ui.busy && !option.disabled) { music.choose(option.id) } }
        }
        AddRow(ui, onAdd)
    }
}

/** Một lựa chọn: dấu tích đầu dòng (luôn giữ chỗ, nở / thu), tên hổ phách khi đang chọn, mô tả dưới tên, độ dài / số bài ở mép phải. */
@Composable
private fun OptionRow(option: MusicOption, chosen: Boolean, enabled: Boolean, onChoose: () -> Unit) {
    val colors = Abook.colors
    val mark by animateFloatAsState(if (chosen) 1f else 0f, Motion.Expand, label = "mark")
    val ink by animateColorAsState(
        when {
            chosen -> colors.accentText
            option.disabled -> colors.text3
            else -> colors.text
        },
        tween(MotionMs.FAST), label = "ink",
    )
    ListItem(
        option.label,
        Modifier.semantics {
            selected = chosen
            if (option.disabled) disabled()
        },
        if (enabled) onChoose else null,
        "music_option_${option.id ?: "auto"}",
        hint = option.description.ifEmpty { null },
        hintColor = colors.text3,
        titleColor = ink,
        leading = {
            Box(Modifier.size(Dim.s24).graphicsLayer { scaleX = mark; scaleY = mark }, contentAlignment = Alignment.CenterStart) {
                CheckIcon(colors.accentText)
            }
        },
        trailing = if (option.hint.isNotEmpty()) ({ BasicText(option.hint, style = Abook.type.caption.copy(color = colors.text2)) }) else null,
        role = Role.RadioButton,
    )
}

/**
 * "Mức nhạc dưới giọng đọc" (chữ của web): một hàng vạch to dần từ nhỏ tới to như thanh âm lượng - năm, sáu mức nằm vừa một hàng ở 360dp kể cả chữ 1.3
 * (lưới ba cột để lại ô trống cuối). Vạch tới mức đang chọn tô hổ phách, chữ của mức hiện dưới tên (cùng chữ với ô chọn của web).
 */
@Composable
private fun LevelMeter(level: Double, enabled: Boolean, onPick: (Double) -> Unit) {
    val colors = Abook.colors
    val options = MusicLevels.options(level).reversed()
    val chosen = options.indexOfFirst { it.first == level }
    Column(Modifier.fillMaxWidth().padding(top = Dim.s16).testTag("music_levels")) {
        BasicText(MusicLevels.TITLE, style = Abook.type.bodyStrong)
        AnimatedContent(
            targetState = MusicLevels.label(level),
            transitionSpec = {
                (slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 2 } + fadeIn(tween(MotionMs.MEDIUM)))
                    .togetherWith(slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it / 2 } + fadeOut(tween(MotionMs.FAST_OUT)))
                    .using(SizeTransform(clip = false))
            },
            label = "level-label",
            modifier = Modifier.padding(top = Dim.s4).testTag("music_level_value"),
        ) { label -> BasicText(label, style = Abook.type.bodySmall.copy(color = colors.accentText)) }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
            options.forEachIndexed { index, (value, label) ->
                val fill by animateColorAsState(if (index <= chosen) colors.accent else colors.fg3, tween(MotionMs.FAST), label = "level-bar")
                val step = index.toFloat() / (options.size - 1).coerceAtLeast(1)
                val tall = 20.dp + (48.dp - 20.dp) * step
                // Vạch đầu sát mép trái, vạch cuối sát mép phải (cùng mép với chữ), các vạch cách đều; cả ô vẫn là chỗ chạm.
                Box(
                    Modifier.weight(1f).height(64.dp)
                        .then(if (enabled) Modifier.pressable(Role.RadioButton) { onPick(value) } else Modifier)
                        .semantics {
                            selected = value == level
                            contentDescription = label
                        }
                        .testTag("music_level_${value.toInt()}"),
                    contentAlignment = BiasAlignment(-1f + 2f * step, 1f),
                ) {
                    Box(Modifier.padding(bottom = Dim.s8).size(Dim.s16, tall).clip(RoundedCornerShape(Dim.radiusControl)).background(fill))
                }
            }
        }
    }
}

/**
 * Bài đang phát (CC BY đòi nêu tác giả ở nơi nhạc phát): hàng "Đang phát" + tên bài · tác giả; chạm mở đủ ghi công, giấy phép (mở trang giấy phép), lời
 * "đã chỉnh sửa" và trang của bài. Không có bài thì khép lại.
 */
@Composable
fun MusicCreditBlock(credit: MusicCredit?) {
    var last by remember { mutableStateOf(credit) }
    if (credit != null) last = credit
    var open by remember(credit) { mutableStateOf(false) }
    val turn by animateFloatAsState(if (open) 1f else 0f, Motion.Expand, label = "turn")
    val links = LocalUriHandler.current
    val openUri: (String) -> Unit = { uri -> runCatching { links.openUri(uri) } }
    // Khối nằm cuối bảng: mở ra thì cuộn cho thấy đủ phần vừa mở, không để nó nở ra ngoài mép.
    val into = remember { BringIntoViewRequester() }
    LaunchedEffect(open) {
        if (!open) return@LaunchedEffect
        delay(MotionMs.MEDIUM.toLong())
        into.bringIntoView()
    }
    Reveal(credit != null) {
        val shown = last ?: return@Reveal
        Column(Modifier.fillMaxWidth().padding(top = Dim.s12).bringIntoViewRequester(into).testTag("music_credit")) {
            Box(Modifier.fillMaxWidth().height(1.dp).background(Abook.colors.line))
            ListItem(
                "Đang phát", Modifier, { open = !open }, "music_credit_toggle",
                hint = MusicText.creditLine(shown),
                trailing = { ChevronIcon(Abook.colors.text3, turn = { turn }) },
            )
            Reveal(open) {
                Column(Modifier.fillMaxWidth().testTag("music_credit_detail")) {
                    BasicText(MusicText.creditText(shown), style = Abook.type.bodySmall)
                    if (shown.license.isNotEmpty() || shown.licenseUrl.isNotEmpty()) {
                        val label = MusicText.licenseLabel(shown.license, shown.licenseUrl)
                        if (shown.licenseUrl.isNotEmpty()) ActionRow("Giấy phép", label, { openUri(shown.licenseUrl) }, "music_license")
                        else ListRow("Giấy phép") { BasicText(label, style = Abook.type.bodySmall) }
                    }
                    if (MusicText.needsModifiedNote(shown.license)) Caption(MusicText.MODIFIED_NOTE, Modifier.padding(bottom = Dim.s8))
                    if (shown.landing.isNotEmpty()) ActionRow("Trang của bài nhạc", "Mở", { openUri(shown.landing) }, "music_landing")
                }
            }
        }
    }
}

/** Đang đọc nhạc của cuốn: khung xám đúng hình ba hàng lựa chọn (DESIGN.md §2 "đang tải"), không vòng xoay. */
@Composable
private fun MusicSkeleton(rows: Int = 3) {
    Column(Modifier.fillMaxWidth().testTag("music_loading")) {
        for (width in listOf(0.5f, 0.3f, 0.62f).take(rows)) {
            Row(Modifier.fillMaxWidth().height(56.dp), verticalAlignment = Alignment.CenterVertically) {
                Spacer(Modifier.size(Dim.s24 + Dim.s12, 1.dp))
                Box(Modifier.fillMaxWidth(width).height(14.dp).clip(RoundedCornerShape(Dim.radiusControl)).background(Abook.colors.bgSunken))
            }
        }
    }
}
