package vn.abook.player.ui.components

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
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
import androidx.compose.ui.platform.LocalDensity
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
 * Lớp bảng trượt: nền tối chạm để đóng, bảng bo 20 trượt từ đáy lên (300 ms giảm tốc) và xuống (200 ms tăng tốc), kéo tay nắm xuống để đóng.
 * Nền tối đi cùng chuyển động trượt (không phải chuyển cảnh chỉ có mờ) và vẽ trong pha vẽ.
 */
@Composable
fun SheetLayer(host: SheetHost) {
    val spec = host.current
    var shown by remember { mutableStateOf<SheetSpec?>(null) }
    val progress = remember { Animatable(0f) }
    val drag = remember { Animatable(0f) }
    LaunchedEffect(spec) {
        if (spec != null) {
            shown = spec
            drag.snapTo(0f)
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
    val scope = rememberCoroutineScope()
    val closeAt = with(LocalDensity.current) { 120.dp.toPx() }
    Box(
        Modifier.fillMaxSize().testTag("sheet_layer")
            .drawBehind { drawRect(scrim, alpha = progress.value) }
            .pointerInput(Unit) { detectTapGestures { host.dismiss() } },
    ) {
        Column(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth()
                .graphicsLayer { translationY = (1f - progress.value) * size.height + drag.value }
                .clip(RoundedCornerShape(topStart = Dim.radiusSheet, topEnd = Dim.radiusSheet))
                .background(colors.panel)
                .then(if (colors.dark) Modifier.sheetEdge(colors.line) else Modifier)
                .pointerInput(Unit) { detectTapGestures { } },
        ) {
            Box(
                Modifier.fillMaxWidth().height(Dim.s24)
                    .draggable(
                        rememberDraggableState { delta -> scope.launch { drag.snapTo((drag.value + delta).coerceAtLeast(0f)) } },
                        Orientation.Vertical,
                        onDragStopped = { velocity ->
                            if (drag.value > closeAt || velocity > 1800f) host.dismiss() else drag.animateTo(0f, Motion.SheetIn)
                        },
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Box(Modifier.width(36.dp).height(4.dp).clip(CircleShape).background(colors.line))
            }
            Box(Modifier.navigationBarsPadding().padding(horizontal = Dim.margin).padding(bottom = Dim.s16)) {
                sheet.content { host.dismiss() }
            }
        }
    }
}

/** Vạch 1 dp theo mép trên (cả hai góc bo) của bảng trượt tối: bóng đổ không thấy trên nền tối, vạch này tách bảng khỏi trang (DESIGN.md §5.5 Bóng). */
internal fun Modifier.sheetEdge(color: Color): Modifier = drawWithContent {
    drawContent()
    val radius = Dim.radiusSheet.toPx()
    val stroke = 1.dp.toPx()
    clipRect(bottom = radius) {
        drawRoundRect(color, Offset(stroke / 2, stroke / 2), Size(size.width - stroke, radius * 4), CornerRadius(radius - stroke / 2), Stroke(stroke))
    }
}
