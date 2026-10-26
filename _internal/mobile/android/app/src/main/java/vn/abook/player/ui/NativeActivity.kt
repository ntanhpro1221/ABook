package vn.abook.player.ui

import android.content.ActivityNotFoundException
import android.content.ComponentCallbacks2
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.AbookApplication
import vn.abook.player.AppLog
import vn.abook.player.BuildConfig
import vn.abook.player.Diagnostics
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsLinks
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal
import vn.abook.player.ui.theme.ThemeRevealHost

/**
 * Màn mở app của giao diện native (docs/NATIVE_PHONE_UI.md): một Activity, Compose, không WebView. Chỉ là màn khởi động khi dựng với `-PnativeUi`
 * (src/nativeUi/AndroidManifest.xml); bản thường vẫn mở MainActivity (WebView).
 */
class NativeActivity : ComponentActivity() {
    private val app get() = application as AbookApplication
    private var started = false
    private var contentReady = false
    private var demo = false

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val library = app.library
        val covers = app.covers
        val player = app.player
        val prefs = app.uiPrefs
        val settings = app.settings
        // Màn chờ giữ tới khi Thư viện có nội dung VÀ đã biết giao diện sáng / tối của bạn: khung đầu đã là lưới bìa đúng màu, không phải màn trống hay
        // màn đổi màu ngay sau khi hiện. Hai lần đọc chạy song song ở luồng nền.
        splash.setKeepOnScreenCondition { library.state.value is LibraryState.Loading || !settings.loaded.value }
        lifecycleScope.launch { settings.load() }
        val demoBooks = if (BuildConfig.NATIVE_UI) intent.getIntExtra(DEMO_BOOKS, 0) else 0
        demo = demoBooks > 0
        if (demo) library.showDemo(demoBooks) else lifecycleScope.launch { library.refresh() }
        // Dừng phát thì chỗ nghe đã ghi: đọc lại để "Đang nghe" và vạch tiến độ theo kịp.
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                player.state.map { it.playing }.distinctUntilChanged().drop(1).collect { playing ->
                    if (!playing && !demo) {
                        delay(800)
                        library.refresh()
                    }
                }
            }
        }
        setContent {
            val scope = rememberCoroutineScope()
            val reveal = remember { ThemeReveal(scope) }
            val chosen by settings.state.collectAsStateWithLifecycle()
            val dark = chosen.theme.dark(isSystemInDarkTheme())
            // Biểu tượng thanh trạng thái / điều hướng theo giao diện của APP (app tối trên máy sáng và ngược lại), đổi cùng lúc với giao diện.
            LaunchedEffect(dark) {
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = !dark
                    isAppearanceLightNavigationBars = !dark
                }
            }
            ThemeRevealHost(reveal) {
                AbookTheme(dark) {
                    val shell = remember {
                        ShellState(scope) { sort -> lifecycleScope.launch(Dispatchers.IO) { prefs.setSort(sort) } }
                    }
                    val env = remember { SettingsEnv(settings, reveal, links) }
                    LaunchedEffect(Unit) { shell.library.restoreSort(withContext(Dispatchers.IO) { prefs.sort() }) }
                    val state by library.state.collectAsStateWithLifecycle()
                    AppShell(shell, state, player, covers, env, onFirstContent = ::onFirstContent)
                }
            }
        }
    }

    /** Cửa ra hệ điều hành của Cài đặt: trang thông báo của ABook, bảng chia sẻ nhật ký, trang mã nguồn. */
    private val links = SettingsLinks(
        openNotificationSettings = {
            open(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
        },
        shareLogs = ::shareLogs,
        openSource = { open(Intent(Intent.ACTION_VIEW, Uri.parse(SOURCE_URL))) },
    )

    private fun open(intent: Intent) {
        try {
            startActivity(intent)
        } catch (error: ActivityNotFoundException) {
            AppLog.w("Settings", "máy không mở được ${intent.action}")
        }
    }

    /** "Gửi nhật ký": gom gói ở luồng nền ([Diagnostics.shareIntent]) rồi mở bảng chia sẻ - bạn tự chọn gửi cho ai. */
    private fun shareLogs() {
        lifecycleScope.launch {
            val shared = withContext(Dispatchers.IO) {
                try {
                    Diagnostics.shareIntent(this@NativeActivity)
                } catch (error: Exception) {
                    AppLog.w("Diagnostics", "không gom được nhật ký để gửi: ${error.javaClass.simpleName}")
                    null
                }
            } ?: return@launch
            open(shared.first)
            AppLog.i("Diagnostics", "mở bảng chia sẻ nhật ký (${shared.second.length()} byte)")
        }
    }

    /** Khung nội dung đầu đã vẽ: báo "vẽ xong" và bắt đầu nghe lõi phát (Playback.init không nằm trong đường mở nguội). */
    private fun onFirstContent() {
        reportFullyDrawn()
        contentReady = true
        if (started) app.player.attach()
    }

    override fun onStart() {
        super.onStart()
        started = true
        if (contentReady) app.player.attach()
    }

    override fun onStop() {
        super.onStop()
        started = false
        app.player.detach()
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        // Giao diện đã ẩn (phát nền): trả bộ nhớ bìa ngay (ngân sách RAM phát nền, NATIVE_PHONE_UI.md §1).
        if (level >= ComponentCallbacks2.TRIM_MEMORY_UI_HIDDEN) app.covers.trim()
    }

    companion object {
        /** Extra của Intent: số sách giả thay Thư viện thật (đo đạc, chỉ bản -PnativeUi). */
        const val DEMO_BOOKS = "abook.demo.books"

        /** "Mã nguồn mở" (Cài đặt > Nâng cao): trang của ABook trên GitHub - địa chỉ cố định, không nhận từ đâu. */
        const val SOURCE_URL = "https://github.com/ntanhpro1221/ABook/"
    }
}
