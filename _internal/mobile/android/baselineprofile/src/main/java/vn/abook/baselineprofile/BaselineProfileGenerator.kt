package vn.abook.baselineprofile

import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.junit4.BaselineProfileRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test

/**
 * Sinh baseline profile + startup profile cho khung native: mở app (sách giả như bản đo), cuộn lưới, đổi ba tab nhiều vòng (cả đường trượt hai tab một lúc),
 * vào trang sách rồi Back, mở bảng bộ nhiều tập, menu Xếp theo, ô Tìm, bảng Thêm sách. Mọi đường mà người nghe đi thường xuyên phải nằm trong profile,
 * không thì lần đầu chạy nó bị thông dịch (khung 20-40 ms trên OPPO).
 * Chạy: gradlew -PbenchAppId=com.ngdtuanh.abook.dev2 :app:generateBaselineProfile (sách giả chỉ có ở bản thử; đặt ANDROID_SERIAL; Android 13+ chạy được không cần root - máy ảo API 34).
 */
class BaselineProfileGenerator {
    @get:Rule
    val rule = BaselineProfileRule()

    private fun collect(startup: Boolean = false, block: MacrobenchmarkScope.() -> Unit) {
        // Bound this emulator audit explicitly; normal profile generation retains library stability defaults.
        if (InstrumentationRegistry.getArguments().getString("perf165BoundedProfile") == "true") {
            rule.collect(packageName = BuildConfig.TARGET_PACKAGE, includeInStartupProfile = startup,
                maxIterations = 5, stableIterations = 2, strictStability = false) { block() }
        } else {
            rule.collect(packageName = BuildConfig.TARGET_PACKAGE, includeInStartupProfile = startup) { block() }
        }
    }

    /** Cover the real startup graph as well as the demo-only navigation scenarios. */
    @Test
    fun diskStartup() = collect(startup = true) {
        pressHome()
        startActivityAndWait()
        check(device.wait(Until.hasObject(By.res("tab_library")), 8_000))
        device.waitForIdle()
        Thread.sleep(1_500)
    }

    /** Real disk fixture: also profile audio startup, container transform, read-along and player sheets. */
    @Test
    fun diskPlayer() = collect {
        pressHome()
        startActivityAndWait()
        check(device.wait(Until.hasObject(By.res("book_cell")), 8_000)) { "Seed the disk fixture before generating the player profile" }
        device.findObjects(By.res("book_cell")).first().click()
        check(device.wait(Until.hasObject(By.res("book_primary")), 8_000))
        device.findObject(By.res("book_primary")).click()
        Thread.sleep(1_500)
        device.pressBack()
        check(device.wait(Until.hasObject(By.res("mini_open")), 8_000))
        repeat(3) {
            checkNotNull(device.wait(Until.findObject(By.res("mini_open")), 8_000)).click()
            check(device.wait(Until.hasObject(By.res("collapse_player")), 8_000))
            Thread.sleep(500)
            for (tag in listOf("player_speed", "player_sleep", "player_more")) {
                device.findObject(By.res(tag)).click()
                Thread.sleep(400)
                device.pressBack()
                Thread.sleep(400)
            }
            device.findObject(By.res("mode_read")).click()
            check(device.wait(Until.hasObject(By.res("read_along_text")), 8_000))
            val text = device.findObject(By.res("read_along_text"))
            val bounds = text.visibleBounds
            val x = bounds.centerX()
            val top = bounds.top + bounds.height() / 4
            val bottom = bounds.bottom - bounds.height() / 4
            device.swipe(x, bottom, x, top, 20)
            Thread.sleep(600)
            device.swipe(x, top, x, bottom, 20)
            Thread.sleep(600)
            device.findObject(By.res("mode_listen")).click()
            // Let the mode transition settle before locating and clicking the collapse control.
            Thread.sleep(600)
            device.findObject(By.res("collapse_player")).click()
            check(device.wait(Until.hasObject(By.res("mini_open")), 8_000))
        }
    }

    @Test
    fun generate() = collect(startup = true) {
        pressHome()
        startActivityAndWait { it.putExtra("abook.demo.books", 200) }
        device.wait(Until.hasObject(By.res("library_grid")), 8_000)
        // Dựng trước ba tab chạy lúc rảnh sau khung đầu: chờ nó xong để vào profile.
        device.waitForIdle()
        Thread.sleep(1_000)
        scrollLibrary()
        // Ba vòng: kề nhau, nhảy cách một tab, quay lại.
        repeat(3) {
            for (tag in listOf("tab_studio", "tab_settings", "tab_library", "tab_settings", "tab_studio", "tab_library")) tapTab(tag)
        }
        scrollLibrary()
        // Hàng lọc (Tất cả / Nghe dở / Chưa nghe / Xong) + đếm sách: hàng mới sau lần sinh profile cuối, đi qua mỗi lần mở Thư viện.
        for (tag in listOf("filter_listening", "filter_new", "filter_finished", "filter_all")) tapTab(tag)
        scrollLibrary()
        openBookTabs()
        openAndBack("book_cell", "book_screen")
        openAndBack("series_cell", "series_sheet")
        openAndBack("sort_button", "sort_menu")
        openAndBack("search_button", "search_field")
        openAndBack("add_book", "add_book_sheet")
        scrollLibrary()
        device.waitForIdle()
    }

    private fun MacrobenchmarkScope.tapTab(tag: String) {
        device.findObject(By.res(tag))?.click()
        device.waitForIdle()
        // Hoạt ảnh trượt 220 ms: đợi nó chạy hết (waitForIdle không chờ hoạt ảnh Compose).
        Thread.sleep(400)
    }

    /** Trang sách và ba mục của nó (Chương / Lịch sử / Nhân vật): đường ScrollingTabs + danh sách chương mới, trước đây không nằm trong profile. */
    private fun MacrobenchmarkScope.openBookTabs() {
        device.findObject(By.res("book_cell"))?.click() ?: return
        device.wait(Until.hasObject(By.res("book_screen")), 2_000)
        Thread.sleep(400)
        for (tag in listOf("book_tab_history", "book_tab_cast", "book_tab_chapters")) tapTab(tag)
        device.pressBack()
        device.waitForIdle()
        Thread.sleep(400)
    }

    private fun MacrobenchmarkScope.scrollLibrary() {
        val grid = device.findObject(By.res("library_grid")) ?: return
        grid.setGestureMargin(device.displayWidth / 5)
        repeat(2) { grid.fling(Direction.DOWN) }
        repeat(2) { grid.fling(Direction.UP) }
        device.waitForIdle()
    }

    /** Chạm phần tử có thẻ [tag] rồi chờ [shown] hiện, rồi Back. Phần tử không có thì bỏ qua (mỗi bước là một đường nhỏ của profile, không phải ca kiểm). */
    private fun MacrobenchmarkScope.openAndBack(tag: String, shown: String) {
        val target = device.findObject(By.res(tag)) ?: return
        target.click()
        device.wait(Until.hasObject(By.res(shown)), 2_000)
        Thread.sleep(400)
        device.pressBack()
        device.waitForIdle()
        Thread.sleep(400)
        // Bàn phím của ô Tìm ăn cú Back đầu: Back lần nữa để đóng hẳn.
        if (device.hasObject(By.res(shown))) {
            device.pressBack()
            device.waitForIdle()
            Thread.sleep(400)
        }
    }
}
