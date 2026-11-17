package vn.abook.player.ui

import android.graphics.BitmapFactory
import android.graphics.Color
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.RoborazziTaskType
import java.io.File
import kotlin.math.abs
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.Work
import vn.abook.player.WorkStep
import vn.abook.player.ui.addbook.AddBookScreen
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportStage
import vn.abook.player.ui.addbook.ImportState
import vn.abook.player.ui.snapshot.captureRoboImage
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ImportStepProgressTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val resolver get() = RuntimeEnvironment.getApplication().contentResolver

    @After fun restoreScale() {
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
    }

    @Test fun reducedMotionUpdatesWhetherTheCurrentStepHasATotal() {
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 0f)
        val work = mutableStateOf(Work(WorkStep.Copy, 90, 100))
        val state = ImportState(items = listOf(ImportItem(1, "content://test", "Progress test", stage = ImportStage.Reading)))
        rule.setContent {
            AbookTheme(false) {
                AddBookScreen(state, {}, {}, {}, {}, {}, {}, progress = { work })
            }
        }
        rule.onNodeWithTag("stage_progress").assertExists()
        rule.runOnUiThread { work.value = Work(WorkStep.Read) }
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithTag("stage_progress_running").assertExists()
        rule.runOnUiThread { work.value = Work(WorkStep.Check, 20, 100) }
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithTag("stage_progress").assertExists()
    }

    @Test fun reducedMotionKeepsTheOutgoingStepsLastFraction() {
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 0f)
        val work = mutableStateOf(Work(WorkStep.Copy, 90, 100))
        val state = ImportState(items = listOf(ImportItem(1, "content://test", "Progress test", stage = ImportStage.Reading)))
        rule.setContent {
            AbookTheme(false) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    AddBookScreen(state, {}, {}, {}, {}, {}, {}, progress = { work })
                }
            }
        }
        rule.waitForIdle()
        val bar = rule.onNodeWithTag("stage_progress").fetchSemanticsNode().boundsInRoot
        rule.mainClock.autoAdvance = false
        rule.runOnUiThread { work.value = Work(WorkStep.Check, 0, 100) }
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(32)
        rule.waitForIdle()

        // The new step is empty. During the fade, the old 90% fill must still cover 80% of the row.
        // A recreated cache used to turn it into a centered 40% segment, leaving this point bare.
        val image = File("build/icon_probe/import-step-reduced.png")
        image.parentFile.mkdirs()
        rule.onRoot().captureRoboImage(image.path, RoborazziOptions(taskType = RoborazziTaskType.Record))
        val bitmap = BitmapFactory.decodeFile(image.path)
        try {
            val y = (bar.bottom - 1f).toInt()
            val filled = bitmap.getPixel((bar.left + bar.width * .8f).toInt(), y)
            val track = bitmap.getPixel((bar.left + bar.width * .95f).toInt(), y)
            val difference = abs(Color.red(filled) - Color.red(track)) + abs(Color.green(filled) - Color.green(track)) + abs(Color.blue(filled) - Color.blue(track))
            assertTrue("Outgoing progress lost its 90% fill during the reduced fade: difference=$difference", difference > 20)
        } finally {
            bitmap.recycle()
            rule.mainClock.autoAdvance = true
        }
    }
}
