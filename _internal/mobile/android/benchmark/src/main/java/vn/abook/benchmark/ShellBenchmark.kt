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

/**
 * Macrobenchmark của khung native (docs/NATIVE_PHONE_UI.md §1) trên bản `-PnativeUi`. Sách giả (`abook.demo.books`) để cuộn đủ 200 cuốn mà không
 * chạm thư viện thật. Ngân sách: mở nguội <= 500 ms, ấm <= 200 ms, khung p95 <= 8 ms / p99 <= 12 ms.
 */
class ShellBenchmark {
    @get:Rule
    val rule = MacrobenchmarkRule()

    /**
     * [home] false for the frame scenarios: Home puts the playing app into picture-in-picture and the next launch leaves PiP into Now playing (a feature),
     * which would turn every library scenario into a Now playing one. The launch intent already restarts the activity (NEW_TASK | CLEAR_TASK).
     */
    private fun MacrobenchmarkScope.launchLibrary(books: Int = 200, home: Boolean = true) {
        if (home) pressHome()
        startActivityAndWait { it.putExtra("abook.demo.books", books) }
        Thread.sleep(1_500)
    }

    @Test
    fun coldStartup() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.COLD, compilationMode = compilation(),
    ) { launchLibrary() }

    /** Khung vẽ của chính lần mở nguội (tới khi lưới Thư viện hiện): ngân sách khung áp cho cả kịch bản này. */
    @Test
    fun coldStartFrames() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 10,
        startupMode = StartupMode.COLD, compilationMode = compilation(),
    ) { launchLibrary() }

    @Test
    fun warmStartup() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
    ) { launchLibrary() }

    @Test
    fun tabSwitching() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { launchLibrary(home = false) },
    ) {
        for (spot in listOf(Spot.tabStudio, Spot.tabSettings, Spot.tabLibrary, Spot.tabSettings, Spot.tabStudio, Spot.tabLibrary)) tap(spot, 600)
    }

    @Test
    fun gridScroll() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { launchLibrary(home = false) },
    ) {
        repeat(3) { swipe(0.5f, 0.75f, 0.5f, 0.2f, 120, 900) }
        repeat(3) { swipe(0.5f, 0.2f, 0.5f, 0.75f, 120, 900) }
    }

    @Test
    fun addAndEditBackFiveTimes() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 5,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { launchLibrary() },
    ) {
        repeat(5) {
            device.findObject(By.res("add_book")).click()
            check(device.wait(Until.hasObject(By.res("add_book_screen")), 2_000))
            device.pressBack()
            device.waitForIdle()
            device.findObjects(By.res("book_cell")).first().click()
            check(device.wait(Until.hasObject(By.res("edit_book")), 2_000))
            device.findObject(By.res("edit_book")).click()
            check(device.wait(Until.hasObject(By.res("edit_book_screen")), 2_000))
            device.pressBack()
            check(device.wait(Until.hasObject(By.res("book_screen")), 2_000))
            device.pressBack()
            device.waitForIdle()
        }
    }

    @Test
    fun pushAndBack() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = { launchLibrary(home = false) },
    ) {
        repeat(3) {
            tap(Spot.firstBook, 900)
            back(900)
        }
    }

    /** Mở một nhóm Cài đặt rồi Back (màn con đẩy vào bằng NavState, như trang sách). */
    @Test
    fun settingsGroupBackFiveTimes() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = compilation(),
        setupBlock = {
            launchLibrary()
            device.findObject(By.res("tab_settings")).click()
            check(device.wait(Until.hasObject(By.res("settings_look")), 2_000))
            device.waitForIdle()
        },
    ) {
        repeat(5) {
            device.findObject(By.res("settings_look")).click()
            check(device.wait(Until.hasObject(By.res("settings_look_screen")), 2_000))
            device.waitForIdle()
            device.pressBack()
            check(device.wait(Until.hasObject(By.res("settings_look")), 2_000))
            device.waitForIdle()
        }
    }

    private companion object {
        const val PACKAGE = BuildConfig.TARGET_PACKAGE
    }
}
