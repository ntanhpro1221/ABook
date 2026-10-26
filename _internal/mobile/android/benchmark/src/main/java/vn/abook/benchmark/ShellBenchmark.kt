package vn.abook.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
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

    private fun MacrobenchmarkScope.launchLibrary(books: Int = 200) {
        pressHome()
        startActivityAndWait { it.putExtra("abook.demo.books", books) }
        device.wait(Until.hasObject(By.res("library_grid")), 5_000)
    }

    @Test
    fun coldStartup() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.COLD, compilationMode = CompilationMode.Partial(),
    ) { launchLibrary() }

    @Test
    fun warmStartup() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.WARM, compilationMode = CompilationMode.Partial(),
    ) { launchLibrary() }

    @Test
    fun tabSwitching() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = CompilationMode.Partial(),
        setupBlock = { launchLibrary() },
    ) {
        for (tag in listOf("tab_studio", "tab_settings", "tab_library", "tab_settings", "tab_studio", "tab_library")) {
            device.findObject(By.res(tag)).click()
            device.waitForIdle()
        }
    }

    @Test
    fun gridScroll() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = CompilationMode.Partial(),
        setupBlock = { launchLibrary() },
    ) {
        val grid = device.findObject(By.res("library_grid"))
        grid.setGestureMargin(device.displayWidth / 5)
        repeat(3) { grid.fling(Direction.DOWN) }
        repeat(3) { grid.fling(Direction.UP) }
    }

    @Test
    fun pushAndBack() = rule.measureRepeated(
        packageName = PACKAGE, metrics = listOf(FrameTimingMetric()), iterations = 8,
        startupMode = StartupMode.WARM, compilationMode = CompilationMode.Partial(),
        setupBlock = { launchLibrary() },
    ) {
        repeat(3) {
            device.findObjects(By.res("book_cell")).first().click()
            device.wait(Until.hasObject(By.res("book_screen")), 2_000)
            device.pressBack()
            device.wait(Until.hasObject(By.res("library_grid")), 2_000)
        }
    }

    private companion object {
        const val PACKAGE = "com.ngdtuanh.abook"
    }
}
