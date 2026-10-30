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
import android.widget.Toast
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
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.AbookApplication
import vn.abook.player.AppLog
import vn.abook.player.BuildConfig
import vn.abook.player.Diagnostics
import vn.abook.player.IncomingFile
import vn.abook.player.ui.data.DemoPlaybackCore
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.nowplaying.AndroidReadAlongSource
import vn.abook.player.ui.nowplaying.DemoReadAlongSource
import vn.abook.player.ui.nowplaying.rememberRepoNowPlaying
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsLinks
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.pip.PipControl
import vn.abook.player.ui.pip.PipParams
import vn.abook.player.ui.pip.PipSupport
import vn.abook.player.ui.shell.ShellState
import androidx.compose.ui.text.font.createFontFamilyResolver
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.BeVietnamPro
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
    private lateinit var pip: PipControl

    /** Android 8-11: chính app vừa mở một Activity khác (chọn file, Studio, bảng chia sẻ, hộp xin quyền) - [onUserLeaveHint] cũng nổ ở đó nhưng không phải bạn rời app. */
    private var openedByApp = false

    /** File app khác gửi tới ("Mở bằng", chia sẻ) chờ khung vẽ xong để vào hàng nhập sách ([ShellState.receive]); mở nguội thì khung chưa có, nên cần chỗ đợi. */
    private val incoming = Channel<List<String>>(Channel.UNLIMITED)

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // Phông Be Vietnam Pro nạp ngay ở luồng nền (bộ nhớ phông dùng chung với Compose): lần dàn chữ đầu tiên của khung đầu khỏi tự nạp từng độ đậm ở luồng chính.
        lifecycleScope.launch(Dispatchers.Default) { createFontFamilyResolver(applicationContext).preload(BeVietnamPro) }
        val library = app.library
        val covers = app.covers
        val demoBooks = if (BuildConfig.NATIVE_UI) intent.getIntExtra(DEMO_BOOKS, 0) else 0
        demo = demoBooks > 0
        if (savedInstanceState == null) receive(intent)
        // Chế độ đo: cùng đường thật (PlayerRepo -> cửa sổ Đang nghe) nhưng nguồn là một cuốn giả, không chạm lõi phát thật.
        player = if (demo) PlayerRepo(DemoPlaybackCore(), lifecycleScope, Dispatchers.IO, { null }, { null }) else app.player
        val readAlong = if (demo) DemoReadAlongSource else AndroidReadAlongSource(this)
        val prefs = app.uiPrefs
        val settings = app.settings
        pip = PipControl(PipSupport.available(this)) { enterPip() }
        if (pip.available) {
            addOnPictureInPictureModeChangedListener { info -> pip.active = info.isInPictureInPictureMode }
            // Params của PiP luôn khớp trạng thái phát: nút Phát / Tạm dừng đổi theo, và tự vào PiP chỉ khi có sách mở + công tắc bật (Android 12+ hệ thống tự vào, nên phải đặt trước khi bạn rời app).
            lifecycleScope.launch {
                combine(
                    player.state.map { it.hasTrack to it.playing }.distinctUntilChanged(), settings.state.map { it.autoPip }.distinctUntilChanged(),
                ) { track, on -> PipParams.plan(playing = track.second, hasBook = track.first, switchOn = on) }
                    .distinctUntilChanged().collect { plan ->
                        try {
                            setPictureInPictureParams(PipParams.build(this@NativeActivity, plan))
                        } catch (error: IllegalStateException) {
                            AppLog.w("Pip", "không đặt được thông số cửa sổ nhỏ: ${error.javaClass.simpleName}")
                        }
                    }
            }
        }
        if (!demo) app.deviceLinks = deviceLinks
        if (!demo) app.exportLinks = exportLinks
        if (!demo) lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                player.state.map { it.playing }.distinctUntilChanged().collect { playing ->
                    if (playing) settings.offerNotifications { deviceLinks.askNotifications {} }
                }
            }
        }
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
                    val env = remember { SettingsEnv(settings, reveal, links, if (demo) null else app.devices, if (demo) null else app.voice, if (demo) null else app.music, pip, if (demo) null else app.prepare, if (demo) null else app.night) }
                    LaunchedEffect(shell) { for (files in incoming) shell.receive(app.imports, files) }
                    LaunchedEffect(Unit) { shell.library.restoreSort(withContext(Dispatchers.IO) { prefs.sort() }) }
                    // Dáng chữ của Đọc theo: đọc một lần lúc mở app, ghi mỗi khi người nghe đổi.
                    LaunchedEffect(shell) {
                        shell.window.look = withContext(Dispatchers.IO) { prefs.readLook() }
                        shell.window.onLook = { look -> lifecycleScope.launch(Dispatchers.IO) { prefs.setReadLook(look) } }
                    }
                    val state by library.state.collectAsStateWithLifecycle()
                    // Thư viện dưới dạng danh sách cuốn cho Đang nghe: lời "Đã nghe hết ..." mời cuốn kế, và hỏi khi máy khác đã nghe xa hơn.
                    val bookList = remember(library) {
                        library.state.map { (it as? vn.abook.player.ui.data.LibraryState.Ready)?.books.orEmpty() }
                            .stateIn(scope, kotlinx.coroutines.flow.SharingStarted.Eagerly, emptyList())
                    }
                    AppShell(
                        shell, state, player, covers, env, onFirstContent = ::onFirstContent, books = library, deletions = library.deletions, companion = if (demo) null else app.companion,
                        nowPlaying = rememberRepoNowPlaying(player, readAlong, env.music, env.voice, bookList, env.prepare, env.night),
                        imports = app.imports, editors = app.editors, exports = if (demo) null else app.exports, demo = demo, askNotifications = deviceLinks.askNotifications, autoPick = !demo,
                        pip = pip,
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        receive(intent)
    }

    /** "Mở bằng ABook" / chia sẻ một file tới app (cùng cách lấy địa chỉ với MainActivity): vào hàng nhập sách như file chọn từ "Thêm sách". */
    private fun receive(intent: Intent?) {
        if (demo || intent == null) return
        val uri = IncomingFile.uri(intent)
        if (uri == null) {
            if (IncomingFile.textOnly(intent)) Toast.makeText(this, IncomingFile.TEXT_ONLY, Toast.LENGTH_LONG).show()
            return
        }
        runCatching { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        incoming.trySend(listOf(uri.toString()))
    }

    // Nơi đang đợi câu trả lời của các hộp hệ thống nằm ở Application ([PendingAnswers]): Activity bị huỷ lúc hộp còn mở thì Activity mới vẫn giao được.
    private val nearby = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> app.answers.nearby.deliver(granted) }
    // Từ chối thông báo thì chia sẻ vẫn chạy (chỉ không có thông báo "Tắt chia sẻ").
    private val notifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { app.answers.notifications.deliver(Unit) }

    /** Cửa ra hệ điều hành của ba màn Thiết bị: Studio của máy tính, trang thông tin ứng dụng, quyền "Thiết bị ở gần" và thông báo. */
    private val deviceLinks = DeviceLinks(
        openStudio = { computer, path -> open(Intent(this, StudioActivity::class.java).putExtra("computer", computer).putExtra("path", path)) },
        openAppSettings = { open(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) },
        askNearby = { result ->
            if (Build.VERSION.SDK_INT < 31) {
                result(true)
            } else {
                app.answers.nearby.expect(result)
                openedByApp = true
                nearby.launch(Manifest.permission.BLUETOOTH_CONNECT)
            }
        },
        askNotifications = { then ->
            if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                app.answers.notifications.expect { then() }
                openedByApp = true
                notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                then()
            }
        },
        copyText = { text ->
            val clipboard = getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
            clipboard != null && runCatching { clipboard.setPrimaryClip(ClipData.newPlainText("ABook", text)) }.isSuccess
        },
        openRelease = { url -> if (url.startsWith(SOURCE_URL)) open(Intent(Intent.ACTION_VIEW, Uri.parse(url))) },
    )

    private val pickFolder = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        app.answers.folder.deliver(result.data?.data?.takeIf { result.resultCode == RESULT_OK }?.toString())
    }
    private val createFile = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        app.answers.file.deliver(result.data?.data?.takeIf { result.resultCode == RESULT_OK }?.toString())
    }

    /** Cửa ra hệ điều hành của màn Xuất sách: bộ chọn thư mục MP3, hộp "tạo file" của M4B và sách nói, bảng chia sẻ file vừa xuất, trang thông tin ứng dụng. */
    private val exportLinks = ExportLinks(
        pickFolder = { result ->
            app.answers.folder.expect(result)
            pickFolder.launch(Mp3Exports.pickIntent(this))
        },
        createFile = { title, result ->
            app.answers.file.expect(result)
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
        openRelease = { url ->
            if (url.startsWith("https://github.com/ntanhpro1221/ABook/")) open(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        },
        saveOld = { name, result ->
            app.answers.file.expect(result)
            createFile.launch(Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType(vn.abook.player.OldSaves.mimeOf(name)).putExtra(Intent.EXTRA_TITLE, name))
        },
    )

    private fun open(intent: Intent) {
        try {
            startActivity(intent)
        } catch (error: ActivityNotFoundException) {
            AppLog.w("Settings", "máy không mở được ${intent.action}")
            app.settings.problem.value = "Không mở được trình duyệt"
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
                    app.settings.problem.value = "Chưa gửi được nhật ký"
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
        if (!demo) {
            app.settings.openRelease = links.openRelease
            app.settings.loadMaintenance()
        }
    }

    /** Vào cửa sổ nhỏ (PiP) ngay: nút "Cửa sổ mini" của Đang nghe, và [onUserLeaveHint] trên Android 8-11. */
    private fun enterPip() {
        if (!pip.available) return
        try {
            enterPictureInPictureMode(PipParams.build(this, currentPipPlan()))
        } catch (error: IllegalStateException) {
            AppLog.w("Pip", "không vào được cửa sổ nhỏ: ${error.javaClass.simpleName}")
        }
    }

    private fun currentPipPlan() = player.state.value.let { PipParams.plan(it.playing, it.hasTrack, app.settings.state.value.autoPip) }

    // Android 12+ tự vào PiP nhờ setAutoEnterEnabled (PipParams); 8-11 thì gọi tay ở đây khi bạn rời app (Home / vuốt).
    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S && pip.available && !openedByApp && !isInPictureInPictureMode && currentPipPlan().autoEnter) enterPip()
    }

    @Suppress("DEPRECATION")
    override fun startActivityForResult(intent: Intent, requestCode: Int, options: Bundle?) {
        openedByApp = true
        super.startActivityForResult(intent, requestCode, options)
    }

    override fun onStart() {
        super.onStart()
        started = true
        openedByApp = false
        pip.active = pip.available && isInPictureInPictureMode
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
