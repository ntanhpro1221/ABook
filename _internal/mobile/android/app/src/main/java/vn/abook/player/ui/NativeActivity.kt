package vn.abook.player.ui

import android.content.ComponentCallbacks2
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
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
import vn.abook.player.BuildConfig
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme

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
        // Màn chờ giữ tới khi Thư viện có nội dung: khung đầu người dùng thấy đã là lưới bìa, không phải màn trống.
        splash.setKeepOnScreenCondition { library.state.value is LibraryState.Loading }
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
            AbookTheme {
                val scope = rememberCoroutineScope()
                val shell = remember {
                    ShellState(scope) { sort -> lifecycleScope.launch(Dispatchers.IO) { prefs.setSort(sort) } }
                }
                LaunchedEffect(Unit) { shell.library.restoreSort(withContext(Dispatchers.IO) { prefs.sort() }) }
                val state by library.state.collectAsStateWithLifecycle()
                AppShell(shell, state, player, covers, onFirstContent = ::onFirstContent)
            }
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
    }
}
