package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
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
import vn.abook.player.ui.addbook.*
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.screens.*
import vn.abook.player.ui.theme.*

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class Gap3UiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private fun show(dark: Boolean, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(dark) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
        rule.waitForIdle()
    }
    private fun shot(name: String) {
        rule.mainClock.advanceTimeBy(400); rule.waitForIdle()
        rule.assertIconLedTextColumns()
        rule.onRoot().captureRoboImage("build/shots/gap3_$name.png")
    }
    @Test fun maintenanceLight() = maintenance(false)
    @Test fun maintenanceDark() = maintenance(true)
    private fun maintenance(dark: Boolean) {
        val file = OldSave("Dế Mèn phiêu lưu ký 20261029-123456.abook", 5000000, 0)
        var files = listOf(file)
        var deletes = 0
        val core = object : SettingsCore by FakeSettingsCore() {
            override fun oldSaves() = files
            override fun deleteOldSave(name: String) { deletes++; files = emptyList() }
            override fun release() = AppRelease("0.4.150", "page", "apk")
        }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val repo = SettingsRepo(core, scope, Dispatchers.Unconfined)
        val sheets = SheetHost()
        var exported = ""
        var downloaded = ""
        try {
            show(dark) {
                val theme = ThemeReveal(rememberCoroutineScope())
                Column(Modifier.fillMaxSize().padding(Dim.margin)) {
                    MaintenanceSections(SettingsEnv(repo, theme, SettingsLinks(saveOld = { name, _ -> exported = name }, openRelease = { downloaded = it })), sheets)
                }
                SheetLayer(sheets)
            }
            rule.onNodeWithText("Bản lưu cũ (1)").assertIsDisplayed()
            rule.onNodeWithText("Có bản mới 0.4.150").assertIsDisplayed()
            shot("maintenance_${if (dark) "dark" else "light"}")
            rule.onNodeWithTag("old_export_${file.name}").performClick(); assertEquals(file.name, exported)
            rule.onNodeWithTag("update_download").performClick(); assertEquals("apk", downloaded)
            rule.onNodeWithTag("old_delete_${file.name}").performClick(); rule.waitForIdle()
            assertEquals(0, deletes)
            shot("recovery_confirm_${if (dark) "dark" else "light"}")
            rule.onNodeWithTag("old_delete_keep").performClick(); rule.waitForIdle(); assertEquals(0, deletes)
            rule.onNodeWithTag("old_delete_${file.name}").performClick(); rule.waitForIdle()
            rule.onNodeWithTag("old_delete_yes").performClick(); rule.waitForIdle(); assertEquals(1, deletes)
        } finally { scope.cancel() }
    }
    @Test fun packageLight() = packageReview(false)
    @Test fun packageDark() = packageReview(true)
    private fun packageReview(dark: Boolean) {
        var kept = 0; var replaced = 0
        val state = ImportState(packageReview = PackageReview("b", "Một cuốn sách có tên rất dài để kiểm tra xuống dòng", "Tên trong bản thu cũ", "older"))
        show(dark) { PackageReviewScreen(state, {}, { kept++ }, { replaced++ }) }
        rule.onNodeWithText("Chỉnh sửa và chỗ nghe của bạn vẫn được giữ.").assertIsDisplayed()
        shot("package_${if (dark) "dark" else "light"}")
        assertEquals(0, replaced)
        rule.onNodeWithTag("package_keep").performClick(); assertEquals(1, kept)
        rule.onNodeWithTag("package_replace").performClick(); assertEquals(1, replaced)
    }
    @Test fun bluetoothLight() = bluetooth(false)
    @Test fun bluetoothDark() = bluetooth(true)
    @Test
    @Config(sdk = [35], qualifiers = "w411dp-h900dp-420dpi")
    fun connectionMethodsKeepTheirGapAtTheEmulatorsWidth() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val devices = DevicesState(FakeDevicesSource(), scope)
        val sheets = SheetHost()
        try {
            show(false) { PairScreen(devices, sheets) {}; SheetLayer(sheets) }
            fun checkGap() {
                val bounds = PairMethod.entries.map { rule.onNodeWithText(it.label, useUnmergedTree = true).getUnclippedBoundsInRoot() }
                for ((first, second) in bounds.zipWithNext()) {
                    if (kotlin.math.abs(first.top.value-second.top.value) < 1f)
                        assertTrue("Adjacent labels need their 24 dp gap: $bounds", second.left-first.right >= 23.5.dp)
                    else assertTrue("Wrapped labels must occupy a new line: $bounds", second.top >= first.bottom)
                }
            }
            checkGap()
            rule.onNodeWithTag("pair_method_bluetooth").performClick(); rule.waitForIdle()
            checkGap()
            shot("connection_methods_411")
        } finally { scope.cancel() }
    }
    private fun bluetooth(dark: Boolean) {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val source = FakeDevicesSource().also { it.nearby = false }
        var requested = 0
        val devices = DevicesState(source, scope, DeviceLinks(askNearby = { requested++; it(false) }))
        val sheets = SheetHost()
        try {
            show(dark) { PairScreen(devices, sheets) {}; SheetLayer(sheets) }
            rule.onNodeWithTag("pair_method_bluetooth").performClick(); rule.waitForIdle()
            assertEquals(0, requested)
            rule.onNodeWithTag("bluetooth_allow").assertIsDisplayed()
            shot("bluetooth_${if (dark) "dark" else "light"}")
            rule.onNodeWithTag("bluetooth_allow").performClick(); rule.waitForIdle()
            assertEquals(1, requested)
            rule.onNodeWithTag("pair_denied").assertIsDisplayed()
        } finally { scope.cancel() }
    }
}
