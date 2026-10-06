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
import java.util.concurrent.atomic.AtomicBoolean

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
 * Mọi loa / TV đang phát cho phiên media: điện thoại tự phát trước (nó giữ máy thức vì chúng), không thì máy tính phát
 * ([ComputerCasts]). Lệnh đi theo mã: "cast:…" qua máy tính, còn lại thẳng tới thiết bị.
 */
object CastSessions : CastSource {
    override fun now(): CastNow? = PhoneCast.players.now() ?: ComputerCasts.now()

    override fun send(id: String, command: JSONObject): Any? =
        if (id.startsWith(RemotePlayers.CAST)) ComputerCasts.send(id, command) else PhoneCast.players.send(id, command)

    override fun end(id: String) = if (id.startsWith(RemotePlayers.CAST)) ComputerCasts.end(id) else PhoneCast.players.end(id)
}

/**
 * Giữ điện thoại thức khi nó đang phục vụ audio cho loa / TV: màn hình tắt thì Android ngủ sâu - cổng audio ngừng trả lời
 * giữa chương, hết lượt hỏi thiết bị nên không lưu chỗ nghe, không sang chương sau. Dịch vụ chạy nền (mediaPlayback) có
 * thông báo "Đang phát trên <TV>", giữ khoá CPU + khoá Wi-Fi, và tự dừng khi không còn phiên nào (hỏi mỗi 15 giây).
 *
 * Kèm một phiên media ([CastPlayer], 07-10): màn hình khoá, nút tai nghe / Bluetooth, đồng hồ điều khiển loa / TV như
 * trình phát trong app - phát / dừng, lùi / tới 15 giây, chương trước / sau, phím âm lượng chỉnh loa / TV nếu nó cho.
 * Thông báo dùng kiểu media gắn phiên ấy.
 *
 * Loa / TV máy tính phát ([ComputerCasts], 07-10) cũng có phiên ấy, nhưng dịch vụ chỉ bắt đầu vì chúng khi app đang hiện
 * thanh "Đang phát trên…" (giao diện đang hỏi máy tính), và không giữ khoá nào: điện thoại chỉ gửi lệnh, máy tính phục vụ.
 * Khi giao diện thôi hỏi, dịch vụ tự hỏi máy tính mỗi ~3 giây (lúc máy thức) tới khi máy tính hết phát.
 */
@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
class CastService : Service() {
    private var wake: PowerManager.WakeLock? = null
    private var wifi: WifiManager.WifiLock? = null
    private var player: CastPlayer? = null
    private var session: MediaSession? = null
    private val handler = Handler(Looper.getMainLooper())
    private val asking = AtomicBoolean(false)
    private val tick = object : Runnable {
        override fun run() {
            // Giao diện thôi hỏi máy tính (app ở nền): tự hỏi, một lượt một lúc, ngoài luồng chính.
            if (ComputerCasts.quiet() && asking.compareAndSet(false, true)) {
                Thread {
                    try {
                        ComputerCasts.poll()
                    } finally {
                        asking.set(false)
                    }
                }.start()
            }
            player?.refresh() // vị trí, phát / dừng, chương trên màn hình khoá theo bản chụp mới nhất
            handler.postDelayed(this, 1_000)
        }
    }
    private val check = object : Runnable {
        override fun run() {
            val names = PhoneCast.players.active()
            if (names.isEmpty() && !ComputerCasts.active()) {
                stopSelf()
                return
            }
            hold(names.isNotEmpty())
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(ID, notification(names))
            // Chỉ máy tính phát: hỏi dày hơn để thông báo theo kịp lúc máy tính dừng (không giữ khoá nào nên rẻ).
            handler.postDelayed(this, if (names.isEmpty()) 5_000 else 15_000)
        }
    }

    override fun onCreate() {
        super.onCreate()
        live = this
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "Phát trên loa / TV", NotificationManager.IMPORTANCE_LOW))
        }
        val cast = CastPlayer(CastSessions)
        player = cast
        // Mã riêng: phiên của trình phát trong app (PlaybackService) giữ mã mặc định.
        session = MediaSession.Builder(this, cast).setId("cast").setSessionActivity(openApp()).build()
        val names = PhoneCast.players.active()
        val notification = notification(names)
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
        hold(names.isNotEmpty())
        handler.postDelayed(check, 15_000)
    }

    /**
     * Khoá CPU + khoá Wi-Fi chỉ khi điện thoại phục vụ audio ([on]); loa / TV máy tính phát thì không cần - nhả ra cho đỡ pin.
     */
    @SuppressLint("WakelockTimeout")
    @Suppress("DEPRECATION") // WIFI_MODE_FULL_HIGH_PERF: Wi-Fi không vào chế độ tiết kiệm giữa lúc TV tải chương
    private fun hold(on: Boolean) {
        if (on) {
            if (wake?.isHeld != true) {
                wake = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "abook:cast")
                    .apply { acquire() }
            }
            if (wifi?.isHeld != true) {
                wifi = (applicationContext.getSystemService(WIFI_SERVICE) as WifiManager)
                    .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "abook:cast").apply { acquire() }
            }
        } else {
            wake?.takeIf { it.isHeld }?.release()
            wifi?.takeIf { it.isHeld }?.release()
        }
    }

    /** Hỏi lại ngay: một chuỗi hỏi duy nhất - bỏ lượt hẹn sẵn rồi chạy (nó tự hẹn lượt sau), không chồng chuỗi mới. */
    private fun recheck() {
        handler.post {
            if (live !== this) return@post
            handler.removeCallbacks(check)
            check.run()
        }
    }

    /**
     * Nút trên thông báo (Tạm dừng / Phát tiếp / Dừng) tới đây; lệnh tới thiết bị đi qua mạng nên chạy ngoài luồng chính.
     * Không kèm nút ([start] lần nữa - phiên mới): xem lại ngay danh sách phiên và khoá.
     */
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (action == null) {
            recheck()
            return START_NOT_STICKY
        }
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
            ComputerCasts.now()?.let { now ->
                runCatching {
                    when (action) {
                        ACTION_PAUSE -> if (now.playing) ComputerCasts.send(now.id, CastControls.playPause(false))
                        ACTION_PLAY -> if (!now.playing) ComputerCasts.send(now.id, CastControls.playPause(true))
                        ACTION_STOP -> ComputerCasts.end(now.id)
                    }
                }
            }
            recheck()
        }.start()
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        if (live === this) live = null
        handler.removeCallbacks(check)
        handler.removeCallbacks(tick)
        session?.release()
        session = null
        player?.release()
        player = null
        hold(false)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun openApp(): PendingIntent = PendingIntent.getActivity(this, 0,
        Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE)

    /** [names]: thiết bị điện thoại tự phát; rỗng thì nói về loa / TV máy tính đang phát. */
    private fun notification(names: List<String>): Notification {
        val computer = if (names.isEmpty()) ComputerCasts.now() else null
        val playing = computer?.playing ?: PhoneCast.players.playing().any { it.second }
        val where = computer?.device ?: names.joinToString(", ")
        val toggle = if (playing) ACTION_PAUSE else ACTION_PLAY
        val builder = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(applicationInfo.icon)
            .setContentTitle("${if (playing) "Đang phát" else "Đang dừng"} trên ${where.ifEmpty { "loa / TV" }}")
            .setContentText(if (computer != null) "Máy tính đang phát cuốn này" else "Điện thoại đang phục vụ audio - giữ Wi-Fi bật")
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

        /** Dịch vụ đang chạy (luồng chính ghi). */
        @Volatile
        private var live: CastService? = null

        /** Có phiên mới: bật dịch vụ, hay bảo dịch vụ đang chạy xem lại ngay (giữ khoá nếu giờ điện thoại phục vụ audio). */
        fun start(context: Context) {
            live?.let {
                it.recheck()
                return
            }
            // Android 12+ có thể từ chối bật dịch vụ chạy nền khi app không ở trước mặt: thiếu thông báo, không làm sập app.
            runCatching { ContextCompat.startForegroundService(context, Intent(context, CastService::class.java)) }
        }

        /** Bật dịch vụ nếu chưa chạy (loa / TV máy tính đang phát - gọi mỗi lượt giao diện hỏi, nên không làm gì thêm). */
        fun ensure(context: Context) {
            if (live == null) start(context)
        }
    }
}
