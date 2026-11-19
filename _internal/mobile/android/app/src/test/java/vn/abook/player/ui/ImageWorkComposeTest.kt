package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.IdlingResource
import androidx.compose.ui.test.onNodeWithTag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.ImageWork
import vn.abook.player.ui.data.produceImageState
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ImageWorkComposeTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun composeWaitsForAWorkerAndItsPublishedPixels() {
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        var observedBusyWorker = false
        // Unlock only when Compose actually polls the pending worker. No timer/sleep.
        val observer = object : IdlingResource {
            override val isIdleNow: Boolean get() {
                if (started.count == 0L && !ImageWork.isIdle) {
                    observedBusyWorker = true
                    release.countDown()
                }
                return true
            }
        }
        rule.registerIdlingResource(observer)
        try {
            rule.setContent {
                val loaded by produceImageState(false, Unit) {
                    value = withContext(Dispatchers.IO) {
                        started.countDown()
                        check(release.await(30, TimeUnit.SECONDS)) { "Compose did not observe image work" }
                        true
                    }
                }
                BasicText("image", Modifier.testTag(if (loaded) "pixels" else "placeholder"))
            }
            rule.waitForIdle()
            assertTrue("Compose must observe off-main image work", observedBusyWorker)
            rule.onNodeWithTag("pixels").assertExists()
            assertTrue(ImageWork.isIdle)
        } finally {
            release.countDown()
            rule.unregisterIdlingResource(observer)
        }
    }
}
