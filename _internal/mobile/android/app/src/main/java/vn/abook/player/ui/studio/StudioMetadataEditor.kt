package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import vn.abook.player.S
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.FieldGroup
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.theme.Dim

@Composable
fun StudioMetadataEditor(book: StudioBook, state: StudioProjectState) {
    var editing by remember(book.id) { mutableStateOf(false) }
    var draft by remember(book.id) { mutableStateOf(book.metadata) }
    var author by remember(book.id) { mutableStateOf(book.author) }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(Dim.s12)) {
        BookMetadataDetails(ListenBook(book.id, book.title, book.author, metadata = book.metadata))
        InlineActionRow(S.s_sua_thong_tin_17e4a8a6, { draft = book.metadata; author = book.author; editing = !editing }, "studio_edit_metadata", icon = LucidePaths.PENCIL)
        Reveal(editing) {
            // Các ô + nút Lưu dưới ô là một nhóm: đang gõ thì cả nhóm cuộn lên trên bàn phím, nút Lưu không bị che.
            FieldGroup(Modifier.fillMaxWidth().imePadding(), verticalArrangement = Arrangement.spacedBy(Dim.s12)) {
                BookField(S.s_tac_gia_0ec4731b, author, { author = it }, "studio_author", !state.busy)
                BookField(S.s_bookmeta_illustrator, draft.illustrator, { draft = draft.copy(illustrator = it) }, "studio_illustrator", !state.busy)
                BookField(S.s_bookmeta_alt_titles, draft.altTitles.joinToString("\n"), { draft = draft.copy(altTitles = it.split("\n")) }, "studio_alt_titles", !state.busy)
                BookField(S.s_bookmeta_genres, draft.genres.joinToString("\n"), { draft = draft.copy(genres = it.split("\n")) }, "studio_genres", !state.busy)
                BookField(S.s_tom_tat_b4bb3064, draft.summary, { draft = draft.copy(summary = it) }, "studio_summary", !state.busy)
                BookField(S.s_nguon_c76d57b3, draft.sourceUrl, { draft = draft.copy(sourceUrl = it) }, "studio_source", !state.busy)
                BookField(S.s_bookmeta_source_site, draft.sourceSite, { draft = draft.copy(sourceSite = it) }, "studio_source_site", !state.busy)
                PrimaryButton(S.s_bookmeta_save, { state.saveMetadata(draft.json().put("author", author)) }, Modifier.fillMaxWidth(), enabled = !state.busy)
            }
        }
    }
}
