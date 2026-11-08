package vn.abook.player

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import org.json.JSONObject
import vn.abook.player.ui.nowplaying.SleepText
import java.util.Calendar
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Hẹn giờ ngủ: tắt sau N phút hoặc hết chương, tiếng nhỏ dần trước khi dừng, lắc máy để hẹn lại (đồng hồ về N phút, không cộng dồn).
 *
 * Lắc được cả khi đang nhỏ dần và trong 2 phút sau khi đã tự dừng (người nghe vẫn còn thức, lắc để nghe tiếp).
 * Hai nốt xác nhận và rung nhẹ cùng lượt, theo hai công tắc riêng, không cần mở mắt nhìn màn hình.
 *
 * Đồng hồ chỉ chạy khi ĐANG PHÁT (tự tạm dừng rồi nghe lại không bị tắt ngay), nhỏ dần theo thang dB (tai nghe âm
 * lượng theo logarit - giảm đều theo biên độ thì mấy bậc cuối tụt như bị cắt). Lịch đêm chỉ tự hẹn khi người nghe đã bật trong Cài đặt.
 */
object SleepTimer {
    enum class Mode { OFF, MINUTES, CHAPTER }

    private val main = Handler(Looper.getMainLooper())
    var mode = Mode.OFF
        private set
    /** Thời gian còn lại tính tới mốc runningSinceMs; runningSinceMs = 0 nghĩa là đồng hồ đang đứng (đang dừng). */
    private var remainingMs = 0L
    private var runningSinceMs = 0L
    /** Số phút người nghe CHỌN lúc hẹn giờ này (không phải thời gian còn lại): "Hẹn lại" đưa đồng hồ về đúng số này, không bao giờ hơn. Ghi cùng hẹn giờ ([persist]). Hẹn theo chương dùng "Mỗi lần nghe thêm". */
    private var minutes = 0
    /** Lịch đêm: (từ phút-trong-ngày, đến phút-trong-ngày, số phút hẹn) hoặc null. */
    var schedule: Triple<Int, Int, Int>? = null
    private var scheduleOffFor = ""
    private var stoppedAtMs = 0L
    var fadeMs = 30_000L
    /** "Mỗi lần nghe thêm" của Cài đặt: số phút "Hẹn lại" khi hẹn theo chương hay vừa tự dừng (hẹn phút thì là số đã chọn, [extendTarget]). */
    var extendMinutes = 10
    var shakeEnabled = true
    /** Ngưỡng một cú lắc, tính bằng g: nhỏ = nhẹ tay cũng tính (Cài đặt: nhẹ tay 1,6 / vừa 2,2 / mạnh tay 2,8). */
    var shakeThresholdG = 2.2
    private var ticking = false
    private var warned = false
    var automaticReason = ""
        private set
    private var stoppedAutomatically = false
    private var ownerBook = ""
    private var ownerRecord = ""

    /** An awake signal cancels automatic timers only. Explicitly chosen timers keep counting. */
    fun onAwake() {
        ListenerActivity.evidence.awake(SystemClock.elapsedRealtime())
        stoppedAtMs = 0L
        if (automaticReason.isNotEmpty() && mode != Mode.OFF) cancel()
    }

    fun checkSchedule() {
        if (schedule == null) return
        ListenerActivity.sampleScreen()
        ListenerActivity.sampleVolume()
        if (mode == Mode.OFF) maybeSchedule()
    }

    /** Listener của lõi cho dịch vụ phát: hẹn giờ đặt / gia hạn / hết / lịch đêm tự bật (sự kiện "sleep") thì dựng lại nút thông báo - không phụ thuộc giao diện còn sống (soát a77 #10). */
    fun buttonsListener(refresh: () -> Unit): (JSONObject) -> Unit = { event ->
        if (event.optString("kind") == "sleep") refresh()
    }

    /**
     * Nhớ hẹn giờ phút đang chạy ở kho native ([ListenPrefs]) để tiến trình chết rồi dậy lại (tai nghe / widget / xe) không mất nó: đang phát thì ghi MỐC KẾT THÚC tuyệt đối (đồng hồ thật tiếp tục
     * trôi trong lúc tiến trình chết), đang tạm dừng thì ghi thời gian còn lại (đồng hồ đứng). Hết chương không khôi phục được (tính theo vị trí chương) - không ghi (soát a77 #6).
     */
    fun persist(now: Long = System.currentTimeMillis()) {
        val timer = if (mode == Mode.MINUTES && automaticReason.isEmpty()) JSONObject().put("minutes", minutes)
            .put("source", "manual").put("bookId", ownerBook).put("recordId", ownerRecord).put("savedAt", now).also {
            if (runningSinceMs > 0) it.put("endsAt", now + leftMs(now)) else it.put("remainingMs", leftMs(now))
        } else null
        ListenPrefs.saveTimer(timer)
    }

    /** Khôi phục hẹn giờ đã ghi ([persist]) lúc tiến trình dậy: chưa quá mốc kết thúc thì còn lại đúng phần chưa trôi, đồng hồ đứng tới khi phát ([onPlaying]); quá rồi thì bỏ. */
    fun restore(timer: JSONObject?, now: Long = System.currentTimeMillis()) {
        if (timer == null || mode != Mode.OFF) return
        val left = if (timer.has("endsAt")) timer.optLong("endsAt") - now else timer.optLong("remainingMs", 0L)
        val picked = timer.optInt("minutes")
        if (timer.optString("source") != "manual" || timer.optString("bookId").isEmpty() ||
            now - timer.optLong("savedAt") !in 0..(24 * 3_600_000L) || picked !in 1..60 || left !in 1..(picked * 60_000L)) {
            ListenPrefs.saveTimer(null)
            return
        }
        automaticReason = ""
        ownerBook = timer.optString("bookId")
        ownerRecord = timer.optString("recordId")
        mode = Mode.MINUTES
        minutes = timer.optInt("minutes", (left / 60_000L).toInt())
        remainingMs = left
        warned = false
        runningSinceMs = 0L
    }

    fun describe(now: Long = System.currentTimeMillis()): JSONObject {
        val json = JSONObject().put("mode", mode.name.lowercase()).put("reason", automaticReason)
        when (mode) {
            Mode.MINUTES -> json.put("remaining", leftMs(now) / 1000.0).put("minutes", minutes).put("counting", runningSinceMs > 0)
            Mode.CHAPTER -> json.put("remaining", remainingInChapter())
            Mode.OFF -> if (stoppedAtMs > 0) json.put("stoppedAt", stoppedAtMs / 1000.0)
        }
        return json
    }

    private fun remainingInChapter(): Double {
        if (Playback.player == null) return 0.0
        return Playback.remainingInChapterMs() / 1000.0
    }

    private fun leftMs(now: Long = System.currentTimeMillis()): Long =
        (if (runningSinceMs > 0) remainingMs - (now - runningSinceMs) else remainingMs).coerceAtLeast(0L)

    private fun playing() = Playback.player?.isPlaying == true

    /** Gọi khi trình phát bắt đầu/ngừng phát: đồng hồ hẹn giờ chạy/đứng theo. */
    fun checkOwner() {
        if (mode != Mode.OFF && (ownerBook != Playback.bookId || ownerRecord != Playback.recordId)) cancel()
    }

    fun onPlaying(isPlaying: Boolean) {
        if (mode != Mode.MINUTES) return
        if (isPlaying && (ownerBook != Playback.bookId || ownerRecord != Playback.recordId)) { cancel(); return }
        val now = System.currentTimeMillis()
        if (isPlaying && runningSinceMs == 0L) {
            runningSinceMs = now
            tick() // hẹn giờ khôi phục sau khi tiến trình chết ([restore]) chưa có vòng đếm
        } else if (!isPlaying && runningSinceMs > 0L) {
            remainingMs = leftMs(now)
            runningSinceMs = 0L
        }
        persist(now)
        Playback.emit("sleep")
    }

    fun setMinutes(value: Int, reason: String? = null, feedback: Boolean = true) {
        if (value !in 1..60) return
        if (reason == null) onAwake()
        automaticReason = reason?.takeIf { it == "schedule" }.orEmpty()
        ownerBook = Playback.bookId
        ownerRecord = Playback.recordId
        mode = Mode.MINUTES
        minutes = value
        remainingMs = value * 60_000L
        warned = false
        runningSinceMs = if (playing()) System.currentTimeMillis() else 0L
        stoppedAtMs = 0
        Playback.player?.pauseAtEndOfMediaItems = false
        restoreVolume()
        Bedtime.timerSet(value, reason)
        Motion.refresh()
        tick()
        persist()
        Playback.emit("sleep")
        if (reason == null && feedback) Feedback.play("toggle")
    }

    fun setEndOfChapter() {
        onAwake()
        ownerBook = Playback.bookId
        ownerRecord = Playback.recordId
        automaticReason = ""
        mode = Mode.CHAPTER
        warned = false
        stoppedAtMs = 0
        Playback.holdAtItemEnd(true)
        restoreVolume()
        Bedtime.timerSet(-1)
        Motion.refresh()
        tick()
        persist()
        Playback.emit("sleep")
        Feedback.play("toggle")
    }

    fun cancel() {
        // Tự tắt hẹn giờ trong khung lịch đêm: đêm ấy không tự bật lại nữa.
        scheduleOffFor = scheduleWindow() ?: ""
        mode = Mode.OFF
        automaticReason = ""
        stoppedAtMs = 0L
        ListenerActivity.evidence.awake(SystemClock.elapsedRealtime())
        Playback.player?.pauseAtEndOfMediaItems = false
        restoreVolume()
        Motion.refresh()
        persist()
        Playback.emit("sleep")
    }

    /** Số phút "Hẹn lại" của hẹn giờ hiện tại: hẹn phút thì số người nghe đã chọn, hết chương thì [extendMinutes] (một hàm với nhãn nút: [SleepText.extendMinutes]). */
    fun extendTarget(): Int = SleepText.extendMinutes(mode == Mode.MINUTES, minutes, extendMinutes)

    /**
     * Nghe thêm = hẹn lại: đồng hồ về đúng [extendTarget] phút, không bao giờ hơn (lắc nhiều lần không cộng dồn). Còn lại đã >= số ấy thì giữ nguyên, chỉ trả tiếng.
     * Đang hẹn hết chương thì chuyển thành N phút kể từ bây giờ.
     */
    fun extend(feedback: Boolean = true) {
        // Hẹn giờ đã hết (hay đã tắt): nút "Hẹn lại" cũ còn trên thông báo không được dựng hẹn giờ mới ngoài ý bạn - như máy tính (extendSleep: kind off thì bỏ qua). Lắc sau khi vừa tự dừng có đường riêng ([onShake]).
        if (mode == Mode.OFF) return
        if (automaticReason.isNotEmpty()) { onAwake(); if (feedback) Feedback.play("sleepExtend"); return }
        val now = System.currentTimeMillis()
        val target = extendTarget()
        remainingMs = maxOf(if (mode == Mode.MINUTES) leftMs(now) else 0L, target * 60_000L)
        runningSinceMs = if (playing()) now else 0L
        if (mode != Mode.MINUTES) {
            mode = Mode.MINUTES
            Playback.player?.pauseAtEndOfMediaItems = false
        }
        minutes = target
        warned = false
        restoreVolume()
        tick()
        persist()
        Playback.emit("sleep")
        if (feedback) Feedback.play("sleepExtend")
    }

    /** Vừa tự dừng chưa tới 2 phút: cảm biến còn nghe để "lắc để nghe tiếp". */
    fun stoppedRecently(now: Long = System.currentTimeMillis()) = stoppedAtMs > 0 && now - stoppedAtMs in 0 until 125_000L

    /** Lắc máy: đang hẹn giờ thì hẹn lại ([extend]); vừa tự dừng (< 2 phút) thì phát tiếp và hẹn [extendMinutes] phút. */
    fun onShake() {
        val now = System.currentTimeMillis()
        val changed = shakeEnabled && applyShake(now)
        Playback.touched()
        if (changed) {
            Bedtime.event("shake")
            Feedback.play("sleepExtend")
        }
    }

    /** Phần đổi hẹn giờ của cú lắc (tách khỏi rung / nhật ký để thử trên JVM): true khi có việc đã làm. */
    internal fun applyShake(now: Long): Boolean = when {
        mode != Mode.OFF -> { extend(feedback = false); true }
        stoppedAtMs > 0 && now - stoppedAtMs in 0 until 120_000L -> {
            val automatic = stoppedAutomatically
            if (automatic) scheduleOffFor = scheduleWindow() ?: ""
            stoppedAtMs = 0L
            Playback.play()
            if (!automatic) setMinutes(extendMinutes, feedback = false)
            true
        }
        else -> false
    }

    fun onChapterChanged(manual: Boolean = false) {
        if (mode == Mode.CHAPTER) {
            if (manual) Playback.holdAtItemEnd(true) else finish()
        }
    }

    /** Gọi khi ExoPlayer dừng ở cuối chương (chế độ hết chương). */
    fun onPausedAtChapterEnd() {
        if (mode == Mode.CHAPTER) finish()
    }

    private fun finish() {
        val automatic = automaticReason.isNotEmpty()
        Playback.player?.pause()
        Playback.player?.pauseAtEndOfMediaItems = false
        mode = Mode.OFF
        automaticReason = ""
        stoppedAutomatically = automatic
        stoppedAtMs = System.currentTimeMillis()
        restoreVolume()
        Bedtime.stopped()
        // No sound or vibration at expiry: the listener may already be asleep (DESIGN 5.4).
        // Cảm biến còn nghe thêm 2 phút để "lắc để nghe tiếp" vẫn chạy.
        main.postDelayed({ Motion.refresh() }, 125_000L)
        persist()
        Playback.emit("sleep")
    }

    private fun tick() {
        if (ticking) return
        ticking = true
        main.post(object : Runnable {
            override fun run() {
                val exo = Playback.player
                if (mode == Mode.OFF || exo == null) {
                    ticking = false
                    return
                }
                if (automaticReason.isNotEmpty()) {
                    if (!ListenerActivity.allowsNightSchedule()) onAwake()
                    if (mode == Mode.OFF) { ticking = false; return }
                }
                val remaining = when (mode) {
                    Mode.MINUTES -> leftMs()
                    Mode.CHAPTER -> Playback.remainingInChapterMs()
                    Mode.OFF -> 0L
                }
                if (mode == Mode.MINUTES && remaining <= 0) {
                    finish()
                    ticking = false
                    return
                }
                if (exo.isPlaying && remaining in 0 until fadeMs) {
                    // Tuyến tính theo dB: 0 dB xuống -40 dB trong đoạn nhỏ dần.
                    val progress = 1.0 - remaining.toDouble() / fadeMs
                    Playback.applyVolume(10.0.pow(-40.0 * progress / 20.0).toFloat().coerceIn(0.01f, 1f))
                } else if (Playback.fadeLevel < 1f && remaining >= fadeMs) {
                    Playback.applyVolume(1f)
                }
                if (exo.isPlaying) warning(remaining)
                main.postDelayed(this, 250)
            }
        })
    }

    /** Đang trong khung lịch đêm? Trả về khoá của đêm ấy (ngày bắt đầu khung). */
    fun scheduleWindow(now: Calendar = Calendar.getInstance()): String? {
        val (from, to, _) = schedule ?: return null
        val current = now.get(Calendar.HOUR_OF_DAY) * 60 + now.get(Calendar.MINUTE)
        val overnight = from > to
        val inside = if (overnight) current >= from || current < to else current in from until to
        if (!inside) return null
        val start = now.clone() as Calendar
        if (overnight && current < to) start.add(Calendar.DAY_OF_YEAR, -1)
        return "${start.get(Calendar.YEAR)}-${start.get(Calendar.DAY_OF_YEAR)}"
    }

    /** Bắt đầu phát trong khung lịch đêm mà chưa hẹn giờ: tự hẹn. */
    fun maybeSchedule() {
        val (_, _, planned) = schedule ?: return
        val window = scheduleWindow() ?: return
        if (mode != Mode.OFF || scheduleOffFor == window || !playing()) return
        if (!ListenerActivity.allowsNightSchedule()) return
        setMinutes(planned, "schedule")
    }

    private fun restoreVolume() {
        Playback.applyVolume(1f)
    }

    internal fun warning(remaining: Long) {
        if (remaining in 1..30_000L && !warned) Feedback.play("sleepWarn")
        warned = remaining in 1..30_000L
    }
}

/**
 * Cảm biến gia tốc dùng chung cho hai việc: nhận ra cú lắc (thêm giờ ngủ) và nhận ra lúc điện thoại nằm yên
 * (nhật ký đêm đoán lúc người nghe thiếp đi). Cũng nghe khi đang phát để kiểm bằng chứng cho hẹn tự động.
 */
object Motion : SensorEventListener {
    private var manager: SensorManager? = null
    private var running = false
    var available = false
        private set

    /** Úp máy để tạm dừng, lật lên (trong `FLIP_RESUME_MS`) để nghe tiếp - Cài đặt, mặc định tắt. */
    var flipEnabled = false
    private const val FLIP_RESUME_MS = 10 * 60_000L
    private var faceDownSinceMs = 0L
    private var flipPausedAtMs = 0L
    // Độ lệch độ lớn gia tốc trong ~1 giây gần nhất: nằm yên trên bàn/nệm gần 0; cầm trên tay (kể cả nằm ngửa giơ máy
    // lên xem - màn hình cũng úp xuống!) luôn rung nhẹ. Chỉ tính là "úp" khi úp VÀ yên.
    private val recent = ArrayDeque<Pair<Long, Double>>()

    /**
     * Bật cảm biến khi có ai cần: hẹn giờ đang chạy (lắc để nghe thêm), vừa tự dừng < 2 phút (lắc để nghe tiếp), hoặc
     * đang phát để xét hẹn tự động, hoặc vừa úp máy dừng. Không ai cần thì tắt - đỡ pin.
     */
    fun refresh() {
        val now = System.currentTimeMillis()
        val wanted = (Playback.player?.isPlaying == true && SleepTimer.schedule != null) || SleepTimer.mode != SleepTimer.Mode.OFF || SleepTimer.stoppedRecently(now) ||
            (flipEnabled && (Playback.player?.isPlaying == true || (flipPausedAtMs > 0 && now - flipPausedAtMs < FLIP_RESUME_MS)))
        if (wanted) start(Playback.appContext) else stop()
    }
    private val peaks = ArrayDeque<Long>()
    private var lastShakeMs = 0L
    // Cửa sổ 30 giây: độ lệch của độ lớn gia tốc - rất nhỏ nghĩa là máy nằm yên.
    private var windowStartMs = 0L
    private var windowStartElapsedMs = 0L
    private var count = 0
    private var sum = 0.0
    private var sumSquares = 0.0

    fun start(context: Context) {
        if (running) return
        manager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val sensor = manager?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        available = sensor != null
        if (sensor == null) return
        running = manager?.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL) == true
        ListenerActivity.evidence.resetMotion()
        count = 0; sum = 0.0; sumSquares = 0.0
        windowStartMs = System.currentTimeMillis()
        windowStartElapsedMs = SystemClock.elapsedRealtime()
    }

    fun stop() {
        if (!running) return
        manager?.unregisterListener(this)
        running = false
        ListenerActivity.evidence.resetMotion()
        recent.clear(); peaks.clear()
    }

    override fun onSensorChanged(event: SensorEvent) {
        val (x, y, z) = Triple(event.values[0], event.values[1], event.values[2])
        val magnitude = sqrt((x * x + y * y + z * z).toDouble())
        val now = System.currentTimeMillis()
        if (flipEnabled) watchFlip(z.toDouble(), magnitude, now)
        // Lắc: hai đỉnh vượt ngưỡng (mặc định 2,2 g) trong 800 ms, cách lần lắc trước > 2 giây.
        if (magnitude / SensorManager.GRAVITY_EARTH > SleepTimer.shakeThresholdG) {
            peaks.addLast(now)
            while (peaks.isNotEmpty() && now - peaks.first() > 800) peaks.removeFirst()
            if (peaks.size >= 2 && now - lastShakeMs > 2000) {
                lastShakeMs = now
                peaks.clear()
                Playback.onMain { SleepTimer.onShake() }
            }
        }
        count += 1
        sum += magnitude
        sumSquares += magnitude * magnitude
        val elapsed = SystemClock.elapsedRealtime()
        if (elapsed - windowStartElapsedMs >= SleepPolicy.WINDOW_MS) {
            val mean = sum / count
            val deviation = sqrt((sumSquares / count - mean * mean).coerceAtLeast(0.0))
            val start = windowStartMs
            val elapsedStart = windowStartElapsedMs
            Playback.onMain {
                ListenerActivity.evidence.motionWindow(elapsedStart, elapsed, deviation)
                if (deviation >= SleepPolicy.STILL_DEVIATION) Playback.touched()
                Bedtime.window(start, deviation)
            }
            windowStartMs = now
            windowStartElapsedMs = elapsed
            count = 0
            sum = 0.0
            sumSquares = 0.0
        }
    }

    private fun watchFlip(z: Double, magnitude: Double, now: Long) {
        recent.addLast(now to magnitude)
        while (recent.isNotEmpty() && now - recent.first().first > 1000) recent.removeFirst()
        val mean = recent.sumOf { it.second } / recent.size
        val still = recent.size >= 5 && recent.all { kotlin.math.abs(it.second - mean) < 0.35 }
        val playing = Playback.player?.isPlaying == true
        if (z < -8.0 && still) {
            if (faceDownSinceMs == 0L) faceDownSinceMs = now
            if (playing && now - faceDownSinceMs > 1500) {
                faceDownSinceMs = 0L
                flipPausedAtMs = now
                Playback.onMain { Playback.pause() }
            }
        } else if (z >= -8.0) {
            faceDownSinceMs = 0L
        }
        if (z > 7.0 && flipPausedAtMs > 0 && !playing) {
            val pausedFor = now - flipPausedAtMs
            flipPausedAtMs = 0L
            if (pausedFor < FLIP_RESUME_MS) Playback.onMain { Playback.play() }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}
