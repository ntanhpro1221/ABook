package vn.abook.player.ui.music.library

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import vn.abook.player.S
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.LucideIcon
import vn.abook.player.ui.components.LucidePaths
import vn.abook.player.ui.theme.Abook

/** Lối sang màn "Nhạc" ở những chỗ từng chứa "Nhạc của tôi" (Cài đặt › Nghe, Sửa sách, Studio › Nhạc nền) - như OpenMusicRow của web. */
@Composable
fun OpenMusicRow(onOpen: () -> Unit, modifier: Modifier = Modifier) {
    ListItem(
        S.s_mo_nhac_c2f1b86b, modifier, onClick = onOpen, tag = "open_music", hint = S.s_nhac_cua_toi_f65b7ac6, chevron = true,
        leading = { LucideIcon(LucidePaths.LIST_MUSIC, Abook.colors.text2) },
    )
}
