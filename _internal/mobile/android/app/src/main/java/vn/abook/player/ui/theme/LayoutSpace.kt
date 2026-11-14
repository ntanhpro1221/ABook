package vn.abook.player.ui.theme

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Reserve space before deriving padding, dimensions or ratios from a constrained viewport. */
internal fun remainingSpace(total: Dp, reserved: Dp): Dp = (total - reserved).coerceAtLeast(0.dp)
internal fun remainingSpace(total: Int, reserved: Int): Int = (total - reserved).coerceAtLeast(0)
