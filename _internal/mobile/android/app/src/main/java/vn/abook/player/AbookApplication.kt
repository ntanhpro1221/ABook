package vn.abook.player

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import vn.abook.player.ui.data.AndroidPlaybackCore
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibraryRepo
import vn.abook.player.ui.data.PlayPlan
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.UiPrefs

/**
 * Điểm vào của tiến trình (a114): dựng nhật ký bền ([AppLog]) và bắt văng ([CrashLog]) TRƯỚC mọi Activity / Service / Worker, kể cả khi tiến trình
 * được dựng lại chỉ để chạy một việc nền (WorkManager, Media3 sau nút tai nghe). Ghi một dòng "khởi động" kèm phiên bản để đọc nhật ký biết ngay
 * các lần tiến trình mới sinh ra.
 */
class AbookApplication : Application() {
    // Giao diện native (vn.abook.player.ui): dựng tay, lười - tiến trình chỉ chạy việc nền / bản WebView không tốn gì.
    val library by lazy { LibraryRepo(this) }
    val covers by lazy { CoverLoader() }
    val uiPrefs by lazy { UiPrefs(this) }
    private val uiScope by lazy { CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate) }

    /** Trình phát của giao diện native: chỉ lắng nghe lõi phát khi Activity hiện ([PlayerRepo.attach]). */
    val player by lazy {
        PlayerRepo(
            AndroidPlaybackCore(this), uiScope, Dispatchers.IO,
            coverOf = LibraryRepo.Companion::coverOf,
            planOf = { id -> Store.init(this); PlayPlan.fromStore(id) },
            lastPlan = { Store.init(this); PlayPlan.fromLast() },
        )
    }

    override fun onCreate() {
        super.onCreate()
        AppLog.init(this)
        CrashLog.install(this)
        AppLog.i("App", "tiến trình khởi động (Android ${android.os.Build.VERSION.SDK_INT}, ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL})")
    }
}
