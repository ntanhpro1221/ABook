package vn.abook.player.ui.components

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ValuePickerUiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun countUsesTheSameValueFieldAndEightDpLabelGap() {
        val value = mutableStateOf(3.0)
        rule.setContent { AbookTheme(false) {
            Box(Modifier.width(360.dp).padding(horizontal = 24.dp)) {
                ValuePicker(ValueSpecs.sleepChapters, value.value, { value.value = it }, { it.toInt().toString() }, "Count", "count", stepperOnly = true)
            }
        } }
        rule.waitForIdle()
        val label = rule.onNodeWithTag("count_section_label").getUnclippedBoundsInRoot()
        val field = rule.onNodeWithTag("count_value").getUnclippedBoundsInRoot()
        assertEquals(8f, (field.top - label.bottom).value, 0.1f)
        assertTrue(field.bottom - field.top >= 48.dp)
        rule.onNodeWithTag("count_up").performClick()
        rule.runOnIdle { assertEquals(4.0, value.value, 0.0) }
        rule.onNodeWithTag("count_down").performClick()
        rule.runOnIdle { assertEquals(3.0, value.value, 0.0) }
    }

    @Test fun everyPickerAt100And130Percent() {
        var expectedText = androidx.compose.ui.graphics.Color.Unspecified
        val selected = mutableStateOf(ValueSpecs.speed)
        val scale = mutableStateOf(1f)
        val dense = mutableStateOf(false)
        val value = mutableStateOf(1.0)
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, scale.value)) {
                AbookTheme(false) {
                    expectedText = vn.abook.player.ui.theme.Abook.colors.text
                    Box(Modifier.width(360.dp).padding(horizontal = 24.dp)) {
                        ValuePicker(selected.value, value.value, { value.value = it }, { ValuePickerLogic.format(selected.value, it) }, "Number", "probe", dense = dense.value)
                    }
                }
            }
        }
        for (fontScale in listOf(1f, 1.3f)) for ((name, spec) in ValueSpecs.all) for (compact in listOf(false, true)) {
            rule.runOnIdle { selected.value = spec; scale.value = fontScale; dense.value = compact; value.value = spec.min }
            rule.waitForIdle()
            val ruler = rule.onNodeWithTag("probe_ruler").fetchSemanticsNode().boundsInRoot
            val ticks = spec.typical.indices.mapNotNull { i ->
                rule.onAllNodesWithTag("probe_tick_$i", useUnmergedTree = true).fetchSemanticsNodes().singleOrNull()?.boundsInRoot
            }
            val labels = spec.typical.indices.map { i -> rule.onNodeWithTag("probe_label_$i", useUnmergedTree = true).fetchSemanticsNode().boundsInRoot }
            val fallback = rule.onAllNodesWithTag("probe_chips", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()
            assertEquals("$name detent count", if (fallback) 0 else labels.size, ticks.size)
            fun check(captions: List<androidx.compose.ui.geometry.Rect>) {
                assertTrue("$name: count", ticks.isEmpty() || ticks.size == captions.size)
                captions.forEachIndexed { i, label ->
                    assertTrue("$name label under a step button", label.left >= ruler.left - 1 && label.right <= ruler.right + 1)
                    if (ticks.isNotEmpty()) assertEquals("$name $fontScale dense=$compact caption $i", ticks[i].center.x.toDouble(), label.center.x.toDouble(), 2.0)
                }
            }
            check(labels)
            // Prove the same rendered-layout check rejects the original spread-across-buttons regression.
            if (ticks.isNotEmpty()) {
                val broken = labels.mapIndexed { i, r -> if (i == 0) r.translate(9f, 0f) else r }
                assertThrows(AssertionError::class.java) { check(broken) }
                val missing = labels.dropLast(1)
                assertThrows(AssertionError::class.java) { check(missing) }
            }
            val bounds = spec.typical.map { rule.onNodeWithTag("probe_chip_${ValuePickerLogic.format(spec, it)}").getUnclippedBoundsInRoot() }
            val rows = bounds.groupBy { it.top.value.toInt() }
            assertTrue("$name at $fontScale: orphan", rows.values.none { it.size == 1 })
            for (typical in spec.typical) {
                val tag = "probe_chip_${ValuePickerLogic.format(spec, typical)}"
                val chip = rule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
                assertTrue("$name touch target", chip.right - chip.left >= 48.dp && chip.bottom - chip.top >= 48.dp)
                rule.onNodeWithTag(tag).performClick()
                rule.runOnIdle { assertEquals(typical, value.value, 0.0) }
                rule.mainClock.advanceTimeBy(1000)
                val index = spec.typical.indexOf(typical)
                val layouts = mutableListOf<androidx.compose.ui.text.TextLayoutResult>()
                rule.onNodeWithTag("probe_label_$index", useUnmergedTree = true)
                    .performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.GetTextLayoutResult) { it(layouts) }
                val style = layouts.single().layoutInput.style
                assertEquals("$name selected text", expectedText, style.color)
                assertEquals("$name selected weight", androidx.compose.ui.text.font.FontWeight.Bold, style.fontWeight)
            }
        }
    }
}
