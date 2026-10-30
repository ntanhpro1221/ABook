package vn.abook.player.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.BookOpenTextIcon
import vn.abook.player.ui.components.ChevronDownIcon
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.fadeEdgesHorizontal
import vn.abook.player.ui.components.MoreIcon
import vn.abook.player.ui.components.PlayIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.StopIcon
import vn.abook.player.ui.components.VoiceIcon
import vn.abook.player.ui.components.HistoryIcon
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.UserRoundIcon
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookNotes
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.Cast
import vn.abook.player.ui.data.CastMember
import vn.abook.player.ui.data.CastView
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.History
import vn.abook.player.ui.data.ListenRecord
import vn.abook.player.ui.data.ListenSession
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.voice.SamplePlayer
import kotlin.math.ceil
import kotlin.math.floor

/*
 * Các mục của trang sách ngoài danh sách chương: "Lịch sử" (mỗi lượt nghe một dòng, gom theo ngày, bấm nghe tiếp từ cuối lượt ấy) và "Nhân vật" (người kể chuyện, vai
 * chính, vai phụ) - viết lại từ listen/BookScreen.tsx (HistoryTab, CastList, PersonRow, RecordPicker, tab bar), cùng chữ. Là các mục của MỘT LazyColumn nên cuộn mượt
 * như danh sách chương.
 */

/** Ba mục của trang sách, theo thứ tự trên thanh. */
enum class BookTab(val label: String, val tag: String) {
    Chapters("Chương", "book_tab_chapters"),
    History("Lịch sử", "book_tab_history"),
    Cast("Nhân vật", "book_tab_cast"),
}

/**
 * Thanh mục (web: TabsList): chữ nằm ngang, gạch chân hổ phách TRƯỢT sang mục mới (cùng chuyển động với bộ lọc), mục "Chương" kèm số chương. Mỗi mục cao 48; chữ đang
 * chọn đậm màu mực, mục khác mực phụ.
 */
@Composable
fun BookTabs(tabs: List<BookTab>, selected: BookTab, chapterCount: Int, onPick: (BookTab) -> Unit, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val index = tabs.indexOf(selected).coerceAtLeast(0)
    val position = remember { Animatable(index.toFloat()) }
    LaunchedEffect(index) { position.animateTo(index.toFloat(), Motion.TabSlide) }
    val lefts = remember(tabs.size) { FloatArray(tabs.size) }
    val widths = remember(tabs.size) { FloatArray(tabs.size) }
    // Số lần dàn trang đổi vị trí: gạch chân đọc nó nên vẽ lại khi các mục dịch chỗ.
    var layouts by remember { mutableIntStateOf(0) }
    val viewport = remember { intArrayOf(0) }
    val scroll = rememberScrollState()
    // Đường kẻ chân nằm ở khung ngoài (trải cả bề rộng); gạch chân hổ phách ở hàng trong, trôi cùng chữ khi hàng cuộn (chữ hệ thống to / màn 320 dp: thiếu chỗ thì
    // cuộn ngang với mép mờ, không cắt chữ). Mục đang chọn tự cuộn vào khung.
    LaunchedEffect(index) {
        val left = lefts[index].toInt()
        val right = left + widths[index].toInt()
        val view = viewport[0]
        val target = when {
            view <= 0 -> scroll.value
            left < scroll.value -> left
            right > scroll.value + view -> right - view
            else -> scroll.value
        }
        if (target != scroll.value) scroll.animateScrollTo(target.coerceIn(0, scroll.maxValue), Motion.TabSlide)
    }
    Box(
        modifier.fillMaxWidth().testTag("book_tabs").onSizeChanged { viewport[0] = it.width }.drawBehind {
            drawRect(colors.line, Offset(0f, size.height - 1.dp.toPx()), Size(size.width, 1.dp.toPx()))
        },
    ) {
    Row(
        Modifier.fadeEdgesHorizontal(scroll).horizontalScroll(scroll).drawBehind {
            if (layouts < 0) return@drawBehind // chỉ để vẽ lại khi các mục dịch chỗ
            val thick = 3.dp.toPx()
            if (tabs.isEmpty()) return@drawBehind
            val p = position.value
            val low = floor(p).toInt().coerceIn(0, tabs.size - 1)
            val high = ceil(p).toInt().coerceIn(0, tabs.size - 1)
            val t = p - low
            val left = lefts[low] + (lefts[high] - lefts[low]) * t
            val width = widths[low] + (widths[high] - widths[low]) * t
            drawRect(colors.accent, Offset(left, size.height - thick), Size(width, thick))
        },
        horizontalArrangement = Arrangement.spacedBy(Dim.s24),
    ) {
        for ((i, tab) in tabs.withIndex()) {
            Row(
                Modifier.heightIn(min = Dim.s48).pressable(Role.Tab) { onPick(tab) }.semantics { this.selected = tab == selected }
                    .onGloballyPositioned {
                        val x = it.positionInParent().x
                        val w = it.size.width.toFloat()
                        if (lefts[i] != x || widths[i] != w) {
                            lefts[i] = x
                            widths[i] = w
                            layouts += 1
                        }
                    }
                    .testTag(tab.tag),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                BasicText(
                    tab.label,
                    style = Abook.type.tab,
                    color = { lerp(colors.text2, colors.text, (1f - kotlin.math.abs(position.value - i)).coerceIn(0f, 1f)) },
                )
                if (tab == BookTab.Chapters) {
                    Spacer(Modifier.width(Dim.s8))
                    BasicText("$chapterCount", style = Abook.type.caption.copy(color = colors.text2))
                }
            }
        }
    }
    }
}

/** Chip "Hồ sơ nghe: <tên> ⌄" dưới tiến độ (chỉ khi cuốn có từ hai hồ sơ): chạm mở bảng chọn hồ sơ. Cao 44 để chạm, viền mảnh bo tròn. */
@Composable
fun RecordChip(active: ListenRecord, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    Row(
        modifier.heightIn(min = Dim.touch).pressable(onClick = onClick).clip(CircleShape).border(1.dp, colors.line, CircleShape)
            .padding(horizontal = Dim.s12, vertical = Dim.s8).testTag("book_record_chip"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        UserRoundIcon(colors.text2, size = 14.dp)
        Spacer(Modifier.width(6.dp))
        BasicText("Hồ sơ nghe:", style = Abook.type.caption.copy(color = colors.text2))
        Spacer(Modifier.width(6.dp))
        BasicText(active.name, style = Abook.type.caption.copy(color = colors.text, fontWeight = FontWeight.Medium), modifier = Modifier.weight(1f, fill = false))
        Spacer(Modifier.width(6.dp))
        ChevronDownIcon(colors.text2, size = 14.dp)
    }
}

/** Lời báo ngắn của trang (xem [BookNotes]) dưới danh sách: đẩy nội dung lên, không che; Back không liên quan. */
@Composable
fun NotesBar(notes: BookNotes) {
    val note by notes.note.collectAsState()
    val visible by notes.visible.collectAsState()
    Reveal(visible) {
        Row(
            Modifier.fillMaxWidth().background(Abook.colors.panel).navigationBarsPadding().heightIn(min = Dim.s48).padding(horizontal = Dim.margin).testTag("book_note"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BasicText(note.text, style = Abook.type.bodySmall, modifier = Modifier.weight(1f).padding(vertical = Dim.s12))
            note.actionLabel?.let { label ->
                Spacer(Modifier.width(Dim.s16))
                TextAction(label, notes::act, "book_note_action")
            }
        }
    }
}

/** Trang trống có lời giải thích (web: EmptyState): biểu tượng nhạt, tên, một câu. `action` (nút) nằm dưới. */
@Composable
fun EmptyNote(title: String, body: String, modifier: Modifier = Modifier, tag: String = "empty_note", icon: @Composable (Color) -> Unit, action: (@Composable () -> Unit)? = null) {
    val colors = Abook.colors
    Column(modifier.fillMaxWidth().padding(vertical = Dim.s32).testTag(tag), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(Dim.s48), contentAlignment = Alignment.Center) { icon(colors.text3) }
        Spacer(Modifier.height(Dim.s8))
        BasicText(title, style = Abook.type.bodyStrong.copy(textAlign = TextAlign.Center))
        Spacer(Modifier.height(Dim.s4))
        BasicText(body, style = Abook.type.bodySmall.copy(textAlign = TextAlign.Center))
        if (action != null) {
            Spacer(Modifier.height(Dim.s16))
            action()
        }
    }
}

// ---- Lịch sử ------------------------------------------------------------------------------------------------------------

/**
 * Mục "Lịch sử": lượt nghe của hồ sơ đang dùng, mới nhất trước, gom theo ngày (mỗi ngày một phần gập, tóm tắt "3 lượt nghe"); bấm "Nghe tiếp từ …" nghe tiếp từ CUỐI lượt ấy.
 * `detail` null = trang chưa đọc xong: ba khung chờ (không phải "Chưa có lịch sử nghe" rồi mới đổi).
 */
fun LazyListScope.historyItems(detail: BookDetail?, fade: () -> Float, onResume: (ListenSession) -> Unit) {
    if (detail == null) {
        items(HISTORY_SKELETON, key = { "history_skeleton_$it" }, contentType = { "skeleton" }) { SkeletonLine(fade) }
        return
    }
    if (detail.sessions.isEmpty()) {
        item(key = "history_empty", contentType = "empty") {
            EmptyNote("Chưa có lịch sử nghe", "Mỗi lượt nghe lưu lại chỗ bạn dừng.", Modifier.fade(fade), "history_empty", icon = { ink -> HistoryIcon(ink, size = 28.dp) })
        }
        return
    }
    val titles = detail.chapters.associate { it.id to it.title }
    val days = History.byDay(detail.sessions)
    item(key = "history_week", contentType = "week") {
        val colors = Abook.colors
        val seconds = History.weekListened(detail.sessions)
        BasicText(weekText(seconds), style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.fade(fade).padding(top = Dim.s4, bottom = Dim.s8).testTag("history_week"))
    }
    for (day in days) {
        item(key = "history_day_${day.label}", contentType = "day") {
            Fold(day.label, "history_day_${day.label}", Modifier.fade(fade), summary = History.daySummary(day)) {
                for ((n, session) in day.sessions.withIndex()) {
                    if (n > 0) RowLine()
                    HistoryRow(session, { titles[it] }, onResume)
                }
            }
        }
    }
}

private const val HISTORY_SKELETON = 3

/** "7 ngày qua: **2 giờ** nghe cuốn này." - phần thời gian đậm màu mực. */
private fun weekText(seconds: Double): AnnotatedString {
    val line = History.weekLine(seconds)
    val part = Fmt.length(seconds)
    val at = line.indexOf(part)
    return buildAnnotatedString {
        if (at < 0) {
            append(line)
        } else {
            append(line.substring(0, at))
            withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(part) }
            append(line.substring(at + part.length))
        }
    }
}

@Composable
private fun HistoryRow(session: ListenSession, titleOf: (Int) -> String?, onResume: (ListenSession) -> Unit) {
    val colors = Abook.colors
    Row(Modifier.fillMaxWidth().padding(vertical = Dim.s8).testTag("history_row"), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            BasicText(History.headline(session), style = Abook.type.label)
            RowHint(History.route(session, titleOf))
        }
        Spacer(Modifier.width(Dim.s12))
        Row(
            Modifier.widthIn(max = 148.dp).heightIn(min = Dim.touch).pressable { onResume(session) }.testTag("history_resume"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            PlayIcon(colors.accentText, size = 14.dp)
            Spacer(Modifier.width(6.dp))
            BasicText(History.resumeLabel(session), style = Abook.type.label.copy(color = colors.accentText))
        }
    }
}

// ---- Nhân vật -----------------------------------------------------------------------------------------------------------

/** Nghe thử giọng một người (file `samples/<n>.wav` trong gói): một mẫu một lúc; chạm lại là dừng. Sống cùng trang sách. */
@Stable
class CastSamples(
    private val bookId: String,
    private val source: BookSource,
    private val player: SamplePlayer,
    private val scope: CoroutineScope,
) {
    /** Mã mẫu đang phát (null: không có). */
    var playing by mutableStateOf<Int?>(null)
        private set

    fun toggle(sampleId: Int) {
        if (playing == sampleId) {
            stop()
            return
        }
        player.stop()
        playing = sampleId
        scope.launch {
            val path = source.samplePath(bookId, sampleId)
            if (path == null || playing != sampleId) {
                if (playing == sampleId) playing = null
                return@launch
            }
            player.play(path, onEnded = { if (playing == sampleId) playing = null }, onFailed = { if (playing == sampleId) playing = null })
        }
    }

    fun stop() {
        player.stop()
        playing = null
    }
}

/**
 * Mục "Nhân vật": người kể chuyện, rồi "Vai chính" (mở sẵn khi ≤ 4 người) và "Vai phụ" (người chỉ có một cảnh). Dàn chỉ lộ tới chỗ đang nghe (`reached`): người xuất hiện SAU đó bị ẩn
 * tới khi bấm "Hiện chương sau" - dàn không lộ nội dung. `cast` null và `loaded` = chưa phân vai hay không đọc được.
 */
fun LazyListScope.castItems(
    cast: CastView?,
    loaded: Boolean,
    reached: Set<String>?,
    later: Boolean,
    onLater: () -> Unit,
    samples: CastSamples,
    onMore: (CastMember) -> Unit,
    fade: () -> Float,
) {
    if (!loaded) {
        items(CAST_SKELETON, key = { "cast_skeleton_$it" }, contentType = { "skeleton" }) { SkeletonLine(fade) }
        return
    }
    if (cast == null || cast.isEmpty) {
        item(key = "cast_empty", contentType = "empty") {
            EmptyNote(
                "Chưa có dàn nhân vật", "Dàn nhân vật hiện ra khi truyện đã được phân vai.", Modifier.fade(fade), "cast_empty",
                icon = { ink -> VoiceIcon(ink, size = 28.dp) },
            )
        }
        return
    }
    item(key = "cast_narrator", contentType = "narrator") { NarratorRow(cast, Modifier.fade(fade)) }
    if (cast.characters.isNotEmpty()) {
        item(key = "cast_main", contentType = "fold") {
            val ahead = if (reached != null) Cast.ahead(cast.characters, reached) else 0
            val shown = Cast.visible(cast.characters, reached, later)
            Fold(
                "Vai chính", "cast_main", Modifier.fade(fade).padding(top = Dim.s16),
                summary = "${cast.characters.size} người có lời thoại", defaultOpen = cast.characters.size <= 4,
            ) {
                for ((n, person) in shown.withIndex()) {
                    if (n > 0) RowLine(start = PersonTextStart)
                    PersonRow(person, samples, onMore)
                }
                if (ahead > 0) {
                    TextAction(Cast.laterLabel(later, ahead), onLater, "cast_later", Modifier.padding(top = Dim.s4), align = Alignment.CenterStart)
                }
            }
        }
    }
    if (cast.extras.isNotEmpty()) {
        item(key = "cast_extras", contentType = "fold") {
            Fold("Vai phụ", "cast_extras", Modifier.fade(fade).padding(top = Dim.s8), summary = "${cast.extras.size} người trong một cảnh") {
                for ((n, person) in cast.extras.withIndex()) {
                    if (n > 0) RowLine(start = PersonTextStart)
                    PersonRow(person, samples, onMore)
                }
            }
        }
    }
}

private const val CAST_SKELETON = 6

/** Chữ của hàng người bắt đầu sau vòng chữ cái (40) và khoảng cách (12): vạch chia hàng thụt theo chữ. */
private val PersonTextStart = 52.dp

@Composable
private fun NarratorRow(cast: CastView, modifier: Modifier) {
    val colors = Abook.colors
    Row(modifier.fillMaxWidth().padding(top = Dim.s8, bottom = Dim.s8).testTag("cast_narrator"), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(40.dp).clip(CircleShape).background(colors.accentSoft), contentAlignment = Alignment.Center) { BookOpenTextIcon(colors.accentText) }
        Spacer(Modifier.width(Dim.s12))
        Column(Modifier.weight(1f)) {
            BasicText("Người kể chuyện", style = Abook.type.caption.copy(color = colors.text2))
            BasicText(Cast.narratorName(cast.narrator), style = Abook.type.bodyStrong, modifier = Modifier.padding(top = 2.dp))
            RowHint(Cast.narratorCountLine(cast.narrator))
        }
    }
}

/** Một người: vòng chữ cái (sắc độ cố định theo giọng), tên + giới, tên gốc, giọng, việc đang chờ, số câu; bên phải nghe thử và "…". */
@Composable
private fun PersonRow(person: CastMember, samples: CastSamples, onMore: (CastMember) -> Unit) {
    val colors = Abook.colors
    val name = Cast.cleanName(person.displayName)
    Row(Modifier.fillMaxWidth().padding(vertical = Dim.s12).testTag("person_row"), verticalAlignment = Alignment.Top) {
        Avatar(Cast.initials(name), Cast.hue(person.voice?.preset?.ifEmpty { null } ?: person.name))
        Spacer(Modifier.width(Dim.s12))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.Bottom) {
                BasicText(name, style = Abook.type.bodyStrong, modifier = Modifier.weight(1f, fill = false))
                if (person.gender.isNotEmpty()) {
                    Spacer(Modifier.width(Dim.s8))
                    BasicText(person.gender, style = Abook.type.caption.copy(color = colors.text2))
                }
            }
            person.originalName?.let { BasicText("(tên gốc: ${Cast.cleanName(it)})", style = Abook.type.caption) }
            Row(Modifier.padding(top = 2.dp), verticalAlignment = Alignment.Top) {
                Box(Modifier.size(14.dp, 18.dp), contentAlignment = Alignment.CenterStart) { VoiceIcon(colors.text3, size = 14.dp) }
                Spacer(Modifier.width(4.dp))
                BasicText(Cast.voiceLine(person), style = Abook.type.caption.copy(color = colors.text2))
            }
            Cast.pendingLine(person)?.let { BasicText(it, style = Abook.type.caption.copy(color = colors.accentText, fontWeight = FontWeight.Medium), modifier = Modifier.padding(top = 2.dp)) }
            Cast.mergeLine(person)?.let { BasicText(it, style = Abook.type.caption.copy(color = colors.accentText, fontWeight = FontWeight.Medium), modifier = Modifier.padding(top = 2.dp)) }
            BasicText(Cast.countLine(person), style = Abook.type.caption.copy(color = colors.text2), modifier = Modifier.padding(top = Dim.s4))
        }
        person.sampleId?.let { sample -> SampleButton(samples.playing == sample, "Nghe $name nói") { samples.toggle(sample) } }
        Box(
            Modifier.size(Dim.touch).pressable { onMore(person) }.semantics { contentDescription = "Thêm tuỳ chọn cho $name" }.testTag("person_more"),
            contentAlignment = Alignment.Center,
        ) { MoreIcon(colors.text2) }
    }
}

/** Nút nghe thử (▶ / ■): ô chạm 44, mực nhỏ 14; đang phát thì hổ phách và là nút dừng. */
@Composable
private fun SampleButton(active: Boolean, label: String, onClick: () -> Unit) {
    val colors = Abook.colors
    Box(
        Modifier.size(Dim.touch).pressable(onClick = onClick).semantics { contentDescription = if (active) "Dừng nghe thử" else label }.testTag("person_sample"),
        contentAlignment = Alignment.Center,
    ) {
        if (active) StopIcon(colors.accentText, size = 14.dp) else PlayIcon(colors.text2, size = 14.dp)
    }
}

/** Vòng chữ cái của một người (web: `.avatar`, sắc độ theo giọng): nền nhạt, chữ đậm cùng sắc. */
@Composable
private fun Avatar(initials: String, hue: Int) {
    val dark = Abook.colors.dark
    val background = Color.hsv(hue.toFloat(), if (dark) 0.28f else 0.14f, if (dark) 0.30f else 0.96f)
    val ink = Color.hsv(hue.toFloat(), if (dark) 0.30f else 0.60f, if (dark) 0.90f else 0.38f)
    Box(Modifier.size(40.dp).clip(CircleShape).background(background), contentAlignment = Alignment.Center) {
        BasicText(initials, style = Abook.type.label.copy(color = ink, fontWeight = FontWeight.Bold))
    }
}

/** Khung xám đứng yên đúng hình một dòng (đang tải: không nhấp nháy, DESIGN.md §2). */
@Composable
private fun SkeletonLine(fade: () -> Float) {
    val sunken = Abook.colors.bgSunken
    Column(Modifier.fade(fade).fillMaxWidth().height(64.dp).padding(vertical = Dim.s12), verticalArrangement = Arrangement.Center) {
        Box(Modifier.fillMaxWidth(0.6f).height(14.dp).clip(RoundedCornerShape(Dim.radiusControl)).background(sunken))
        Spacer(Modifier.height(Dim.s8))
        Box(Modifier.fillMaxWidth(0.3f).height(10.dp).clip(RoundedCornerShape(Dim.radiusControl)).background(sunken))
    }
}

/** Nội dung mục mới mờ vào và nhích lên một chút (đọc trong pha vẽ - không dựng lại gì giữa chừng); mờ một mình là kiểu chuyển cảnh cấm (NATIVE_PHONE_UI.md §4). */
internal fun Modifier.fade(alpha: () -> Float): Modifier = graphicsLayer {
    val a = alpha()
    this.alpha = a
    translationY = (1f - a) * 8.dp.toPx()
}
