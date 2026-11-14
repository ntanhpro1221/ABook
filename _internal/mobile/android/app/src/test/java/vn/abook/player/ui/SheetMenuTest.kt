package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.text.TextLayoutResult
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.*
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout
import vn.abook.player.ui.theme.AbookTheme
import org.json.JSONObject
import java.io.File

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h640dp-xhdpi", fontScale = 1.3f)
class SheetMenuTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun everyRowRetainsItsWholeLabelIncludingTheLastRowAndLateHints() {
        val menuSources = File("src/main/java/vn/abook/player/ui").walkTopDown()
            .filter { it.extension == "kt" }.map { it.readText() }.filter { it.contains("MenuRow(") }.toList()
        val keys = menuSources.flatMap { source ->
            Regex("MenuRow\\(\\s*([^,\\n]+)").findAll(source).flatMap { call ->
                Regex("S\\.(s_[A-Za-z0-9_]+)").findAll(call.groupValues[1]).map { it.groupValues[1] }
            }.toList()
        }.distinct()
        assertTrue("Audit must cover menu labels across the app", keys.size >= 20)
        val strings = JSONObject(File("../../../ui_strings/vi.json").readText()).getJSONObject("strings")
        val labels = keys.map { strings.getString(it).replace(Regex("\\{\\d+}"), "148 MB") } +
            List(16) { "Một việc có tên dài phải xuống dòng đầy đủ $it" }
        val hint = mutableStateOf<String?>(null)
        val host = SheetHost()
        rule.setContent {
            AbookTheme(false) { Box(Modifier.fillMaxSize()) { SheetLayer(host) } }
        }
        rule.runOnUiThread {
            host.show {
                SheetMenu {
                    for ((index, text) in labels.withIndex()) {
                        SwapContent(index, { it }, ContentLayout.Column) {
                            MenuRow(text, "probe_$it", hint = hint.value,
                                value = if (it % 2 == 0) "Một giá trị dài" else null) { TrashIcon(it) }
                        }
                    }
                }
            }
        }
        rule.waitForIdle()
        rule.runOnUiThread { hint.value = "Chiếm 148 MB" }
        for (index in labels.indices) {
            rule.onNodeWithTag("probe_$index").performScrollTo().assertIsDisplayed()
            val label = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag("probe_$index")), useUnmergedTree = true)
            label.assertIsDisplayed()
            val results = mutableListOf<TextLayoutResult>()
            label.fetchSemanticsNode().config[SemanticsActions.GetTextLayoutResult].action!!(results)
            val layout = results.single()
            assertTrue(layout.layoutInput.text.text.isNotBlank())
            assertTrue("Label lost its width", layout.size.width > 0)
            // Use glyph bounds, as assertNoTextOverflow does. Paragraph width may round
            // down by a fraction of one pixel at a fractional system font scale.
            val widest = (0 until layout.lineCount).maxOf { layout.getLineRight(it) }
            assertTrue("Row $index clipped '${labels[index]}': ${layout.size}, ink=$widest x ${layout.multiParagraph.height}",
                widest <= layout.size.width + 1f && layout.multiParagraph.height <= layout.size.height + 1f)
            assertEquals(layout.layoutInput.text.length, layout.getLineEnd(layout.lineCount - 1))
        }
    }
}
