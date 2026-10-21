package vn.abook.player.readaloud

import android.annotation.SuppressLint
import android.content.Context
import android.net.wifi.WifiManager
import android.os.PowerManager

/**
 * Giữ CPU + Wi-Fi thức trong lúc đang đi lấy một clip mà người nghe ĐANG CHỜ (soát a47 mục 6): hàng đợi ExoPlayer cạn (Edge chậm) thì nó ở STATE_ENDED và nhả hết khoá của nó
 * (WAKE_MODE_NETWORK chỉ giữ khi READY / BUFFERING), dịch vụ chỉ còn là dịch vụ nền - tắt màn hình thì CPU / Wi-Fi có thể ngủ giữa lượt gọi Edge hay quãng nghỉ thử lại và giọng im
 * tới khi người nghe bấm lại. Khoá chỉ giữ khi có một lượt lấy clip người nghe đang chờ ([hold]), nhả ngay khi xong, khi người nghe tạm dừng / tua / dừng ([release]); đồng hồ an toàn
 * [TIMEOUT_MS] tự nhả nếu có chỗ quên. Đếm số lượt đang giữ: lượt cũ nhả muộn không nhả hộ lượt mới. Chạy được trong test JVM (khoá do `factory` tạo).
 * Giọng trên máy (gap2) cũng giữ, chỉ khoá CPU: hàng đợi cạn mà màn tắt thì không gì giữ CPU thức trong lúc đọc đoạn người nghe đang chờ - chưa đo trên máy thật.
 */
object FetchWake {
    /** Một lượt lấy clip tối đa ~20 giây thử lại + lần đầu tới 45 giây ([ClipBudget]); quá chừng này là có gì quên - tự nhả. */
    const val TIMEOUT_MS = 90_000L

    /** Hai khoá thật (CPU, Wi-Fi). `acquire(ms, network)` giữ CPU tối đa `ms`, `network` thì cả Wi-Fi; `release()` nhả cả hai. */
    interface Locks {
        fun acquire(timeoutMs: Long, network: Boolean)
        fun release()
    }

    private var appContext: Context? = null

    /** Gọi một lần lúc khởi động ([ReadAloud.init]). */
    @Synchronized
    fun init(context: Context) {
        appContext = context.applicationContext
    }

    /** Nơi tạo khoá thật; bài thử thay bằng khoá giả (đổi nhà máy thì bỏ khoá đã tạo). */
    internal var factory: () -> Locks? = { appContext?.let(::systemLocks) }
        @Synchronized set(value) {
            field = value
            locks = null
        }

    private var locks: Locks? = null
    private var holders = 0
    private var epoch = 0 // [releaseAll] sang đợt mới: [release] của lượt thuộc đợt cũ thành không-làm-gì
    private var timeout: java.util.concurrent.ScheduledFuture<*>? = null
    private val timer by lazy { java.util.concurrent.Executors.newSingleThreadScheduledExecutor { Thread(it, "clip-fetch-wake").apply { isDaemon = true } } }

    /** Bắt đầu một lượt lấy clip người nghe chờ: giữ khoá (làm mới đồng hồ hẹn nhả nếu đã giữ). Giọng trên máy ([network] false): chỉ CPU. Trả "vé" cho [release] của chính lượt này. */
    @Synchronized
    fun hold(network: Boolean = true): Int {
        val current = locks ?: runCatching { factory() }.getOrNull()?.also { locks = it } ?: return epoch
        holders += 1
        runCatching { current.acquire(TIMEOUT_MS, network) }
        // Khoá Wi-Fi không có hạn giờ riêng: đồng hồ chung nhả cả hai nếu có chỗ quên [release].
        timeout?.cancel(false)
        timeout = runCatching { timer.schedule({ releaseAll() }, TIMEOUT_MS, java.util.concurrent.TimeUnit.MILLISECONDS) }.getOrNull()
        return epoch
    }

    /** Hết lượt đó (xong, hỏng, bị bỏ; `ticket` = giá trị [hold] trả): nhả khi không còn lượt nào giữ. Vé của đợt đã [releaseAll] thì bỏ qua. */
    @Synchronized
    fun release(ticket: Int) {
        if (ticket != epoch || holders == 0) return
        holders -= 1
        if (holders == 0) {
            timeout?.cancel(false)
            runCatching { locks?.release() }
        }
    }

    /** Nhả hết (người nghe tạm dừng / dừng / tua đi chỗ khác): các lượt đang chạy sẽ tự bỏ khi phát hiện việc đã cũ, [release] của chúng (vé cũ) thành không-làm-gì. */
    @Synchronized
    fun releaseAll() {
        epoch += 1
        holders = 0
        timeout?.cancel(false)
        runCatching { locks?.release() }
    }

    @Synchronized
    internal fun heldCount(): Int = holders

    @SuppressLint("WakelockTimeout")
    @Suppress("DEPRECATION") // WIFI_MODE_FULL_HIGH_PERF: Wi-Fi không vào chế độ tiết kiệm giữa lượt gọi (cùng cách với PhoneCast)
    private fun systemLocks(context: Context): Locks {
        val cpu = (context.getSystemService(Context.POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "abook:clipfetch")
            .apply { setReferenceCounted(false) }
        val wifi = (context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager)
            .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "abook:clipfetch").apply { setReferenceCounted(false) }
        return object : Locks {
            override fun acquire(timeoutMs: Long, network: Boolean) {
                cpu.acquire(timeoutMs)
                if (network && !wifi.isHeld) wifi.acquire() // WifiLock không có hạn giờ: nhả cùng CPU ở [release] (hạn của khoá CPU là lưới an toàn)
            }

            override fun release() {
                if (cpu.isHeld) cpu.release()
                if (wifi.isHeld) wifi.release()
            }
        }
    }
}
