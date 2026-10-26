package vn.abook.player.ui.shell

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.motion.ScreenGeometry
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.NavState
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.LibraryScreen
import vn.abook.player.ui.screens.SettingsScreen
import vn.abook.player.ui.screens.StudioScreen
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.nowplaying.NowPlayingHost
import vn.abook.player.ui.nowplaying.NowPlayingModel
import vn.abook.player.ui.nowplaying.PlayerCoverProvider
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max

/** Mọi trạng thái sống của khung (ngăn xếp, tab, vị trí cuộn từng tab) ở MỘT chỗ - tab rời khỏi cây vẫn giữ chỗ cuộn. */
@Stable
class ShellState(scope: CoroutineScope) {
    val nav = NavState(scope)
    val tabs = TabState(scope)
    val libraryGrid = LazyGridState()
}

/**
 * Khung app: ngăn xếp màn con (trượt phải / Back dự đoán) trên ba tab (trượt ngang). Gốc = [RootTabs].
 * `onFirstContent` gọi một lần khi Thư viện đã có nội dung (reportFullyDrawn).
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun AppShell(shell: ShellState, library: LibraryState, covers: CoverLoader, onFirstContent: () -> Unit = {}, nowPlaying: NowPlayingModel? = null) {
    val nav = shell.nav
    PredictiveBackHandler(enabled = nav.canPop) { events ->
        try {
            events.collect { nav.dragBack(it.progress) }
            nav.commitBack()
        } catch (cancelled: CancellationException) {
            nav.cancelBack()
            throw cancelled
        }
    }
    if (library is LibraryState.Ready) LaunchedEffect(Unit) { onFirstContent() }
    Box(Modifier.fillMaxSize().background(Abook.colors.bg).semantics { testTagsAsResourceId = true }) {
        val screens: @Composable () -> Unit = { ScreenStack(
            nav = nav,
            root = { RootTabs(shell, library, covers) },
            screen = { destination ->
                when (destination) {
                    is Destination.Book -> BookScreen(destination.book, covers, onBack = nav::pop)
                }
            },
        ) }
        if (nowPlaying != null) PlayerCoverProvider(covers) { NowPlayingHost(nowPlaying, content = screens) }
        else screens()
    }
}

private enum class Layer { Alone, Below, Top }

private const val ROOT_KEY = -1

/**
 * Các lớp màn: gốc + từng màn con; chỉ vẽ hai lớp trên cùng. Vị trí mỗi lớp chỉ là hàm của MỘT tiến trình ([NavState.progress]) qua [ScreenGeometry],
 * đọc trong graphicsLayer (pha vẽ). Lớp bên dưới đã khuất hẳn thì đẩy ra ngoài màn (không vẽ) nhưng vẫn giữ trong cây: Back không phải dựng lại nó.
 */
@Composable
fun ScreenStack(nav: NavState, root: @Composable () -> Unit, screen: @Composable (Destination) -> Unit) {
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
                    Modifier.fillMaxSize()
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
private fun RootTabs(shell: ShellState, library: LibraryState, covers: CoverLoader) {
    val tabs = shell.tabs
    Column(Modifier.fillMaxSize()) {
        TabHost(tabs, Modifier.weight(1f)) { tab ->
            when (tab) {
                Tab.Library -> LibraryScreen(
                    library, shell.libraryGrid, covers,
                    onOpen = { book -> shell.nav.push(Destination.Book(book)) },
                )
                Tab.Studio -> StudioScreen()
                Tab.Settings -> SettingsScreen()
            }
        }
        TabBar(tabs)
    }
}

/** Nội dung tab trượt ngang theo chỉ số: tab i ở `(i - position)` bề rộng. Chỉ dựng hai tab kề nhau đang lộ ra. */
@Composable
fun TabHost(tabs: TabState, modifier: Modifier = Modifier, content: @Composable (Tab) -> Unit) {
    val last = Tab.entries.size - 1
    val low by remember(tabs) { derivedStateOf { floor(tabs.position.value).toInt().coerceIn(0, last) } }
    val high by remember(tabs) { derivedStateOf { ceil(tabs.position.value).toInt().coerceIn(0, last) } }
    Box(modifier.clipToBounds()) {
        for (index in low..high) {
            key(index) {
                Box(Modifier.fillMaxSize().graphicsLayer { translationX = (index - tabs.position.value) * size.width }) {
                    content(Tab.entries[index])
                }
            }
        }
    }
}

/** Thanh tab đáy: chữ đổi màu theo khoảng cách tới vị trí trượt, vạch hổ phách trượt theo cùng giá trị ấy. */
@Composable
fun TabBar(tabs: TabState, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val navBar = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
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
                Box(Modifier.width(28.dp).height(3.dp).background(colors.accent))
            }
        }
        Box(Modifier.fillMaxWidth().height(navBar))
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
