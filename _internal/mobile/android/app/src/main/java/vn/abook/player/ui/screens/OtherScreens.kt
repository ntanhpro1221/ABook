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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BackButton
import vn.abook.player.ui.components.PlaceholderTab
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.PlayerState
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
fun BookScreen(book: ListenBook, covers: CoverLoader, onBack: () -> Unit, modifier: Modifier = Modifier, onEdit: (() -> Unit)? = null) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    Column(modifier.fillMaxSize().testTag("book_screen").verticalScroll(rememberScrollState()).padding(top = top, start = Dim.margin, end = Dim.margin)) {
        BackButton(onBack)
        Spacer(Modifier.height(Dim.s16))
        BookCover(book.cover, book.title, book.part, covers, 160.dp, Modifier.width(160.dp))
        Spacer(Modifier.height(Dim.s16))
        BasicText(book.title, style = Abook.type.sectionTitle, modifier = Modifier.fillMaxWidth())
        if (book.author.isNotEmpty()) BasicText(book.author, style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s24))
        if (onEdit != null) vn.abook.player.ui.addbook.BookAction("Sửa sách", onEdit, Modifier.testTag("edit_book"))
        BasicText("Trang sách sắp có.", style = Abook.type.body.copy(color = Abook.colors.text2))
    }
}

/** Trình phát đầy đủ (giữ chỗ cho tới khi màn thật vào): thanh phát nhỏ mở tới đây. */
@Composable
fun NowPlayingPlaceholder(player: PlayerState, covers: CoverLoader, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    Column(modifier.fillMaxSize().testTag("now_playing_screen").padding(top = top, start = Dim.margin, end = Dim.margin)) {
        BackButton(onBack)
        Spacer(Modifier.height(Dim.s16))
        BookCover(player.cover, player.bookTitle, null, covers, 200.dp, Modifier.width(200.dp))
        Spacer(Modifier.height(Dim.s16))
        BasicText(player.chapterTitle.ifEmpty { player.bookTitle }, style = Abook.type.sectionTitle, modifier = Modifier.fillMaxWidth())
        BasicText(player.bookTitle, style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s24))
        BasicText("Trình phát đầy đủ sắp có.", style = Abook.type.body.copy(color = Abook.colors.text2))
    }
}
