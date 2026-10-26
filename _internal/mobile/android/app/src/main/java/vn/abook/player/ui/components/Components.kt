package vn.abook.player.ui.components

import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
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
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Chạm: thu 0,97 khi nhấn (90 ms), về 1 khi thả (120 ms), không chấm gợn đọng lại (DESIGN.md §5.2). Hệ số thu đọc trong pha vẽ
 * (graphicsLayer) nên mỗi khung của hoạt ảnh không dựng lại gì.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun Modifier.pressable(role: Role = Role.Button, onLongClick: (() -> Unit)? = null, onClick: () -> Unit): Modifier {
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) Motion.PRESS_SCALE else 1f,
        animationSpec = if (pressed) Motion.PressDown else Motion.PressUp,
        label = "press",
    )
    val base = graphicsLayer { scaleX = scale; scaleY = scale }
    return if (onLongClick == null) {
        base.clickable(interactionSource = source, indication = null, role = role, onClick = onClick)
    } else {
        base.combinedClickable(interactionSource = source, indication = null, role = role, onLongClick = onLongClick, onClick = onClick)
    }
}

/** Đầu màn gốc: tiêu đề 24 + dòng phụ ngay dưới (DESIGN.md §6 "Đầu màn"). */
@Composable
fun ScreenHeader(title: String, modifier: Modifier = Modifier, subtitle: String? = null, trailing: (@Composable () -> Unit)? = null) {
    Column(modifier.padding(top = Dim.s12, bottom = Dim.s16)) {
        Box(Modifier.fillMaxWidth().height(Dim.s48), contentAlignment = Alignment.CenterStart) {
            BasicText(title, style = Abook.type.screenTitle)
            if (trailing != null) Box(Modifier.align(Alignment.CenterEnd)) { trailing() }
        }
        if (subtitle != null) BasicText(subtitle, style = Abook.type.bodySmall)
    }
}

/** Nút ← của màn con: nét mũi tên thẳng mép nội dung, vùng chạm 48. */
@Composable
fun BackButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val ink = Abook.colors.text
    Box(
        modifier.size(Dim.s48).pressable(onClick = onClick).semantics { contentDescription = "Quay lại" },
        contentAlignment = Alignment.CenterStart,
    ) {
        // lucide ArrowLeft như bản web; mũi nhọn (x 4 kể cả nửa nét) dời về mép trái ô để thẳng mép nội dung.
        Canvas(Modifier.size(24.dp)) {
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
fun PrimaryButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, icon: (@Composable (Color) -> Unit)? = null) {
    val accent = Abook.colors.accent
    Box(
        modifier.height(Dim.s48)
            .then(if (enabled) Modifier.pressable(onClick = onClick) else Modifier.semantics { disabled() })
            .clip(RoundedCornerShape(Dim.radiusControl)).background(if (enabled) accent else accent.copy(alpha = 0.45f))
            .padding(horizontal = Dim.s24),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (icon != null) {
                icon(Abook.colors.accentInk)
                Spacer(Modifier.width(Dim.s8))
            }
            BasicText(label, style = Abook.type.bodyStrong.copy(color = Abook.colors.accentInk))
        }
    }
}
