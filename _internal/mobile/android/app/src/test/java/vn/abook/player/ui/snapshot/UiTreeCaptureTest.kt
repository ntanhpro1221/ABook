package vn.abook.player.ui.snapshot

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicText
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class UiTreeCaptureTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun preservesUnmergedTextLayoutInsideAButton() {
        rule.setContent {
            Box(Modifier.size(100.dp, 48.dp).semantics(mergeDescendants = true) {
                role = Role.Button
                onClick { true }
            }) {
                BasicText("Play", style = TextStyle(fontSize = 16.sp, color = Color(0xff1a1814)))
            }
        }
        rule.waitForIdle()
        val json = UiTree.describe(rule.onRoot().fetchSemanticsNode(), "test.png")
        assertFalse(json.getBoolean("merged"))
        val nodes = json.getJSONArray("nodes")
        val all = (0 until nodes.length()).map { nodes.getJSONObject(it) }
        val text = all.first { it.optString("text") == "Play" && it.has("font_size") }
        assertEquals(16.0, text.getDouble("font_size"), 0.01)
        assertEquals(1, text.getInt("line_count"))
        assertEquals(1, text.getJSONArray("lines").length())
        assertTrue(all.any { it.optString("role") == "button" })
        assertEquals(100.0, json.getDouble("width"), 1.0)
        assertEquals(48.0, json.getDouble("height"), 1.0)
    }
}
