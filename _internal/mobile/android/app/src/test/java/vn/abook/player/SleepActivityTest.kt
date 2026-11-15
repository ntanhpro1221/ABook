package vn.abook.player

import android.app.Application
import android.content.Intent
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class SleepActivityTest {
    private val context get() = RuntimeEnvironment.getApplication()
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }
    @Before fun setup() {
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("sleep-activity"))
        Playback::class.java.getDeclaredField("appContext").also { it.isAccessible = true }.set(Playback, context)
        field("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("selectedMode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("selectedMinutes").setInt(SleepTimer, 10)
        field("retained").setBoolean(SleepTimer, false)
        field("automaticReason").set(SleepTimer, "")
        field("runningSinceMs").setLong(SleepTimer, 0)
        SleepTimer.activityResets = true
        ListenerActivity.start(context)
        field("remainingMs").setLong(SleepTimer, 240_000)
    }
    @After fun cleanup() {
        ListenerActivity.stop()
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        DiskWrites.flush(TestTime.ms(5_000))
    }
    private fun send(action: String) {
        context.sendBroadcast(Intent(action))
        shadowOf(android.os.Looper.getMainLooper()).idle()
    }
    @Test fun screenOnAndUnlockResetTheCountdown() {
        for (action in listOf(Intent.ACTION_SCREEN_ON, Intent.ACTION_USER_PRESENT)) {
            field("remainingMs").setLong(SleepTimer, 240_000)
            send(action)
            assertEquals(action, 600.0, SleepTimer.describe().getDouble("remaining"), 0.01)
        }
    }
    @Test fun deliberateScreenOffResetsButTimeoutDoesNot() {
        Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_OFF_TIMEOUT, 30_000)
        ListenerActivity.inputObserved()
        shadowOf(context.getSystemService(PowerManager::class.java)).setIsInteractive(false)
        send(Intent.ACTION_SCREEN_OFF)
        assertEquals(600.0, SleepTimer.describe().getDouble("remaining"), 0.01)
        field("remainingMs").setLong(SleepTimer, 240_000)
        ListenerActivity::class.java.getDeclaredField("lastInput").also { it.isAccessible = true }
            .setLong(ListenerActivity, SystemClock.elapsedRealtime() - 30_000)
        send(Intent.ACTION_SCREEN_OFF)
        assertEquals(240.0, SleepTimer.describe().getDouble("remaining"), 0.01)
    }
}
