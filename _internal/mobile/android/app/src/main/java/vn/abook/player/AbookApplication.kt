package vn.abook.player

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import vn.abook.player.ui.data.AndroidPlaybackCore
import vn.abook.player.ui.data.AndroidSettingsCore
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibraryRepo
import vn.abook.player.ui.data.PlayPlan
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.UiPrefs

/**
 * Điểm vào của tiến trình (a114): dựng nhật ký bền ([AppLog]) và bắt văng ([CrashLog]) TRƯỚC mọi Activity / Service / Worker, kể cả khi tiến trình
 * được dựng lại chỉ để chạy một việc nền (WorkManager, Media3 sau nút tai nghe). Ghi một dòng "khởi động" kèm phiên bản để đọc nhật ký biết ngay
 * các lần tiến trình mới sinh ra.
 */
class AbookApplication : Application() {
    val imports by lazy { vn.abook.player.ui.addbook.ImportQueue(vn.abook.player.ui.addbook.ImportRepo(this), uiScope) { library.refresh() } }
    val editors by lazy {
        val repository = vn.abook.player.ui.editbook.EditBookRepo(this, library)
        val editors = vn.abook.player.ui.editbook.EditBooks(repository, uiScope)
        EditsSync.refresh = repository::refreshFromHolder
        EditsSync.changed = { id -> uiScope.launch { editors.refresh(id); library.refresh() } }
        editors
    }
    // Giao diện native (vn.abook.player.ui): dựng tay, lười - tiến trình chỉ chạy việc nền / bản WebView không tốn gì.
    val library by lazy { LibraryRepo(this, uiScope) { id -> player.bookRemoved(id) } }
    val companion by lazy { vn.abook.player.ui.devices.CompanionRepo(vn.abook.player.ui.devices.AndroidCompanionCore(this)) }
    val covers by lazy { CoverLoader() }
    val uiPrefs by lazy { UiPrefs(this) }

    /** Cài đặt của giao diện native: cùng kho với bản WebView ([AndroidSettingsCore]). */
    val settings by lazy { SettingsRepo(AndroidSettingsCore(this), uiScope, Dispatchers.IO) }
    private val uiScope by lazy { CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate) }

    /**
     * Ba màn Thiết bị (Nối máy tính, Chia sẻ thư viện, Dung lượng): một holder cho cả tiến trình, nên lượt tải đang chạy không mất trạng thái khi Activity dựng lại.
     * Việc cần hệ điều hành (quyền, mở Studio) đi qua [deviceLinks] - Activity đang hiện đặt vào đó.
     */
    @Volatile
    var deviceLinks = vn.abook.player.ui.devices.DeviceLinks()
    val devices by lazy {
        vn.abook.player.ui.devices.DevicesState(
            vn.abook.player.ui.devices.DevicesRepo(this, library), uiScope,
            vn.abook.player.ui.devices.DeviceLinks(
                openStudio = { computer, path -> deviceLinks.openStudio(computer, path) },
                openAppSettings = { deviceLinks.openAppSettings() },
                askNearby = { result -> deviceLinks.askNearby(result) },
                askNotifications = { then -> deviceLinks.askNotifications(then) },
            ),
            changed = { library.refresh() },
        )
    }

    /**
     * Giọng đọc làm thêm (giọng tải về máy, khóa giọng trực tuyến, nghe thử, Nhạc của tôi): một holder cho cả tiến trình nên lượt tải giọng đang chạy không mất trạng thái khi
     * Activity dựng lại. Giọng vừa tải / gỡ, khóa vừa dùng được thì danh sách giọng của Cài đặt đọc lại.
     */
    val voice by lazy {
        vn.abook.player.ui.voice.VoiceState(
            vn.abook.player.ui.voice.VoiceRepo(this), uiScope, vn.abook.player.ui.voice.AndroidSamplePlayer(this), voicesChanged = { settings.loadVoices() },
        )
    }

    /** Nhạc nền của từng cuốn (bảng ở trình phát và ở trang sách): thêm nhạc đi chung kho với Nhạc của tôi. */
    val music by lazy { vn.abook.player.ui.music.MusicState(vn.abook.player.ui.music.MusicRepo(this, vn.abook.player.ui.voice.VoiceRepo(this)), uiScope) }

    /** Trình phát của giao diện native: chỉ lắng nghe lõi phát khi Activity hiện ([PlayerRepo.attach]). */
    val player by lazy {
        PlayerRepo(
            AndroidPlaybackCore(this), uiScope, Dispatchers.IO,
            coverOf = LibraryRepo.Companion::coverOf,
            planOf = { id -> Store.init(this); PlayPlan.fromStore(id) },
            lastPlan = { Store.init(this); PlayPlan.fromLast() },
            planAt = { id, chapter, seconds -> Store.init(this); PlayPlan.fromStoreAt(id, chapter, seconds) },
        )
    }

    override fun onCreate() {
        super.onCreate()
        AppLog.init(this)
        CrashLog.install(this)
        AppLog.i("App", "tiến trình khởi động (Android ${android.os.Build.VERSION.SDK_INT}, ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL})")
    }
}
