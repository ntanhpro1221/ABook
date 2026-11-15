package vn.abook.player.ui.components

import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsPropertyKey
import androidx.compose.ui.semantics.semantics

/** Captured with the unmerged tree; only the icon drawing primitives set this key. */
val VisualIcon = SemanticsPropertyKey<Boolean>("visual_icon")
val VisualTextColor = SemanticsPropertyKey<Int>("visual_text_color")
val VisualImage = SemanticsPropertyKey<Boolean>("visual_image")
fun Modifier.visualIcon() = semantics { this[VisualIcon] = true }
fun Modifier.visualImage() = semantics { this[VisualImage] = true }
