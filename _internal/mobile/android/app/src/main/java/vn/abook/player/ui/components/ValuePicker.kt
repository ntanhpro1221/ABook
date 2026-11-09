package vn.abook.player.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import vn.abook.player.Feedback
import vn.abook.player.S
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.theme.insetSurface
import kotlin.math.roundToInt

/** Giữ nút -/+: chờ chừng này rồi lặp. */
private const val REPEAT_DELAY_MS = 400L
private const val REPEAT_EVERY_MS = 80L

/**
 * Bộ chọn giá trị số - MỘT kiểu cho cả app (DESIGN mục 6 "Chọn giá trị"; web shared/ValuePicker.tsx, Qt ValuePicker.qml cùng cấu trúc), từ trên xuống:
 *  1. giá trị hiện tại chữ lớn - chạm vào là gõ số (bàn phím số, Xong / Enter xác nhận, kẹp trong biên và báo nhẹ "Trong khoảng a–b");
 *  2. thước kéo tự do giữa nút - / + (giữ để lặp); nấc hút + rung CLOCK_TICK ở các giá trị tiêu biểu; TalkBack kéo lên/xuống một bước, phím mũi tên
 *     một bước, PageUp/PageDown mười bước;
 *  3. hàng chip giá trị tiêu biểu, chip trùng giá trị đang chọn chữ hổ phách đậm;
 *  4. `special`: lựa chọn đặc biệt không phải số ("Hết chương này"), hàng riêng dưới cùng.
 * `onChange` là lúc áp (thả tay, chạm chip, -/+, Xong, phím); khi kéo, chữ lớn và thước chạy theo tay, `onPreview` nếu cần nghe ngay.
 * `dense`: hàng gọn cho danh sách nhiều núm (âm thanh, Cài đặt) - tên + giá trị một hàng, thước, chip.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ValuePicker(
    spec: ValueSpec,
    value: Double,
    onChange: (Double) -> Unit,
    format: (Double) -> String,
    label: String,
    tag: String,
    modifier: Modifier = Modifier,
    chipLabel: (Double) -> String = format,
    hint: String? = null,
    dense: Boolean = false,
    enabled: Boolean = true,
    /** false: giá trị này chưa phải lựa chọn đang áp (hẹn giờ đang "Hết chương") - không tô chip nào, chọn đúng giá trị đang đứng vẫn là đặt. */
    current: Boolean = true,
    onPreview: ((Double) -> Unit)? = null,
    special: (@Composable () -> Unit)? = null,
) {
    val colors = Abook.colors
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    val change by rememberUpdatedState(onChange)
    val preview by rememberUpdatedState(onPreview)
    var moving by remember { mutableStateOf<Double?>(null) }
    var typing by remember { mutableStateOf(false) }
    var clampNote by remember { mutableStateOf(false) }
    val shown = ValuePickerLogic.quantize(spec, moving ?: value)
    // Giá trị mới nhất kể cả giữa hai lần vẽ (giữ nút -/+ lặp nhanh hơn một khung hình).
    val latest = remember { mutableDoubleStateOf(shown) }
    SideEffect { if (moving == null) latest.doubleValue = shown }
    val valueNow by rememberUpdatedState(value)
    val currentNow by rememberUpdatedState(current)

    fun commit(next: Double) {
        moving = null
        latest.doubleValue = next
        if (next != valueNow || !currentNow) change(next)
    }
    fun nudge(steps: Int) {
        val before = latest.doubleValue
        val next = ValuePickerLogic.step(spec, before, steps)
        if (next == before) return
        if (ValuePickerLogic.isDetent(spec, before, next)) Feedback.play("tick", view)
        commit(next)
    }
    fun drag(fraction: Float) {
        val next = ValuePickerLogic.fromFraction(spec, fraction.toDouble())
        val before = latest.doubleValue
        if (next == before) return
        if (ValuePickerLogic.isDetent(spec, before, next)) Feedback.play("tick", view)
        latest.doubleValue = next
        moving = next
        preview?.invoke(next)
    }
    fun finishTyping(text: String?) {
        typing = false
        val parsed = text?.let { ValuePickerLogic.parse(spec, it) } ?: return
        clampNote = parsed.clamped
        if (parsed.clamped) Feedback.play("reject", view)
        commit(parsed.value)
    }

    val range = S.s_trong_khoang_0_1_5313ae3f(format(spec.min), format(spec.max))
    Column(modifier.fillMaxWidth().then(if (enabled) Modifier else Modifier.alpha(.5f)).testTag(tag),
        verticalArrangement = Arrangement.spacedBy(if (dense) 0.dp else Dim.s8)) {
        val display: @Composable () -> Unit = {
            ValueDisplay(format(shown), typing, dense, enabled, "$label: ${format(shown)}. ${S.s_cham_de_go_so_adc1d0d1}",
                ValuePickerLogic.format(spec, shown), "${tag}_value", onStart = { clampNote = false; typing = true }, onDone = ::finishTyping)
        }
        if (dense) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    BasicText(label, style = Abook.type.body)
                    if (hint != null) RowHint(hint)
                }
                display()
            }
        } else {
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { display() }
        }
        AnimatedVisibility(clampNote, enter = fadeIn(tween(MotionMs.MEDIUM)) + expandVertically(tween(MotionMs.MEDIUM)),
            exit = fadeOut(tween(MotionMs.MEDIUM_OUT)) + shrinkVertically(tween(MotionMs.MEDIUM_OUT))) {
            BasicText(range, Modifier.fillMaxWidth().testTag("${tag}_clamped"),
                style = Abook.type.caption.copy(color = colors.text2, textAlign = if (dense) TextAlign.Start else TextAlign.Center))
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            StepButton(-1, enabled && shown > spec.min, "${tag}_down", ::nudge, scope)
            val fraction = ValuePickerLogic.toFraction(spec, shown).toFloat()
            val drawn by animateFloatAsState(fraction, if (moving != null) tween(0) else Motion.Expand, label = "ruler")
            val ticks = remember(spec) { spec.typical.map { ValuePickerLogic.toFraction(spec, it).toFloat() } }
            Canvas(Modifier.weight(1f).height(Dim.s48).testTag("${tag}_ruler")
                .semantics {
                    contentDescription = label
                    stateDescription = format(shown)
                    val steps = ((spec.max - spec.min) / spec.step).roundToInt() - 1
                    progressBarRangeInfo = ProgressBarRangeInfo(shown.toFloat(), spec.min.toFloat()..spec.max.toFloat(), steps.coerceAtLeast(0))
                    if (!enabled) disabled()
                    setProgress { target -> if (enabled) { commit(ValuePickerLogic.quantize(spec, target.toDouble())); true } else false }
                }
                .onKeyEvent { event ->
                    if (!enabled || event.type != KeyEventType.KeyDown) return@onKeyEvent false
                    val steps = when (event.key) {
                        Key.DirectionRight, Key.DirectionUp -> 1
                        Key.DirectionLeft, Key.DirectionDown -> -1
                        Key.PageUp -> ValuePickerLogic.PAGE_STEPS
                        Key.PageDown -> -ValuePickerLogic.PAGE_STEPS
                        Key.MoveHome -> { commit(spec.min); return@onKeyEvent true }
                        Key.MoveEnd -> { commit(spec.max); return@onKeyEvent true }
                        else -> return@onKeyEvent false
                    }
                    nudge(steps)
                    true
                }
                .focusable(enabled)
                .pointerInput(spec, enabled) {
                    if (enabled) detectTapGestures { offset -> drag(offset.x / size.width); moving?.let(::commit) }
                }
                .pointerInput(spec, enabled) {
                    if (enabled) detectHorizontalDragGestures(
                        onDragStart = { offset -> drag(offset.x / size.width) },
                        onHorizontalDrag = { pointer, _ -> pointer.consume(); drag(pointer.position.x / size.width) },
                        onDragEnd = { moving?.let(::commit) },
                        onDragCancel = { moving = null },
                    )
                }) {
                val y = size.height / 2
                val inset = 8.dp.toPx()
                val width = size.width - 2 * inset
                val x = inset + drawn * width
                drawLine(colors.line, Offset(inset, y), Offset(inset + width, y), 3.dp.toPx(), StrokeCap.Round)
                drawLine(colors.accent, Offset(inset, y), Offset(x, y), 3.dp.toPx(), StrokeCap.Round)
                for (tick in ticks) {
                    val at = inset + tick * width
                    drawLine(colors.text2.copy(alpha = .6f), Offset(at, y - 5.dp.toPx()), Offset(at, y + 5.dp.toPx()), 2.dp.toPx(), StrokeCap.Round)
                }
                drawCircle(colors.accent, (if (moving != null) 9 else 7).dp.toPx(), Offset(x, y))
            }
            StepButton(1, enabled && shown < spec.max, "${tag}_up", ::nudge, scope)
        }
        if (spec.typical.isNotEmpty()) {
            val selected = if (current) ValuePickerLogic.chipIndex(spec, shown) else -1
            FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(if (dense) 0.dp else Dim.s4, if (dense) Alignment.Start else Alignment.CenterHorizontally)) {
                spec.typical.forEachIndexed { index, typical ->
                    val chosen = index == selected
                    val color by animateColorAsState(if (chosen) colors.accentText else colors.text, tween(MotionMs.MEDIUM), label = "chip")
                    Box(Modifier.heightIn(min = Dim.s48).widthIn(min = Dim.s48)
                        .then(if (enabled) Modifier.pressable { Feedback.play("toggle", view); clampNote = false; commit(typical) } else Modifier)
                        .semantics { this.selected = chosen; contentDescription = format(typical); if (!enabled) disabled() }
                        .testTag("${tag}_chip_${ValuePickerLogic.format(spec, typical)}")
                        .padding(horizontal = Dim.s12), contentAlignment = Alignment.Center) {
                        BasicText(chipLabel(typical), style = (if (dense) Abook.type.bodySmall else Abook.type.body)
                            .copy(color = color, fontWeight = if (chosen) FontWeight.Bold else FontWeight.Normal))
                    }
                }
            }
        }
        special?.invoke()
    }
}

/** Nút -/+ (vùng chạm 48 dp): chạm một bước, giữ thì lặp; TalkBack: một lần chạm đúp là một bước. */
@Composable
private fun StepButton(steps: Int, enabled: Boolean, tag: String, nudge: (Int) -> Unit, scope: kotlinx.coroutines.CoroutineScope) {
    val name = if (steps < 0) S.s_giam_a6c2901a else S.s_tang_a2363bce
    val colors = Abook.colors
    val step by rememberUpdatedState(nudge)
    Box(Modifier.size(Dim.s48).testTag(tag)
        .semantics {
            role = Role.Button
            contentDescription = name
            if (!enabled) disabled()
            onClick { if (enabled) { step(steps); true } else false }
        }
        .pointerInput(enabled) {
            if (!enabled) return@pointerInput
            awaitEachGesture {
                awaitFirstDown()
                step(steps)
                val repeat = scope.launch {
                    delay(REPEAT_DELAY_MS)
                    while (true) { step(steps); delay(REPEAT_EVERY_MS) }
                }
                waitForUpOrCancellation()
                repeat.cancel()
            }
        }, contentAlignment = Alignment.Center) {
        LucideIcon(if (steps < 0) LucidePaths.MINUS else LucidePaths.PLUS, if (enabled) colors.text2 else colors.text3)
    }
}

/** Chữ lớn của giá trị; chạm vào thành ô gõ số (bàn phím số), Xong / mất tiêu điểm là áp, chữ không ra số thì giữ giá trị cũ. */
@Composable
private fun ValueDisplay(text: String, typing: Boolean, dense: Boolean, enabled: Boolean, description: String, number: String, tag: String,
                         onStart: () -> Unit, onDone: (String?) -> Unit) {
    val colors = Abook.colors
    val style = if (dense) Abook.type.bodySmall.copy(color = colors.text2) else Abook.type.screenTitle
    if (!typing) {
        Box(Modifier.heightIn(min = Dim.s48).then(if (enabled) Modifier.pressable(onClick = onStart) else Modifier)
            .semantics { contentDescription = description }.testTag(tag).padding(horizontal = Dim.s8), contentAlignment = Alignment.Center) {
            BasicText(text, style = style)
        }
        return
    }
    val focus = remember { FocusRequester() }
    var field by remember { mutableStateOf(TextFieldValue(number, TextRange(0, number.length))) }
    var focused by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { focus.requestFocus() }
    BasicTextField(
        field, { field = it }, singleLine = true,
        textStyle = style.copy(color = colors.text, textAlign = TextAlign.Center),
        cursorBrush = SolidColor(colors.accentText),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = { onDone(field.text) }),
        modifier = Modifier.widthIn(min = 96.dp, max = 160.dp).heightIn(min = Dim.s48).insetSurface(colors)
            .focusRequester(focus)
            .onFocusChanged { state -> if (focused && !state.isFocused) onDone(field.text); focused = state.isFocused }
            .semantics { contentDescription = description }.testTag("${tag}_input")
            .padding(horizontal = Dim.s8, vertical = Dim.s8),
    )
}
