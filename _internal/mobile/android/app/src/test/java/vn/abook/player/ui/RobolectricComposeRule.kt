package vn.abook.player.ui

import android.content.ComponentName
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule as platformComposeRule
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf

/** Register the host in the JVM sandbox, including Release tests without the Debug manifest. */
inline fun <reified A : ComponentActivity> createAndroidComposeRule() = run {
    val application = RuntimeEnvironment.getApplication()
    shadowOf(application.packageManager).addActivityIfNotPresent(ComponentName(application, A::class.java))
    platformComposeRule<A>()
}
