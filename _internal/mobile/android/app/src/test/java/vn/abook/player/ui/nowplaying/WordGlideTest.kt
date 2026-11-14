package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.createAndroidComposeRule

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class WordGlideTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun punctuationOnlyChangesDrawingRanges() {
        for ((text, core) in listOf("văn," to "văn", "“Nghĩ" to "Nghĩ", "chuyện." to "chuyện",
            "...!?" to "", "«(nhẹ-nhàng)—" to "nhẹ-nhàng")) {
            val range = WordInk.range(text, 0, text.length)
            assertEquals(core, text.substring(range.first, range.last + 1))
        }
        assertEquals(40, WordInk.duration(120, 3.0))
        assertEquals(120, WordInk.duration(500, 1.0))
    }

    @Test fun animationMovesInkToExactBoundsWithoutComposingItsTextEachFrame() {
        val glide = WordGlide()
        lateinit var scope: CoroutineScope
        var compositions = 0
        rule.mainClock.autoAdvance = false
        rule.setContent {
            scope = rememberCoroutineScope()
            SideEffect { compositions++ }
            Box(Modifier.size(240.dp).drawBehind {
                if (glide.visible) drawRect(Color.Yellow, glide.rect.value.topLeft, glide.rect.value.size)
            })
        }
        val first = Rect(10f, 20f, 45f, 50f)
        val target = Rect(55f, 20f, 130f, 50f)
        rule.runOnUiThread { scope.launch { glide.move(first, 0, false) } }
        rule.mainClock.advanceTimeByFrame()
        val composed = compositions
        rule.runOnUiThread { scope.launch { glide.move(target, 120, true) } }
        rule.mainClock.advanceTimeBy(48)
        rule.runOnUiThread {
            assertTrue(glide.rect.value.left > first.left)
            assertTrue(glide.rect.value.left < target.left)
        }
        rule.mainClock.advanceTimeBy(160)
        rule.runOnUiThread { assertEquals(target, glide.rect.value) }
        assertEquals(composed, compositions)
        // Robolectric renders no frames while the clock is paused; the ink state itself is the contract.
        assertTrue(glide.visible)
    }
}
