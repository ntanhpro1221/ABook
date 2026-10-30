package vn.abook.player.ui.screens

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.BackButton
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.keepUnitsTogether
import vn.abook.player.ui.components.CloudDownloadIcon
import vn.abook.player.ui.components.DashedCircleIcon
import vn.abook.player.ui.components.MoreIcon
import vn.abook.player.ui.components.PlayPauseGlyph
import vn.abook.player.ui.components.RestartIcon
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SearchIcon
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookPage
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.ChapterLine
import vn.abook.player.ui.data.CoverArt
import vn.abook.player.ui.data.BookNotes
import vn.abook.player.ui.data.Cast
import vn.abook.player.ui.data.CastView
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.ListenRecord
import vn.abook.player.ui.data.RecordAction
import vn.abook.player.ui.voice.AndroidSamplePlayer
import vn.abook.player.ui.components.BookOpenTextIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.music.MusicState
import vn.abook.player.ui.data.PlayerClock
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.components.fadeEdges

/** Việc mà trang sách nhờ nơi khác làm (về, phát, nhảy chương, sau khi xoá) - tách khỏi màn để thử và để dựng ảnh chụp. */
@Stable
class BookScreenActions(
    val back: () -> Unit,
    /** Nút chính khi cuốn chưa ở trình phát: nạp ở chỗ nghe tiếp và phát (PlayerRepo.togglePlay). */
    val playBook: (String) -> Unit,
    /** Phát / dừng cuốn đang ở trình phát. */
    val toggle: () -> Unit,
    /** Phát một chương từ giây cho trước (PlayerRepo.playChapter). */
    val playChapter: (bookId: String, chapterId: Int, seconds: Double) -> Unit,
    /** Cuốn vừa bị xoá khỏi máy: rời trang sách. */
    val deleted: () -> Unit,
    /** Menu "Đọc theo": đưa cuốn vào trình phát (dừng, chỗ nghe tiếp) rồi mở Đang nghe thẳng ở chế độ đọc. */
    val readAlong: (bookId: String) -> Unit = {},
    /** "Sửa thông tin" ở bảng Thêm: mở màn Sửa sách (nơi DUY NHẤT sửa tên, tác giả, bìa, chương). */
    val edit: (ListenBook) -> Unit,
    /** "Xuất MP3" / "Xuất M4B" / "Xuất sách nói" ở bảng Thêm: mở màn Xuất của cuốn, sẵn dạng file đã chọn (null: sách chỉ có chữ). */
    val export: (ListenBook, ExportFormat?) -> Unit = { _, _ -> },
    /** Dòng phụ của hàng xuất trong bảng Thêm ("Đang xuất · 27%"); null = không có gì để nói. */
    val exportHint: (bookId: String) -> StateFlow<String?> = { NoExportHint },
    /** Mở một cuốn khác của Thư viện ("Mở cuốn ấy" sau khi chuyển hồ sơ sang đó). */
    val openBook: (bookId: String) -> Unit = {},
)

/** Không có việc xuất nào để nói (ảnh chụp, bản thử không dựng màn Xuất). */
val NoExportHint: StateFlow<String?> = MutableStateFlow(null)

/**
 * Trạng thái của MỘT trang sách: trang đọc từ kho ([BookSource.detail]) ở luồng nền, đọc lại mỗi khi Thư viện đổi (dừng phát, đánh dấu, sửa tên).
 * Chưa đọc xong thì màn vẽ phần đầu từ ô của Thư viện (cùng [ListenBook]) - bấm được ngay, bìa không nhảy.
 */
@Stable
class BookUiState(val bookId: String, private val source: BookSource) {
    var detail by mutableStateOf<BookDetail?>(null)
        private set

    /** Đã thử đọc ít nhất một lần (phân biệt "đang đọc" với "cuốn không còn"). */
    var loaded by mutableStateOf(false)
        private set

    /** Dàn nhân vật (chỉ đọc khi người nghe mở mục "Nhân vật"; sau đó đọc lại cùng trang). */
    var cast by mutableStateOf<CastView?>(null)
        private set
    var castLoaded by mutableStateOf(false)
        private set
    private var castWanted = false

    suspend fun load() {
        val next = source.detail(bookId)
        // Cuốn vừa bị xoá (trang đang đóng): giữ trang cuối, không nháy sang "Không tìm thấy sách này".
        if (next != null || detail == null) detail = next
        loaded = true
        if (castWanted) loadCast()
    }

    suspend fun wantCast() {
        castWanted = true
        loadCast()
    }

    private suspend fun loadCast() {
        cast = source.cast(bookId)
        castLoaded = true
    }
}

/**
 * Trang sách (DESIGN.md §7): đầu trang (bìa · tên · tác giả · giọng · thời lượng, tập / bộ, tiến độ mảnh), MỘT nút chính hổ phách (Nghe / Nghe tiếp · chương /
 * Tạm dừng / Nghe lại từ đầu), hàng phụ cùng kiểu (Tìm · Từ đầu · Thêm), rồi danh sách chương phẳng - chạm chương là phát chương ấy.
 *
 * Danh sách là MỘT LazyColumn (đầu trang là các mục đầu của nó), mọi mục có `key` + `contentType`. Vạch tiến độ của chương đang phát đọc đồng hồ phát
 * trong pha vẽ ([PlayerClock]) - mỗi nhịp không dựng lại hàng nào.
 */
@Composable
fun BookScreen(
    book: ListenBook,
    library: LibraryState,
    player: PlayerState,
    clock: PlayerClock,
    covers: CoverLoader,
    source: BookSource,
    sheets: SheetHost,
    actions: BookScreenActions,
    modifier: Modifier = Modifier,
    music: MusicState? = null,
    prepare: vn.abook.player.ui.data.PrepareState? = null,
) {
    val ui = remember(book.id, source) { BookUiState(book.id, source) }
    // Chương đã "Làm trước" (dấu "Đã làm sẵn"): lắng nghe lõi chỉ khi trang đang hiện.
    androidx.compose.runtime.DisposableEffect(prepare) {
        prepare?.watch(true)
        onDispose { prepare?.watch(false) }
    }
    val prepared by (prepare?.status ?: remember { kotlinx.coroutines.flow.MutableStateFlow(vn.abook.player.ui.data.PrepareStatus()) }).collectAsState()
    val preparedIds = remember(prepared, book.id) { prepared.readyIds(book.id) }
    // Thư viện đọc lại (dừng phát, đánh dấu, sửa) thì trang cũng đọc lại.
    LaunchedEffect(ui, library) { ui.load() }
    val detail = ui.detail
    val others = (library as? LibraryState.Ready)?.books
    val shown = detail?.book ?: others?.firstOrNull { it.id == book.id } ?: book
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val list = rememberLazyListState()
    val current = BookPage.currentChapter(shown, player)
    val chapters = detail?.chapters
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val notes = remember(book.id) { BookNotes(scope) }
    var tab by rememberSaveable(book.id) { mutableStateOf(BookTab.Chapters) }
    var later by rememberSaveable(book.id) { mutableStateOf(false) }
    val tabs = if (shown.textOnly) listOf(BookTab.Chapters, BookTab.History) else BookTab.entries
    val shownTab = if (tab in tabs) tab else BookTab.Chapters
    // Đổi mục thì nội dung mờ vào (đọc trong pha vẽ); lần dựng đầu không mờ.
    val fade = remember { Animatable(1f) }
    val firstTab = remember { booleanArrayOf(true) }
    LaunchedEffect(shownTab) {
        if (firstTab[0]) {
            firstTab[0] = false
            return@LaunchedEffect
        }
        if (list.firstVisibleItemIndex > TABS_ITEM) list.scrollToItem(TABS_ITEM)
        fade.snapTo(0f)
        fade.animateTo(1f, tween(MotionMs.MEDIUM, easing = Motion.Decelerate))
    }
    LaunchedEffect(ui, shownTab == BookTab.Cast) { if (shownTab == BookTab.Cast) ui.wantCast() }
    val samples = remember(book.id) { CastSamples(book.id, source, AndroidSamplePlayer(context), scope) }
    DisposableEffect(samples) { onDispose { samples.stop() } }
    LaunchedEffect(shownTab) { if (shownTab != BookTab.Cast) samples.stop() }
    val reached = remember(chapters, current) { chapters?.let { Cast.reachedTitles(it, current) } }
    val currentItem = if (shownTab == BookTab.Chapters) chapters?.indexOfFirst { it.id == current }?.takeIf { it >= 0 }?.plus(HEAD_ITEMS) else null
    // Chương đang nghe nằm khuất BÊN DƯỚI: lối "Tới chỗ đang nghe" dưới thanh mục. Trang không tự cuộn - đầu trang + nút "Nghe tiếp" (đã ghi tên chương) luôn là thứ thấy đầu tiên.
    val below by remember(currentItem) {
        derivedStateOf { currentItem != null && (list.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: Int.MAX_VALUE) < currentItem }
    }
    // Cuốn không còn trên máy (bị chuyển thư mục / xoá ở nơi khác): trang nói rõ, nút về Thư viện.
    val gone = ui.loaded && detail == null && others != null && others.none { it.id == book.id }
    if (gone) {
        Column(modifier.fillMaxSize().testTag("book_screen")) {
            Box(Modifier.padding(top = top, start = Dim.margin, end = Dim.margin).fillMaxWidth().height(Dim.s48)) {
                BackButton(actions.back, Modifier.testTag("book_back"))
            }
            EmptyNote(
                "Không tìm thấy sách này", "Sách có thể đã bị chuyển sang thư mục khác hoặc bị xoá khỏi thư viện.",
                Modifier.padding(horizontal = Dim.margin, vertical = Dim.s32), "book_gone", icon = { ink -> BookOpenTextIcon(ink, size = 28.dp) },
            ) { PrimaryButton("Về thư viện", actions.back, Modifier.testTag("book_gone_back")) }
        }
        return
    }
    val openRecords: (RecordAction?) -> Unit = { start ->
        val loaded = detail
        if (loaded != null && loaded.records.isNotEmpty()) {
            sheets.show { dismiss -> RecordSheet(shown, loaded.records, others.orEmpty().filter { it.id != shown.id }, source, notes, start, actions.openBook, dismiss) }
        }
    }
    Column(modifier.fillMaxSize().testTag("book_screen")) {
        Box(Modifier.padding(top = top, start = Dim.margin, end = Dim.margin).fillMaxWidth().height(Dim.s48)) {
            BackButton(actions.back, Modifier.testTag("book_back"))
        }
        LazyColumn(
            state = list,
            modifier = Modifier.weight(1f).fillMaxWidth().fadeEdges(list).testTag("book_list"),
            contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, top = Dim.s12, bottom = bottom + Dim.s32),
        ) {
            item(key = "head", contentType = "head") { BookHead(shown, covers, detail?.records.orEmpty(), player.bookId == shown.id && player.hasTrack, player.error.isNotEmpty()) { openRecords(null) } }
            item(key = "actions", contentType = "actions") {
                BookButtons(shown, detail, player, sheets, source, actions, music, notes, openRecords)
            }
            item(key = "tabs", contentType = "tabs") {
                BookTabs(tabs, shownTab, chapters?.size ?: shown.chaptersTotal, { tab = it }, Modifier.padding(top = Dim.sectionGap, bottom = Dim.s8))
            }
            when (shownTab) {
                BookTab.Chapters -> {
                    // Đã đọc xong mà sách không có chương: câu ở chỗ nút chính đã nói điều ấy - không thêm gì ở đây.
                    val noChapters = ui.loaded && chapters.isNullOrEmpty()
                    if (!noChapters) item(key = "chapters_jump", contentType = "jump") {
                        ChapterJump(below) { currentItem?.let { scope.launch { list.animateScrollToItem((it - 1).coerceAtLeast(0)) } } }
                    }
                    when {
                        chapters == null && !ui.loaded -> items(SKELETON_ROWS, key = { "skeleton_$it" }, contentType = { "skeleton" }) { SkeletonRow() }
                        chapters.isNullOrEmpty() -> Unit
                        else -> items(chapters.orEmpty(), key = { it.id }, contentType = { "chapter" }) { chapter ->
                            val here = chapter.id == current
                            val live = here && player.bookId == shown.id
                            Box(Modifier.fade { fade.value }) {
                                ChapterRow(
                                    chapter = chapter,
                                    current = here,
                                    playing = live && player.playing,
                                    livePosition = if (live) clock else null,
                                    durationMs = if (live) player.durationMs else 0L,
                                    prepared = chapter.id in preparedIds,
                                    producing = shown.producing,
                                    onPlay = {
                                        if (live) actions.toggle() else actions.playChapter(shown.id, chapter.id, chapter.resumeAt)
                                    },
                                    onMore = {
                                        sheets.show { dismiss ->
                                            ChapterSheet(shown, chapter, source, onListenFromStart = { actions.playChapter(shown.id, chapter.id, 0.0) }, dismiss = dismiss, notes = notes)
                                        }
                                    },
                                )
                            }
                        }
                    }
                }
                BookTab.History -> historyItems(detail, { fade.value }) { session -> actions.playChapter(shown.id, session.toChapter, session.toSeconds) }
                BookTab.Cast -> castItems(
                    ui.cast, ui.castLoaded, reached, later, { later = !later }, samples,
                    onMore = { person ->
                        sheets.show { dismiss -> PersonSheet(shown.id, person, ui.cast?.characters.orEmpty(), source, notes, dismiss) }
                    },
                    fade = { fade.value },
                )
            }
        }
        NotesBar(notes)
    }
}

private const val SKELETON_ROWS = 6

/** Số mục đứng trước chương đầu trong danh sách: đầu trang, hàng nút, thanh mục, lối "Tới chỗ đang nghe". */
private const val HEAD_ITEMS = 4

/** Vị trí thanh mục trong danh sách: đổi mục thì cuộn tới đây nếu trang đang ở sâu hơn. */
private const val TABS_ITEM = 2

/** Bìa · (tập / bộ) · tên · tác giả · giọng · số chương · thời lượng · dòng tình trạng · tiến độ mảnh. Tên dài xuống dòng, không cắt. */
@Composable
private fun BookHead(book: ListenBook, covers: CoverLoader, records: List<ListenRecord>, listening: Boolean, failed: Boolean, onRecords: () -> Unit) {
    val colors = Abook.colors
    val (main, sub) = remember(book.title, book.part) { CoverArt.splitTitle(book.title, book.part) }
    Column(Modifier.fillMaxWidth().testTag("book_head")) {
        Row(Modifier.fillMaxWidth()) {
            BookCover(book.cover, book.title, book.part, covers, CoverWidth, Modifier.width(CoverWidth).testTag("book_cover"))
            Spacer(Modifier.width(Dim.s16))
            Column(Modifier.weight(1f)) {
                if (sub.isNotEmpty()) {
                    BasicText(sub, style = Abook.type.caption.copy(color = colors.accentText, fontWeight = FontWeight.Medium))
                    Spacer(Modifier.height(Dim.s4))
                }
                BasicText(main, style = Abook.type.screenTitle, modifier = Modifier.testTag("book_title"))
                Spacer(Modifier.height(Dim.s8))
                BasicText(keepUnitsTogether(BookPage.metaLine(book)), style = Abook.type.bodySmall)
                BookPage.statusLine(book)?.let { line ->
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(line, style = Abook.type.bodySmall.copy(color = if (book.complete) colors.text2 else colors.accentText))
                }
            }
        }
        if (!book.textOnly) {
            Spacer(Modifier.height(Dim.s16))
            val fraction = book.progress.fraction
            val fill = if (book.progress.finished) colors.success else colors.accent
            Box(
                Modifier.fillMaxWidth().height(3.dp).clip(CircleShape).semantics { contentDescription = "Đã nghe" }.drawBehind {
                    drawRect(colors.line)
                    drawRect(fill, Offset.Zero, Size(size.width * fraction, size.height))
                },
            )
            Spacer(Modifier.height(Dim.s8))
            BasicText(BookPage.progressLine(book, listening, failed), style = Abook.type.caption.copy(color = colors.text2))
        }
        // Một hồ sơ thì không có chip: các việc với hồ sơ duy nhất nằm trong bảng "Thêm" (web: singleRecordActions).
        val active = if (records.size > 1) records.firstOrNull { it.active } else null
        if (active != null) {
            Spacer(Modifier.height(Dim.s12))
            RecordChip(active, onRecords)
        }
    }
}

private val CoverWidth = 112.dp

/** Nút chính + hàng phụ. Sách đã nghe hết phần đã có (đang làm dở): một dòng chữ thay cho nút chính, hàng phụ giữ nguyên chỗ. */
@Composable
private fun BookButtons(
    book: ListenBook,
    detail: BookDetail?,
    player: PlayerState,
    sheets: SheetHost,
    source: BookSource,
    actions: BookScreenActions,
    music: MusicState?,
    notes: BookNotes,
    openRecords: (RecordAction?) -> Unit,
) {
    val haptic = LocalHapticFeedback.current
    val listening = player.bookId == book.id
    val playingHere = listening && player.playing
    val finished = book.progress.finished && !playingHere
    val caughtUp = book.progress.caughtUp && !listening
    val resume = book.resume
    val started = book.progress.heardSeconds > 0 || book.state.last != null
    val first = detail?.chapters?.firstOrNull { it.playable }
    val restart = {
        if (first != null) {
            actions.playChapter(book.id, first.id, 0.0)
            // Bấm nhầm "Từ đầu" giữa chừng: một lời báo đủ lâu để kịp quay lại chỗ đang nghe (web: toast "Quay lại chỗ cũ").
            if (resume != null && !finished && (resume.chapterId != first.id || resume.at > 30)) {
                notes.say("Đang nghe lại từ đầu", "Quay lại chỗ cũ") { actions.playChapter(book.id, resume.chapterId, resume.at) }
            }
        }
    }
    Column(Modifier.fillMaxWidth().padding(top = Dim.s24)) {
        when {
            caughtUp -> BasicText(
                "Đã nghe hết phần đã có. Chương mới sẽ hiện ở đây khi làm xong.",
                style = Abook.type.bodySmall,
                modifier = Modifier.padding(vertical = Dim.s12),
            )
            resume == null -> BasicText(
                "Sách chưa có chương nào nghe được trên máy này.",
                style = Abook.type.bodySmall,
                modifier = Modifier.padding(vertical = Dim.s12),
            )
            else -> ListenButton(
                label = BookPage.primaryLabel(playingHere, finished, resume, book.progress.heardSeconds),
                detail = BookPage.primaryDetail(playingHere, finished, resume, book.progress.heardSeconds),
                playing = playingHere,
                restart = finished,
                onClick = {
                    haptic.performHapticFeedback(HapticFeedbackType.ContextClick)
                    when {
                        finished -> restart()
                        listening -> actions.toggle()
                        else -> actions.playBook(book.id)
                    }
                },
            )
        }
        Spacer(Modifier.height(Dim.s12))
        // Hàng phụ: luôn cùng ba chỗ, cùng thứ tự - nút chưa dùng được thì nhạt đi chứ không biến mất (không nhảy chỗ khi bắt đầu nghe).
        Row(Modifier.fillMaxWidth().testTag("book_secondary"), horizontalArrangement = Arrangement.SpaceBetween) {
            SecondaryButton("Tìm", "Tìm chữ trong sách", enabled = !detail?.chapters.isNullOrEmpty(), tag = "book_find", edge = -1, onClick = {
                val loaded = detail ?: return@SecondaryButton
                sheets.show { dismiss ->
                    FindInBookSheet(loaded, source, onPick = { hit ->
                        dismiss()
                        actions.playChapter(book.id, hit.chapterId, hit.start ?: 0.0)
                    })
                }
            }) { color -> SearchIcon(color) }
            SecondaryButton(
                "Từ đầu", "Nghe lại từ đầu", enabled = started && resume != null && !finished && first != null, tag = "book_restart", edge = 0, onClick = restart,
            ) { color -> RestartIcon(color) }
            SecondaryButton("", "Thêm tuỳ chọn", enabled = true, tag = "book_more", edge = 1, onClick = {
                sheets.show { dismiss -> BookMenuSheet(book, detail, source, actions, dismiss, music, player.music.takeIf { player.bookId == book.id }, onRecord = { openRecords(it) }, notes = notes) }
            }) { color -> MoreIcon(color) }
        }
    }
}

/**
 * Nút chính hổ phách, rộng cả hàng, cao tối thiểu 48. Dòng nhãn = biểu tượng phát / dừng (biến hình nét vẽ) + một động từ ngắn, luôn một dòng;
 * dòng phụ (chương sẽ phát) nằm riêng bên dưới, chữ nhỏ, tên dài thì xuống dòng - không cắt, và không bao giờ đẩy biểu tượng lệch khỏi nhãn của nó.
 * Nhãn / dòng phụ đổi thì trượt (chữ cũ lên, chữ mới từ dưới lên).
 */
@Composable
private fun ListenButton(label: String, detail: String?, playing: Boolean, restart: Boolean, onClick: () -> Unit) {
    val colors = Abook.colors
    Box(
        Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable(onClick = onClick).clip(RoundedCornerShape(Dim.radiusControl))
            .background(colors.accent).padding(horizontal = Dim.s16, vertical = Dim.s12).testTag("book_primary"),
        contentAlignment = Alignment.Center,
    ) {
        AnimatedContent(
            targetState = label to detail,
            transitionSpec = {
                (slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it } togetherWith
                    slideOutVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { -it })
                    .using(SizeTransform(clip = true))
            },
            contentAlignment = Alignment.Center,
            label = "primary",
        ) { (text, sub) ->
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(Dim.s24), contentAlignment = Alignment.Center) {
                        if (restart) RestartIcon(colors.accentInk) else PlayPauseGlyph(playing, colors.accentInk, 22.dp)
                    }
                    Spacer(Modifier.width(Dim.s8))
                    BasicText(text, style = Abook.type.bodyStrong.copy(color = colors.accentInk))
                }
                if (sub != null) {
                    BasicText(sub, style = Abook.type.caption.copy(color = colors.accentInk, textAlign = TextAlign.Center))
                }
            }
        }
    }
}

/** Nút phụ (DESIGN.md §6 "Nút (b)"): biểu tượng trơn trong ô chạm 44 + nhãn nhỏ dưới. Nhãn rỗng (nút ⋯): vẫn chừa dòng nhãn để các biểu tượng thẳng hàng; tên đọc màn hình ở `description`. */
@Composable
private fun SecondaryButton(
    label: String,
    description: String,
    enabled: Boolean,
    tag: String,
    edge: Int,
    onClick: () -> Unit,
    icon: @Composable (androidx.compose.ui.graphics.Color) -> Unit,
) {
    val colors = Abook.colors
    val ink = if (enabled) colors.text else colors.fg3
    Column(
        Modifier.offset(x = EdgeInset * edge)
            .then(if (enabled) Modifier.pressable(onClick = onClick) else Modifier.semantics { disabled() })
            .semantics { contentDescription = description }
            .testTag(tag),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.size(Dim.touch), contentAlignment = Alignment.Center) { icon(ink) }
        BasicText(label, style = Abook.type.caption.copy(color = if (enabled) colors.text2 else colors.fg3))
    }
}

/** Mực biểu tượng 22 dp nằm giữa ô chạm 44: hai nút ở đầu mút dịch ra nửa phần thừa để mực thẳng mép nút chính (DESIGN.md §6 "INK EDGE"). */
private val EdgeInset = (Dim.touch - 22.dp) / 2

/** Cao một dòng chữ thân (16 / 24). */
private val FirstLine = 24.dp

/** Lối tới chương đang nghe, dưới thanh mục: trượt lên từ dưới (cùng hướng với chỗ nó dẫn tới), không mờ dần; ẩn thì không chiếm chỗ. */
@Composable
private fun ChapterJump(visible: Boolean, onJump: () -> Unit) {
    AnimatedVisibility(
        visible = visible,
        modifier = Modifier.fillMaxWidth().clipToBounds(),
        enter = slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it },
        exit = slideOutVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it },
    ) {
        Box(Modifier.fillMaxWidth().heightIn(min = Dim.touch).pressable(onClick = onJump).testTag("book_jump_current"), contentAlignment = Alignment.CenterEnd) {
            BasicText("Tới chỗ đang nghe", style = Abook.type.label.copy(color = Abook.colors.accentText))
        }
    }
}

/**
 * Một chương (DESIGN.md §6 "Hàng danh sách"): trái trạng thái (phát / dừng, đã nghe, chưa có audio), giữa tên (16) + dòng phụ (14: thời lượng, phần trăm đã nghe),
 * phải "…". Hàng đang nghe: chữ hổ phách + vạch tiến độ mảnh, không tô nền cả hàng. `livePosition`: chương đang ở trình phát - vạch đọc đồng hồ trong pha vẽ.
 */
@Composable
private fun ChapterRow(
    chapter: ChapterLine,
    current: Boolean,
    playing: Boolean,
    livePosition: PlayerClock?,
    durationMs: Long,
    prepared: Boolean,
    producing: Boolean = false,
    onPlay: () -> Unit,
    onMore: () -> Unit,
) {
    val colors = Abook.colors
    val title = when {
        current -> colors.accentText
        chapter.done || !chapter.playable -> colors.text2
        else -> colors.text
    }
    // Cả hai biểu tượng của hàng (trạng thái bên trái, "…" bên phải) bám DÒNG ĐẦU của tên - một luật căn cho cả hàng, tên dài xuống dòng cũng không lệch nhau.
    Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).testTag("chapter_row"), verticalAlignment = Alignment.Top) {
        Row(
            Modifier.weight(1f).heightIn(min = 64.dp)
                .then(if (chapter.playable) Modifier.pressable(onClick = onPlay) else Modifier.semantics { disabled() })
                .semantics { selected = current }
                .padding(vertical = Dim.s12)
                .testTag("chapter_${chapter.id}"),
            verticalAlignment = Alignment.Top,
        ) {
            // Biểu tượng đứng giữa DÒNG ĐẦU của tên (cao đúng một dòng chữ 16/24): tên dài xuống dòng thì biểu tượng vẫn thẳng dòng đầu.
            Box(Modifier.size(Dim.s24, FirstLine).testTag("chapter_status"), contentAlignment = Alignment.CenterStart) {
                when {
                    current -> PlayPauseGlyph(playing, colors.accentText, 20.dp)
                    chapter.done -> CheckIcon(colors.success)
                    chapter.playable -> PlayPauseGlyph(false, colors.text2, 20.dp)
                    else -> DashedCircleIcon(colors.fg3)
                }
            }
            Spacer(Modifier.width(Dim.s12))
            Column(Modifier.weight(1f)) {
                BasicText(chapter.title, style = Abook.type.body.copy(color = title, fontWeight = if (current) FontWeight.Medium else FontWeight.Normal))
                RowHint(BookPage.chapterLine(chapter, producing))
                if (prepared) PreparedMark()
                val partly = chapter.heard > 0f && chapter.heard < 1f
                if (livePosition != null || partly) {
                    Spacer(Modifier.height(6.dp))
                    val accent = colors.accent
                    val track = colors.line
                    val stored = chapter.heard
                    Box(
                        Modifier.width(96.dp).height(3.dp).clip(CircleShape).drawBehind {
                            val fraction = if (livePosition != null && durationMs > 0) {
                                (livePosition.positionMs.value.toFloat() / durationMs).coerceIn(0f, 1f)
                            } else {
                                stored
                            }
                            drawRect(track)
                            drawRect(accent, Offset.Zero, Size(size.width * fraction, size.height))
                        },
                    )
                }
            }
        }
        Box(
            // Ô chạm 44 có tâm đúng tâm dòng đầu (lề trên 12 + nửa dòng 24).
            Modifier.padding(top = Dim.s12 + FirstLine / 2 - Dim.touch / 2).size(Dim.touch)
                .pressable(onClick = onMore).semantics { contentDescription = "Thêm tuỳ chọn cho ${chapter.title}" }
                .testTag("chapter_more"),
            contentAlignment = Alignment.CenterEnd,
        ) {
            MoreIcon(colors.text2)
        }
    }
}

/** Dấu "Đã làm sẵn" của một chương đã "Làm trước": máy đã đọc sẵn, nghe liền mạch (web: viên nhỏ nền nhấn kèm CloudDownload). */
@Composable
private fun PreparedMark() {
    Row(Modifier.padding(top = Dim.s4).background(Abook.colors.accentSoft, RoundedCornerShape(Dim.radiusControl)).padding(horizontal = Dim.s4).testTag("chapter_prepared"),
        verticalAlignment = Alignment.CenterVertically) {
        CloudDownloadIcon(Abook.colors.accentText)
        Spacer(Modifier.width(Dim.s4))
        BasicText("Đã làm sẵn", style = Abook.type.caption.copy(color = Abook.colors.accentText))
    }
}

/** Hàng chờ khi trang chưa đọc xong: khung xám đúng hình hàng chương, đứng yên (không nhấp nháy). */
@Composable
private fun SkeletonRow() {
    val sunken = Abook.colors.bgSunken
    Row(Modifier.fillMaxWidth().height(64.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(Dim.s24))
        Spacer(Modifier.width(Dim.s12))
        Column(Modifier.weight(1f)) {
            Box(Modifier.fillMaxWidth(0.6f).height(14.dp).clip(RoundedCornerShape(Dim.radiusControl)).background(sunken))
            Spacer(Modifier.height(Dim.s8))
            Box(Modifier.fillMaxWidth(0.3f).height(10.dp).clip(RoundedCornerShape(Dim.radiusControl)).background(sunken))
        }
    }
}
