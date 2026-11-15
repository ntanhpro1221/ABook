package vn.abook.player.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.GraphicsLayerScope
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.layout.layout
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.offset
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Alpha compositing needs room outside the layout box, including reduced-motion fades. */
internal fun Modifier.floatingMotionLayer(motion: GraphicsLayerScope.(Size) -> Unit): Modifier =
    layout { measurable, constraints ->
        val pad = Dim.s24.roundToPx()
        val layer = measurable.measure(constraints.offset(horizontal = pad * 2, vertical = pad * 2))
        layout((layer.width - pad * 2).coerceAtLeast(0), (layer.height - pad * 2).coerceAtLeast(0)) {
            layer.place(-pad, -pad)
        }
    }.graphicsLayer {
        val pad = Dim.s24.toPx()
        motion(Size((size.width - pad * 2).coerceAtLeast(0f), (size.height - pad * 2).coerceAtLeast(0f)))
        // Preserve the surface's pivot despite the transparent recording gutter.
        transformOrigin = TransformOrigin(
            (pad + (size.width - pad * 2) * transformOrigin.pivotFractionX) / size.width,
            (pad + (size.height - pad * 2) * transformOrigin.pivotFractionY) / size.height,
        )
    }.padding(Dim.s24)

/** Apply AFTER the surface's motion layer. Shadow, fill and edge share its transform and opacity. */
@Composable
internal fun Modifier.floatingSurface(shape: Shape, sheet: Boolean = false): Modifier {
    val colors = Abook.colors
    return shadow(Dim.s8, shape, clip = false)
        .clip(shape)
        .background(colors.panel)
        .then(if (sheet) {
            if (colors.dark) Modifier.sheetEdge(colors.line) else Modifier
        } else Modifier.border(1.dp, colors.line, shape))
}
