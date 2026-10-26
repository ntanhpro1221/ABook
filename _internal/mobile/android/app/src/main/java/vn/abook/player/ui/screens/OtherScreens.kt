package vn.abook.player.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BackButton
import vn.abook.player.ui.components.PlaceholderTab
import vn.abook.player.ui.data.BookRow
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

@Composable
fun StudioScreen(modifier: Modifier = Modifier) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    PlaceholderTab("Studio", "Studio từ xa sắp có.", modifier.fillMaxSize().padding(top = top))
}

@Composable
fun SettingsScreen(modifier: Modifier = Modifier) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    PlaceholderTab("Cài đặt", "Cài đặt sắp có.", modifier.fillMaxSize().padding(top = top))
}

/** Trang sách (P0 giữ chỗ để có một màn con thật cho chuyển cảnh): bìa + tên + tác giả. Nội dung đầy đủ ở P2. */
@Composable
fun BookScreen(book: BookRow, covers: CoverLoader, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    Column(modifier.fillMaxSize().testTag("book_screen").padding(top = top, start = Dim.margin, end = Dim.margin)) {
        BackButton(onBack)
        Spacer(Modifier.height(Dim.s16))
        BookCover(book, covers, 480, 720, Modifier.width(160.dp))
        Spacer(Modifier.height(Dim.s16))
        BasicText(book.title, style = Abook.type.sectionTitle, modifier = Modifier.fillMaxWidth())
        if (book.author.isNotEmpty()) BasicText(book.author, style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s24))
        BasicText("Trang sách sắp có.", style = Abook.type.body.copy(color = Abook.colors.text2))
    }
}
