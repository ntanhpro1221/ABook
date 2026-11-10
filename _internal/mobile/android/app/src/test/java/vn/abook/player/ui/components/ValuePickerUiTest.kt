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

    @Test fun everyPickerAt100And130Percent() {
        val selected = mutableStateOf(ValueSpecs.speed)
        val scale = mutableStateOf(1f)
        val dense = mutableStateOf(false)
        val value = mutableStateOf(1.0)
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, scale.value)) {
                AbookTheme(false) {
                    Box(Modifier.width(360.dp).padding(horizontal = 24.dp)) {
                        ValuePicker(selected.value, value.value, { value.value = it }, { ValuePickerLogic.format(selected.value, it) }, "Number", "probe", dense = dense.value)
                    }
                }
            }
        }
        for (fontScale in listOf(1f, 1.3f)) for ((name, spec) in ValueSpecs.all) {
            rule.runOnIdle { selected.value = spec; scale.value = fontScale; dense.value = false; value.value = spec.min }
            rule.waitForIdle()
            val bounds = spec.typical.map { rule.onNodeWithTag("probe_chip_${ValuePickerLogic.format(spec, it)}").getUnclippedBoundsInRoot() }
            val rows = bounds.groupBy { it.top.value.toInt() }
            if (fontScale == 1f) assertEquals("$name at 360dp", 1, rows.size)
            assertTrue("$name at $fontScale: orphan", rows.values.none { it.size == 1 })
            rule.runOnIdle { dense.value = true }
            rule.waitForIdle()
            val ruler = rule.onNodeWithTag("probe_ruler").getUnclippedBoundsInRoot()
            for (typical in spec.typical) {
                val tag = "probe_chip_${ValuePickerLogic.format(spec, typical)}"
                val tick = rule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
                val expected = ruler.left.value + 8 + ValuePickerLogic.toFraction(spec, typical) * (ruler.right.value - ruler.left.value - 16)
                assertEquals("$name tick centre", expected, (tick.left.value + tick.right.value) / 2.0, 0.6)
                assertTrue("$name touch target", tick.right - tick.left >= 48.dp && tick.bottom - tick.top >= 48.dp)
                rule.onNodeWithTag(tag).performClick()
                rule.runOnIdle { assertEquals(typical, value.value, 0.0) }
            }
        }
    }
}
