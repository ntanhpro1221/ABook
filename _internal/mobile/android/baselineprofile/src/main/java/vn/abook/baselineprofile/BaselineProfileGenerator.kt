package vn.abook.baselineprofile

import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.junit4.BaselineProfileRule
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

    @Test
    fun generate() = rule.collect(packageName = BuildConfig.TARGET_PACKAGE, includeInStartupProfile = true) {
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
