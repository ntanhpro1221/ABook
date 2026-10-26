package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.nowplaying.*
import vn.abook.player.ui.screens.*
import vn.abook.player.ui.shell.*
import vn.abook.player.ui.theme.*

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class GapSurfacesTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private fun shot(name: String) {
        // Drain the sheet and lazy-row geometry before recording the final surface.
        rule.mainClock.advanceTimeBy(400)
        rule.waitForIdle()
        rule.assertIconLedTextColumns()
        rule.onRoot().captureRoboImage("src/test/snapshots/gap1_$name.png")
    }
    private val core = FakeCompanionCore()
    private val companion = CompanionRepo(core) { 1_000 }
    private val book = ListenBook("b1", "Dế Mèn phiêu lưu ký", "Tô Hoài", chaptersAvailable = 2, chaptersTotal = 2)
    private fun theme(dark: Boolean, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(dark) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
    }

    @Test fun studioNoticesLight() = notices(false)
    @Test fun studioNoticesDark() = notices(true)
    private fun notices(dark: Boolean) {
        core.noticeState = StudioNoticeState(true, false)
        runBlocking { companion.refresh() }
        var opened = 0
        theme(dark) { StudioScreen(companion = companion, openNotificationSettings = { opened++ }) }
        rule.onNodeWithText("Báo từ Studio").assertIsDisplayed()
        rule.onNodeWithText("Android đang chặn thông báo của ABook.").assertIsDisplayed()
        rule.onNodeWithTag("studio_notification_settings").performClick()
        assertEquals(1, opened)
        shot("studio_${if (dark) "dark" else "light"}")
        rule.onNodeWithTag("studio_alerts").performClick()
        rule.waitForIdle()
        assertFalse(core.noticeState.enabled)
        rule.onNodeWithText("Android đang chặn thông báo của ABook.").assertDoesNotExist()
    }

    @Test fun remotePlayersLight() = remote(false)
    @Test fun remotePlayersDark() = remote(true)
    private fun remote(dark: Boolean) {
        runBlocking { companion.refresh() }
        val playback = FakePlaybackCore(playerSnapshot(book = "", chapter = null))
        val local = PlayerRepo(playback, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null })
        val host = SheetHost()
        theme(dark) {
            LaunchedEffect(Unit) { host.show { dismiss -> OtherPlayersSheet(companion, local, dismiss) } }
            SheetLayer(host)
        }
        rule.onNodeWithText("Máy tính phòng khách").assertIsDisplayed()
        rule.onNodeWithText("Chương 1 · Ngày trở về").assertIsDisplayed()
        assertRemoteTransport("main")
        rule.onNodeWithTag("remote_toggle_main").performClick()
        rule.waitForIdle()
        assertEquals("toggle", core.commands.last().second.getString("action"))
        for ((tag, description) in listOf("back" to "Lùi 15 giây", "toggle" to "Tạm dừng", "forward" to "Tới 15 giây")) {
            val node = rule.onNodeWithTag("remote_${tag}_main")
            node.assertContentDescriptionEquals("$description trên Máy tính phòng khách")
            val bounds = node.getUnclippedBoundsInRoot()
            assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        }
        rule.onNodeWithTag("remote_back_main").performClick()
        rule.waitForIdle()
        assertEquals(-15.0, core.commands.last().second.getDouble("seconds"), 0.0)
        rule.onNodeWithTag("remote_forward_main").performClick()
        rule.waitForIdle()
        assertEquals(15.0, core.commands.last().second.getDouble("seconds"), 0.0)
        assertTrue("Tìm lại must remain fully inside the screen",
            rule.onNodeWithTag("remote_retry").getUnclippedBoundsInRoot().bottom <= rule.onRoot().getUnclippedBoundsInRoot().bottom)
        shot("remote_players_${if (dark) "dark" else "light"}")
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithTag("remote_players_sheet").assertDoesNotExist()
    }

    @Test fun remoteSleepLight() = sleep(false)
    @Test fun remoteSleepDark() = sleep(true)
    @Test @Config(qualifiers = "w411dp-h780dp-xxhdpi") fun remoteSleep411() = sleep(false, suffix = "411_light")
    @Test fun remoteSleep360LargeText() = sleep(false, fontScale = 1.3f, suffix = "360_font130_light")
    @Test @Config(qualifiers = "w411dp-h780dp-xxhdpi") fun remoteSleep411LargeText() = sleep(false, fontScale = 1.3f, suffix = "411_font130_light")
    private fun sleep(dark: Boolean, fontScale: Float = 1f, suffix: String = if (dark) "dark" else "light") {
        core.rows.getJSONObject(0).put("via", "cast")
        runBlocking { companion.refresh() }
        val local = PlayerRepo(FakePlaybackCore(playerSnapshot(book = "", chapter = null)), CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null })
        val host = SheetHost()
        theme(dark) {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale)) {
            LaunchedEffect(Unit) { host.show { dismiss -> OtherPlayersSheet(companion, local, dismiss) } }
            SheetLayer(host)
            }
        }
        rule.onNodeWithTag("remote_sleep_main").performClick()
        rule.onNodeWithText("30 phút").assertIsDisplayed()
        rule.onNodeWithTag("remote_main", useUnmergedTree = true).assertIconLedTextColumn()
        assertRemoteTransport("main")
        // It is a scrollable list, not a compressed grid: scroll the final option into view.
        rule.onNodeWithTag("remote_players_list").performScrollToNode(hasTestTag("remote_sleep_chapter"))
        val left = rule.onNodeWithTag("remote_sleep_main").getUnclippedBoundsInRoot().left
        for (tag in listOf("remote_sleep_main_15", "remote_sleep_main_30", "remote_sleep_main_45", "remote_sleep_main_60", "remote_sleep_off", "remote_sleep_chapter")) {
            rule.onNodeWithTag(tag).assertIsDisplayed()
            assertEquals(left, rule.onNodeWithTag(tag).getUnclippedBoundsInRoot().left)
        }
        shot("remote_sleep_$suffix")
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithText("30 phút").assertDoesNotExist()
        rule.onNodeWithTag("remote_players_sheet").assertIsDisplayed()
    }

    private fun assertRemoteTransport(device: String) {
        val row = rule.onNodeWithTag("remote_transport_$device").getUnclippedBoundsInRoot()
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag("remote_$device")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val back = rule.onNodeWithTag("remote_back_$device").getUnclippedBoundsInRoot()
        val play = rule.onNodeWithTag("remote_toggle_$device").getUnclippedBoundsInRoot()
        val forward = rule.onNodeWithTag("remote_forward_$device").getUnclippedBoundsInRoot()
        assertEquals(title.left, row.left)
        assertEquals(rule.onNodeWithTag("remote_$device", useUnmergedTree = true).getUnclippedBoundsInRoot().right, row.right)
        assertEquals(((row.left + row.right) / 2).value, ((play.left + play.right) / 2).value, 0.5f)
        assertEquals(((row.left + row.right) / 2).value, ((back.left + forward.right) / 2).value, 0.5f)
        assertTrue(back.left >= row.left && forward.right <= row.right)
        assertEquals((back.top + back.bottom) / 2, (play.top + play.bottom) / 2)
        assertEquals((play.top + play.bottom) / 2, (forward.top + forward.bottom) / 2)
    }

    @Test fun remoteLibraryLight() = remoteBook(false)
    @Test fun remoteLibraryDark() = remoteBook(true)
    @Test fun libraryRemoteMarkLight() = libraryRemote(false)
    @Test fun libraryRemoteMarkDark() = libraryRemote(true)
    private fun libraryRemote(dark: Boolean) {
        val remoteBook = ListenBook("r1", "Những ngày gió hát", "Một người viết", chaptersAvailable = 2, chaptersTotal = 2, remote = RemoteRef("máy tính"))
        val source = FakeDevicesSource()
        val devices = DevicesState(source, CoroutineScope(Dispatchers.Unconfined), DeviceLinks(), {})
        val playback = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        theme(dark) {
            val scope = rememberCoroutineScope()
            val shell = remember { ShellState(scope) }
            val player = remember { PlayerRepo(playback, scope, Dispatchers.Unconfined, { null }, {
                LoadRequest(it, remoteBook.title, "", emptyList(), 1, 0.0, 1.0)
            }) }
            LaunchedEffect(Unit) { player.attach() }
            val settings = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined), ThemeReveal(scope), devices = devices) }
            AppShell(shell, LibraryState.Ready(listOf(book, remoteBook)), player, CoverLoader(), settings, sampleClock = false)
        }
        rule.onNodeWithText("Trên máy tính").assertIsDisplayed()
        shot("library_remote_${if (dark) "dark" else "light"}")
        rule.onAllNodesWithTag("book_cell")[1].performClick()
        rule.onNodeWithTag("remote_book_sheet").assertIsDisplayed()
        rule.onNodeWithTag("remote_book_stream").performClick()
        rule.waitForIdle()
        assertEquals("r1", playback.loads.single().id)
    }
    private fun remoteBook(dark: Boolean) {
        val source = FakeDevicesSource()
        val devices = DevicesState(source, CoroutineScope(Dispatchers.Unconfined), DeviceLinks(), {})
        val remoteBook = ListenBook("b1", book.title, book.author, chaptersAvailable = 2, chaptersTotal = 2, remote = RemoteRef("máy tính"))
        val host = SheetHost()
        var played = 0
        theme(dark) {
            LaunchedEffect(Unit) { host.show { RemoteBookSheet(remoteBook, devices) { played++ } } }
            SheetLayer(host)
        }
        rule.onNodeWithText("Trên máy tính").assertIsDisplayed()
        rule.onNodeWithTag("remote_book_stream").performClick()
        assertEquals(1, played)
        shot("remote_book_${if (dark) "dark" else "light"}")
        rule.onNodeWithTag("remote_book_download").performClick()
        rule.waitForIdle()
        assertEquals(listOf("b1"), source.downloads)
        rule.onNodeWithTag("remote_book_download").performClick()
        assertEquals(listOf("b1"), source.cancels)
    }

    @Test fun undoRestoresTheRowInPlaceLight() = undo(false)
    @Test fun undoRestoresTheRowInPlaceDark() = undo(true)
    private fun undo(dark: Boolean) {
        val all = listOf(book, ListenBook("b2", "Tắt đèn", "Ngô Tất Tố"))
        var library by mutableStateOf<LibraryState>(LibraryState.Ready(all))
        lateinit var deletes: UndoDelete
        lateinit var scope: CoroutineScope
        val erased = mutableListOf<String>()
        theme(dark) {
            scope = rememberCoroutineScope()
            deletes = remember { UndoDelete(scope, { erased += it; null }, { library = LibraryState.Ready(all.filterNot { deletes.contains(it.id) }) }) }
            val shell = remember { ShellState(scope) }
            val player = remember { PlayerRepo(FakePlaybackCore(playerSnapshot(book = "b2", playing = true)), scope, Dispatchers.Unconfined, { null }, { null }) }
            LaunchedEffect(Unit) { player.attach() }
            val settings = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined), ThemeReveal(scope)) }
            AppShell(shell, library, player, CoverLoader(), settings, sampleClock = false, deletions = deletes)
        }
        val before = rule.onNodeWithText(book.title).getUnclippedBoundsInRoot()
        val fullHeight = rule.onNodeWithText(book.title).fetchSemanticsNode().boundsInRoot.height
        rule.runOnUiThread { scope.launch { deletes.remove("b1") } }
        rule.waitForIdle()
        rule.onNodeWithText(book.title).assertDoesNotExist()
        rule.onNodeWithTag("undo_delete").assertIsDisplayed()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        rule.onNodeWithTag("tab_library").assertIsDisplayed()
        shot("undo_${if (dark) "dark" else "light"}")
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("undo_delete").performClick()
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(64)
        // The restored row has entered but its height is still opening.
        assertTrue(rule.onNodeWithText(book.title).fetchSemanticsNode().boundsInRoot.height < fullHeight ||
            rule.onNodeWithText(book.title).getUnclippedBoundsInRoot().top != before.top)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        assertEquals(before, rule.onNodeWithText(book.title).getUnclippedBoundsInRoot())
        assertTrue(erased.isEmpty())
    }

    @Test fun deletedPlayingBookClosesTheWindowAndTheMiniPlayer() {
        var library by mutableStateOf<LibraryState>(LibraryState.Ready(listOf(book)))
        val playback = FakePlaybackCore(playerSnapshot(playing = true), simulate = true)
        lateinit var player: PlayerRepo
        lateinit var shell: ShellState
        theme(false) {
            val scope = rememberCoroutineScope()
            shell = remember { ShellState(scope) }
            player = remember { PlayerRepo(playback, scope, Dispatchers.Unconfined, { null }, { null }) }
            LaunchedEffect(Unit) { player.attach() }
            val settings = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined), ThemeReveal(scope)) }
            AppShell(shell, library, player, CoverLoader(), settings, sampleClock = false)
        }
        rule.onNodeWithTag("mini_player").performClick()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        rule.runOnUiThread { library = LibraryState.Ready(emptyList()) }
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
        rule.onNodeWithTag("mini_player").assertDoesNotExist()
        assertEquals(listOf("close"), playback.calls)
        assertFalse(player.state.value.playing)
    }

    @Test fun storageDeleteUsesTheSameUndoAndRestoresItsRowAtTheSamePlace() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        lateinit var devices: DevicesState
        val erased = mutableListOf<String>()
        val deletes = UndoDelete(scope, { erased += it; null }, { devices.openStorage() })
        val stored = listOf(Stored("b1", book.title, 1_024, false), Stored("b2", "Tắt đèn", 512, false))
        val source = object : DevicesSource by FakeDevicesSource() {
            override suspend fun storage() = Storage(entries = stored.filterNot { deletes.contains(it.id) })
            override suspend fun delete(id: String): String? { deletes.remove(id); return null }
        }
        devices = DevicesState(source, scope, DeviceLinks(), {})
        val host = SheetHost()
        theme(false) {
            Column {
                Box(Modifier.weight(1f)) { StorageScreen(devices, host, {}) }
                UndoBar(deletes)
            }
            SheetLayer(host)
        }
        val before = rule.onNodeWithTag("stored_b1").getUnclippedBoundsInRoot()
        rule.onNodeWithTag("stored_b1").performClick()
        rule.onNodeWithTag("delete_yes").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("stored_b1").assertDoesNotExist()
        rule.onNodeWithTag("undo_delete").performClick()
        rule.waitForIdle()
        assertEquals(before, rule.onNodeWithTag("stored_b1").getUnclippedBoundsInRoot())
        assertTrue(erased.isEmpty())
        scope.cancel()
    }

    @Test fun remoteSheetFromThePlayerJoinsBackAboveThePlayer() {
        runBlocking { companion.refresh() }
        val playback = FakePlaybackCore(playerSnapshot(playing = true), simulate = true)
        lateinit var shell: ShellState
        theme(false) {
            val scope = rememberCoroutineScope()
            shell = remember { ShellState(scope) }
            val player = remember { PlayerRepo(playback, scope, Dispatchers.Unconfined, { null }, { null }) }
            LaunchedEffect(Unit) { player.attach() }
            val settings = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined), ThemeReveal(scope)) }
            AppShell(shell, LibraryState.Ready(listOf(book)), player, CoverLoader(), settings, sampleClock = false, companion = companion)
        }
        rule.onNodeWithTag("mini_player").performClick()
        rule.runOnUiThread { shell.window.openSheet(PlayerSheet.More) }
        rule.onNode(hasText("Thiết bị phát") and hasAnyAncestor(hasTestTag("player_sheet_more"))).performClick()
        rule.onNodeWithTag("remote_players_sheet").assertIsDisplayed()
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithTag("remote_players_sheet").assertDoesNotExist()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        assertTrue(shell.window.expanded)
    }
}
