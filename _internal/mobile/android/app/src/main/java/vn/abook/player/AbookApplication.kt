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

    /** Studio từ xa của giao diện native: các phiên theo máy tính ghép, sống cùng tiến trình (quyền "chỉ nghe" đã biết không phải hỏi lại mỗi lần mở màn). */
    val studio by lazy {
        // Nghe thử trong Studio: clip tải về bộ nhớ đệm (nối lại được), tối đa 50 MB, dọn khi tiến trình khởi động.
        val clips = StudioClips(java.io.File(cacheDir, "studio_clips"), { computer, path, partial -> StudioDownloads.fetch(this, computer, path, partial) }, vn.abook.player.ui.voice.AndroidSamplePlayer(this), uiScope)
        uiScope.launch(Dispatchers.IO) { clips.trim() }
        vn.abook.player.ui.studio.StudioHub(vn.abook.player.ui.studio.StudioRepo(this), uiScope, clips)
    }
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
                openStudio = { computer, route -> deviceLinks.openStudio(computer, route) },
                openAppSettings = { deviceLinks.openAppSettings() },
                askNearby = { result -> deviceLinks.askNearby(result) },
                askNotifications = { then -> deviceLinks.askNotifications(then) },
            ),
            changed = { library.refresh() },
        )
    }

    /**
     * Màn Xuất sách (MP3, M4B, sách nói): một holder cho cả tiến trình - việc xuất chạy ở WorkManager nên sống lâu hơn Activity, holder nghe tin của nó từ lúc dựng nên
     * rời màn rồi quay lại vẫn thấy tiến độ. Việc cần hệ điều hành (chọn thư mục, tạo file, gửi) đi qua [exportLinks] - Activity đang hiện đặt vào đó.
     */
    @Volatile
    var exportLinks = vn.abook.player.ui.export.ExportLinks()

    /** Câu trả lời đang đợi của các hộp hệ thống Activity mở hộ (chọn thư mục, tạo file, xin quyền): sống qua lần Activity dựng lại. */
    val answers = vn.abook.player.ui.PendingAnswers()
    val exports by lazy {
        vn.abook.player.ui.export.ExportState(
            vn.abook.player.ui.export.ExportRepo(this), uiScope,
            vn.abook.player.ui.export.ExportLinks(
                pickFolder = { result -> exportLinks.pickFolder(result) },
                createFile = { title, result -> exportLinks.createFile(title, result) },
                share = { uri, name -> exportLinks.share(uri, name) },
                openAppSettings = { exportLinks.openAppSettings() },
            ),
        )
    }

    /**
     * Giọng đọc làm thêm (giọng tải về máy, khoá giọng trực tuyến, nghe thử, Nhạc của tôi): một holder cho cả tiến trình nên lượt tải giọng đang chạy không mất trạng thái khi
     * Activity dựng lại. Giọng vừa tải / gỡ, khoá vừa dùng được thì danh sách giọng của Cài đặt đọc lại.
     */
    val voice by lazy {
        vn.abook.player.ui.voice.VoiceState(
            voiceRepo, uiScope, vn.abook.player.ui.voice.AndroidSamplePlayer(this), voicesChanged = { settings.loadVoices() }, imports = myMusicImports,
        )
    }
    private val voiceRepo by lazy { vn.abook.player.ui.voice.VoiceRepo(this) }

    /** Thêm nhạc vào Nhạc của tôi: MỘT lượt mỗi lúc cho cả app, Cài đặt > Nhạc của tôi và bảng Nhạc nền cùng thấy, cùng đọc lại kho khi xong. */
    private val myMusicImports by lazy { vn.abook.player.ui.voice.MineImports(voiceRepo, uiScope) }

    /** Nhật ký đêm (thẻ "Tối qua" ở Thư viện, tấm Hẹn giờ nhắc thẻ ấy). */
    val night by lazy { vn.abook.player.ui.data.NightState(vn.abook.player.ui.data.AndroidNightSource(this), uiScope) }

    /** "Làm trước" các chương tới bằng giọng tải về máy: một holder cho cả tiến trình (trình phát và trang sách cùng xem một trạng thái). */
    val prepare by lazy { vn.abook.player.ui.data.PrepareState(vn.abook.player.ui.data.AndroidPrepareSource(this), uiScope) }

    /** Nhạc nền của từng cuốn (bảng ở trình phát và ở trang sách): thêm nhạc đi chung kho và chung lượt với Nhạc của tôi. */
    val music by lazy { vn.abook.player.ui.music.MusicState(vn.abook.player.ui.music.MusicRepo(this), myMusicImports, uiScope) }

    /** Cửa hỏi bạn trước khi đọc bằng giọng trực tuyến chưa được đồng ý (chữ chưa rời máy khi chưa có câu trả lời): trình phát qua nó, Activity vẽ câu hỏi. */
    val consent by lazy { vn.abook.player.ui.voice.ConsentGate(vn.abook.player.ui.voice.AndroidConsentSource(this), uiScope) }

    /** Trình phát của giao diện native: chỉ lắng nghe lõi phát khi Activity hiện ([PlayerRepo.attach]). */
    val player by lazy {
        PlayerRepo(
            AndroidPlaybackCore(this), uiScope, Dispatchers.IO,
            coverOf = LibraryRepo.Companion::coverOf,
            planOf = { id -> Store.init(this); PlayPlan.fromStore(id) },
            lastPlan = { Store.init(this); PlayPlan.fromLast() },
            planAt = { id, chapter, seconds -> Store.init(this); PlayPlan.fromStoreAt(id, chapter, seconds) },
            gate = consent,
        )
    }

    override fun onCreate() {
        super.onCreate()
        AppLog.init(this)
        CrashLog.install(this)
        AppLog.i("App", "tiến trình khởi động (Android ${android.os.Build.VERSION.SDK_INT}, ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL})")
    }
}
