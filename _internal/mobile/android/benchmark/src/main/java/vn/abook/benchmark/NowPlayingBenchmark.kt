package vn.abook.benchmark

import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Rule
import org.junit.Test

/**
 * Opens the REAL mini player of the demo book, which runs through the real PlayerRepo -> window path over a fake core; the window is the app-root
 * overlay, not a screen. Input goes through Taps.kt (UiAutomator does not see the app on ColorOS).
 */
class NowPlayingBenchmark {
    @get:Rule val rule = MacrobenchmarkRule()
    private val target get() = InstrumentationRegistry.getArguments().getString("targetPackage") ?: BuildConfig.TARGET_PACKAGE

    // No pressHome: Home sends the playing app to PiP and the next launch leaves PiP straight into Now playing (a feature that would skew every scenario).
    private fun MacrobenchmarkScope.launchPlayer() {
        startActivityAndWait { it.putExtra("abook.demo.books", 200) }
        Thread.sleep(1_500)
    }

    private fun MacrobenchmarkScope.openPlayer() {
        launchPlayer()
        tap(Spot.miniOpen, 900)
    }

    @Test fun openCloseFiveTimes() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { launchPlayer() },
    ) {
        repeat(3) {
            tap(Spot.miniOpen, 900)
            tap(Spot.collapse, 900)
        }
    }

    @Test fun readAlongFiveTimes() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { openPlayer() },
    ) {
        repeat(3) {
            tap(Spot.modeRead, 1_000)
            tap(Spot.modeListen, 1_000)
        }
        tap(Spot.collapse, 900)
    }

    /** Kéo thanh tua qua lại (kéo chậm 0,6 s mỗi chiều), rồi thu nhỏ. */
    @Test fun seekDragFiveTimes() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { openPlayer() },
    ) {
        repeat(3) {
            swipe(Spot.SEEK_LEFT, Spot.SEEK_Y, Spot.SEEK_RIGHT, Spot.SEEK_Y, 600, 400)
            swipe(Spot.SEEK_RIGHT, Spot.SEEK_Y, Spot.SEEK_LEFT, Spot.SEEK_Y, 600, 400)
        }
        tap(Spot.collapse, 900)
    }

    /** Mở bảng Tốc độ rồi Hẹn giờ, mỗi bảng đóng bằng Back. */
    @Test fun speedAndSleepSheetsFiveTimes() = rule.measureRepeated(
        packageName = target, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { openPlayer() },
    ) {
        repeat(3) {
            tap(Spot.speed, 900)
            back(900)
            tap(Spot.sleep, 900)
            back(900)
        }
        tap(Spot.collapse, 900)
    }
}
