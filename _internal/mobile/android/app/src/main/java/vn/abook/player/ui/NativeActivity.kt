package vn.abook.player.ui

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import vn.abook.player.StudioActivity
import vn.abook.player.ui.devices.DeviceLinks
import vn.abook.player.ui.export.ExportLinks
import vn.abook.player.M4bExports
import vn.abook.player.Mp3Exports
import android.content.ClipData
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
import vn.abook.player.ui.data.DemoPlaybackCore
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.nowplaying.AndroidReadAlongSource
import vn.abook.player.ui.nowplaying.DemoReadAlongSource
import vn.abook.player.ui.nowplaying.rememberRepoNowPlaying
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
    private lateinit var player: PlayerRepo

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val library = app.library
        val covers = app.covers
        val demoBooks = if (BuildConfig.NATIVE_UI) intent.getIntExtra(DEMO_BOOKS, 0) else 0
        demo = demoBooks > 0
        // Chế độ đo: cùng đường thật (PlayerRepo -> cửa sổ Đang nghe) nhưng nguồn là một cuốn giả, không chạm lõi phát thật.
        player = if (demo) PlayerRepo(DemoPlaybackCore(), lifecycleScope, Dispatchers.IO, { null }, { null }) else app.player
        val readAlong = if (demo) DemoReadAlongSource else AndroidReadAlongSource(this)
        val prefs = app.uiPrefs
        val settings = app.settings
        if (!demo) app.deviceLinks = deviceLinks
        if (!demo) app.exportLinks = exportLinks
        // Màn chờ giữ tới khi Thư viện có nội dung VÀ đã biết giao diện sáng / tối của bạn: khung đầu đã là lưới bìa đúng màu, không phải màn trống hay
        // màn đổi màu ngay sau khi hiện. Hai lần đọc chạy song song ở luồng nền.
        splash.setKeepOnScreenCondition { library.state.value is LibraryState.Loading || !settings.loaded.value }
        lifecycleScope.launch { settings.load() }
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
        if (!demo) lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                vn.abook.player.StudioAlerts.checkSoon(this@NativeActivity)
                launch {
                    while (true) {
                        app.companion.refresh()
                        delay(if (app.companion.state.value.players.any { it.playing }) 2_000 else 8_000)
                    }
                }
                launch {
                    while (true) {
                        app.devices.syncStreamed()
                        delay(8_000)
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
                    val env = remember { SettingsEnv(settings, reveal, links, if (demo) null else app.devices, if (demo) null else app.voice, if (demo) null else app.music) }
                    LaunchedEffect(Unit) { shell.library.restoreSort(withContext(Dispatchers.IO) { prefs.sort() }) }
                    val state by library.state.collectAsStateWithLifecycle()
                    AppShell(
                        shell, state, player, covers, env, onFirstContent = ::onFirstContent, books = library, deletions = library.deletions, companion = if (demo) null else app.companion,
                        nowPlaying = rememberRepoNowPlaying(player, readAlong, env.music),
                        imports = app.imports, editors = app.editors, exports = if (demo) null else app.exports, demo = demo, askNotifications = deviceLinks.askNotifications, autoPick = !demo,
                    )
                }
            }
        }
    }

    private var nearbyResult: ((Boolean) -> Unit)? = null
    private val nearby = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        nearbyResult?.invoke(granted)
        nearbyResult = null
    }
    private var notificationsThen: (() -> Unit)? = null
    private val notifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        // Từ chối thông báo thì chia sẻ vẫn chạy (chỉ không có thông báo "Tắt chia sẻ").
        notificationsThen?.invoke()
        notificationsThen = null
    }

    /** Cửa ra hệ điều hành của ba màn Thiết bị: Studio của máy tính, trang thông tin ứng dụng, quyền "Thiết bị ở gần" và thông báo. */
    private val deviceLinks = DeviceLinks(
        openStudio = { computer, path -> open(Intent(this, StudioActivity::class.java).putExtra("computer", computer).putExtra("path", path)) },
        openAppSettings = { open(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) },
        askNearby = { result ->
            if (Build.VERSION.SDK_INT < 31) {
                result(true)
            } else {
                nearbyResult = result
                nearby.launch(Manifest.permission.BLUETOOTH_CONNECT)
            }
        },
        askNotifications = { then ->
            if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                notificationsThen = then
                notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                then()
            }
        },
    )

    private var pickFolderResult: ((String?) -> Unit)? = null
    private val pickFolder = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        pickFolderResult?.invoke(result.data?.data?.takeIf { result.resultCode == RESULT_OK }?.toString())
        pickFolderResult = null
    }
    private var createFileResult: ((String?) -> Unit)? = null
    private val createFile = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        createFileResult?.invoke(result.data?.data?.takeIf { result.resultCode == RESULT_OK }?.toString())
        createFileResult = null
    }

    /** Cửa ra hệ điều hành của màn Xuất sách: bộ chọn thư mục MP3, hộp "tạo file" của M4B và sách nói, bảng chia sẻ file vừa xuất, trang thông tin ứng dụng. */
    private val exportLinks = ExportLinks(
        pickFolder = { result ->
            pickFolderResult = result
            pickFolder.launch(Mp3Exports.pickIntent(this))
        },
        createFile = { title, result ->
            createFileResult = result
            createFile.launch(M4bExports.createIntent(title))
        },
        share = ::shareExport,
        openAppSettings = { open(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) },
    )

    /** Gửi file vừa xuất cho app khác qua bảng chia sẻ của hệ thống (quyền đọc đi kèm); máy không gửi được thì false. */
    private fun shareExport(uri: String, name: String): Boolean = try {
        val file = Uri.parse(uri)
        val send = Intent(Intent.ACTION_SEND).setType(M4bExports.MIME).putExtra(Intent.EXTRA_STREAM, file).putExtra(Intent.EXTRA_TITLE, name)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        send.clipData = ClipData.newRawUri(name, file)
        startActivity(Intent.createChooser(send, null))
        true
    } catch (error: ActivityNotFoundException) {
        false
    } catch (error: SecurityException) {
        false
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
        if (started) player.attach()
        // Lượt tải còn giữ, chia sẻ đã bật từ lần trước, sách nghe thẳng của máy đã ghép: sau khung đầu, không nằm trong đường mở nguội.
        if (!demo) app.devices.apply { restore(); syncStreamed() }
    }

    override fun onStart() {
        super.onStart()
        started = true
        if (contentReady) player.attach()
    }

    override fun onStop() {
        super.onStop()
        started = false
        player.detach()
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        // Giao diện đã ẩn (phát nền): trả bộ nhớ bìa ngay (ngân sách RAM phát nền, NATIVE_PHONE_UI.md §1).
        if (level >= ComponentCallbacks2.TRIM_MEMORY_UI_HIDDEN) app.covers.trim()
    }

    override fun onDestroy() {
        // Application sống lâu hơn Activity (phát nền sau khi bạn bấm Back): gỡ cầu nối của Activity này, không giữ cả cây Compose đã huỷ.
        if (app.deviceLinks === deviceLinks) app.deviceLinks = DeviceLinks()
        if (app.exportLinks === exportLinks) app.exportLinks = ExportLinks()
        super.onDestroy()
    }

    companion object {
        /** Extra của Intent: số sách giả thay Thư viện thật (đo đạc, chỉ bản -PnativeUi). */
        const val DEMO_BOOKS = "abook.demo.books"

        /** "Mã nguồn mở" (Cài đặt > Nâng cao): trang của ABook trên GitHub - địa chỉ cố định, không nhận từ đâu. */
        const val SOURCE_URL = "https://github.com/ntanhpro1221/ABook/"
    }
}
