package vn.abook.player.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BackButton
import vn.abook.player.ui.components.ChevronIcon
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.Switch
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/*
 * Khối dựng của các màn Cài đặt (shared/SettingsNav.tsx của bản WebView): khoảng trắng + tiêu đề nhỏ thay khung (DESIGN.md §4.2), hàng = tên (16) + mô tả
 * một dòng (12, mực phụ) bên trái, điều khiển bên phải; nhóm chọn-một nằm DƯỚI tên, trải hết bề ngang. Chữ dài xuống dòng, không cắt.
 */

/** Một lựa chọn chữ + giá trị (số giờ, số phút...) cho [ChoiceRow]. */
data class Option<V>(val value: V, override val label: String) : Choice {
    override val key: String get() = value.toString()
}

/**
 * Màn con của Cài đặt (cấp hai): nút ← thẳng mép nội dung + tên nhóm (24, sát sau nút), rồi nội dung cuộn. Đệm dưới theo thanh điều hướng của máy - màn con phủ cả
 * thanh tab.
 */
@Composable
fun SettingsPage(title: String, onBack: () -> Unit, tag: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    Column(
        modifier.fillMaxSize().testTag(tag).verticalScroll(rememberScrollState())
            .padding(top = top, start = Dim.margin, end = Dim.margin, bottom = bottom + Dim.s48),
    ) {
        PageHeader(title, onBack)
        content()
    }
}

/** Đầu màn con: đệm trên 12, hàng cao 48 - nút ← rồi tiêu đề, chân chữ trùng tiêu đề màn gốc (ScreenHeader). */
@Composable
fun PageHeader(title: String, onBack: () -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().padding(top = Dim.s12).heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically) {
        BackButton(onBack)
        // Mũi tên 24 nằm đầu ô chạm 48: kéo tiêu đề lùi vào nửa trống của ô để nó "sát sau" nét mũi tên (DESIGN.md §6 "Đầu màn").
        BasicText(title, style = Abook.type.screenTitle, modifier = Modifier.weight(1f).offset(x = -Dim.s12))
    }
}

/** Khối phẳng: khoảng 32 trên (giữa các phần của một màn), tiêu đề nhỏ nếu có, các hàng cách nhau bằng vạch mảnh ([RowLine]). */
@Composable
fun SettingsBlock(title: String? = null, modifier: Modifier = Modifier, first: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth().padding(top = if (first) Dim.s16 else Dim.sectionGap)) {
        if (title != null) {
            Box(Modifier.fillMaxWidth().heightIn(min = Dim.s48), contentAlignment = Alignment.CenterStart) {
                BasicText(title, style = Abook.type.sectionTitle)
            }
        }
        content()
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
            BasicText(hint, style = Abook.type.caption.copy(color = Abook.colors.text2))
        }
    }
}

/** Hàng có tên bên trái, điều khiển / giá trị bên phải (canh giữa hàng). Cao tối thiểu 56. */
@Composable
fun SettingsRow(
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
    SettingsRow(
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
fun TextAction(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier) {
    Box(
        modifier.heightIn(min = Dim.s48).widthIn(min = Dim.touch).pressable(onClick = onClick).testTag(tag),
        contentAlignment = Alignment.CenterEnd,
    ) {
        BasicText(label, style = Abook.type.label.copy(color = Abook.colors.accentText))
    }
}

/** Hàng có một việc bên phải ("Xem", "Gửi", "Dọn"...). */
@Composable
fun ActionRow(label: String, action: String, onClick: () -> Unit, tag: String, hint: String? = null) {
    SettingsRow(label, hint = hint) { TextAction(action, onClick, tag) }
}

/** Tính năng mà lõi / giao diện native chưa có: nói thẳng "Sắp có", không giả một nút chạy được. */
@Composable
fun SoonRow(label: String, hint: String? = null, tag: String? = null) {
    SettingsRow(label, if (tag != null) Modifier.testTag(tag) else Modifier, hint = hint) {
        BasicText("Sắp có", style = Abook.type.caption)
    }
}

/** Hàng mở một bảng / một màn: tên (+ dòng giá trị), mũi tên ">" ở mép phải. */
@Composable
fun DisclosureRow(
    title: String,
    onClick: () -> Unit,
    tag: String,
    modifier: Modifier = Modifier,
    summary: String? = null,
    icon: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier.fillMaxWidth().heightIn(min = 56.dp).pressable(onClick = onClick).testTag(tag).padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Box(Modifier.size(IconSlot), contentAlignment = Alignment.CenterStart) { icon() }
            Spacer(Modifier.width(IconGap))
        }
        Column(Modifier.weight(1f)) {
            BasicText(title, style = Abook.type.bodyStrong)
            if (!summary.isNullOrEmpty()) BasicText(summary, style = Abook.type.bodySmall)
        }
        Spacer(Modifier.width(Dim.s12))
        ChevronIcon(Abook.colors.text3)
    }
}

/** Cột biểu tượng của hàng nhóm và khoảng tới chữ: vạch chia hàng thụt theo chữ (bắt đầu ở [IconSlot] + [IconGap]). */
val IconSlot = 22.dp
val IconGap = 14.dp

/**
 * Giải thích dài cần biết (quyền riêng tư, an toàn dữ liệu) gập sau "Tìm hiểu thêm" (shared/SettingsNav.tsx `MoreInfo`): chạm thì chữ MỞ ra tại chỗ (khép / mở
 * chiều cao kèm trượt), mũi tên xoay xuống.
 */
@Composable
fun MoreInfo(text: String, tag: String, label: String = "Tìm hiểu thêm") {
    var open by remember { mutableStateOf(false) }
    val turn = remember { Animatable(0f) }
    LaunchedEffect(open) { turn.animateTo(if (open) 1f else 0f, if (open) Motion.Expand else Motion.Collapse) }
    Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable { open = !open }.testTag(tag),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BasicText(label, style = Abook.type.label.copy(color = Abook.colors.text2), modifier = Modifier.weight(1f))
            ChevronIcon(Abook.colors.text3, turn = { turn.value })
        }
        Reveal(open) {
            BasicText(text, style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(bottom = Dim.s12))
        }
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
