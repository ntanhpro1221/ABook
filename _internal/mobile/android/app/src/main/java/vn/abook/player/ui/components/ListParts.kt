package vn.abook.player.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.layout
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.Constraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.collapse
import androidx.compose.ui.semantics.expand
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/*
 * Khối dựng danh sách chung (Cài đặt, Thêm sách, Sửa sách): khoảng trắng + tiêu đề nhỏ thay khung (DESIGN.md §4.2), hàng = tên (16) + mô tả
 * một dòng (12, mực phụ) bên trái, điều khiển bên phải; nhóm chọn-một nằm DƯỚI tên, trải hết bề ngang. Chữ dài xuống dòng, không cắt.
 */

/** Một lựa chọn chữ + giá trị (số giờ, số phút...) cho [ChoiceRow]. */
data class Option<V>(val value: V, override val label: String) : Choice {
    override val key: String get() = value.toString()
}


/** Đầu màn con: đệm trên 12, hàng cao 48 - nút ← rồi tiêu đề, chân chữ trùng tiêu đề màn gốc (ScreenHeader). */
@Composable
fun PageHeader(title: String, onBack: () -> Unit, modifier: Modifier = Modifier, trailing: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth().padding(top = Dim.s12).heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically) {
        BackButton(onBack)
        // Mũi tên 24 nằm đầu ô chạm 48: kéo tiêu đề lùi vào nửa trống của ô để nó "sát sau" nét mũi tên (DESIGN.md §6 "Đầu màn").
        BasicText(title, style = Abook.type.screenTitle, modifier = Modifier.weight(1f).offset(x = -Dim.s12))
        if (trailing != null) trailing()
    }
}


/** Khối phẳng: khoảng 32 trên (giữa các phần của một màn), tiêu đề nhỏ nếu có, các hàng cách nhau bằng vạch mảnh ([RowLine]). */
@Composable
fun ListSection(title: String? = null, modifier: Modifier = Modifier, first: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth()) {
        if (title != null) SectionTitle(title, first) else Spacer(Modifier.height(if (first) Dim.s16 else Dim.sectionGap))
        content()
    }
}

/** Tiêu đề nhỏ của một phần: khoảng 32 trên (16 khi là phần đầu), hàng cao 48. Dùng riêng trong LazyColumn (mỗi hàng của phần là một mục). */
@Composable
fun SectionTitle(title: String, first: Boolean = false, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().padding(top = if (first) Dim.s16 else Dim.sectionGap).heightIn(min = Dim.s48), contentAlignment = Alignment.CenterStart) {
        BasicText(title, style = Abook.type.sectionTitle)
    }
}

/** Vạch chia hàng: 1 dp màu vạch, trải hết cột (DESIGN.md §5.5 "Viền"). */
@Composable
fun RowLine(modifier: Modifier = Modifier, start: Dp = 0.dp) {
    Box(modifier.fillMaxWidth().padding(start = start).height(1.dp).background(Abook.colors.line))
}

/** Tên + mô tả của một hàng. */
@Composable
private fun RowLabel(label: String, hint: String?, modifier: Modifier = Modifier) {
    Column(modifier) {
        BasicText(label, style = Abook.type.bodyStrong)
        if (hint != null) {
            Spacer(Modifier.height(2.dp))
            RowHint(hint)
        }
    }
}

/** Dòng mô tả dưới tên một hàng (DESIGN.md §6: 14, `--fg-2` = bodySmall): MỘT kiểu cho mọi hàng và mọi dòng phụ dưới một tên - hàng nào cũng gọi hàm này, không tự chọn cỡ chữ; chỉ màu đổi được (lỗi). */
@Composable
fun RowHint(text: String, modifier: Modifier = Modifier, color: Color = Abook.colors.text2) {
    BasicText(text, style = Abook.type.bodySmall.copy(color = color), modifier = modifier)
}

/** Hàng có tên bên trái, điều khiển / giá trị bên phải (canh giữa hàng). Cao tối thiểu 56. */
@Composable
fun ListRow(
    label: String,
    modifier: Modifier = Modifier,
    hint: String? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier.fillMaxWidth().heightIn(min = 56.dp).padding(vertical = Dim.s12),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RowLabel(label, hint, Modifier.weight(1f))
        if (trailing != null) {
            Spacer(Modifier.width(Dim.s16))
            trailing()
        }
    }
}

/** Hàng công tắc: CẢ hàng là chỗ chạm (không chỉ cái núm). */
@Composable
fun SwitchRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit, tag: String, hint: String? = null) {
    ListRow(
        label,
        Modifier.pressable(Role.Switch) { onChange(!checked) }
            .semantics { stateDescription = if (checked) "Bật" else "Tắt" }
            .testTag(tag),
        hint = hint,
    ) {
        Switch(checked)
    }
}

/** Hàng chọn-một: tên (và mô tả) ở trên, hàng chữ có gạch chân hổ phách bên dưới, trải hết bề ngang. */
@Composable
fun <T : Choice> ChoiceSetting(
    label: String,
    options: List<T>,
    value: T,
    onPick: (T, Offset) -> Unit,
    tag: String,
    hint: String? = null,
) {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s12, bottom = Dim.s4).testTag(tag)) {
        RowLabel(label, hint, Modifier.fillMaxWidth())
        Spacer(Modifier.height(Dim.s4))
        ChoiceRow(options, value, onPick, Modifier.fillMaxWidth(), tag = tag)
    }
}

/** Nút chữ (DESIGN.md §6 "Nút (c)": màu chữ nhấn), cao 48, mép chữ chạm mép phải của cột. */
@Composable
fun TextAction(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier, align: Alignment = Alignment.CenterEnd) {
    Box(
        modifier.heightIn(min = Dim.s48).widthIn(min = Dim.touch).pressable(onClick = onClick).testTag(tag),
        contentAlignment = align,
    ) {
        BasicText(label, style = Abook.type.label.copy(color = Abook.colors.accentText))
    }
}

/** Hàng có một việc bên phải ("Xem", "Gửi", "Dọn"...). */
@Composable
fun ActionRow(label: String, action: String, onClick: () -> Unit, tag: String, hint: String? = null) {
    ListRow(label, hint = hint) { TextAction(action, onClick, tag) }
}


/** Hàng mở một bảng / một màn: tên (+ dòng giá trị), mũi tên ">" ở mép phải; biểu tượng đầu hàng và mũi tên cùng thẳng dòng đầu của tên. */
@Composable
fun DisclosureRow(
    title: String,
    onClick: () -> Unit,
    tag: String,
    modifier: Modifier = Modifier,
    summary: String? = null,
    icon: (@Composable () -> Unit)? = null,
    hintColor: Color = Abook.colors.text2,
) {
    ListItem(
        title, modifier, onClick, tag, hint = summary?.takeIf { it.isNotEmpty() }, hintColor = hintColor,
        leading = icon, leadingWidth = IconSlot, leadingGap = IconGap, chevron = true, titleStyle = Abook.type.bodyStrong,
    )
}

/** Cột biểu tượng của hàng nhóm và khoảng tới chữ: vạch chia hàng thụt theo chữ (bắt đầu ở [IconSlot] + [IconGap]). */
val IconSlot = 22.dp
val IconGap = 14.dp

/** Hàng mở / khép tại chỗ: mũi tên ">" xoay xuống khi mở (web: DisclosureRow `expanded`), trợ năng đọc được việc mở / khép. */
private fun Modifier.toggles(open: Boolean, onToggle: () -> Unit): Modifier = semantics {
    if (open) collapse { onToggle(); true } else expand { onToggle(); true }
}

/**
 * Lời giải thích gập sau dấu "?" (web: MoreInfo của shared/SettingsNav.tsx): một hàng [label] ("Tìm hiểu thêm", "Cách lấy mã"...) có biểu tượng "?" và mũi
 * tên; chạm mở câu [text] ngay dưới, trong cột
 * chữ của hàng - không chiếm chỗ khi không cần.
 */
@Composable
fun MoreInfo(label: String, text: String, tag: String, modifier: Modifier = Modifier) {
    var open by rememberSaveable { mutableStateOf(false) }
    val turn by animateFloatAsState(if (open) 1f else 0f, if (open) Motion.Expand else Motion.Collapse, label = "more_info_turn")
    ListItem(
        label, modifier.toggles(open) { open = !open }, { open = !open }, tag, titleStyle = Abook.type.bodyStrong,
        leading = { HelpIcon(Abook.colors.text2) }, leadingWidth = IconSlot, leadingGap = IconGap,
        trailing = { ChevronIcon(Abook.colors.text3, turn = { turn }) },
        below = { Reveal(open) { RowHint(text, Modifier.testTag("${tag}_text")) } },
    )
}

/**
 * Phần gập (web: Fold của shared/Collapse.tsx): tiêu đề phần + mũi tên, chạm mở / khép nội dung ngay dưới (mở / khép chiều cao kèm trượt). Phần ít dùng để gập, không
 * chiếm cả trang; mở hay gập giữ qua lần xoay màn hình.
 */
@Composable
fun Fold(title: String, tag: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    var open by rememberSaveable { mutableStateOf(false) }
    val turn by animateFloatAsState(if (open) 1f else 0f, if (open) Motion.Expand else Motion.Collapse, label = "fold_turn")
    Column(modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable { open = !open }.toggles(open) { open = !open }.testTag(tag),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BasicText(title, style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
            Spacer(Modifier.width(Dim.s12))
            ChevronIcon(Abook.colors.text3, turn = { turn })
        }
        Reveal(open) { Column(Modifier.fillMaxWidth().testTag("${tag}_body"), content = content) }
    }
}


/** Hiện / ẩn một khối trong dòng chảy: mở / khép chiều cao kèm trượt dọc (NATIVE_PHONE_UI.md §4 - không mờ). */
@Composable
fun Reveal(visible: Boolean, content: @Composable () -> Unit) {
    AnimatedVisibility(
        visible = visible,
        enter = expandVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate), expandFrom = Alignment.Top) +
            slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { -it / 4 },
        exit = shrinkVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate), shrinkTowards = Alignment.Top) +
            slideOutVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { -it / 4 },
    ) {
        content()
    }
}

/** Dòng chữ đầu của tên một hàng (16/24): biểu tượng hai bên hàng đứng giữa dòng này. */
val FirstLine: Dp
    @Composable get() = with(LocalDensity.current) { Abook.type.body.lineHeight.toDp() }

private val RowPad = Dim.s16

/**
 * Đặt nội dung sao cho TÂM của nó trùng tâm dòng chữ đầu của hàng (đệm trên [RowPad] + nửa dòng). Một luật cho cả hai bên hàng: tên dài xuống dòng cũng không
 * lệch nhau; nội dung cao hơn dòng (ô chạm 48) thì mở ra hai phía từ tâm ấy.
 */
@Composable
fun Modifier.onFirstLine(): Modifier {
    val firstLine = FirstLine
    return layout { measurable, constraints ->
        val placeable = measurable.measure(constraints.copy(minHeight = 0, maxHeight = Constraints.Infinity))
        val y = (RowPad.roundToPx() + firstLine.roundToPx() / 2 - placeable.height / 2).coerceAtLeast(0)
        layout(placeable.width, y + placeable.height) { placeable.place(0, y) }
    }
}

/**
 * Hàng danh sách (DESIGN.md §6 "Hàng danh sách"): [leading] (biểu tượng) · tên (16, xuống dòng không cắt) + mô tả (14, [RowHint]) · [trailing] hay mũi tên. Cả hai bên thẳng dòng
 * đầu của tên ([onFirstLine]); có `onClick` thì CẢ hàng là chỗ chạm. Hàng cao ít nhất 56, đệm trên dưới 16.
 */
@Composable
fun ListItem(
    title: String,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    tag: String? = null,
    hint: String? = null,
    hintColor: Color = Abook.colors.text2,
    titleColor: Color = Abook.colors.text,
    titleStyle: TextStyle = Abook.type.body,
    leading: (@Composable () -> Unit)? = null,
    leadingWidth: Dp = Dim.s24,
    leadingGap: Dp = Dim.s12,
    trailing: (@Composable () -> Unit)? = null,
    chevron: Boolean = false,
    below: (@Composable ColumnScope.() -> Unit)? = null,
    role: Role = Role.Button,
) {
    Column(
        modifier.fillMaxWidth()
            .then(if (onClick != null) Modifier.pressable(role, onClick = onClick) else Modifier)
            .then(if (tag != null) Modifier.testTag(tag) else Modifier),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            if (leading != null) {
                Box(Modifier.width(leadingWidth).onFirstLine()) { Box(Modifier.testTag("row_leading")) { leading() } }
                Spacer(Modifier.width(leadingGap))
            }
            Column(Modifier.weight(1f).heightIn(min = if (below != null) 0.dp else 56.dp).padding(top = RowPad, bottom = if (below != null) 0.dp else RowPad)) {
                BasicText(title, style = titleStyle.copy(color = titleColor), modifier = Modifier.testTag("row_title"))
                if (hint != null) {
                    Spacer(Modifier.height(2.dp))
                    RowHint(hint, Modifier.testTag("row_hint"), hintColor)
                }
            }
            if (trailing != null || chevron) {
                Spacer(Modifier.width(Dim.s12))
                Box(Modifier.onFirstLine(), contentAlignment = Alignment.CenterEnd) {
                    Box(Modifier.testTag("row_trailing")) { if (trailing != null) trailing() else ChevronIcon(Abook.colors.text3) }
                }
            }
        }
        // Phần dưới (thanh tiến độ) chạy từ cột chữ tới mép phải của hàng, qua cả cột hành động: cùng bề ngang với đường kẻ dưới hàng.
        if (below != null) Column(Modifier.fillMaxWidth().testTag("row_below").padding(start = if (leading != null) leadingWidth + leadingGap else 0.dp, bottom = RowPad)) { below() }
    }
}

/** Thanh tiến độ mảnh dưới một hàng: mốc, không phải phần trăm byte đoán. Giá trị đổi chỉ được đọc trong pha vẽ. */
@Composable
fun StageProgress(progress: () -> Float) {
    val track = Abook.colors.line
    val ink = Abook.colors.accent
    Canvas(Modifier.fillMaxWidth().padding(top = Dim.s8).height(3.dp)) {
        drawRect(track)
        drawRect(ink, size = size.copy(width = size.width * progress().coerceIn(0f, 1f)))
    }
}

/** Một dòng thông tin phụ (12, mực phụ) - tối đa một dòng cho mỗi phần, chỉ khi nó mang tin (số đếm, nguồn, lỗi). */
@Composable
fun Caption(text: String, modifier: Modifier = Modifier, color: Color = Abook.colors.text2) {
    BasicText(text, style = Abook.type.caption.copy(color = color), modifier = modifier)
}

/** Lỗi tại chỗ: một câu màu nguy hiểm, kèm "Thử lại" ở mép phải khi có việc để làm lại; mở / khép chiều cao kèm trượt. */
@Composable
fun InlineProblem(message: String, onRetry: (() -> Unit)? = null, tag: String = "problem", modifier: Modifier = Modifier) {
    // Giữ câu cuối cùng trong lúc khép lại (message trống thì khối đang thu, không để nó co thành khoảng trống nhảy).
    var shown by remember { mutableStateOf(message) }
    if (message.isNotEmpty()) shown = message
    Reveal(message.isNotEmpty()) {
        Row(modifier.fillMaxWidth().testTag(tag), verticalAlignment = Alignment.Top) {
            BasicText(shown, style = Abook.type.bodySmall.copy(color = Abook.colors.danger), modifier = Modifier.weight(1f).padding(top = if (onRetry != null) 14.dp else Dim.s8, bottom = if (onRetry != null) 13.dp else Dim.s8))
            if (onRetry != null) {
                Spacer(Modifier.width(Dim.s12))
                TextAction("Thử lại", onRetry, "$tag-retry")
            }
        }
    }
}

/** Câu dẫn lại nguyên văn trên mặt chìm (ví dụ một lời chú): bo 8, đệm 12, chữ phụ - không viền, không khung. */
@Composable
fun QuoteSample(text: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().clip(RoundedCornerShape(Dim.radiusControl)).background(Abook.colors.bgSunken).padding(Dim.s12)) {
        BasicText(text, style = Abook.type.bodySmall)
    }
}

/**
 * Một dòng menu (DESIGN.md §6 "Dòng menu"): trọn bề ngang bảng, biểu tượng đầu dòng, nhãn xuống dòng khi dài (không cắt); biểu tượng và nhãn "Sắp có"
 * cùng tâm với dòng chữ đầu. `soon`: việc chưa làm ở giao diện native - nhạt đi, nhãn "Sắp có" ở mép phải, không bấm được. `unavailable`: việc có rồi
 * nhưng cuốn này không làm được - cũng nhạt đi, không bấm được, KHÔNG có nhãn "Sắp có". `hint`: một dòng nhỏ dưới nhãn nói việc đang diễn ra ("Đang xuất · 27%").
 */
@Composable
fun MenuRow(
    label: String,
    tag: String,
    soon: Boolean = false,
    unavailable: Boolean = false,
    danger: Boolean = false,
    hint: String? = null,
    onClick: () -> Unit = {},
    /** Giá trị hiện tại bên phải (vd "Nhạc nền" ... "Theo cảnh"); dài thì xuống dòng, không cắt. */
    value: String? = null,
    icon: @Composable (Color) -> Unit,
) {
    val colors = Abook.colors
    val inert = soon || unavailable
    val ink = when {
        inert -> colors.fg3
        danger -> colors.danger
        else -> colors.text
    }
    Row(
        Modifier.fillMaxWidth().heightIn(min = Dim.s48)
            .then(if (inert) Modifier.semantics { disabled() } else Modifier.pressable(onClick = onClick))
            .padding(vertical = Dim.s12)
            .testTag(tag),
        verticalAlignment = Alignment.Top,
    ) {
        Box(Modifier.size(Dim.s24, FirstLine).testTag("${tag}_icon"), contentAlignment = Alignment.CenterStart) {
            Box(Modifier.testTag("row_leading")) { icon(ink) }
        }
        Spacer(Modifier.width(Dim.s12))
        Column(Modifier.weight(1f).then(if (value != null) Modifier.alignByBaseline() else Modifier)) {
            BasicText(label, style = Abook.type.body.copy(color = if (inert) colors.text2 else ink), modifier = Modifier.testTag("row_title"))
            if (hint != null) RowHint(hint, Modifier.padding(top = 2.dp).testTag("${tag}_hint"), colors.text2)
        }
        if (value != null) {
            Spacer(Modifier.width(Dim.s12))
            // Cùng cỡ chữ phụ với giá trị ở hàng của tấm trình phát; chung đường chân chữ với tên, dài thì xuống dòng.
            BasicText(value, Modifier.widthIn(max = 160.dp).alignByBaseline().testTag("${tag}_value"), Abook.type.bodySmall.copy(color = colors.text2))
        }
        if (soon) {
            Spacer(Modifier.width(Dim.s12))
            Box(Modifier.height(FirstLine), contentAlignment = Alignment.CenterStart) { BasicText("Sắp có", style = Abook.type.caption) }
        }
    }
}
