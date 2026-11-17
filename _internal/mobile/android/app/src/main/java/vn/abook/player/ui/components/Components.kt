package vn.abook.player.ui.components

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import vn.abook.player.S

import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.AnimationVector1D
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.ContentDrawScope
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.input.pointer.PointerEvent
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.PointerEventType
import androidx.compose.ui.node.DrawModifierNode
import androidx.compose.ui.node.ModifierNodeElement
import androidx.compose.ui.node.PointerInputModifierNode
import androidx.compose.ui.node.requireDensity
import androidx.compose.ui.platform.InspectorInfo
import androidx.compose.ui.unit.IntSize
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.width
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Chạm: thu 0,97 khi nhấn (90 ms), về 1 khi thả (120 ms), không chấm gợn đọng lại (DESIGN.md §5.2). Không composable: trạng thái nhấn và hoạt ảnh nằm trong
 * một Modifier.Node ([PressScaleNode]) chỉ sinh hoạt ảnh lúc bạn chạm thật - trước đây mỗi nơi chạm mang theo `remember` + `animateFloatAsState` +
 * `collectIsPressedAsState` (một LaunchedEffect mỗi phần tử), nên màn nào có nhiều nút cũng tốn dựng lần đầu (NATIVE_POLISH: trace Perfetto của trang sách /
 * Đang nghe). Hệ số thu đọc trong pha vẽ nên mỗi khung của hoạt ảnh không dựng lại gì.
 */
@OptIn(ExperimentalFoundationApi::class)
fun Modifier.pressable(role: Role = Role.Button, onLongClick: (() -> Unit)? = null, onClickLabel: String? = null, onClick: () -> Unit): Modifier {
    val base = this.then(PressScaleElement)
    return if (onLongClick == null) {
        base.clickable(interactionSource = null, indication = null, role = role, onClickLabel = onClickLabel, onClick = onClick)
    } else {
        base.combinedClickable(interactionSource = null, indication = null, role = role, onClickLabel = onClickLabel, onLongClick = onLongClick, onClick = onClick)
    }
}

private object PressScaleElement : ModifierNodeElement<PressScaleNode>() {
    override fun create() = PressScaleNode()
    override fun update(node: PressScaleNode) {}
    override fun hashCode() = 1
    override fun equals(other: Any?) = other === this
    override fun InspectorInfo.inspectableProperties() { name = "pressScale" }
}

/** Quan sát (không nuốt) chạm: nhấn -> thu, thả / huỷ / trượt quá ngưỡng -> về. Hoạt ảnh tạo lười ở lần nhấn đầu. */
private class PressScaleNode : Modifier.Node(), DrawModifierNode, PointerInputModifierNode {
    private var factor by mutableFloatStateOf(1f)
    private var animation: Animatable<Float, AnimationVector1D>? = null
    private var job: Job? = null
    private var downAt: Offset? = null
    private var pressed = false

    override fun ContentDrawScope.draw() {
        val value = factor
        if (value == 1f) drawContent() else scale(value, value, center) { this@draw.drawContent() }
    }

    override fun onPointerEvent(pointerEvent: PointerEvent, pass: PointerEventPass, bounds: IntSize) {
        if (pass != PointerEventPass.Initial) return
        val change = pointerEvent.changes.firstOrNull() ?: return
        when (pointerEvent.type) {
            // Cú chạm đã bị một lớp nổi phía trên giữ ([floatingLayer]): phần tử nằm dưới không thu lại như thể được bấm.
            PointerEventType.Press -> if (!change.isConsumed) { downAt = change.position; setPressed(true) }
            PointerEventType.Move -> {
                val from = downAt
                if (pressed && from != null && (change.position - from).getDistance() > requireDensity().run { SLOP.toPx() }) setPressed(false)
            }
            PointerEventType.Release -> setPressed(false)
        }
    }

    override fun onCancelPointerInput() = setPressed(false)

    private fun setPressed(value: Boolean) {
        if (pressed == value) return
        pressed = value
        job?.cancel()
        job = coroutineScope.launch {
            val anim = animation ?: Animatable(factor).also { animation = it }
            anim.animateTo(if (value) Motion.PRESS_SCALE else 1f, if (value) Motion.PressDown else Motion.PressUp) { factor = this.value }
        }
    }

    override fun onDetach() {
        job?.cancel()
        factor = 1f
        pressed = false
    }

    private companion object {
        val SLOP = 8.dp
    }
}

/**
 * Lớp nổi đè lên nội dung cuộn (thanh nghe thử, gợi ý, dải nút đáy...): giữ cú BẤM trong CẢ khung của nó - kể cả vùng trống và phần đệm - để cú bấm
 * không lọt xuống dòng nằm dưới, nhưng để cú VUỐT đi qua: danh sách bên dưới vẫn cuộn khi vuốt bắt đầu trên lớp (như web, Qt). Đặt NGOÀI CÙNG chuỗi
 * Modifier (trước `padding`); phần bấm được bên trong vẫn nhận chạm như thường. Máy dò: scripts/ui_parity_rules.py (L12).
 */
fun Modifier.floatingLayer(): Modifier = this then FloatingLayerElement

private object FloatingLayerElement : ModifierNodeElement<FloatingLayerNode>() {
    override fun create() = FloatingLayerNode()
    override fun update(node: FloatingLayerNode) {}
    override fun hashCode() = 2
    override fun equals(other: Any?) = other === this
    override fun InspectorInfo.inspectableProperties() { name = "floatingLayer" }
}

/**
 * Soát 17-11: bản trước (`pointerInput { detectTapGestures {} }`) chặn cả cú vuốt - Compose không dò tiếp anh em nằm dưới một nút đã trúng chạm, nên
 * danh sách giọng / Kho nhạc không cuộn được khi vuốt bắt đầu trên viên gợi ý hay lề thanh. Node này chia chạm cho anh em nằm dưới
 * ([sharePointerInputWithSiblings]) và chỉ giữ cú NHẤN: ở pha Main (con bên trong lớp đã xử lý xong) nó đánh dấu cú nhấn là đã dùng; nhánh nằm dưới
 * được giao sau nhánh của lớp, nên `clickable` / [pressable] của dòng bên dưới bỏ qua cú nhấn ấy (không bấm, không thu lại). Cú di chuyển không bị
 * đụng tới: phần cuộn của danh sách (nhận cả cú nhấn đã dùng) vẫn kéo được.
 */
private class FloatingLayerNode : Modifier.Node(), PointerInputModifierNode {
    override fun sharePointerInputWithSiblings() = true

    override fun onPointerEvent(pointerEvent: PointerEvent, pass: PointerEventPass, bounds: IntSize) {
        if (pass != PointerEventPass.Main || pointerEvent.type != PointerEventType.Press) return
        for (change in pointerEvent.changes) if (change.pressed && !change.previousPressed) change.consume()
    }

    override fun onCancelPointerInput() {}
}

/** Đầu màn gốc: tiêu đề 24 + dòng phụ ngay dưới (DESIGN.md §6 "Đầu màn"). */
@Composable
fun ScreenHeader(title: String, modifier: Modifier = Modifier, subtitle: String? = null, trailing: (@Composable () -> Unit)? = null, bottomGap: Dp = Dim.s16) {
    Column(modifier.padding(top = Dim.s12, bottom = bottomGap)) {
        Box(Modifier.fillMaxWidth().height(Dim.s48), contentAlignment = Alignment.CenterStart) {
            BasicText(title, style = Abook.type.screenTitle)
            SwapContent(trailing, contentKey = { trailing -> trailing != null }, layout = ContentLayout.Box, modifier = Modifier.align(Alignment.CenterEnd)) { trailing ->
                if (trailing != null) Box { trailing() }
            }
        }
        SwapContent(subtitle, contentKey = { subtitle -> subtitle != null }, layout = ContentLayout.Column) { subtitle ->
            if (subtitle != null) BasicText(subtitle, style = Abook.type.bodySmall)
        }
    }
}

/** Nút ← của màn con: nét mũi tên thẳng mép nội dung, vùng chạm 48. */
@Composable
fun BackButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val ink = Abook.colors.text
    Box(
        modifier.size(Dim.s48).pressable(onClick = onClick).semantics { contentDescription = S.s_quay_lai_6d793582 },
        contentAlignment = Alignment.CenterStart,
    ) {
        // lucide ArrowLeft như bản web; mũi nhọn (x 4 kể cả nửa nét) dời về mép trái ô để thẳng mép nội dung.
        Canvas(Modifier.size(24.dp).visualIcon()) {
            val unit = size.width / 24f
            translate(-4f * unit, 0f) { drawLucide(LucidePaths.ARROW_LEFT, ink, unit) }
        }
    }
}

/** Màn tab chưa làm: đầu màn + một dòng. */
@Composable
fun PlaceholderTab(title: String, line: String, modifier: Modifier = Modifier) {
    Column(modifier.padding(horizontal = Dim.margin)) {
        ScreenHeader(title)
        BasicText(line, style = Abook.type.body.copy(color = Abook.colors.text2))
        Spacer(Modifier.height(Dim.s16))
    }
}

/** Nút chính: nền hổ phách, cao 48, chữ ≤ 3 từ (DESIGN.md §6 "Nút (a)"). `enabled` = false: nhạt hơn và không bấm được (việc đang chạy). */
@Composable
fun PrimaryButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, compact: Boolean = false, pending: Boolean = false, icon: (@Composable (Color) -> Unit)? = null) =
    ActionButton(label, onClick, modifier, enabled, icon, compact, false, pending)

/** Secondary action paired with a primary button: same height, compact label and a control outline. */
@Composable
fun OutlineButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, pending: Boolean = false, icon: (@Composable (Color) -> Unit)? = null) =
    ActionButton(label, onClick, modifier, enabled, icon, true, true, pending)

@Composable
private fun ActionButton(label: String, onClick: () -> Unit, modifier: Modifier, enabled: Boolean, icon: (@Composable (Color) -> Unit)?, compact: Boolean, outline: Boolean, pending: Boolean) {
    val accent = Abook.colors.accent
    val shape = RoundedCornerShape(Dim.radiusControl)
    val ink = if (outline) Abook.colors.text else Abook.colors.accentInk
    Box(
        modifier.height(Dim.s48)
            .then(if (enabled && !pending) Modifier.pressable(onClick = onClick) else Modifier.semantics { disabled() })
            .clip(shape).background(if (outline) Color.Transparent else if (enabled) accent else accent.copy(alpha = 0.45f))
            .then(if (outline) Modifier.border(1.dp, Abook.colors.controlLine, shape) else Modifier)
            .padding(horizontal = if (compact) Dim.s12 else Dim.s24),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ButtonLead(pending, ink, icon)
            BasicText(label, style = (if (compact) Abook.type.label else Abook.type.bodyStrong).copy(color = ink))
        }
    }
}
