package vn.abook.benchmark

import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test

/** Uses the installed disk library, including actual cover decoding and playback, instead of DEMO_BOOKS. */
class Perf165Benchmark {
    @get:Rule val rule = MacrobenchmarkRule()
    private val target = BuildConfig.TARGET_PACKAGE

    private fun MacrobenchmarkScope.launchLibrary() {
        startActivityAndWait()
        check(device.wait(Until.hasObject(By.res("library_grid")), 10_000))
        Thread.sleep(1_000)
    }

    @Test fun coldStartup() = rule.measureRepeated(
        packageName = target, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.COLD, compilationMode = compilation(),
    ) { launchLibrary() }

    @Test fun warmStartup() = rule.measureRepeated(
        packageName = target, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
    ) { launchLibrary() }

    @Test fun diskLibraryScroll() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { launchLibrary() },
    ) {
        val width = device.displayWidth
        val height = device.displayHeight
        repeat(5) { device.swipe(width / 2, height * 55 / 100, width / 2, height * 28 / 100, 12); Thread.sleep(400) }
        repeat(5) { device.swipe(width / 2, height * 28 / 100, width / 2, height * 55 / 100, 12); Thread.sleep(400) }
    }
}
