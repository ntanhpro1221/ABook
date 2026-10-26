package vn.abook.player.ui

import android.content.ComponentCallbacks2
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import vn.abook.player.AbookApplication
import vn.abook.player.BuildConfig
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.nowplaying.FakeNowPlayingModel
import vn.abook.player.ui.nowplaying.NowPlayingModel
import vn.abook.player.ui.nowplaying.PlaybackNowPlayingModel

/**
 * Màn mở app của giao diện native (docs/NATIVE_PHONE_UI.md): một Activity, Compose, không WebView. Chỉ là màn khởi động khi dựng với `-PnativeUi`
 * (src/nativeUi/AndroidManifest.xml); bản thường vẫn mở MainActivity (WebView).
 */
class NativeActivity : ComponentActivity() {
    private val app get() = application as AbookApplication

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val library = app.library
        val covers = app.covers
        // Màn chờ giữ tới khi Thư viện có nội dung: khung đầu người dùng thấy đã là lưới bìa, không phải màn trống.
        splash.setKeepOnScreenCondition { library.state.value is LibraryState.Loading }
        val demo = if (BuildConfig.NATIVE_UI) intent.getIntExtra(DEMO_BOOKS, 0) else 0
        if (demo > 0) library.showDemo(demo) else lifecycleScope.launch { library.refresh() }
        setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                val shell = remember { ShellState(scope) }
                val player: NowPlayingModel = remember(demo) {
                    if (demo > 0) FakeNowPlayingModel() else PlaybackNowPlayingModel(applicationContext, scope)
                }
                LaunchedEffect(player) { if (player is PlaybackNowPlayingModel) player.attach() }
                DisposableEffect(player) { onDispose { if (player is PlaybackNowPlayingModel) player.detach() } }
                val state by library.state.collectAsStateWithLifecycle()
                AppShell(shell, state, covers, onFirstContent = ::reportFullyDrawn, nowPlaying = player)
            }
        }
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
