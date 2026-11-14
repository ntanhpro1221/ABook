package vn.abook.player.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.unit.dp
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.components.*
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class LazyFoldTest {
    @get:Rule val rule = createComposeRule()

    @Test fun openingTwoHundredRowsOnlyBuildsTheViewportAndAnimationDoesNotRecomposeThem() {
        val built = mutableSetOf<Int>()
        var compositions = 0
        var measurements = 0
        rule.setContent {
            AbookTheme(false) {
                val folds = rememberLazyFoldState()
                LazyColumn(Modifier.size(360.dp)) {
                    foldItems(folds, "People", "people", (0 until 200).toList(), { it.toString() }) { index, _ ->
                        SideEffect { built += index; compositions++ }
                        Column(Modifier.height(64.dp).testTag("person_$index").layout { measurable, constraints ->
                            measurements++
                            val child = measurable.measure(constraints)
                            layout(child.width, child.height) { child.place(0, 0) }
                        }) { BasicText("Person $index") }
                    }
                }
            }
        }
        assertTrue(built.isEmpty())
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("people").performClick()
        rule.mainClock.advanceTimeByFrame()
        rule.waitForIdle()
        assertTrue("Only visible rows and prefetch may be built: ${built.size}", built.size in 1..12)
        val before = compositions
        val measured = measurements
        rule.mainClock.advanceTimeBy(100)
        rule.waitForIdle()
        assertEquals("Layer animation must not recompose row content", before, compositions)
        assertEquals("Layer animation must not remeasure row content", measured, measurements)
        rule.mainClock.advanceTimeBy(300)
        rule.onNodeWithTag("people").performClick()
        rule.mainClock.advanceTimeBy(300)
        rule.waitForIdle()
        rule.onNodeWithTag("person_0").assertDoesNotExist()
        assertTrue("Closing must not build the other 194 rows", built.size <= 12)
    }

    @Test fun rapidReversalKeepsRowsAndSavedGroupState() {
        val restoration = StateRestorationTester(rule)
        restoration.setContent {
            AbookTheme(false) {
                val folds = rememberLazyFoldState()
                LazyColumn(Modifier.size(360.dp)) {
                    foldItems(folds, "People", "people", (0 until 200).toList(), { it.toString() }) { _, item ->
                        BasicText("Person $item", Modifier.height(64.dp).testTag("person_$item"))
                    }
                }
            }
        }
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("people").performClick()
        rule.mainClock.advanceTimeBy(60)
        rule.onNodeWithTag("people").performClick()
        rule.mainClock.advanceTimeBy(30)
        rule.onNodeWithTag("people").performClick()
        rule.mainClock.advanceTimeBy(400)
        rule.waitForIdle()
        rule.onNodeWithTag("person_0").assertIsDisplayed()
        restoration.emulateSavedInstanceStateRestore()
        rule.mainClock.advanceTimeBy(400)
        rule.waitForIdle()
        rule.onNodeWithTag("person_0").assertIsDisplayed()
    }
}
