package vn.abook.player.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.CloseIcon
import vn.abook.player.ui.components.HandIcon
import vn.abook.player.ui.components.PhoneIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SleepIcon
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.TimerResetIcon
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.MarkerKind
import vn.abook.player.ui.data.NightMarker
import vn.abook.player.ui.data.NightRecap
import vn.abook.player.ui.data.NightState
import vn.abook.player.ui.nowplaying.ReadParagraph
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Thẻ buổi sáng "Tối qua - nghe tới đâu rồi thiếp đi?" ở đầu Thư viện (web: MorningRecap.tsx): các mốc chắc chắn của đêm (hẹn giờ, lần cuối chạm máy, máy bắt đầu
 * nằm yên, tự dừng) đặt CÂU VĂN đang được đọc ở mỗi mốc cạnh nhau - người nghe nhận ra đoạn cuối mình còn nhớ nhanh hơn nhìn một con số giây. Chạm một mốc là nghe từ
 * đó; "Tìm đúng câu" cho lướt từng đoạn. Không hiện khi sách đã bị xoá, hay đã nghe tiếp sau đêm ấy (mời quay lại chỗ cũ là lùi họ về).
 */
@Composable
fun MorningRecap(night: NightState, books: List<ListenBook>, play: (bookId: String, chapterId: Int, seconds: Double) -> Unit, modifier: Modifier = Modifier,
    nowMs: () -> Long = System::currentTimeMillis) {
    val session by night.session.collectAsState()
    val lines by night.lines.collectAsState()
    val shown = session
    var scrubbing by remember { mutableStateOf(false) }
    val markers = remember(shown) { shown?.let { NightRecap.markers(it) }.orEmpty() }
    val book = shown?.let { s -> books.firstOrNull { it.id == s.bookId } }
    val visible = shown != null && book != null && markers.isNotEmpty() && NightRecap.fresh(shown, nowMs() / 1000.0) &&
        !NightRecap.heardSince(shown.endedAt ?: 0.0, book.state.last?.at)
    if (shown == null) return
    Reveal(visible) {
        val colors = Abook.colors
        val resume = { chapterId: Int, seconds: Double -> play(shown.bookId, chapterId, seconds); night.dismiss() }
        val suggested = markers.firstOrNull { it.suggested } ?: markers.firstOrNull()
        Column(modifier.fillMaxWidth().padding(bottom = Dim.s16).testTag("morning_recap")) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                SleepIcon(colors.accentText)
                Spacer(Modifier.width(Dim.s8))
                Column(Modifier.weight(1f)) {
                    BasicText(NightRecap.sessionLabel(shown.endedAt, nowMs()), style = Abook.type.label.copy(color = colors.accentText))
                    RowHint(shown.bookTitle)
                }
                Box(Modifier.size(Dim.touch).pressable { night.dismiss() }.semantics { contentDescription = "Ẩn thẻ này" }.testTag("recap_dismiss"), contentAlignment = Alignment.Center) {
                    CloseIcon(colors.text2)
                }
            }
            BasicText("Nghe tới đâu rồi thiếp đi?", Modifier.padding(top = Dim.s4), style = Abook.type.sectionTitle)
            Spacer(Modifier.size(Dim.s8))
            for (marker in markers) MarkerRow(marker, lines[marker.chapterId].orEmpty()) { resume(marker.chapterId, marker.seconds) }
            Spacer(Modifier.size(Dim.s8))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
                if (suggested != null) PrimaryButton("Nghe từ đây", { resume(suggested.chapterId, suggested.seconds) }, Modifier.weight(1f).testTag("recap_resume"))
                if (lines.values.any { paragraphs -> paragraphs.any { it.timed } }) {
                    TextAction(if (scrubbing) "Thu gọn" else "Tìm đúng câu", { scrubbing = !scrubbing }, "recap_scrub_toggle")
                }
            }
            Reveal(scrubbing) { Scrub(markers, lines) { chapterId, seconds -> resume(chapterId, seconds) } }
        }
    }
}

/** Đoạn đang đọc ở `seconds` của chương (null khi chữ chưa có mốc giờ). */
internal fun sentenceAt(paragraphs: List<ReadParagraph>, seconds: Double): String? {
    if (paragraphs.none { it.timed }) return null
    val ms = (seconds * 1000).toLong()
    return paragraphs.lastOrNull { it.timed && it.startMs <= ms }?.text?.trim()?.takeIf { it.isNotEmpty() }
}

@Composable
private fun MarkerRow(marker: NightMarker, paragraphs: List<ReadParagraph>, onClick: () -> Unit) {
    val colors = Abook.colors
    val tint = if (marker.suggested) colors.accentText else colors.text2
    Row(Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable(onClick = onClick).padding(vertical = Dim.s8).testTag("recap_marker_${marker.kind.name.lowercase()}")) {
        Box(Modifier.size(Dim.s24), contentAlignment = Alignment.CenterStart) {
            when (marker.kind) {
                MarkerKind.Timer -> TimerResetIcon(tint)
                MarkerKind.Touch -> HandIcon(tint)
                MarkerKind.Still -> PhoneIcon(tint)
                MarkerKind.Stopped -> SleepIcon(tint)
            }
        }
        Spacer(Modifier.width(Dim.s12))
        Column(Modifier.weight(1f)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                BasicText(marker.label, Modifier.weight(1f), style = Abook.type.bodyStrong.copy(color = tint))
                MarkerClock(marker.at)
            }
            RowHint(marker.hint)
            RowHint(marker.chapterTitle + " · " + Fmt.clock(marker.seconds))
            sentenceAt(paragraphs, marker.seconds)?.let {
                BasicText("“$it”", Modifier.padding(top = Dim.s4), style = Abook.type.bodySmall.copy(color = colors.text, fontStyle = FontStyle.Italic))
            }
        }
    }
}

/** Giờ của mốc, ở mép phải dòng tên (không phải dòng phụ dưới tên). */
@Composable
private fun MarkerClock(at: Double) {
    BasicText(NightRecap.clock(at), style = Abook.type.caption.copy(color = Abook.colors.text2))
}

/** Lướt từng đoạn quanh các mốc: chạm đoạn cuối cùng còn nhớ là nghe từ đó. */
@Composable
private fun Scrub(markers: List<NightMarker>, lines: Map<Int, List<ReadParagraph>>, onPick: (chapterId: Int, seconds: Double) -> Unit) {
    val colors = Abook.colors
    val scroll = rememberScrollState()
    val groups = remember(markers, lines) {
        markers.map { it.chapterId }.distinct().mapNotNull { id ->
            val paragraphs = lines[id].orEmpty().filter { it.timed }
            if (paragraphs.isEmpty()) return@mapNotNull null
            val points = markers.filter { it.chapterId == id }.map { (it.seconds * 1000).toLong() }
            val at = { ms: Long -> paragraphs.indexOfLast { it.startMs <= ms }.coerceAtLeast(0) }
            val from = (at(points.min()) - 2).coerceAtLeast(0)
            val to = (at(points.max()) + 3).coerceAtMost(paragraphs.size)
            Triple(id, markers.first { it.chapterId == id }.chapterTitle, paragraphs.subList(from, to))
        }
    }
    Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("recap_scrub")) {
        BasicText("Chọn câu cuối cùng còn nhớ:", Modifier.padding(bottom = Dim.s4), style = Abook.type.caption.copy(color = colors.text2))
        Column(Modifier.fillMaxWidth().heightIn(max = 320.dp).fadeEdges(scroll).verticalScroll(scroll)) {
            for ((chapterId, title, paragraphs) in groups) {
                BasicText(title, Modifier.padding(top = Dim.s12, bottom = Dim.s4), style = Abook.type.caption.copy(color = colors.text2, fontWeight = FontWeight.Medium))
                for (paragraph in paragraphs) {
                    BasicText(paragraph.text.trim(), Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable { onPick(chapterId, paragraph.startMs / 1000.0) }.padding(vertical = Dim.s12)
                        .testTag("recap_line_${chapterId}_${paragraph.id}"), style = Abook.type.bodySmall.copy(color = colors.text))
                }
            }
        }
    }
}
