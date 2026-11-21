package vn.abook.player.ui

import android.content.ComponentName
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule as platformComposeRule
import androidx.compose.ui.test.IdlingResource
import androidx.compose.ui.test.junit4.AndroidComposeTestRule
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.test.ext.junit.rules.ActivityScenarioRule
import org.junit.runner.Description
import org.junit.runners.model.Statement
import vn.abook.player.ui.data.ImageWork
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf

/** Register the host in the JVM sandbox, including Release tests without the Debug manifest. */
inline fun <reified A : ComponentActivity> createAndroidComposeRule(): AbookComposeRule<A> {
    val application = RuntimeEnvironment.getApplication()
    shadowOf(application.packageManager).addActivityIfNotPresent(ComponentName(application, A::class.java))
    return AbookComposeRule(platformComposeRule<A>())
}

/**
 * The platform rule plus image idling. Image work is process-wide (one sandbox serves many classes), so each test
 * must start and end with none open: a leak fails the test that caused it, by call site, instead of hanging every
 * later class for the 60 s idle timeout.
 */
class AbookComposeRule<A : ComponentActivity>(val platform: AndroidComposeTestRule<ActivityScenarioRule<A>, A>) :
    ComposeContentTestRule by platform {
    val activityRule: ActivityScenarioRule<A> get() = platform.activityRule
    val activity: A get() = platform.activity

    init {
        ImageWork.traceSources = true
        platform.registerIdlingResource(ImageWorkIdlingResource)
    }

    override fun apply(base: Statement, description: Description): Statement {
        val hosted = platform.apply(base, description)
        return object : Statement() {
            override fun evaluate() {
                ImageWorkIdlingResource.requireNoneOpen("before ${description.displayName} (an earlier test leaked it)")
                var failure: Throwable? = null
                try { hosted.evaluate() } catch (error: Throwable) { failure = error }
                try {
                    ImageWorkIdlingResource.requireNoneOpen("after ${description.displayName}: the host is gone")
                } catch (leak: AssertionError) {
                    failure?.addSuppressed(leak) ?: run { failure = leak }
                }
                failure?.let { throw it }
            }
        }
    }

    /** For a test that deliberately holds a decode open and inspects the frame meanwhile; everything else still idles. */
    fun <T> whileImageWorkHeld(block: () -> T): T {
        platform.unregisterIdlingResource(ImageWorkIdlingResource)
        try { return block() } finally { platform.registerIdlingResource(ImageWorkIdlingResource) }
    }
}

/** The shared rule waits on actual worker completion, even while the host CPU is busy. */
object ImageWorkIdlingResource : IdlingResource {
    override val isIdleNow: Boolean get() = ImageWork.isIdle
    override fun getDiagnosticMessageIfBusy(): String? = if (isIdleNow) null else ImageWork.diagnostic

    /** Releases leftovers so one leak cannot cascade, then fails with their call sites. */
    fun requireNoneOpen(moment: String) {
        val leaked = ImageWork.drain()
        if (leaked.isNotEmpty()) throw AssertionError("Image work still open $moment: $leaked")
    }
}
