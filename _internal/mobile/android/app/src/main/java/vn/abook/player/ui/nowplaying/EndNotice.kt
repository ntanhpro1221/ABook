package vn.abook.player.ui.nowplaying

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import kotlinx.coroutines.delay
import vn.abook.player.ui.components.HeadphonesIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Lời sau khi nghe hết (web: `CaughtUpNotice` + `AfterTheEnd`), dưới hàng nút của Đang nghe:
 * hết phần đã có -> một dòng nói các chương sau chưa có audio; hết cuốn mà có tập kế -> "Đã nghe hết cuốn này." + "Nghe tiếp {tập}";
 * hết sách -> "Đã nghe hết sách." + "Nghe lại từ đầu"; cả hai kèm tới 3 cuốn khác để nghe và "Về thư viện".
 */
@Composable
fun EndNotice(state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState, modifier: Modifier = Modifier) {
    // Cần biết máy có giọng đọc không (sách chỉ có chữ chỉ mời khi đọc được): nạp danh sách giọng khi lời này hiện.
    LaunchedEffect(state.ended, state.bookId) { if (state.ended) model.loadVoices() }
    val choices = remember(state.ended, state.bookId, state.voices.size) { if (state.ended) model.endChoices() else PlayerEnd.Choices() }
    // Cuốn khác dài thì cuộn trong khung, không đẩy bìa và hàng nút ra khỏi màn.
    val scroll = rememberScrollState()
    Column(modifier.fillMaxWidth().heightIn(max = 280.dp).fadeEdges(scroll).verticalScroll(scroll)) {
        Reveal(state.ended && !state.whole) {
            BasicText("${PlayerText.CAUGHT_UP_HEAD}. ${PlayerText.CAUGHT_UP_DETAIL}", Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("end_caught_up"),
                style = Abook.type.bodySmall.copy(color = Abook.colors.text2, textAlign = TextAlign.Center))
        }
        Reveal(state.ended && state.whole) {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("end_finished"), horizontalAlignment = Alignment.CenterHorizontally) {
                val next = choices.next
                if (next != null) {
                    BasicText(PlayerText.ENDED_PART, style = Abook.type.bodySmall.copy(color = Abook.colors.text))
                    TextAction("Nghe tiếp ${PlayerEnd.nextLabel(next.title)}", { model.listen(next.id) }, "end_next", align = Alignment.Center)
                } else {
                    BasicText(PlayerText.ENDED_BOOK, style = Abook.type.bodySmall.copy(color = Abook.colors.text))
                    TextAction("Nghe lại từ đầu", model::restart, "end_restart", align = Alignment.Center)
                }
                AfterTheEnd(choices.others, model, window)
            }
        }
    }
}

/** Cuối lời "Đã nghe hết ...": mời nghe cuốn khác (mỗi cuốn một hàng nghe tiếp từ chỗ đã dừng) và đường về thư viện. */
@Composable
private fun AfterTheEnd(others: List<PlayerEnd.Pick>, model: NowPlayingModel, window: NowPlayingWindowState) {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s8), horizontalAlignment = Alignment.CenterHorizontally) {
        Reveal(others.isNotEmpty()) {
            Column(Modifier.fillMaxWidth().testTag("end_others")) {
                BasicText("Nghe cuốn khác", Modifier.padding(bottom = Dim.s4), style = Abook.type.caption.copy(color = Abook.colors.text2))
                for (book in others) {
                    Row(Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable { model.listen(book.id) }
                        .semantics { contentDescription = "Nghe ${book.title}" }.testTag("end_other_${book.id}"),
                        verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            BasicText(book.title, style = Abook.type.bodySmall.copy(color = Abook.colors.text))
                            BasicText(book.line, style = Abook.type.caption.copy(color = Abook.colors.text2))
                        }
                        Spacer(Modifier.width(Dim.s12))
                        HeadphonesIcon(Abook.colors.accentText)
                    }
                }
            }
        }
        if (window.toLibrary != null) TextAction("Về thư viện", { window.toLibrary?.invoke() }, "end_library", align = Alignment.Center)
    }
}

/**
 * Dòng báo ngắn của trình phát (web: toast): "Nghe tiếp Phần 2", "Máy khác đã nghe tới ... · 12:04" kèm "Nghe tiếp từ đó". Tự tan sau `lifeMs`
 * (lời có việc để làm thì lâu hơn); chạm việc là làm ngay.
 */
@Composable
fun PlayerNoteLine(model: NowPlayingModel, modifier: Modifier = Modifier) {
    val note by model.note.collectAsState()
    val shown = note
    LaunchedEffect(shown?.serial) {
        val current = shown ?: return@LaunchedEffect
        delay(current.lifeMs)
        model.dismissNote(current.serial)
    }
    // Giữ chữ cũ trong lúc khối khép lại (note đã null): không để Reveal đóng trên khoảng trống.
    val last = remember { arrayOfNulls<PlayerNote>(1) }
    if (shown != null) last[0] = shown
    Reveal(shown != null) {
        val text = last[0]
        if (text != null) Row(modifier.fillMaxWidth().padding(top = Dim.s8).testTag("player_note"), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
            BasicText(text.text, Modifier.weight(1f), style = Abook.type.bodySmall.copy(color = Abook.colors.text))
            text.action?.let { TextAction(it, model::noteAction, "player_note_action") }
        }
    }
}
