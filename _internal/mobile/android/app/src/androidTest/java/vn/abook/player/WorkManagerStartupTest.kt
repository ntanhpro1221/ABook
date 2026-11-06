package vn.abook.player

import androidx.startup.AppInitializer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.Configuration
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.WorkManagerInitializer
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** A background entry point must still run persisted work without opening an Activity. */
@RunWith(AndroidJUnit4::class)
class WorkManagerStartupTest {
    @Test fun contextAccessRunsWorkWithoutAnActivityOrTheDefaultInitializer() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertTrue(context.applicationContext is Configuration.Provider)
        assertFalse(AppInitializer.getInstance(context).isEagerlyInitialized(WorkManagerInitializer::class.java))
        assertFalse(StudioAlerts.enabled(context))
        val manager = WorkManager.getInstance(context)
        assertSame(manager, WorkManager.getInstance(context))
        // The real periodic worker exits successfully when alerts are disabled; no network or notification.
        val request = OneTimeWorkRequestBuilder<StudioAlertWorker>().build()
        manager.enqueue(request).result.get(10, TimeUnit.SECONDS)
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20)
        var state = manager.getWorkInfoById(request.id).get(5, TimeUnit.SECONDS)!!.state
        while (!state.isFinished && System.nanoTime() < deadline) {
            Thread.sleep(100)
            state = manager.getWorkInfoById(request.id).get(5, TimeUnit.SECONDS)!!.state
        }
        assertEquals(WorkInfo.State.SUCCEEDED, state)
    }
}
