package vn.abook.player

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

/**
 * Giữ ABook sống khi "Cho máy khác nghe thư viện này" bật. Trên ColorOS (OplusHansManager) tiến trình của app bị ĐÓNG BĂNG
 * (cgroup frozen) khoảng 30 giây sau khi rời màn hình - [LibraryServer] (Wi-Fi) và [BluetoothShare] (RFCOMM) vẫn "chạy" mà
 * không trả lời ai, máy tính chờ TLS 45 giây (đo thật 08-10). Đo thật cho thấy dịch vụ này MỘT MÌNH không cứu được ColorOS (vẫn
 * đóng băng dù isForeground=true), receiver ACL_CONNECTED cũng không (không nhận được broadcast nào); Wi-Fi thì gói tin tự mở băng
 * sau ~19 s, Bluetooth thì chỉ mở khi hệ điều hành tình cờ đánh thức (kết nối chờ sẵn xong trong tối đa vài phút). Vẫn giữ dịch vụ:
 * chống bị dọn ở nền trên máy hãng khác, và người dùng thấy chia sẻ đang bật kèm nút tắt.
 * Không giữ khoá CPU / Wi-Fi nào - wake lock cũng không chống được đóng băng (đã thử).
 *
 * Loại `connectedDevice` (Android 14+ bắt khai): dịch vụ này giữ kết nối với thiết bị ngoài qua Bluetooth / mạng. Không dùng
 * `dataSync` (từ Android 15 bị ngắt sau 6 giờ) hay `mediaPlayback` (không phát gì). Loại này đòi app có MỘT trong các quyền
 * điều kiện: manifest khai CHANGE_NETWORK_STATE (quyền thường, cấp lúc cài) nên không phụ thuộc người dùng có cho "Thiết bị ở gần".
 * Quyền thông báo (Android 13+) chỉ quyết định thông báo có hiện trong ngăn kéo không - dịch vụ vẫn chạy nền hợp lệ khi bị từ chối.
 *
 * Bật / tắt đi qua [turnOn] / [turnOff] (công tắc trong app và nút "Tắt chia sẻ" trên thông báo dùng cùng đường).
 */
class ShareService : Service() {
    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "Chia sẻ thư viện", NotificationManager.IMPORTANCE_LOW))
        }
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
            } else {
                startForeground(ID, notification())
            }
        } catch (error: Exception) {
            // Máy từ chối dịch vụ chạy nền: không làm sập app - chia sẻ vẫn chạy, chỉ thiếu phần chống đóng băng.
            stopSelf()
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            // Nút trên thông báo: tắt công tắc như người dùng tắt trong app.
            Thread({ turnOff(applicationContext) }, "share-service-stop").start()
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(this, 0,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, ACTION_STOP.hashCode(),
            Intent(this, ShareService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(applicationInfo.icon)
            .setContentTitle("Đang cho máy khác nghe thư viện này")
            .setContentText("Máy tính hay điện thoại đã ghép nghe được sách trên máy này")
            .setContentIntent(open)
            .addAction(0, "Tắt chia sẻ", stop)
            .setOngoing(true)
            .setSilent(true)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build()
    }

    companion object {
        /** Khoá SyncLink.prefs lưu công tắc "Cho máy khác nghe thư viện này" (LibraryPlugin đọc lại khi mở app). */
        const val SHARE_KEY = "shareLibrary"
        private const val CHANNEL = "share"
        private const val ID = 4208
        private const val ACTION_STOP = "vn.abook.player.share.STOP"

        /** Công tắc đổi từ ngoài giao diện (nút "Tắt chia sẻ" trên thông báo): LibraryPlugin báo màn hình hỏi lại trạng thái. */
        @Volatile
        var changed: (() -> Unit)? = null

        /**
         * Chạy chia sẻ: bật dịch vụ giữ tiến trình rồi mở [LibraryServer] (kéo theo [BluetoothShare]); idempotent. Không ghi
         * công tắc - xem [turnOn]. Chạy ngoài luồng chính. Không bật được dịch vụ (Android 12+ từ chối khi app không ở trước
         * mặt, hay máy khó tính) thì chia sẻ vẫn chạy như trước, chỉ có thể bị đóng băng ở nền.
         */
        fun enable(context: Context) {
            runCatching { ContextCompat.startForegroundService(context, Intent(context, ShareService::class.java)) }
            try {
                LibraryServer.start(context)
            } catch (error: Exception) {
                runCatching { context.stopService(Intent(context, ShareService::class.java)) }
                throw error
            }
        }

        /** Dừng chia sẻ và bỏ dịch vụ + thông báo. */
        fun disable(context: Context) {
            LibraryServer.stop()
            runCatching { context.stopService(Intent(context, ShareService::class.java)) }
        }

        /** Công tắc bật: nhớ lại cho lần mở app sau rồi [enable]. */
        fun turnOn(context: Context) {
            SyncLink.prefs(context).edit().putBoolean(SHARE_KEY, true).commit()
            enable(context)
        }

        /** Công tắc tắt (trong app hay nút "Tắt chia sẻ" trên thông báo). */
        fun turnOff(context: Context) {
            SyncLink.prefs(context).edit().putBoolean(SHARE_KEY, false).commit()
            disable(context)
            changed?.invoke()
        }
    }
}
