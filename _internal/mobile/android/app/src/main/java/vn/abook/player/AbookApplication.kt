package vn.abook.player

import android.app.Application

/**
 * Điểm vào của tiến trình (a114): dựng nhật ký bền ([AppLog]) và bắt văng ([CrashLog]) TRƯỚC mọi Activity / Service / Worker, kể cả khi tiến trình
 * được dựng lại chỉ để chạy một việc nền (WorkManager, Media3 sau nút tai nghe). Ghi một dòng "khởi động" kèm phiên bản để đọc nhật ký biết ngay
 * các lần tiến trình mới sinh ra.
 */
class AbookApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        AppLog.init(this)
        CrashLog.install(this)
        AppLog.i("App", "tiến trình khởi động (Android ${android.os.Build.VERSION.SDK_INT}, ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL})")
    }
}
