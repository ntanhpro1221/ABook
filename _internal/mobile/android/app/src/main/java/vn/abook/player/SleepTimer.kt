package vn.abook.player

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.ui.components.ValueSpecs
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

    /** Cửa sổ "lắc để nghe tiếp" sau khi hẹn giờ tự dừng (2 phút + 5 giây cho cảm biến): cũng là hạn tối thiểu dịch vụ phát giữ tiền cảnh ([PlaybackService.foregroundGraceMs]). */
    const val SHAKE_RESUME_MS = 125_000L

    private val main = Handler(Looper.getMainLooper())
    var mode = Mode.OFF
        private set
    /** Thời gian còn lại tính tới mốc runningSinceMs; runningSinceMs = 0 nghĩa là đồng hồ đang đứng (đang dừng). */
    private var remainingMs = 0L
    private var runningSinceMs = 0L
    /** Số phút người nghe CHỌN lúc hẹn giờ này (không phải thời gian còn lại): "Hẹn lại" đưa đồng hồ về đúng số này, không bao giờ hơn. Ghi cùng hẹn giờ ([persist]). Hẹn theo chương dùng "Mỗi lần nghe thêm". */
    private var minutes = 0
    private var selectedMode = Mode.OFF
    private var selectedMinutes = 0
    private var selectedChapters = 1
    private var scheduleFor = ""
    private var retained = false
    var activityResets = true

    /** All deliberate input enters here; polling and automatic playback events must never call it. */
    fun onUserActivity(source: String, now: Long = System.currentTimeMillis()) {
        ListenerActivity.inputObserved()
        ListenerActivity.evidence.awake(SystemClock.elapsedRealtime())
        if (mode == Mode.OFF) return
        if (automaticReason == "schedule" && scheduleFor.isNotEmpty() && scheduleFor != scheduleWindow()) { turnOff(); return }
        // Tắt "Thao tác hẹn lại": thao tác thường không đặt lại đồng hồ, nhưng lúc đang nhỏ dần vẫn là "Hẹn lại" - như máy tính và web (soát 0.4.173 B9).
        // Cú lắc có đường riêng ([applyShake]) nên không hẹn lại hai lần.
        if (activityResets) resetCycle(now) else if (source != "shake" && Playback.fadeLevel < 1f) extend()
        Bedtime.interaction(source)
    }

    private fun resetCycle(now: Long = System.currentTimeMillis()) {
        val extension = !retained && mode == Mode.MINUTES && selectedMode == Mode.CHAPTER
        if (!extension) {
            mode = selectedMode
            minutes = selectedMinutes
        }
        chapters = selectedChapters
        remainingMs = minutes * 60_000L
        runningSinceMs = if (playing()) now else 0L
        warned = false
        restoreVolume()
        Playback.holdAtItemEnd(mode == Mode.CHAPTER && chapters == 1 && !retained)
        persist(now)
        Playback.emit("sleep")
    }

    /** Lần hẹn cuối người nghe tự đặt (chưa từng đặt: 30 phút): mốc mở sẵn của tấm Hẹn giờ và nút "Bật lại". Nạp ở [ListenPrefs.load], nhớ ở
     *  [ListenPrefs.saveLastSleep] mỗi lần người nghe tự đặt ([setMinutes] không có `reason`, [setEndOfChapter]); lịch đêm tự hẹn không đổi nó.
     *  Ghi từ luồng nạp (Playback.init chạy ở IO) và luồng chính, đọc từ giao diện: giữ trong StateFlow (an toàn luồng); giao diện đọc [lastFlow]
     *  để đứng ở mốc vừa nạp nếu tấm mở trước khi lõi nạp xong (soát sleeplast lỗi 6). */
    private val lastState = MutableStateFlow(LastSleep())
    val lastFlow: StateFlow<LastSleep> = lastState.asStateFlow()
    var last: LastSleep
        get() = lastState.value
        internal set(value) { lastState.value = value }

    private fun remember(choice: LastSleep) {
        last = choice
        ListenPrefs.saveLastSleep(choice)
    }

    /** Nút "Bật lại" (tấm Hẹn giờ, widget): đặt lại đúng lần hẹn cuối - số phút hay số chương. */
    fun restartLast() {
        val choice = last
        if (choice.isChapter) setEndOfChapter(choice.chapters) else setMinutes(choice.minutes)
    }
    /** "Hết N chương": số chương còn phải nghe hết (1 = chương này). Chỉ chương cuối của hẹn giữ ở cuối mục ([Playback.holdAtItemEnd]); các chương trước
     *  đếm xuống ở lúc sang chương tự nhiên ([onChapterChanged]), không nhỏ dần. */
    var chapters = 1
        private set
    /** Hẹn "hết chương" dừng ở cuối CHƯƠNG NÀY (chương cuối của "Hết N chương"). */
    val stopsAtChapterEnd: Boolean get() = mode == Mode.CHAPTER && chapters == 1
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
        // Motion and screen samples are evidence for the schedule, not deliberate input.
    }

    fun checkSchedule() {
        if (automaticReason == "schedule" && scheduleFor != scheduleWindow()) turnOff()
        if (schedule == null) return
        ListenerActivity.sampleScreen()
        ListenerActivity.sampleVolume()
        if (mode == Mode.OFF) maybeSchedule()
    }

    /** Listener của lõi cho dịch vụ phát: hẹn giờ đặt / gia hạn / hết / lịch đêm tự bật (sự kiện "sleep") thì dựng lại nút thông báo - không phụ thuộc giao diện còn sống (soát a77 #10). */
    fun buttonsListener(refresh: () -> Unit): (JSONObject) -> Unit = { event ->
        if (event.optString("kind") == "sleep") refresh()
    }

    /** Persist the selected mode, never an in-flight extension or countdown. */
    fun persist(now: Long = System.currentTimeMillis()) {
        val timer = JSONObject()
            .put("selection", selectedMode.name.lowercase()).put("minutes", selectedMinutes)
            .put("chapters", selectedChapters).put("source", automaticReason.ifEmpty { "manual" })
            .put("window", scheduleFor).put("retained", retained).put("disabledWindow", scheduleOffFor)
            .put("bookId", ownerBook).put("recordId", ownerRecord)
        ListenPrefs.saveTimer(timer)
    }

    /** Process recreation restores a full cycle, paused until playback starts. */
    fun restore(timer: JSONObject?, now: Long = System.currentTimeMillis()) {
        if (timer == null || mode != Mode.OFF) return
        scheduleOffFor = timer.optString("disabledWindow")
        if (timer.optString("selection") == "off") return
        if (!adoptSaved(timer, now)) ListenPrefs.saveTimer(null)
    }

    /**
     * Đổi sách hay hồ sơ nghe: lựa chọn hẹn giờ đi theo từng (sách, hồ sơ) - sách vừa mở nhận lại lựa chọn của chính nó (đủ một lượt, đứng chờ phát),
     * sách cũ giữ lựa chọn của nó cho lần quay lại. Như máy tính (Player::restoreSleep) và web (readSleepSelection); không tắt hẹn giờ, không khoá
     * lịch đêm (trước đây đổi sách là [cancel] - soát 0.4.173 B7).
     */
    internal fun adopt(book: String, record: String, now: Long = System.currentTimeMillis()) {
        if (mode != Mode.OFF) Bedtime.timerOff()
        mode = Mode.OFF
        selectedMode = Mode.OFF
        retained = false
        automaticReason = ""
        scheduleFor = ""
        stoppedAtMs = 0L
        Playback.player?.pauseAtEndOfMediaItems = false
        restoreVolume()
        ownerBook = book
        ownerRecord = record
        ListenPrefs.savedTimer(book, record)?.let { adoptSaved(it, now) }
        Motion.refresh()
        persist(now)
        Playback.emit("sleep")
    }

    /** Một lựa chọn đã lưu thành hẹn giờ đứng chờ phát; false khi nó không còn dùng được (đã tắt, sai miền, lịch của đêm khác). */
    private fun adoptSaved(timer: JSONObject, now: Long): Boolean {
        if (timer.optString("selection") == "off") return false
        val picked = timer.optInt("minutes")
        val kind = timer.optString("selection")
        val count = timer.optInt("chapters", 1)
        val source = timer.optString("source")
        if (timer.optString("bookId").isEmpty() || source !in listOf("manual", "schedule") ||
            (kind != "minutes" && kind != "chapter") || (kind == "minutes" && !minutesAllowed(picked)) ||
            count !in 1..10 || (source == "schedule" && timer.optString("window") != scheduleWindow(Calendar.getInstance().apply { timeInMillis = now }))) {
            return false
        }
        automaticReason = if (source == "manual") "" else source
        scheduleFor = timer.optString("window")
        retained = timer.optBoolean("retained")
        ownerBook = timer.optString("bookId")
        ownerRecord = timer.optString("recordId")
        mode = if (kind == "chapter") Mode.CHAPTER else Mode.MINUTES
        selectedMode = mode
        selectedMinutes = picked
        selectedChapters = count
        chapters = count
        minutes = picked
        remainingMs = picked * 60_000L
        warned = false
        runningSinceMs = 0L
        retained = true
        return true
    }

    fun describe(now: Long = System.currentTimeMillis()): JSONObject {
        val json = JSONObject().put("mode", mode.name.lowercase()).put("reason", automaticReason)
        if (stoppedAtMs > 0) json.put("stoppedAt", stoppedAtMs / 1000.0)
        when (mode) {
            Mode.MINUTES -> json.put("remaining", leftMs(now) / 1000.0).put("minutes", minutes).put("counting", runningSinceMs > 0)
            Mode.CHAPTER -> json.put("remaining", remainingInChapter()).put("chapters", chapters)
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
        if (ownerBook != Playback.bookId || ownerRecord != Playback.recordId) adopt(Playback.bookId, Playback.recordId)
    }

    /** Only playback advances the countdown; a retained cycle restarts in full. */
    fun onPlaying(isPlaying: Boolean) {
        if (isPlaying && (ownerBook != Playback.bookId || ownerRecord != Playback.recordId)) adopt(Playback.bookId, Playback.recordId)
        if (mode == Mode.OFF) return
        val now = System.currentTimeMillis()
        if (automaticReason == "schedule" && scheduleFor != scheduleWindow()) { turnOff(); return }
        if (isPlaying && retained) {
            resetCycle(now)
            retained = false
            Bedtime.timerSet(if (selectedMode == Mode.MINUTES) selectedMinutes else -1, automaticReason.ifEmpty { null })
            stoppedAtMs = 0L
        }
        if (isPlaying && mode == Mode.CHAPTER) Playback.holdAtItemEnd(chapters == 1)
        if (isPlaying) tick() // vòng đếm đã ngừng lúc dừng (hay chưa có: hẹn giờ khôi phục sau khi tiến trình chết, [restore])
        if (mode != Mode.MINUTES) return
        if (isPlaying && runningSinceMs == 0L) {
            runningSinceMs = now
        } else if (!isPlaying && runningSinceMs > 0L) {
            remainingMs = leftMs(now)
            runningSinceMs = 0L
        }
        persist(now)
        Playback.emit("sleep")
    }

    /** Số phút hẹn được: miền tự do của bộ chọn giá trị (1-240, ValueSpecs.sleepMinutes). */
    private fun minutesAllowed(value: Int) = value >= ValueSpecs.sleepMinutes.min && value <= ValueSpecs.sleepMinutes.max

    fun setMinutes(value: Int, reason: String? = null, feedback: Boolean = true) {
        if (!minutesAllowed(value)) return
        if (reason == null) {
            onUserActivity("timer")
            remember(last.withMinutes(value))
        }
        automaticReason = reason?.takeIf { it == "schedule" }.orEmpty()
        scheduleFor = if (reason == "schedule") scheduleWindow().orEmpty() else ""
        retained = false
        ownerBook = Playback.bookId
        ownerRecord = Playback.recordId
        mode = Mode.MINUTES
        minutes = value
        selectedMode = Mode.MINUTES
        selectedMinutes = value
        selectedChapters = 1
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

    /** "Hết chương này" (`count` 1) hay "Hết N chương" (N 1-10, ValueSpecs.sleepChapters). */
    fun setEndOfChapter(count: Int = 1) {
        if (count < ValueSpecs.sleepChapters.min || count > ValueSpecs.sleepChapters.max) return
        onUserActivity("timer")
        remember(last.withChapters(count))
        chapters = count
        selectedMode = Mode.CHAPTER
        selectedChapters = count
        selectedMinutes = 0
        retained = false
        ownerBook = Playback.bookId
        ownerRecord = Playback.recordId
        automaticReason = ""
        mode = Mode.CHAPTER
        warned = false
        stoppedAtMs = 0
        Playback.holdAtItemEnd(count == 1)
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
        ListenerActivity.evidence.awake(SystemClock.elapsedRealtime())
        turnOff()
    }

    private fun turnOff() {
        if (mode != Mode.OFF) Bedtime.timerOff()
        mode = Mode.OFF
        selectedMode = Mode.OFF
        retained = false
        automaticReason = ""
        stoppedAtMs = 0L
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
        val wasRetained = retained
        retained = false
        // The label promises another N minutes: convert the schedule to a manual timer before awake signals arrive.
        if (automaticReason.isNotEmpty()) {
            scheduleOffFor = scheduleWindow() ?: ""
            automaticReason = ""
            scheduleFor = ""
            ListenerActivity.evidence.awake(SystemClock.elapsedRealtime())
        }
        val now = System.currentTimeMillis()
        val target = extendTarget()
        if (wasRetained) Bedtime.timerSet(target)
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
    fun stoppedRecently(now: Long = System.currentTimeMillis()) = stoppedAtMs > 0 && now - stoppedAtMs in 0 until SHAKE_RESUME_MS

    /** Lắc máy: đang hẹn giờ thì hẹn lại ([extend]); vừa tự dừng (< 2 phút) thì phát tiếp và hẹn [extendMinutes] phút. */
    fun onShake() {
        val now = System.currentTimeMillis()
        val changed = shakeEnabled && applyShake(now)
        if (changed) {
            Bedtime.event("shake")
            Feedback.play("sleepExtend")
        }
    }

    /** Phần đổi hẹn giờ của cú lắc (tách khỏi rung / nhật ký để thử trên JVM): true khi có việc đã làm. */
    internal fun applyShake(now: Long): Boolean {
        if (mode == Mode.OFF) return false
        val resume = stoppedRecently(now) && !playing()
        onUserActivity("shake", now)
        if (!activityResets) extend(feedback = false)
        if (resume) Playback.play()
        return true
    }

    /** Sang chương: người nghe tự chuyển thì giữ hẹn như cũ; tự sang (hết chương) khi hẹn còn hơn một chương thì đếm xuống, chương cuối của hẹn mới giữ ở cuối mục. */
    fun onChapterChanged(manual: Boolean = false) {
        if (mode != Mode.CHAPTER || retained) return
        when {
            manual -> { onUserActivity("chapter"); Playback.holdAtItemEnd(chapters == 1) }
            chapters > 1 -> {
                chapters -= 1
                Playback.holdAtItemEnd(chapters == 1)
                Playback.emit("sleep")
            }
            else -> finish()
        }
    }

    /** Gọi khi ExoPlayer dừng ở cuối chương (chế độ hết chương). */
    fun onPausedAtChapterEnd() {
        if (mode == Mode.CHAPTER && chapters == 1 && !retained) finish()
    }

    private fun finish() {
        if (retained || mode == Mode.OFF) return
        val finishedChapter = mode == Mode.CHAPTER
        val automatic = automaticReason.isNotEmpty()
        retained = true
        Playback.player?.pause()
        Playback.player?.pauseAtEndOfMediaItems = false
        mode = selectedMode
        minutes = selectedMinutes
        chapters = selectedChapters
        remainingMs = minutes * 60_000L
        runningSinceMs = 0L
        warned = false
        retained = mode != Mode.OFF
        if (mode == Mode.OFF) selectedMode = Mode.OFF
        stoppedAutomatically = automatic
        stoppedAtMs = System.currentTimeMillis()
        restoreVolume()
        Bedtime.stopped()
        // Park the next chapter while paused. Re-arming a held item before its
        // transition can otherwise pause the already completed item again.
        if (finishedChapter && !ReadAloud.inText()) {
            Playback.player?.takeIf { it.hasNextMediaItem() }?.seekToNextMediaItem()
        }
        // No sound or vibration at expiry: the listener may already be asleep (DESIGN 5.4).
        // Cảm biến còn nghe thêm 2 phút để "lắc để nghe tiếp" vẫn chạy.
        main.postDelayed({ Motion.refresh() }, SHAKE_RESUME_MS)
        persist()
        Playback.emit("sleep")
    }

    private fun tick() {
        if (ticking) return
        ticking = true
        main.post(object : Runnable {
            override fun run() {
                val exo = Playback.player
                // Đang dừng: vòng đếm ngừng (đỡ pin), [onPlaying] chạy lại khi phát.
                if (mode == Mode.OFF || exo == null || !exo.isPlaying) {
                    ticking = false
                    return
                }
                if (automaticReason == "schedule") {
                    if (scheduleFor != scheduleWindow()) { turnOff(); ticking = false; return }
                    if (!ListenerActivity.allowsNightSchedule()) onAwake()
                    if (mode == Mode.OFF) { ticking = false; return }
                }
                val remaining = when (mode) {
                    Mode.MINUTES -> leftMs()
                    // "Hết N chương": chỉ chương cuối của hẹn mới nhỏ dần / báo sắp tắt.
                    Mode.CHAPTER -> if (chapters > 1) Long.MAX_VALUE else Playback.remainingInChapterMs()
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
    const val FLIP_RESUME_MS = 10 * 60_000L
    private var faceDownSinceMs = 0L
    private var flipPausedAtMs = 0L
    // Độ lệch độ lớn gia tốc trong ~1 giây gần nhất: nằm yên trên bàn/nệm gần 0; cầm trên tay (kể cả nằm ngửa giơ máy
    // lên xem - màn hình cũng úp xuống!) luôn rung nhẹ. Chỉ tính là "úp" khi úp VÀ yên.
    private val recent = ArrayDeque<Pair<Long, Double>>()

    /**
     * Bật cảm biến khi có ai cần: đang phát mà có hẹn giờ (lắc để nghe thêm - hẹn giờ đứng lúc dừng thì không cần) hay có lịch đêm (xét hẹn tự động),
     * vừa tự dừng < 2 phút (lắc để nghe tiếp), hoặc vừa úp máy dừng. Không ai cần thì tắt - đỡ pin.
     */
    fun refresh() {
        val now = System.currentTimeMillis()
        val playing = Playback.player?.isPlaying == true
        val wanted = (playing && (SleepTimer.schedule != null || SleepTimer.mode != SleepTimer.Mode.OFF)) || SleepTimer.stoppedRecently(now) ||
            (flipEnabled && (playing ||(flipPausedAtMs > 0 && now - flipPausedAtMs < FLIP_RESUME_MS)))
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
        manager = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager
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
                if (deviation >= SleepPolicy.STILL_DEVIATION) SleepTimer.onAwake()
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
