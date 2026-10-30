package vn.abook.player.ui.components

import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import vn.abook.player.ui.theme.Abook

/** Self-updating time, percentage, size and count: replace in place, with equal-width digits. */
@Composable
fun ClockLabel(text: String, modifier: Modifier = Modifier, style: TextStyle = Abook.type.body) {
    BasicText(text, modifier, style = style.merge(TextStyle(fontFeatureSettings = "tnum")))
}
