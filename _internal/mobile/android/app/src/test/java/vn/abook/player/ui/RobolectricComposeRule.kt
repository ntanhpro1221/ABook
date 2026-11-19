package vn.abook.player.ui

import android.content.ComponentName
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule as platformComposeRule
import androidx.compose.ui.test.IdlingResource
import vn.abook.player.ui.data.ImageWork
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf

/** Register the host in the JVM sandbox, including Release tests without the Debug manifest. */
inline fun <reified A : ComponentActivity> createAndroidComposeRule() = run {
    val application = RuntimeEnvironment.getApplication()
    shadowOf(application.packageManager).addActivityIfNotPresent(ComponentName(application, A::class.java))
    platformComposeRule<A>().also { it.registerIdlingResource(ImageWorkIdlingResource) }
}

/** The shared rule waits on actual worker completion, even while the host CPU is busy. */
object ImageWorkIdlingResource : IdlingResource {
    override val isIdleNow: Boolean get() = ImageWork.isIdle
    override fun getDiagnosticMessageIfBusy(): String? = if (isIdleNow) null else ImageWork.diagnostic
}
