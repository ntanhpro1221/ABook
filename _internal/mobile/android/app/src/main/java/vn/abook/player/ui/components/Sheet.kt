package vn.abook.player.ui.components

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.input.pointer.util.VelocityTracker
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.Velocity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import vn.abook.player.ui.theme.scrim
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Một bảng trượt đang chờ hiện: nội dung nhận hàm đóng. `id` khác nhau cho mỗi lần mở. */
class SheetSpec internal constructor(val id: Int, val content: @Composable (dismiss: () -> Unit) -> Unit)

/**
 * Chỗ xin mở bảng trượt từ đáy (DESIGN.md §6): màn nào cũng gọi [show]; [SheetLayer] ở gốc app vẽ nó TRÊN cả thanh phát và thanh tab.
 * Một lúc một bảng. Back đóng bảng trước (BackHandler của lớp).
 */
@Stable
class SheetHost {
    private var next = 0
    var current by mutableStateOf<SheetSpec?>(null)
        private set

    fun show(content: @Composable (dismiss: () -> Unit) -> Unit) {
        current = SheetSpec(next++, content)
    }

    fun dismiss() {
        current = null
    }
}

/**
 * Lớp bảng trượt: nền tối chạm để đóng, bảng bo 20 trượt từ đáy lên (300 ms giảm tốc) và xuống (200 ms tăng tốc), kéo xuống từ bất kỳ chỗ nào để đóng ([sheetSurface]).
 * Nền tối đi cùng chuyển động trượt (không phải chuyển cảnh chỉ có mờ) và vẽ trong pha vẽ.
 */
@Composable
fun SheetLayer(host: SheetHost) {
    val spec = host.current
    var shown by remember { mutableStateOf<SheetSpec?>(null) }
    val progress = remember { Animatable(0f) }
    val drag = rememberSheetDrag { host.dismiss() }
    LaunchedEffect(spec) {
        if (spec != null) {
            shown = spec
            drag.reset()
            progress.animateTo(1f, Motion.SheetIn)
        } else {
            progress.animateTo(0f, Motion.SheetOut)
            shown = null
        }
    }
    val sheet = shown ?: return
    BackHandler(enabled = spec != null) { host.dismiss() }
    val colors = Abook.colors
    val scrim = colors.scrim
    Box(
        Modifier.fillMaxSize().testTag("sheet_layer")
            .drawBehind { drawRect(scrim, alpha = progress.value) }
            .pointerInput(Unit) { detectTapGestures { host.dismiss() } },
    ) {
        Column(
            // imePadding ở đây (một chỗ cho MỌI bảng): bàn phím mở thì cả bảng - ô nhập lẫn nút - nằm trên bàn phím, không bảng nào phải tự nhớ.
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().imePadding()
                .sheetSurface(drag)
                .graphicsLayer { translationY = (1f - progress.value) * size.height + drag.offset }
                .clip(RoundedCornerShape(topStart = Dim.radiusSheet, topEnd = Dim.radiusSheet))
                .background(colors.panel)
                .then(if (colors.dark) Modifier.sheetEdge(colors.line) else Modifier),
        ) {
            Box(Modifier.fillMaxWidth().height(Dim.s24), contentAlignment = Alignment.Center) {
                Box(Modifier.width(36.dp).height(4.dp).clip(CircleShape).background(colors.line))
            }
            Box(Modifier.gestureBarPadding().padding(horizontal = Dim.margin).padding(bottom = Dim.s16)) {
                sheet.content { host.dismiss() }
            }
        }
    }
}

/** Ngưỡng đóng chung của MỌI bảng trượt (bảng của màn, tấm của trình phát): kéo quá 1/4 chiều cao bảng hay vuốt nhanh xuống. */
object SheetClose {
    const val FRACTION = .25f
    const val VELOCITY = 1500f
}

/** Bảng đang bị kéo xuống bao nhiêu (px) - đọc trong pha vẽ (graphicsLayer); [close] gọi khi thả quá ngưỡng [SheetClose]. */
@Stable
class SheetDrag internal constructor(private val scope: kotlinx.coroutines.CoroutineScope, private val close: () -> Unit) {
    var offset by mutableFloatStateOf(0f)
        private set
    var height = 1f
        internal set
    private var settle: kotlinx.coroutines.Job? = null
    internal fun by(delta: Float): Float {
        settle?.cancel()
        val before = offset
        offset = (offset + delta).coerceAtLeast(0f)
        return offset - before
    }
    internal fun release(velocity: Float) {
        val closing = offset > height * SheetClose.FRACTION || velocity > SheetClose.VELOCITY
        settle = scope.launch {
            if (closing) close() else androidx.compose.animation.core.animate(offset, 0f, animationSpec = Motion.SheetIn) { v, _ -> offset = v }
        }
    }
    /** Mỗi lần mở lại: bảng vừa đóng bằng kéo vẫn giữ chỗ thả (không giật lên khi trượt ra), nên xoá ở đây. */
    fun reset() { settle?.cancel(); offset = 0f }
}

@Composable
fun rememberSheetDrag(close: () -> Unit): SheetDrag {
    val scope = rememberCoroutineScope()
    val latest by androidx.compose.runtime.rememberUpdatedState(close)
    return remember(scope) { SheetDrag(scope) { latest() } }
}

/**
 * Mặt bảng trượt (DESIGN.md §6): kéo xuống từ BẤT KỲ chỗ nào trong bảng thì bảng theo tay - danh sách đang ở đầu cũng vậy (cuộn lồng) - thả quá ngưỡng [SheetClose] thì đóng.
 * Chạm chỗ trống trong bảng không đóng: chỉ chạm nền tối mới đóng. Thanh trượt, hàng cuộn ngang giữ cử chỉ của chúng.
 * Đặt TRƯỚC graphicsLayer dịch bảng: bộ dò nằm trong lớp dịch thì bảng chạy theo tay làm tay "đứng yên" so với bảng, kéo chậm không bao giờ tới ngưỡng.
 */
fun Modifier.sheetSurface(drag: SheetDrag): Modifier = this
    .onSizeChanged { drag.height = it.height.coerceAtLeast(1).toFloat() }
    .nestedScroll(object : NestedScrollConnection {
        override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset =
            if (available.y < 0 && drag.offset > 0) Offset(0f, drag.by(available.y)) else Offset.Zero
        override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset =
            if (available.y > 0 && source == NestedScrollSource.UserInput) Offset(0f, drag.by(available.y)) else Offset.Zero
        override suspend fun onPreFling(available: Velocity): Velocity {
            if (drag.offset <= 0f) return Velocity.Zero
            drag.release(available.y)
            return available
        }
    })
    .pointerInput(drag) {
        val tracker = VelocityTracker()
        detectVerticalDragGestures(
            onDragStart = { tracker.resetTracking() },
            onVerticalDrag = { change, amount -> tracker.addPosition(change.uptimeMillis, change.position); change.consume(); drag.by(amount) },
            onDragEnd = { drag.release(tracker.calculateVelocity().y) },
            onDragCancel = { drag.release(0f) },
        )
    }
    .pointerInput(Unit) { detectTapGestures { } }

/** Vạch 1 dp theo mép trên (cả hai góc bo) của bảng trượt tối: bóng đổ không thấy trên nền tối, vạch này tách bảng khỏi trang (DESIGN.md §5.5 Bóng). */
internal fun Modifier.sheetEdge(color: Color): Modifier = drawWithContent {
    drawContent()
    val radius = Dim.radiusSheet.toPx()
    val stroke = 1.dp.toPx()
    clipRect(bottom = radius) {
        drawRoundRect(color, Offset(stroke / 2, stroke / 2), Size(size.width - stroke, radius * 4), CornerRadius(radius - stroke / 2), Stroke(stroke))
    }
}
