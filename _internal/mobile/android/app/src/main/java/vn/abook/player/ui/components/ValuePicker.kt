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
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.offset
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.IntOffset
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
 *  3. hàng chip giá trị tiêu biểu, chip trùng giá trị đang chọn chữ --text đậm;
 *  4. `special`: lựa chọn đặc biệt không phải số ("Hết chương này"), hàng riêng dưới cùng.
 * `onChange` là lúc áp (thả tay, chạm chip, -/+, Xong, phím); khi kéo, chữ lớn và thước chạy theo tay, `onPreview` nếu cần nghe ngay.
 * `dense`: two rows: label + editable value, then ruler with numeric labels centred below its detents.
 */
@Composable
fun ValuePicker(
    spec: ValueSpec,
    value: Double,
    onChange: (Double) -> Unit,
    format: (Double) -> String,
    label: String,
    tag: String,
    modifier: Modifier = Modifier,
    chipLabel: (Double) -> String = { ValuePickerLogic.format(spec, it) },
    hint: String? = null,
    dense: Boolean = false,
    /** A labelled count with the same value field between the step buttons, without a ruler. */
    stepperOnly: Boolean = false,
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
    Column(modifier.fillMaxWidth().then(if (enabled) Modifier else Modifier.alpha(.5f)).testTag(tag).semantics { if (stepperOnly) selected = current },
        verticalArrangement = Arrangement.spacedBy(if (dense) 0.dp else Dim.s8)) {
        val display: @Composable () -> Unit = {
            ValueDisplay(format(shown), typing, dense, enabled, "$label: ${format(shown)}. ${S.s_cham_de_go_so_adc1d0d1}",
                ValuePickerLogic.format(spec, shown), "${tag}_value", onStart = { if (stepperOnly && !current) commit(shown) else { clampNote = false; typing = true } }, onDone = ::finishTyping)
        }
        if (stepperOnly) {
            BasicText(label, Modifier.testTag("${tag}_section_label"), style = Abook.type.bodySmall.copy(color = colors.text2))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                StepButton(-1, enabled && shown > spec.min, "${tag}_down", ::nudge, scope)
                Box(Modifier.weight(1f).semantics { selected = current }, contentAlignment = Alignment.Center) { display() }
                StepButton(1, enabled && shown < spec.max, "${tag}_up", ::nudge, scope)
            }
        } else {
        if (dense) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    BasicText(label, style = Abook.type.bodySmall)
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
        // Labels are captions of the detents: each one centred under its own detent and inside the ruler (never under -/+).
        // When they cannot fit without touching, the ruler draws no detents and the labels become balanced rows below it.
        val labelStyle = if (dense) Abook.type.caption else Abook.type.bodySmall
        val measurer = rememberTextMeasurer()
        val labels = spec.typical.map(chipLabel)
        val fractions = remember(spec) { spec.typical.map { ValuePickerLogic.toFraction(spec, it) } }
        val selected = if (current) ValuePickerLogic.chipIndex(spec, shown) else -1
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val density = LocalDensity.current
            val rulerWidth = (constraints.maxWidth - 2 * with(density) { Dim.s48.roundToPx() }).toDouble()
            val widths = labels.map { measurer.measure(it, labelStyle.copy(fontWeight = FontWeight.Bold)).size.width.toDouble() }
            val plan = with(density) { ValuePickerLogic.tickLabels(fractions, widths, rulerWidth, 8.dp.toPx().toDouble(), Dim.s4.toPx().toDouble()) }
            val inset = plan.inset.toFloat()
            fun at(x: Float) = (x - inset) / (rulerWidth.toFloat() - 2 * inset)
            Column(Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                    StepButton(-1, enabled && shown > spec.min, "${tag}_down", ::nudge, scope)
                    val fraction = ValuePickerLogic.toFraction(spec, shown).toFloat()
                    val drawn by animateFloatAsState(fraction, if (moving != null) tween(0) else Motion.Expand, label = "ruler")
                    Box(Modifier.weight(1f).height(if (!plan.aligned) Dim.s48 else if (dense) 56.dp else 64.dp)) {
                        Box(Modifier.fillMaxWidth().height(Dim.s48).testTag("${tag}_ruler")
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
                            .pointerInput(spec, enabled, inset) {
                                if (enabled) detectTapGestures { offset -> drag(at(offset.x)); moving?.let(::commit) }
                            }
                            .pointerInput(spec, enabled, inset) {
                                if (enabled) detectHorizontalDragGestures(
                                    onDragStart = { offset -> drag(at(offset.x)) },
                                    onHorizontalDrag = { pointer, _ -> pointer.consume(); drag(at(pointer.position.x)) },
                                    onDragEnd = { moving?.let(::commit) },
                                    onDragCancel = { moving = null },
                                )
                            }) {
                            Canvas(Modifier.matchParentSize()) {
                                val y = size.height / 2
                                drawLine(colors.line, Offset(inset, y), Offset(size.width - inset, y), 3.dp.toPx(), StrokeCap.Round)
                                drawLine(colors.accent, Offset(inset, y), Offset(inset + drawn * (size.width - 2 * inset), y), 3.dp.toPx(), StrokeCap.Round)
                            }
                            // Detents are real nodes so the label-under-detent rule is measured on the layout, not recomputed.
                            if (plan.aligned) fractions.forEachIndexed { index, f ->
                                Box(Modifier.offset { IntOffset((plan.centre(f, rulerWidth) - 1.dp.toPx()).roundToInt(), 19.dp.roundToPx()) }
                                    .size(2.dp, 10.dp).background(colors.text2.copy(alpha = .6f), CircleShape).testTag("${tag}_tick_$index"))
                            }
                            Canvas(Modifier.matchParentSize()) {
                                drawCircle(colors.accent, (if (moving != null) 9 else 7).dp.toPx(), Offset(inset + drawn * (size.width - 2 * inset), size.height / 2))
                            }
                        }
                        if (plan.aligned) spec.typical.forEachIndexed { index, typical ->
                            val chosen = index == selected
                            val box = with(density) { maxOf(48.dp.toPx(), widths[index].toFloat()) }
                            val left = (plan.centre(fractions[index], rulerWidth) - box / 2).toFloat()
                            Box(Modifier.offset { IntOffset(left.roundToInt(), (if (dense) 8.dp else 16.dp).roundToPx()) }
                                .size(with(density) { box.toDp() }, 48.dp)
                                .pointerInput(spec, enabled, rulerWidth, inset) {
                                    // Touch areas overlap where detents are close: a tap picks the detent nearest the finger.
                                    if (enabled) detectTapGestures { offset ->
                                        val x = left + offset.x
                                        val nearest = spec.typical.indices.minBy { kotlin.math.abs(plan.centre(fractions[it], rulerWidth) - x) }
                                        Feedback.play("toggle", view); clampNote = false; commit(spec.typical[nearest])
                                    }
                                }
                                .pointerInput(spec, enabled, rulerWidth, inset) {
                                    if (enabled) detectHorizontalDragGestures(onDragStart = { drag(at(left + it.x)) },
                                        onHorizontalDrag = { pointer, _ -> pointer.consume(); drag(at(left + pointer.position.x)) },
                                        onDragEnd = { moving?.let(::commit) }, onDragCancel = { moving = null })
                                }
                                .semantics {
                                    role = Role.Button; this.selected = chosen; contentDescription = format(typical)
                                    if (!enabled) disabled()
                                    onClick { if (enabled) { commit(typical); true } else false }
                                }
                                .onKeyEvent { event ->
                                    if (enabled && event.type == KeyEventType.KeyDown && event.key in listOf(Key.Enter, Key.NumPadEnter, Key.Spacebar)) {
                                        commit(typical); true
                                    } else false
                                }.focusable(enabled)
                                .testTag("${tag}_chip_${ValuePickerLogic.format(spec, typical)}")
                                .padding(top = 16.dp), contentAlignment = Alignment.Center) {
                                PickerLabel(labels[index], labelStyle, chosen, Modifier.testTag("${tag}_label_$index"))
                            }
                        }
                    }
                    StepButton(1, enabled && shown < spec.max, "${tag}_up", ::nudge, scope)
                }
                if (!plan.aligned && spec.typical.isNotEmpty()) {
                    BalancedPickerChips(Modifier.fillMaxWidth().padding(horizontal = Dim.s48).testTag("${tag}_chips")) {
                        spec.typical.forEachIndexed { index, typical ->
                            Box(Modifier.heightIn(min = Dim.s48).widthIn(min = Dim.s48)
                                .then(if (enabled) Modifier.pressable { Feedback.play("toggle", view); clampNote = false; commit(typical) } else Modifier)
                                .semantics { this.selected = index == selected; contentDescription = format(typical); if (!enabled) disabled() }
                                .testTag("${tag}_chip_${ValuePickerLogic.format(spec, typical)}")
                                .padding(horizontal = Dim.s4), contentAlignment = Alignment.Center) {
                                PickerLabel(labels[index], labelStyle, index == selected, Modifier.testTag("${tag}_label_$index"))
                            }
                        }
                    }
                }
            }
        }
        }
        special?.invoke()
    }
}

/** A caption shares its centre with its detent; bold measurement reserves the selected weight. */
@Composable
private fun PickerLabel(text: String, style: androidx.compose.ui.text.TextStyle, chosen: Boolean, modifier: Modifier) {
    val colors = Abook.colors
    val color by animateColorAsState(if (chosen) colors.text else colors.text2, tween(MotionMs.MEDIUM), label = "chip")
    BasicText(text, modifier, style = style.copy(color = color, fontWeight = if (chosen) FontWeight.Bold else FontWeight.Normal))
}

/** Measure real text at the current font scale, then distribute balanced rows across the ruler's width. */
@Composable
private fun BalancedPickerChips(modifier: Modifier, content: @Composable () -> Unit) {
    Layout(content = content, modifier = modifier) { measurables, constraints ->
        val gap = 4.dp.roundToPx()
        val chips = measurables.map { it.measure(Constraints(maxWidth = constraints.maxWidth)) }
        val rows = ValuePickerLogic.chipRows(chips.map { it.width }, constraints.maxWidth, gap)
        val heights = rows.map { row -> row.maxOf { chips[it].height } }
        layout(constraints.maxWidth, heights.sum()) {
            var y = 0
            rows.forEachIndexed { r, row ->
                val extra = constraints.maxWidth - row.sumOf { chips[it].width }
                var used = 0
                row.forEachIndexed { i, index ->
                    val x = if (row.count() == 1) extra / 2 else used + extra * i / (row.count() - 1)
                    chips[index].placeRelative(x, y)
                    used += chips[index].width
                }
                y += heights[r]
            }
        }
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
        Box(Modifier.widthIn(min = 48.dp).heightIn(min = if (dense) 20.dp else Dim.s48).then(if (enabled) Modifier.pressable(onClick = onStart) else Modifier)
            .semantics { contentDescription = description }.testTag(tag).padding(horizontal = Dim.s8), contentAlignment = Alignment.Center) {
            BasicText(text, Modifier.testTag("${tag}_text"), style = style)
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
