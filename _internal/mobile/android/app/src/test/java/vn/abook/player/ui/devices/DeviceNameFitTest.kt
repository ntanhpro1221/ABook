package vn.abook.player.ui.devices

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.width
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.S
import vn.abook.player.ui.FakeCompanionCore
import vn.abook.player.ui.assertNoTextOverflow
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.data.FakePlaybackCore
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
class DeviceNameFitTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val name = "Điện thoại OPPO Find X8 Ultra của Nguyễn Văn An"

    @Test
    fun discoveredPairedAndSharingNamesWrapAtFullSizeWhenNarrow() {
        rule.setContent {
            AbookTheme(false) {
                Column(Modifier.width(180.dp)) {
                    FoundRow(Found("example.invalid", name, DeviceKind.Phone), false) {}
                    DeviceRow(Paired("example", name, DeviceKind.Phone), {}, {})
                    SharerRow(Sharer("example", name, 0.0)) {}
                }
            }
        }
        val nodes = rule.onAllNodesWithText(name, useUnmergedTree = true)
        nodes.assertCountEquals(3)
        for (index in 0..2) {
            val layout = layout(nodes[index])
            assertEquals(name, layout.layoutInput.text.text)
            assertTrue("the complete name must wrap", layout.lineCount > 1)
            assertEquals("fallback returns to body size", 16f, layout.layoutInput.style.fontSize.value, 0.01f)
            assertFalse(layout.isLineEllipsized(layout.lineCount - 1))
        }
        rule.assertNoTextOverflow()
    }

    @Test
    fun playbackStripGrowsAndItsSheetKeepsTheCompleteName() {
        val core = FakeCompanionCore()
        core.rows.getJSONObject(0).put("name", name)
        val repo = CompanionRepo(core)
        runBlocking { repo.refresh() }
        val local = PlayerRepo(FakePlaybackCore(playerSnapshot(book = "", chapter = null)), CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null })
        val sheets = SheetHost()
        rule.setContent {
            AbookTheme(false) {
                Column(Modifier.width(180.dp)) { OtherPlayersEntry(repo, sheets, local) }
                SheetLayer(sheets)
            }
        }
        val line = rule.onNodeWithText(S.s_dang_phat_tren_0_62a989a1(name), useUnmergedTree = true)
        val stripLayout = layout(line)
        assertTrue(stripLayout.lineCount > 1)
        assertEquals(12f, stripLayout.layoutInput.style.fontSize.value, 0.01f)
        assertFalse(stripLayout.isLineEllipsized(stripLayout.lineCount - 1))
        rule.assertNoTextOverflow()
        rule.onNodeWithTag("other_players").performClick()
        rule.onNodeWithText(name, useUnmergedTree = true).assertIsDisplayed()
        val sheetLayout = layout(rule.onNodeWithText(name, useUnmergedTree = true))
        assertEquals(name, sheetLayout.layoutInput.text.text)
        assertFalse(sheetLayout.isLineEllipsized(sheetLayout.lineCount - 1))
        rule.assertNoTextOverflow()
    }

    private fun layout(node: SemanticsNodeInteraction): TextLayoutResult {
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { assertTrue(it(layouts)) }
        return layouts.single()
    }
}
