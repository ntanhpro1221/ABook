package vn.abook.baselineprofile

import androidx.benchmark.macro.junit4.BaselineProfileRule
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test

/**
 * Sinh baseline profile + startup profile cho khung native: mở app (sách giả như bản đo), cuộn lưới, đổi ba tab, vào trang sách rồi Back.
 * Chạy: gradlew -PnativeUi :app:generateBaselineProfile (đặt ANDROID_SERIAL).
 */
class BaselineProfileGenerator {
    @get:Rule
    val rule = BaselineProfileRule()

    @Test
    fun generate() = rule.collect(packageName = "com.ngdtuanh.abook", includeInStartupProfile = true) {
        pressHome()
        startActivityAndWait { it.putExtra("abook.demo.books", 200) }
        device.wait(Until.hasObject(By.res("library_grid")), 5_000)
        val grid = device.findObject(By.res("library_grid"))
        grid.setGestureMargin(device.displayWidth / 5)
        grid.fling(Direction.DOWN)
        grid.fling(Direction.UP)
        for (tag in listOf("tab_studio", "tab_settings", "tab_library")) {
            device.findObject(By.res(tag)).click()
            device.waitForIdle()
        }
        device.findObjects(By.res("book_cell")).first().click()
        device.wait(Until.hasObject(By.res("book_screen")), 2_000)
        device.pressBack()
        device.wait(Until.hasObject(By.res("library_grid")), 2_000)
    }
}
