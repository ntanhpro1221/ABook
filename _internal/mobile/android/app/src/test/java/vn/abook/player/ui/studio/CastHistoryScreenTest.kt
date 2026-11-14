package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.*
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class CastHistoryScreenTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val id = "12345678123456781234567812345678"

    @Test fun twoTouchesOpenHistoryAndQueueTheExactOperation() {
        val sent = ArrayList<String>()
        rule.setContent { AbookTheme(false) { CastHistoryPanel(listOf(CastHistoryItem(id, "AN", "MAI", 2, 0, "applied")), null, "", true, { sent += it }) } }
        rule.onNodeWithTag("cast_history").performClick()
        rule.onNodeWithTag("cast_undo_$id").performClick()
        assertEquals(listOf(id), sent)
    }

    @Test fun conflictsRemainVisibleAndTheHistoryIsReadOnly() {
        rule.setContent { AbookTheme(false) { CastHistoryPanel(listOf(CastHistoryItem(id, "AN", "MAI", 2, 1, "undone")), null, "", false, {}) } }
        rule.onNodeWithTag("cast_history").performClick()
        rule.onNodeWithText("1 câu xung đột").assertIsDisplayed()
        rule.onNodeWithText("Đã hoàn tác").assertIsDisplayed()
        rule.onNodeWithTag("cast_undo_$id").assertDoesNotExist()
    }
}
