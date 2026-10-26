package vn.abook.player.ui.music

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import kotlinx.coroutines.delay
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import vn.abook.player.MusicImport
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.ChevronIcon
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.PlusIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/**
 * Nhạc nền của một cuốn - MỘT bảng cho "…" của Đang nghe và bảng "Thêm" của trang sách (cùng lựa chọn, lưu vào lớp sửa nên đi theo sách).
 * Sách chỉ có chữ: danh sách chọn (dấu tích đầu dòng, chọn là đổi ngay - bảng vẫn mở để thấy mức), "Thêm nhạc" mở hộp chọn file và chọn luôn Nhạc của tôi.
 * Sách gắn nhạc sẵn: một công tắc. Cả hai: "Mức nhạc" mở ra khi có nhạc, lời báo chỉ khi có điều cần biết, cuối cùng là bài đang phát (ghi công CC BY).
 * `player`: nhạc của trình phát khi cuốn này đang nạp (null ở trang của cuốn khác).
 */
@Composable
fun MusicPanel(music: MusicState, bookId: String, player: PlayerMusic?, modifier: Modifier = Modifier) {
    LaunchedEffect(music, bookId) { music.open(bookId) }
    val all by music.ui.collectAsState()
    val ui = all.takeIf { it.bookId == bookId } ?: BookMusicUi(bookId = bookId)
    val book = ui.book
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris -> music.importMine(uris.map(Uri::toString)) }
    Column(modifier.fillMaxWidth().verticalScroll(rememberScrollState()).testTag("music_panel")) {
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
                kind == null -> InlineProblem("Chưa đọc được nhạc nền", music::retry, "music_load_problem")
                waiting -> MusicSkeleton()
                kind == MusicKind.Playlist -> PlaylistChoices(music, ui) { picker.launch(MusicImport.MIME_TYPES) }
                kind == MusicKind.Packaged -> SwitchRow("Phát nhạc nền", book?.enabled == true, music::setEnabled, "music_enabled")
                else -> Caption("Cuốn này không có nhạc nền.", Modifier.padding(vertical = Dim.s12).testTag("music_none"))
            }
        }
        if (book != null && book.kind != MusicKind.None) {
            Reveal(MusicText.playing(book)) { LevelGrid(book.levelDb, enabled = !ui.busy, music::setLevel) }
            InlineProblem(ui.problem, tag = "music_problem")
            val note = MusicText.note(book, ui.menu, player)
            var lastNote by remember { mutableStateOf(note) }
            if (note.isNotEmpty()) lastNote = note
            Reveal(note.isNotEmpty()) { Caption(lastNote, Modifier.padding(top = Dim.s12).testTag("music_note")) }
        }
        MusicCreditBlock(player?.credit)
    }
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
        ListItem(
            if (ui.importing) "Đang thêm ${ui.done}/${ui.total}" else MusicText.ADD_LABEL, Modifier,
            if (ui.importing) null else onAdd, "music_add",
            titleColor = if (ui.importing) colors.text else colors.accentText,
            leading = { PlusIcon(if (ui.importing) colors.text2 else colors.accentText) },
            below = if (ui.importing) ({ StageProgress { if (ui.total > 0) ui.done.toFloat() / ui.total else 0f } }) else null,
        )
        Reveal(ui.notice.isNotEmpty() && !ui.importing) { Caption(ui.notice, Modifier.testTag("music_notice")) }
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

/** "Mức nhạc": lưới ba cột như tốc độ; ô đang chọn chữ hổ phách đậm, không dấu tích (DESIGN.md §6 ô chọn dạng lưới). */
@Composable
private fun LevelGrid(level: Double, enabled: Boolean, onPick: (Double) -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s16).testTag("music_levels")) {
        BasicText("Mức nhạc", style = Abook.type.bodyStrong, modifier = Modifier.padding(bottom = Dim.s4))
        for (row in MusicLevels.options(level).chunked(3)) Row(Modifier.fillMaxWidth()) {
            for ((value, label) in row) {
                val chosen = value == level
                Box(
                    Modifier.weight(1f).heightIn(min = 56.dp)
                        .then(if (enabled) Modifier.pressable(Role.RadioButton) { onPick(value) } else Modifier)
                        .semantics { selected = chosen }.testTag("music_level_${value.toInt()}"),
                    contentAlignment = Alignment.Center,
                ) {
                    BasicText(label, style = Abook.type.body.copy(
                        color = if (chosen) Abook.colors.accentText else Abook.colors.text,
                        fontWeight = if (chosen) FontWeight.Bold else FontWeight.Normal,
                    ))
                }
            }
            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
        }
        Caption(MusicLevels.CLEAREST_NOTE)
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
                hint = MusicText.creditLine(shown), hintStyle = Abook.type.bodySmall,
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
                    if (shown.landing.isNotEmpty()) ActionRow("Trang của bài", "Mở", { openUri(shown.landing) }, "music_landing")
                }
            }
        }
    }
}

/** Đang đọc nhạc của cuốn: khung xám đúng hình ba hàng lựa chọn (DESIGN.md §2 "đang tải"), không vòng xoay. */
@Composable
private fun MusicSkeleton() {
    Column(Modifier.fillMaxWidth().testTag("music_loading")) {
        for (width in listOf(0.5f, 0.3f, 0.62f)) {
            Row(Modifier.fillMaxWidth().height(56.dp), verticalAlignment = Alignment.CenterVertically) {
                Spacer(Modifier.size(Dim.s24 + Dim.s12, 1.dp))
                Box(Modifier.fillMaxWidth(width).height(14.dp).clip(RoundedCornerShape(4.dp)).background(Abook.colors.bgSunken))
            }
        }
    }
}
