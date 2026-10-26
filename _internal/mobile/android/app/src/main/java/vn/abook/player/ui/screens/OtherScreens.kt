package vn.abook.player.ui.screens

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import vn.abook.player.ui.components.PlaceholderTab

@Composable
fun StudioScreen(modifier: Modifier = Modifier) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    PlaceholderTab("Studio", "Studio từ xa sắp có.", modifier.fillMaxSize().padding(top = top))
}
