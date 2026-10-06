package vn.abook.player

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaStyleNotificationHelper
import org.json.JSONObject

/**
 * Điện thoại phát sách CỦA NÓ lên loa / TV DLNA và Chromecast / Google TV / loa Nest (01-10, Cast 02-10): [DlnaPlayers] với
 * sách lấy từ Store (chỉ sách ĐÃ CÓ trên máy - tải về, mở file .abook; chương phải có file thật) và chỗ nghe ghi vào đúng
 * hồ sơ như trình phát trong app. Sách nghe thẳng từ máy tính không ở đây - máy tính phát (RemotePlayers, mã "cast:").
 */
object PhoneCast {
    private lateinit var appContext: Context

    fun init(context: Context) {
        if (!::appContext.isInitialized) appContext = context.applicationContext
    }

    val players: DlnaPlayers by lazy {
        DlnaPlayers(
            book = ::book,
            save = { id, chapter, seconds, duration -> Store.progress(id, chapter, seconds, duration) },
            findGoogle = { GCast.discover() }, // Chromecast, Google TV, loa Nest (mDNS - trả lời về thẳng, không cần MulticastLock)
            onSession = { CastService.start(appContext) },
        )
    }

    /** Sách đã có trên điện thoại, chỉ các chương có file audio thật; null khi không có (chưa tải, nghe thẳng). */
    fun book(id: String): DlnaPlayers.Book? {
        val manifest = Store.manifest(id) ?: return null
        val chapters = manifest.optJSONArray("chapters") ?: return null
        val list = (0 until chapters.length()).mapNotNull { index ->
            val chapter = chapters.optJSONObject(index) ?: return@mapNotNull null
            val relative = chapter.optString("file").takeIf { it.isNotEmpty() && chapter.optBoolean("available", true) }
                ?: return@mapNotNull null
            val file = runCatching { Store.file(id, relative) }.getOrNull()?.takeIf { it.isFile } ?: return@mapNotNull null
            DlnaPlayers.Chapter(chapter.getInt("id"), chapter.optString("fullTitle").ifEmpty { chapter.optString("title") },
                chapter.optDouble("duration", 0.0), file)
        }
        return if (list.isEmpty()) null else DlnaPlayers.Book(manifest.optString("title"), list)
    }
}

/**
 * Giữ điện thoại thức khi nó đang phục vụ audio cho loa / TV: màn hình tắt thì Android ngủ sâu - cổng audio ngừng trả lời
 * giữa chương, hết lượt hỏi thiết bị nên không lưu chỗ nghe, không sang chương sau. Dịch vụ chạy nền (mediaPlayback) có
 * thông báo "Đang phát trên <TV>", giữ khoá CPU + khoá Wi-Fi, và tự dừng khi không còn phiên nào (hỏi mỗi 15 giây).
 *
 * Kèm một phiên media ([CastPlayer], 07-10): màn hình khoá, nút tai nghe / Bluetooth, đồng hồ điều khiển loa / TV như
 * trình phát trong app - phát / dừng, lùi / tới 15 giây, chương trước / sau. Thông báo dùng kiểu media gắn phiên ấy.
 */
@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
class CastService : Service() {
    private var wake: PowerManager.WakeLock? = null
    private var wifi: WifiManager.WifiLock? = null
    private var player: CastPlayer? = null
    private var session: MediaSession? = null
    private val handler = Handler(Looper.getMainLooper())
    private val tick = object : Runnable {
        override fun run() {
            player?.refresh() // vị trí, phát / dừng, chương trên màn hình khoá theo bản chụp mới nhất
            handler.postDelayed(this, 1_000)
        }
    }
    private val check = object : Runnable {
        override fun run() {
            val names = PhoneCast.players.active()
            if (names.isEmpty()) {
                stopSelf()
                return
            }
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(ID, notification(names))
            handler.postDelayed(this, 15_000)
        }
    }

    @SuppressLint("WakelockTimeout")
    @Suppress("DEPRECATION") // WIFI_MODE_FULL_HIGH_PERF: Wi-Fi không vào chế độ tiết kiệm giữa lúc TV tải chương
    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "Phát trên loa / TV", NotificationManager.IMPORTANCE_LOW))
        }
        val cast = CastPlayer(PhoneCast.players)
        player = cast
        // Mã riêng: phiên của trình phát trong app (PlaybackService) giữ mã mặc định.
        session = MediaSession.Builder(this, cast).setId("cast").setSessionActivity(openApp()).build()
        val notification = notification(PhoneCast.players.active())
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
            } else {
                startForeground(ID, notification)
            }
        } catch (error: Exception) {
            // Máy từ chối dịch vụ chạy nền (đời Android / hãng khó tính): không bao giờ làm sập app - loa vẫn phát, chỉ thiếu
            // phần giữ máy thức khi tắt màn hình.
            stopSelf()
            return
        }
        handler.post(tick)
        wake = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "abook:cast")
            .apply { acquire() }
        wifi = (applicationContext.getSystemService(WIFI_SERVICE) as WifiManager)
            .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "abook:cast").apply { acquire() }
        handler.postDelayed(check, 15_000)
    }

    /** Nút trên thông báo (Tạm dừng / Phát tiếp / Dừng) tới đây; lệnh tới thiết bị đi qua mạng nên chạy ngoài luồng chính. */
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action ?: return START_NOT_STICKY
        Thread {
            val players = PhoneCast.players
            for ((id, playing) in players.playing()) {
                runCatching {
                    when (action) {
                        ACTION_PAUSE -> if (playing) players.send(id, JSONObject().put("action", "pause"))
                        ACTION_PLAY -> if (!playing) players.send(id, JSONObject().put("action", "play"))
                        ACTION_STOP -> players.end(id)
                    }
                }
            }
            // Một chuỗi hỏi duy nhất: bỏ lượt hẹn sẵn rồi chạy ngay (nó tự hẹn lượt sau) - không chồng thêm chuỗi mới.
            handler.post {
                handler.removeCallbacks(check)
                check.run()
            }
        }.start()
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(check)
        handler.removeCallbacks(tick)
        session?.release()
        session = null
        player?.release()
        player = null
        wake?.takeIf { it.isHeld }?.release()
        wifi?.takeIf { it.isHeld }?.release()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun openApp(): PendingIntent = PendingIntent.getActivity(this, 0,
        Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE)

    private fun notification(names: List<String>): Notification {
        val playing = PhoneCast.players.playing().any { it.second }
        val toggle = if (playing) ACTION_PAUSE else ACTION_PLAY
        val builder = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(applicationInfo.icon)
            .setContentTitle("${if (playing) "Đang phát" else "Đang dừng"} trên ${names.joinToString(", ").ifEmpty { "loa / TV" }}")
            .setContentText("Điện thoại đang phục vụ audio - giữ Wi-Fi bật")
            .setContentIntent(openApp())
            .addAction(0, if (playing) "Tạm dừng" else "Phát tiếp", command(toggle))
            .addAction(0, "Dừng", command(ACTION_STOP))
            .setOngoing(true)
            .setSilent(true)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
        // Kiểu media gắn phiên: điều khiển hiện ở màn hình khoá và khung media của hệ thống.
        session?.let { builder.setStyle(MediaStyleNotificationHelper.MediaStyle(it).setShowActionsInCompactView(0, 1)) }
        return builder.build()
    }

    private fun command(action: String): PendingIntent = PendingIntent.getService(this, action.hashCode(),
        Intent(this, CastService::class.java).setAction(action), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    companion object {
        private const val CHANNEL = "cast"
        private const val ID = 4207
        private const val ACTION_PAUSE = "vn.abook.player.cast.PAUSE"
        private const val ACTION_PLAY = "vn.abook.player.cast.PLAY"
        private const val ACTION_STOP = "vn.abook.player.cast.STOP"

        fun start(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, CastService::class.java))
        }
    }
}
