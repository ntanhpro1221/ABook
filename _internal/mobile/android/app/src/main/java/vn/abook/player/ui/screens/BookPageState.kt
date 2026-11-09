package vn.abook.player.ui.screens

import androidx.compose.runtime.staticCompositionLocalOf

/** A page started at the tap shares its result with the destination's first composition. */
val LocalBookPageState = staticCompositionLocalOf<BookUiState?> { null }
