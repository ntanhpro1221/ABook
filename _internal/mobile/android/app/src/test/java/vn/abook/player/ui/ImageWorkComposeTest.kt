package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.IdlingResource
import androidx.compose.ui.test.onNodeWithTag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.Description
import org.junit.runner.RunWith
import org.junit.runners.model.Statement
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.ImageWork
import vn.abook.player.ui.data.produceImageState
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
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

    // The producer is parked on a decoder that never runs. Leaving the composition must release it at once,
    // named by its call site while it is open.
    @Test fun leavingTheCompositionReleasesAProducerParkedOnABlockedDecoder() {
        val gate = CountDownLatch(1)
        val pool = Executors.newSingleThreadExecutor()
        pool.execute { gate.await() }
        try {
            var shown by mutableStateOf(true)
            // setContent waits for idle itself: the decode is held on purpose until the composition leaves.
            rule.whileImageWorkHeld {
                rule.setContent {
                    if (shown) {
                        val loaded by produceImageState(false, Unit) { value = withContext(pool.asCoroutineDispatcher()) { true } }
                        BasicText(if (loaded) "pixels" else "placeholder")
                    }
                }
            }
            val open = ImageWork.pendingSources
            assertEquals(open.toString(), 1, open.size)
            assertTrue(open.toString(), open.single().startsWith("ImageWorkComposeTest.kt:"))
            shown = false
            rule.waitForIdle() // Would time out if the parked producer still counted.
            assertTrue(ImageWork.isIdle)
        } finally {
            gate.countDown(); pool.shutdown()
        }
    }

    // A raw ticket nobody closes stands for any future leak: the rule fails that test by name, and the next test is clean.
    @Test fun theSharedRuleFailsTheLeakingTestInsteadOfHangingTheNextClass() {
        val inner = createAndroidComposeRule<ComponentActivity>()
        val leaking = object : Statement() { override fun evaluate() { ImageWork.begin("LeakyCover.kt:1") } }
        val error = assertThrows(AssertionError::class.java) {
            inner.apply(leaking, Description.createTestDescription("Leaky", "leaks")).evaluate()
        }
        assertTrue(error.message!!, "LeakyCover.kt:1" in error.message!! && "Leaky" in error.message!!)
        assertTrue(ImageWork.isIdle)
    }
}
