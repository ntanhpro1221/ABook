package vn.abook.player

import android.content.Intent
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.widget.Toast
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.getcapacitor.BridgeActivity
import vn.abook.player.readaloud.ReadAloudPlugin
import kotlin.math.roundToInt

/** WebView text zoom (percent) for a system font scale: 1.3 -> 130. */
internal fun textZoomFor(fontScale: Float): Int = (fontScale * 100).roundToInt().coerceIn(50, 300)

private const val SPLASH_MAX_MS = 4000L
private const val SPLASH_FADE_MS = 300L

/** Trang web đầu tiên đã dựng xong (LibraryPlugin.appReady) - màn chờ được mờ đi. */
internal object LaunchSplash {
    @Volatile var ready = false
}

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Mở app (chủ sách 25-10: "giao diện hiện ra từ hư không"): màn chờ giữ tới khi trang đầu đã dựng xong và đứng yên - hết khung chờ,
        // hết hoạt ảnh bố cục (web gọi EbookLibrary.appReady, android/App.tsx useLaunchReady; tối đa 4 s) - rồi MỜ đi, để lộ giao diện hoàn
        // chỉnh. Tắt ngay khi trang vừa tải thì người dùng thấy cả chuỗi dựng: thân trống -> khung chờ -> nội dung mọc dần.
        val splash = installSplashScreen()
        val started = SystemClock.uptimeMillis()
        LaunchSplash.ready = false
        splash.setKeepOnScreenCondition { !LaunchSplash.ready && SystemClock.uptimeMillis() - started < SPLASH_MAX_MS }
        splash.setOnExitAnimationListener { screen ->
            screen.view.animate().alpha(0f).setDuration(SPLASH_FADE_MS).withEndAction { screen.remove() }.start()
        }
        registerPlugin(PlayerPlugin::class.java)
        registerPlugin(LibraryPlugin::class.java)
        registerPlugin(ReadAloudPlugin::class.java)
        super.onCreate(savedInstanceState)
        testOverLock(intent)
        if (savedInstanceState == null) open(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        testOverLock(intent)
        open(intent)
    }

    // Chỉ bản debug, chỉ khi bài thử xin - để chạy kiểm giao diện trên máy khoá có mã mà không cần mở khoá.
    private fun testOverLock(intent: Intent?) {
        if ((applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) == 0 || intent?.getBooleanExtra("abook.test.overLock", false) != true) return
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
    }

    /** "Mở bằng ABook" / chia sẻ một file tới app: file sách nhập vào thư viện, EPUB / DOCX / PDF / TXT mở bước xem trước của
     *  "Thêm sách từ file…" (LibraryPlugin.openFrom). */
    private fun open(intent: Intent?) {
        val uri = IncomingFile.uri(intent)
        if (uri == null) {
            // Chia sẻ chữ trần (vd một đường link) cũng tới đây vì app nhận SEND text/plain cho file .txt: nói rõ thay vì im lặng.
            if (IncomingFile.textOnly(intent)) Toast.makeText(this, IncomingFile.TEXT_ONLY, Toast.LENGTH_LONG).show()
            return
        }
        val plugin = bridge?.getPlugin("EbookLibrary")?.instance as? LibraryPlugin ?: return
        plugin.openFrom(uri, intent?.type)
    }

    // fontScale is in configChanges (AndroidManifest): changing the system text size no longer recreates the activity - which reloaded the WebView,
    // dropped the listener back to the Library and lost the book's speed (a67). The WebView takes the font scale only when it is created, so follow it here.
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        bridge?.webView?.settings?.textZoom = textZoomFor(newConfig.fontScale)
    }

    // Mở app là máy tính thấy điện thoại (để "Phát trên điện thoại" được cả khi chưa nghe gì) - Remote.
    override fun onResume() {
        super.onResume()
        Playback.init(this)
        Remote.foreground = true
        StudioAlerts.checkSoon(this)  // mở app là hỏi máy tính ngay, không đợi lượt 15 phút
    }

    override fun onPause() {
        Remote.foreground = false
        super.onPause()
    }
}
