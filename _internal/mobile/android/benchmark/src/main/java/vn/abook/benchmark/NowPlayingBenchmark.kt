package vn.abook.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test

/**
 * Built offline here; execute only when the owner releases the OPPO for measurements. Opens the REAL mini player (`mini_open`) of the demo book, which runs
 * through the real PlayerRepo -> window path over a fake core; the window is the app-root overlay, not a screen.
 */
class NowPlayingBenchmark {
    @get:Rule val rule = MacrobenchmarkRule()
    private val target get() = InstrumentationRegistry.getArguments().getString("targetPackage") ?: "com.ngdtuanh.abook.dev"

    private fun MacrobenchmarkScope.launchPlayer() {
        pressHome()
        startActivityAndWait { it.putExtra("abook.demo.books", 200) }
        check(device.wait(Until.hasObject(By.res("mini_player")), 5000))
    }
    @Test fun openCloseFiveTimes() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = CompilationMode.Partial(),
        setupBlock = { launchPlayer() },
    ) {
        device.findObject(By.res("mini_open")).click()
        check(device.wait(Until.hasObject(By.res("collapse_player")), 2000))
        device.waitForIdle()
        device.findObject(By.res("collapse_player")).click()
        check(device.wait(Until.hasObject(By.res("mini_player")), 2000))
        device.waitForIdle()
    }
    @Test fun readAlongFiveTimes() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = CompilationMode.Partial(),
        setupBlock = {
            launchPlayer()
            device.findObject(By.res("mini_open")).click()
            check(device.wait(Until.hasObject(By.res("collapse_player")), 2000))
            device.waitForIdle()
        },
    ) {
        device.findObject(By.res("mode_read")).click()
        check(device.wait(Until.hasObject(By.res("read_along_text")), 2000))
        device.waitForIdle()
        device.findObject(By.res("mode_listen")).click()
        check(device.wait(Until.gone(By.res("read_along_text")), 2000))
        device.waitForIdle()
        device.findObject(By.res("collapse_player")).click()
        device.waitForIdle()
    }
}
