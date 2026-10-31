package vn.abook.player.ui.shell

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.runtime.collectAsState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.layout
import androidx.compose.ui.layout.layoutId
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.hideFromAccessibility
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.components.navigationClearance
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.motion.ScreenGeometry
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.NavState
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.player.MorphingMiniPlayer
import vn.abook.player.ui.player.MiniPlayerSlot
import vn.abook.player.ui.addbook.AddBookRoute
import vn.abook.player.ui.editbook.CoverSearchRoute
import vn.abook.player.ui.addbook.ImportQueue
import vn.abook.player.ui.addbook.ImportChapterRoute
import vn.abook.player.ui.addbook.ImportReviewRoute
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.devices.PairScreen
import vn.abook.player.ui.devices.ShareScreen
import vn.abook.player.ui.devices.StorageScreen
import vn.abook.player.ui.studio.StudioHomeRoute
import vn.abook.player.ui.studio.StudioNewRoute
import vn.abook.player.ui.studio.StudioHub
import vn.abook.player.ui.studio.StudioProjectRoute
import vn.abook.player.ui.studio.StudioRequest
import vn.abook.player.ui.studio.StudioSubRoute
import vn.abook.player.ui.voice.KeysScreen
import vn.abook.player.ui.voice.MyMusicScreen
import vn.abook.player.ui.voice.VoicePage
import vn.abook.player.ui.editbook.EditBooks
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.export.ExportScreen
import vn.abook.player.ui.export.ExportState
import vn.abook.player.ui.editbook.EditBookRoute
import vn.abook.player.ui.editbook.EditChapterRoute
import vn.abook.player.ui.editbook.CoverCropRoute
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.BookScreenActions
import vn.abook.player.ui.screens.NoExportHint
import vn.abook.player.ui.screens.LibraryActions
import vn.abook.player.ui.screens.LibraryScreen
import vn.abook.player.ui.screens.LibraryUiState
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsGroupScreen
import vn.abook.player.ui.screens.SettingsScreen
import vn.abook.player.ui.screens.StudioScreen
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.nowplaying.NowPlayingLayer
import vn.abook.player.ui.pip.PipContent
import vn.abook.player.ui.pip.PipControl
import vn.abook.player.ui.nowplaying.NowPlayingModel
import vn.abook.player.ui.nowplaying.NowPlayingWindowState
import vn.abook.player.ui.nowplaying.PlayerCoverProvider
import vn.abook.player.ui.nowplaying.rememberRepoNowPlaying
import kotlin.math.abs
import kotlin.math.max

/** Mọi trạng thái sống của khung (ngăn xếp, tab, vị trí cuộn từng tab) ở MỘT chỗ - tab rời khỏi cây vẫn giữ chỗ cuộn. */
@Stable
class ShellState(val scope: CoroutineScope, onSortChanged: (LibrarySort) -> Unit = {}) {
    val nav = NavState(scope)
    val window = NowPlayingWindowState(scope)
    val tabs = TabState(scope)
    val libraryGrid = LazyGridState()
    val library = LibraryUiState(scope, onSortChanged = onSortChanged)
    val sheets = SheetHost()

    /**
     * File app khác gửi tới ("Mở bằng", chia sẻ): vào hàng nhập sách rồi mở "Thêm sách" (trượt vào như mọi màn con) để bạn thấy tiến độ; Back về chỗ đang đứng.
     * Đang ở chính Thêm sách (hay bước xem trước của nó) thì không đẩy thêm màn: hàng đợi tự hiện file mới.
     */
    suspend fun receive(queue: ImportQueue, sources: List<String>) {
        queue.enqueue(sources)
        while (nav.busy) delay(20) // đang chuyển cảnh thì NavState.push bỏ lệnh
        val top = nav.stack.top?.destination
        if (top == Destination.AddBook || top is Destination.ImportReview || top is Destination.ImportChapter) return
        nav.push(Destination.AddBook)
    }

    /**
     * Thông báo Studio / hàng "Studio" ở Thiết bị mở Studio của một máy: danh sách dự án, thẳng một dự án ở tab đã xin, hay màn con của dự án (đẩy dự án
     * trước để Back về dự án). Thu bảng trượt và cửa sổ Đang nghe như Back; đang ở đúng nơi ấy rồi thì không đẩy thêm màn.
     */
    suspend fun openStudio(request: StudioRequest) {
        sheets.dismiss()
        window.close()
        val route = request.route
        val project = route.book?.let { Destination.StudioProject(request.computer, it, route.tab) }
        val sub = route.sub?.let { kind -> route.book?.let { Destination.StudioSub(request.computer, it, kind) } }
        val target = sub ?: project ?: Destination.Studio(request.computer)
        if (nav.stack.top?.destination == target) return
        if (sub != null && project != null && nav.stack.top?.destination != project) {
            while (nav.busy) delay(20) // đang chuyển cảnh thì NavState.push bỏ lệnh
            nav.push(project)
        }
        while (nav.busy) delay(20)
        nav.push(target)
    }
}

/**
 * Khung app: ngăn xếp màn con (trượt phải / Back dự đoán) trên ba tab (trượt ngang), thanh phát nhỏ trên thanh tab ở mọi màn gốc, bảng trượt trên tất cả.
 * Gốc = [RootTabs]. `onFirstContent` gọi một lần khi Thư viện đã có nội dung (reportFullyDrawn); ngay sau đó các tab chưa hiện được dựng trước lúc rảnh.
 * `books`: kho của trang sách (đọc chương, đánh dấu, sửa, xoá) - mặc định không có (ảnh chụp chỉ cần phần đầu trang).
 * `sampleClock`: false = the window does not sample the core clock per frame (Robolectric never idles with a frame loop running).
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun AppShell(
    shell: ShellState,
    library: LibraryState,
    player: PlayerRepo,
    covers: CoverLoader,
    settings: SettingsEnv,
    onFirstContent: () -> Unit = {},
    books: BookSource = BookSource.None,
    nowPlaying: NowPlayingModel = rememberRepoNowPlaying(player),
    sampleClock: Boolean = true,
    imports: ImportQueue? = null,
    editors: EditBooks? = null,
    exports: ExportState? = null,
    demo: Boolean = false,
    autoPick: Boolean = false,
    deletions: vn.abook.player.ui.data.UndoDelete? = null,
    companion: vn.abook.player.ui.devices.CompanionRepo? = null,
    askNotifications: (() -> Unit) -> Unit = { it() },
    /** Cửa sổ nhỏ (PiP) của hệ điều hành; null = bản thử / máy không có. Đang ở PiP thì khung chỉ vẽ [PipContent]. */
    pip: PipControl? = null,
    /** Studio từ xa (các phiên theo máy tính); null = bản thử không có. */
    studio: StudioHub? = null,
) {
    val nav = shell.nav
    val playerState by player.state.collectAsState()
    PredictiveBackHandler(enabled = nav.canPop) { events ->
        try {
            events.collect { nav.dragBack(it.progress) }
            nav.commitBack()
        } catch (cancelled: CancellationException) {
            nav.cancelBack()
            throw cancelled
        }
    }
    if (library is LibraryState.Ready) {
        LaunchedEffect(Unit) {
            onFirstContent()
            shell.tabs.precomposeRest()
        }
    }
    LaunchedEffect(library, playerState.bookId) {
        if (!demo && library is LibraryState.Ready) player.reconcile(library.books)
    }
    LaunchedEffect(playerState.hasTrack) {
        if (!playerState.hasTrack && shell.window.expanded) shell.window.close()
    }
    LaunchedEffect(deletions) {
        deletions?.pending?.collect { settings.devices?.openStorage() }
    }
    val actions = remember(shell, player, settings.devices) {
        LibraryActions(
            openBook = { book ->
                val devices = settings.devices
                if (book.remote != null && devices != null) shell.sheets.show { dismiss ->
                    vn.abook.player.ui.screens.RemoteBookSheet(book, devices) { dismiss(); player.playNow(book.id) }
                } else shell.nav.push(Destination.Book(book))
            },
            playNow = player::playNow,
            addBook = { shell.nav.push(Destination.AddBook) },
            connect = if (settings.devices != null) ({ shell.nav.push(Destination.Devices(DevicesPage.Pair)) }) else null,
        )
    }
    val window = shell.window
    DisposableEffect(shell) {
        settings.repo.openAdvanced = { shell.nav.push(Destination.Settings(SettingsGroup.Advanced)) }
        onDispose { settings.repo.openAdvanced = {} }
    }
    window.otherPlayers = companion?.let { repo ->
        { shell.sheets.show { dismiss -> vn.abook.player.ui.devices.OtherPlayersSheet(repo, player, dismiss) } }
    }
    val openPlayer = remember(window) { window::open }
    window.miniWindow = remember(pip) { pip?.takeIf { it.available }?.let { control -> { control.enter() } } }
    // Tới Cài đặt > Giọng đọc (tải giọng về máy): thu cửa sổ Đang nghe rồi mở nhóm Giọng đọc như bạn chạm vào nó.
    val openVoiceSettings = remember(shell, window) {
        {
            shell.sheets.dismiss()
            window.close()
            shell.nav.push(Destination.Settings(SettingsGroup.Voice))
        }
    }
    window.voiceSettings = openVoiceSettings
    window.toLibrary = remember(shell, window) {
        {
            window.close()
            shell.nav.popToRoot()
            shell.tabs.select(Tab.Library)
        }
    }
    // Chương chỉ có chữ mà giọng trực tuyến chưa được đồng ý: hỏi trước khi phát (PlayGate); bảng tự đóng khi câu hỏi được trả lời hay bị lệnh khác thay.
    val consent by player.gate.request.collectAsState()
    LaunchedEffect(consent) {
        val request = consent ?: return@LaunchedEffect
        shell.sheets.show { dismiss -> vn.abook.player.ui.voice.OnlineVoiceSheet(request, player.gate.request, settings.voice, openVoiceSettings, dismiss) }
    }
    val inPip = pip?.active == true
    // Vào PiP: đóng mọi lớp phủ như Back (bảng trượt, menu, tìm kiếm). Ra khỏi PiP (bấm vào cửa sổ nhỏ): app đầy đủ mở ở màn Đang nghe.
    val wasInPip = remember { booleanArrayOf(false) }
    LaunchedEffect(inPip) {
        if (inPip) {
            shell.sheets.dismiss()
            window.closeSheet()
            shell.library.closeMenu()
            shell.library.closeSearch()
        } else if (wasInPip[0] && playerState.hasTrack) {
            window.open()
        }
        wasInPip[0] = inPip
    }
    val libraryNow = rememberUpdatedState(library)
    val bookActions = remember(shell, player, exports) {
        BookScreenActions(
            back = shell.nav::pop,
            playBook = player::togglePlay,
            toggle = player::toggle,
            playChapter = player::playChapter,
            deleted = shell.nav::pop,
            readAlong = { book -> shell.scope.launch { if (player.prepare(book)) window.openReading() } },
            edit = { shell.nav.push(Destination.EditBook(it)) },
            export = { book, format -> shell.nav.push(Destination.Export(book, format)) },
            exportHint = { id -> exports?.hint(id) ?: NoExportHint },
            openBook = { id -> (libraryNow.value as? LibraryState.Ready)?.books?.firstOrNull { it.id == id }?.let { shell.nav.push(Destination.Book(it)) } },
        )
    }
    if (inPip) {
        PipContent(playerState, { player.clock.positionMs.value }, covers)
        return
    }
    Box(Modifier.fillMaxSize().background(Abook.colors.bg).semantics { testTagsAsResourceId = true }) {
        // Cửa sổ Đang nghe nằm TRÊN cả ngăn xếp màn lẫn thanh tab; thanh phát nhỏ thật ở gốc là nguồn của chuyển động nở ra (NowPlayingSource).
        PlayerCoverProvider(covers) {
            NowPlayingLayer(nowPlaying, window, sampleClock) {
                ShellFrame(
                    nav,
                    stack = { insets ->
                    ScreenStack(
                        nav = nav, insets = insets,
                        root = { RootTabs(shell, library, playerState, player, covers, actions, openPlayer, settings, companion, askNotifications) },
                        screen = { destination ->
                            when (destination) {
                                is Destination.Book -> BookScreen(
                                    destination.book, library, playerState, player.clock, covers, books, shell.sheets, bookActions, music = settings.music, prepare = settings.prepare,
                                )
                                is Destination.Export -> if (exports != null) ExportScreen(destination.book, exports, nav::pop, destination.format)
                                Destination.AddBook -> if (imports != null) AddBookRoute(imports, nav::pop,
                                    { nav.push(Destination.ImportReview(it)) }, { id ->
                                        (library as? LibraryState.Ready)?.books?.firstOrNull { it.id == id }?.let { nav.push(Destination.Book(it)) }
                                    }, autoPick, active = nav.stack.top?.destination == Destination.AddBook && !nav.progress.isRunning)
                                is Destination.ImportReview -> if (imports != null) ImportReviewRoute(imports, destination.itemId, nav::pop) { nav.push(Destination.ImportChapter(destination.itemId, it)) }
                                is Destination.ImportChapter -> if (imports != null) ImportChapterRoute(imports, destination.index, nav::pop)
                                is Destination.EditBook -> if (editors != null) EditBookRoute(editors.session(destination.book, demo), covers, shell.sheets, nav::pop,
                                    { nav.push(Destination.CropCover(destination.book, it)) }, { nav.push(Destination.EditChapter(destination.book, it)) },
                                    findCover = { nav.push(Destination.CoverSearch(destination.book)) })
                                is Destination.CoverSearch -> if (editors != null) CoverSearchRoute(editors.session(destination.book, demo), destination.book.title, nav::pop,
                                    { nav.push(Destination.CropCover(destination.book, it)) }, active = nav.stack.top?.destination == destination && !nav.progress.isRunning)
                                is Destination.EditChapter -> if (editors != null) EditChapterRoute(editors.session(destination.book, demo), destination.chapterId, nav::pop)
                                is Destination.CropCover -> if (editors != null) CoverCropRoute(editors.session(destination.book, demo), destination.uri, nav::pop)
                                is Destination.Settings -> SettingsGroupScreen(
                                    destination.group, settings, shell.sheets, onBack = nav::pop, openDevices = { nav.push(Destination.Devices(it)) },
                                    openVoice = { nav.push(Destination.Voice(it)) },
                                )
                                is Destination.Devices -> settings.devices?.let { devices ->
                                    when (destination.page) {
                                        DevicesPage.Pair -> PairScreen(devices, shell.sheets, nav::pop)
                                        DevicesPage.Share -> ShareScreen(devices, shell.sheets, nav::pop)
                                        DevicesPage.Storage -> StorageScreen(devices, shell.sheets, nav::pop)
                                    }
                                }
                                is Destination.Voice -> settings.voice?.let { voice ->
                                    when (destination.page) {
                                        VoicePage.Keys -> KeysScreen(voice, shell.sheets, nav::pop)
                                        VoicePage.Music -> MyMusicScreen(voice, shell.sheets, nav::pop)
                                    }
                                }
                                is Destination.Studio -> if (studio != null) StudioHomeRoute(studio, destination.computer, nav::pop,
                                    { nav.push(Destination.StudioProject(destination.computer, it)) },
                                    active = nav.stack.top?.destination == destination && !nav.progress.isRunning,
                                    onNew = { nav.push(Destination.StudioNew(destination.computer)) })
                                is Destination.StudioNew -> if (studio != null) StudioNewRoute(studio, destination.computer, nav::pop,
                                    { nav.replaceTop(Destination.StudioProject(destination.computer, it)) },
                                    active = nav.stack.top?.destination == destination && !nav.progress.isRunning)
                                is Destination.StudioProject -> if (studio != null) StudioProjectRoute(studio, destination.computer, destination.book, destination.tab,
                                    shell.sheets, nav::pop, listen = { nav.popToRoot(); shell.tabs.select(Tab.Library) },
                                    active = nav.stack.top?.destination == destination && !nav.progress.isRunning,
                                    openSub = { nav.push(Destination.StudioSub(destination.computer, destination.book, it)) })
                                is Destination.StudioSub -> if (studio != null) StudioSubRoute(studio, destination.computer, destination.book, destination.kind,
                                    shell.sheets, nav::pop, openSub = { nav.push(Destination.StudioSub(destination.computer, destination.book, it)) },
                                    active = nav.stack.top?.destination == destination && !nav.progress.isRunning)
                            }
                        },
                    )
                    },
                    bars = {
                        if (deletions != null) vn.abook.player.ui.components.UndoBar(deletions,
                            backEnabled = shell.sheets.current == null && !window.expanded, aboveNavigation = !nav.canPop)
                        vn.abook.player.ui.screens.NotesBar(settings.repo.notes)
                    },
                    footer = { RootPlaybackArea(shell, playerState, player, covers, openPlayer, companion) },
                )
            }
            SheetLayer(shell.sheets)
        }
    }
}

/**
 * Chỗ chừa ở đáy của các lớp màn, đo bởi [ShellFrame]: lớp gốc (ba tab) nhường chỗ cho thanh báo + chân (thanh phát nhỏ, thanh tab), màn con chỉ nhường chỗ cho
 * thanh báo (chân đã trượt khuất dưới nó). Kích cỡ từng lớp vì thế KHÔNG đổi trong lúc chuyển cảnh - chỉ phép dịch (graphicsLayer) chạy theo khung. Trước đây chân
 * là một khối thu chiều cao trong dòng chảy (Reveal): mỗi khung chuyển cảnh dàn trang lại, vẽ lại cả màn con lẫn gốc, và dựng lại cả chân lúc Back xong
 * (trace Perfetto NATIVE_POLISH: 6-9 ms dựng + 1-2 ms dàn trang mỗi khung trên máy ảo).
 */
@Stable
class LayerInsets {
    var root by mutableIntStateOf(0)
    var screen by mutableIntStateOf(0)
}

private fun Modifier.layerInset(insets: LayerInsets, isRoot: Boolean): Modifier = layout { measurable, constraints ->
    val inset = if (isRoot) insets.root else insets.screen
    val height = (constraints.maxHeight - inset).coerceAtLeast(0)
    val placeable = measurable.measure(Constraints.fixed(constraints.maxWidth, height))
    layout(constraints.maxWidth, height) { placeable.place(0, 0) }
}

/** Phần chân đang lộ (1 = đầy, 0 = khuất): gốc đầy; màn con đầu tiên trượt vào thì chân trượt xuống theo (1 - p); sâu hơn nữa thì đã khuất. */
internal fun footerShown(nav: NavState): Float = when (nav.stack.size) {
    0 -> 1f
    1 -> 1f - nav.progress.value
    else -> 0f
}

/**
 * Khung đáy của app: từ dưới lên là chân (thanh phát nhỏ + thanh tab), ngăn xếp màn, thanh báo (hoàn tác, lời báo trang). Ba khối được đo MỘT lần ở đây; chân và
 * thanh báo chỉ được đặt bằng lớp vẽ (trượt theo [footerShown]), nên đổi màn không làm đổi dàn trang của ai. Chân luôn nằm trong cây (không dựng lại lúc Back xong);
 * thanh báo nằm TRÊN ngăn xếp để vẫn bấm được khi có màn con, và đứng ngay trên chân khi chân đang lộ.
 */
@Composable
private fun ShellFrame(
    nav: NavState,
    stack: @Composable (LayerInsets) -> Unit,
    bars: @Composable () -> Unit,
    footer: @Composable () -> Unit,
) {
    val insets = remember { LayerInsets() }
    Layout(
        content = {
            Box(
                Modifier.layoutId(0).semantics { if (footerShown(nav) <= 0f) hideFromAccessibility() },
            ) { Column(Modifier.fillMaxWidth()) { footer() } }
            Box(Modifier.layoutId(1)) { stack(insets) }
            Column(Modifier.layoutId(2).fillMaxWidth()) { bars() }
        },
        modifier = Modifier.fillMaxSize(),
    ) { measurables, constraints ->
        val width = constraints.maxWidth
        val height = constraints.maxHeight
        val loose = Constraints(maxWidth = width, maxHeight = height)
        val footerPlaceable = measurables.first { it.layoutId == 0 }.measure(loose)
        val barsPlaceable = measurables.first { it.layoutId == 2 }.measure(loose)
        insets.root = footerPlaceable.height + barsPlaceable.height
        insets.screen = barsPlaceable.height
        val stackPlaceable = measurables.first { it.layoutId == 1 }.measure(Constraints.fixed(width, height))
        layout(width, height) {
            footerPlaceable.placeWithLayer(0, height - footerPlaceable.height) { translationY = footerPlaceable.height * (1f - footerShown(nav)) }
            stackPlaceable.place(0, 0)
            barsPlaceable.placeWithLayer(0, height - barsPlaceable.height) { translationY = -footerPlaceable.height * footerShown(nav) }
        }
    }
}

private enum class Layer { Alone, Below, Top }

private const val ROOT_KEY = -1

/**
 * Các lớp màn: gốc + từng màn con; chỉ vẽ hai lớp trên cùng. Vị trí mỗi lớp chỉ là hàm của MỘT tiến trình ([NavState.progress]) qua [ScreenGeometry],
 * đọc trong graphicsLayer (pha vẽ). Lớp bên dưới đã khuất hẳn thì đẩy ra ngoài màn (không vẽ) nhưng vẫn giữ trong cây: Back không phải dựng lại nó.
 */
@Composable
fun ScreenStack(nav: NavState, root: @Composable () -> Unit, insets: LayerInsets? = null, screen: @Composable (Destination) -> Unit) {
    val entries = nav.stack.entries
    val count = entries.size
    val background = Abook.colors.bg
    Box(Modifier.fillMaxSize()) {
        for (index in max(ROOT_KEY, count - 2) until count) {
            val id = if (index < 0) ROOT_KEY else entries[index].key
            key(id) {
                val layer = when {
                    index == count - 1 && index >= 0 -> Layer.Top
                    index == count - 1 -> Layer.Alone
                    else -> Layer.Below
                }
                Box(
                    // Chừa chỗ cho thanh báo / chân ở đáy NGAY TRONG lớp (kích cỡ lớp cố định suốt chuyển cảnh): xem [LayerInsets].
                    (if (insets == null) Modifier.fillMaxSize() else Modifier.layerInset(insets, index < 0))
                        .graphicsLayer {
                            val fraction = when (layer) {
                                Layer.Alone -> 0f
                                Layer.Top -> ScreenGeometry.topFraction(nav.progress.value)
                                Layer.Below -> nav.progress.value.let { p -> if (p >= 1f) -1f else ScreenGeometry.belowFraction(p) }
                            }
                            translationX = fraction * size.width
                        }
                        .background(background)
                        // Lớp trên chặn chạm: không để chạm xuyên xuống lớp dưới đang trượt lộ ra.
                        .then(if (layer == Layer.Top) Modifier.pointerInput(Unit) {} else Modifier),
                ) {
                    if (index < 0) root() else screen(entries[index].destination)
                }
            }
        }
    }
}

@Composable
private fun RootTabs(
    shell: ShellState,
    library: LibraryState,
    player: PlayerState,
    repo: PlayerRepo,
    covers: CoverLoader,
    actions: LibraryActions,
    openNowPlaying: () -> Unit,
    settings: SettingsEnv,
    companion: vn.abook.player.ui.devices.CompanionRepo?,
    askNotifications: (() -> Unit) -> Unit,
) {
    val tabs = shell.tabs
    // Lambda đọc trạng thái (không phải giá trị): đổi tab / đẩy màn không làm RootTabs hay nội dung các tab dựng lại - chỉ chỗ gọi nó đọc, ở BackHandler của Thư viện.
    val backToLibrary = remember(shell) { { !shell.nav.canPop && shell.tabs.selected == Tab.Library.ordinal } }
    Column(Modifier.fillMaxSize()) {
        TabHost(tabs, Modifier.weight(1f)) { tab ->
            when (tab) {
                Tab.Library -> {
                    val night = settings.night
                    // Thẻ "Tối qua": đọc nhật ký đêm mỗi lần bạn quay về Thư viện (đêm mới kết thúc, hay vừa nghe tiếp thì thẻ biến mất).
                    LaunchedEffect(night) {
                        snapshotFlow { tabs.selected == Tab.Library.ordinal }.filter { it }.collect { night?.load() }
                    }
                    LibraryScreen(
                        library, shell.library, shell.libraryGrid, covers, shell.sheets, actions, backEnabled = backToLibrary,
                        recap = night?.let { n -> { books -> vn.abook.player.ui.screens.MorningRecap(n, books, repo::playChapter) } },
                    )
                }
                Tab.Studio -> StudioScreen(companion = companion, devices = settings.devices, askNotifications = askNotifications,
                    sheets = shell.sheets,
                    openNotificationSettings = settings.links.openNotificationSettings,
                    connect = { shell.nav.push(Destination.Devices(DevicesPage.Pair)) })
                Tab.Settings -> SettingsScreen(
                    settings,
                    onOpen = { group -> shell.nav.push(Destination.Settings(group)) },
                    shown = { tabs.selected == Tab.Settings.ordinal },
                )
            }
        }
    }
}

/** Persistent root footer: transient actions sit ABOVE playback and navigation, in normal layout flow. */
@Composable
private fun RootPlaybackArea(shell: ShellState, player: PlayerState, repo: PlayerRepo, covers: CoverLoader,
    openNowPlaying: () -> Unit, companion: vn.abook.player.ui.devices.CompanionRepo?) {
    val tabs = shell.tabs
    // Thanh phát nhỏ giữ bài cuối cùng khi thu về (không nháy nội dung rỗng giữa lúc thu lại).
    val last = remember { arrayOf(player) }
    if (player.hasTrack) last[0] = player
    val clock = repo.clock
    val position = remember(clock) { { clock.positionMs.value } }
    Column(Modifier.fillMaxWidth()) {
        if (companion != null) vn.abook.player.ui.devices.OtherPlayersEntry(companion, shell.sheets, repo)
        if (last[0].hasTrack) {
            MiniPlayerSlot(visible = player.hasTrack || shell.window.expanded) {
                MorphingMiniPlayer(last[0], position, covers, onToggle = repo::toggle, onOpenNowPlaying = openNowPlaying)
            }
        }
        TabBar(tabs)
    }
}

/**
 * Nội dung tab trượt ngang theo chỉ số: tab i ở `(i - position)` bề rộng. Tab đã từng hiện ở lại trong cây mãi (đổi tab không dựng lại, trạng thái cuộn
 * ở ShellState) và LUÔN được đặt (tab ngoài màn nằm ngoài vùng cắt, HWUI bỏ qua không vẽ): vị trí trượt chỉ đọc trong khối lớp (pha vẽ), nên đổi tab không
 * làm đổi dàn trang gì. Trước đây tab chỉ được đặt khi lộ ra - mỗi lần Thư viện "đặt lại" là một lượt dàn trang + vẽ lại cả cây của nó (trace trên OPPO:
 * measureAndLayout 2 ms + draw 3 ms đã AOT, 10-15 + 8-10 ms khi chưa AOT). Tab ngoài màn ẩn khỏi trợ năng (chỉ tab đang chọn được đọc).
 */
@Composable
fun TabHost(tabs: TabState, modifier: Modifier = Modifier, content: @Composable (Tab) -> Unit) {
    val mask = tabs.visitedMask
    Layout(
        content = {
            for (tab in Tab.entries) {
                if (mask and (1 shl tab.ordinal) != 0) {
                    key(tab) {
                        Box(
                            Modifier.layoutId(tab.ordinal).fillMaxSize().semantics { if (tabs.selected != tab.ordinal) hideFromAccessibility() },
                        ) { content(tab) }
                    }
                }
            }
        },
        modifier = modifier.clipToBounds(),
    ) { measurables, constraints ->
        val width = constraints.maxWidth
        val height = constraints.maxHeight
        val fixed = Constraints.fixed(width, height)
        // Đo và đặt MỌI tab đã dựng (cỡ cố định nên lần sau lấy lại kết quả cũ, gần như miễn phí).
        val placeables = measurables.map { it.measure(fixed) }
        layout(width, height) {
            for (i in measurables.indices) {
                val index = measurables[i].layoutId as Int
                placeables[i].placeWithLayer(0, 0) { translationX = (index - tabs.position.value) * width }
            }
        }
    }
}

/** Thanh tab đáy: chữ đổi màu theo khoảng cách tới vị trí trượt, vạch hổ phách trượt theo cùng giá trị ấy. */
@Composable
fun TabBar(tabs: TabState, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    // Vạch hổ phách nằm đáy hàng tab: chừa ít nhất 8 dp dưới nó kể cả khi máy báo inset đáy 0 (components/Insets.kt).
    val clearance = navigationClearance()
    Column(modifier.fillMaxWidth().background(colors.panel)) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(colors.line))
        Box(Modifier.fillMaxWidth().height(Dim.s48 + Dim.s8)) {
            Row(Modifier.fillMaxSize()) {
                for (tab in Tab.entries) TabItem(tab, tabs, Modifier.weight(1f))
            }
            Box(
                Modifier.fillMaxWidth(1f / Tab.entries.size).height(3.dp).align(Alignment.BottomStart)
                    .graphicsLayer { translationX = tabs.position.value * size.width },
                contentAlignment = Alignment.Center,
            ) {
                Box(Modifier.width(28.dp).height(3.dp).background(colors.accent).testTag("tab_indicator"))
            }
        }
        Box(Modifier.fillMaxWidth().height(clearance))
    }
}

@Composable
private fun TabItem(tab: Tab, tabs: TabState, modifier: Modifier) {
    val colors = Abook.colors
    Box(
        modifier.fillMaxSize()
            .pressable(Role.Tab) { tabs.select(tab) }
            .semantics { selected = tabs.selected == tab.ordinal }
            .testTag(tab.tag),
        contentAlignment = Alignment.Center,
    ) {
        BasicText(
            tab.label,
            style = Abook.type.tab,
            color = { lerp(colors.text2, colors.text, (1f - abs(tabs.position.value - tab.ordinal)).coerceIn(0f, 1f)) },
        )
    }
}
