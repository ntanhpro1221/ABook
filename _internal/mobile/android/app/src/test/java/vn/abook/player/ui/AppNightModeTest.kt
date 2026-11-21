package vn.abook.player.ui

import android.app.UiModeManager
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.util.ReflectionHelpers
import vn.abook.player.ui.data.AppNightMode
import vn.abook.player.ui.data.ThemeMode

/** Soát tapthru5 S4 (18-11): màn chờ theo giao diện chọn TRONG app (Sáng / Tối / Tự động), không theo máy. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class AppNightModeTest {
    @Test fun eachInAppThemeBecomesTheAppsOwnNightModeThatTheSplashReads() {
        val context = ApplicationProvider.getApplicationContext<android.app.Application>()
        val manager = context.getSystemService(UiModeManager::class.java)
        for ((theme, mode) in listOf(ThemeMode.Dark to UiModeManager.MODE_NIGHT_YES, ThemeMode.Light to UiModeManager.MODE_NIGHT_NO,
            ThemeMode.System to UiModeManager.MODE_NIGHT_AUTO)) {
            AppNightMode.apply(context, theme, loaded = true)
            assertEquals(theme.name, mode, shadowOf(manager).applicationNightMode)
        }
    }

    @Test fun loadingDefaultDoesNotClearThePreviousLaunchChoice() {
        val context = ApplicationProvider.getApplicationContext<android.app.Application>()
        val manager = context.getSystemService(UiModeManager::class.java)
        // Last launch chose Dark. SettingsRepo initially publishes System before its asynchronous disk read returns Light.
        AppNightMode.apply(context, ThemeMode.Dark, loaded = true)
        AppNightMode.apply(context, ThemeMode.System, loaded = false)
        assertEquals(UiModeManager.MODE_NIGHT_YES, shadowOf(manager).applicationNightMode)
        AppNightMode.apply(context, ThemeMode.Light, loaded = true)
        assertEquals(UiModeManager.MODE_NIGHT_NO, shadowOf(manager).applicationNightMode)
        AppNightMode.apply(context, ThemeMode.System, loaded = true)
        assertEquals(UiModeManager.MODE_NIGHT_AUTO, shadowOf(manager).applicationNightMode)
    }

    @Test fun demoDoesNotOverwriteTheRealAppsChoice() {
        val context = ApplicationProvider.getApplicationContext<android.app.Application>()
        val manager = context.getSystemService(UiModeManager::class.java)
        AppNightMode.apply(context, ThemeMode.Dark, loaded = true)
        AppNightMode.apply(context, ThemeMode.Light, loaded = true, demo = true)
        assertEquals(UiModeManager.MODE_NIGHT_YES, shadowOf(manager).applicationNightMode)
    }

    @Test fun preAndroidTwelveDoesNotCallTheNewPlatformApi() {
        val context = ApplicationProvider.getApplicationContext<android.app.Application>()
        val manager = context.getSystemService(UiModeManager::class.java)
        val before = shadowOf(manager).applicationNightMode
        val sdk = android.os.Build.VERSION.SDK_INT
        // Exercise the API guard using the pinned offline SDK sandbox.
        try {
            ReflectionHelpers.setStaticField(android.os.Build.VERSION::class.java, "SDK_INT", 30)
            AppNightMode.apply(context, ThemeMode.Dark, loaded = true)
            assertEquals(before, shadowOf(manager).applicationNightMode)
        } finally {
            ReflectionHelpers.setStaticField(android.os.Build.VERSION::class.java, "SDK_INT", sdk)
        }
    }
}
