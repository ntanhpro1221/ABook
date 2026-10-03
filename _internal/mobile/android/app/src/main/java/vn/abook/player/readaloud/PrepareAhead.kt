package vn.abook.player.readaloud

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import vn.abook.player.Playback
import vn.abook.player.R
import java.io.File
import java.util.UUID
import java.util.concurrent.CopyOnWriteArraySet

/**
 * "Làm trước" trên điện thoại: việc nền của WorkManager đọc sẵn các chương tới vào bộ đệm đoạn (phần thuần: PreparePlan.kt). Chạy cả khi app đã đóng; điều kiện
 * (chỉ khi đang sạc - người nghe tắt được, Wi-Fi không tính tiền cho giọng trực tuyến, pin không yếu) do WorkManager giữ: rút sạc thì việc dừng giữa hai đoạn
 * và tự làm tiếp khi cắm lại. Việc lưu ở `readaloud-prepare.json` sau mỗi đoạn; WorkManager tự xếp lại việc sau khi máy khởi động lại / app bị đóng.
 * Mỗi lượt chạy tối đa [SLICE_MS] (giới hạn ~10 phút của một lượt WorkManager) rồi xếp lượt kế. Thông báo nhỏ (không phải dịch vụ chạy nền) cho thấy tiến độ.
 */
object PrepareAhead {
    const val WORK = "readaloud-prepare"
    const val SLICE_MS = 9 * 60_000L
    private const val CHANNEL = "readaloud-prepare"
    private const val NOTIFICATION = 0x5245_4144 // "READ"

    private val lock = Any()
    private var loaded = false
    private var job: PrepareJob? = null

    /** Lượt chạy của WorkManager đang làm (không chỉ đang chờ điều kiện). */
    @Volatile
    private var working = false

    private val listeners = CopyOnWriteArraySet<(JSONObject) -> Unit>()
    fun addListener(listener: (JSONObject) -> Unit) { listeners += listener }
    fun removeListener(listener: (JSONObject) -> Unit) { listeners -= listener }

    private fun file(context: Context) = File(context.filesDir, "readaloud-prepare.json")
    private fun prefs(context: Context) = context.getSharedPreferences("readaloud_prepare", Context.MODE_PRIVATE)

    /** "Chỉ khi đang sạc" - lựa chọn của người nghe, mặc định bật; nhớ cả khi không có việc nào. */
    fun chargingOnly(context: Context): Boolean = prefs(context).getBoolean("chargingOnly", true)

    private fun current(context: Context): PrepareJob? = synchronized(lock) {
        if (!loaded) {
            loaded = true
            job = runCatching { PrepareJob.fromJson(JSONObject(file(context).readText())) }.getOrNull()
        }
        job
    }

    /** Ghi việc xuống file - chỉ khi nó vẫn là việc hiện tại (lượt cũ chạy nốt đoạn của nó không được ghi đè việc mới). */
    private fun save(context: Context, saved: PrepareJob) {
        synchronized(lock) {
            if (job?.id != saved.id) return
            val target = file(context)
            val part = File(target.path + ".part")
            part.writeBytes(saved.toJson().toString().toByteArray(Charsets.UTF_8))
            target.delete()
            part.renameTo(target)
        }
        emit(context)
    }

    private fun replace(context: Context, next: PrepareJob?) {
        synchronized(lock) {
            loaded = true
            job = next
            if (next == null) file(context).delete()
        }
        if (next != null) save(context, next)
    }

    // ---- lệnh từ giao diện (plugin ReadAloud, chạy ở luồng nền) ----------------------------------------------------------------------------

    /** Các chương sẽ nhận (vừa phần bộ đệm dành cho làm trước) + số đoạn đã đưa. */
    private fun select(context: Context, bookId: String, voice: String, ids: List<Int>): Triple<List<PrepareChapter>, Int, Int> {
        ReadAloud.init(context)
        val texts = ReadAloud.textChapters(bookId, ids)
        val offered = ids.mapNotNull { id ->
            texts[id]?.let { (title, paragraphs) -> PrepareChapter(id, title, paragraphs.size, paragraphs.sumOf { it.length }) }
        }.filter { it.paragraphs > 0 }
        val cache = ReadAloud.cache()
        val accepted = PreparePlan.accept(offered, PreparePlan.bytesPerSecond(voice), (cache.cap * PreparePlan.SHARE).toLong())
        return Triple(accepted, offered.size, offered.sumOf { it.paragraphs })
    }

    /** Ước trước khi bấm: số chương nhận, giờ nghe, máy cần bao lâu (tốc độ đã đo của giọng; chưa đo thì null). */
    fun plan(context: Context, bookId: String, voice: String, ids: List<Int>): JSONObject {
        val (accepted, offeredChapters, _) = select(context, bookId, voice, ids)
        val chars = accepted.sumOf { it.chars.toLong() }
        val perChar = runCatching { ReadAloud.speeds().secondsPerChar(voice) }.getOrNull()
        return JSONObject().put("chapters", accepted.size).put("offered", offeredChapters)
            .put("audioSeconds", Math.round(chars / PreparePlan.CHARS_PER_SECOND))
            .put("secondsEstimate", perChar?.let { Math.round(chars * it) } ?: JSONObject.NULL)
    }

    /** Bắt đầu (thay việc cũ). Đoạn đã có trong bộ đệm được bỏ qua, nên bấm lại sau khi dừng / mất mạng là làm tiếp. */
    fun start(context: Context, bookId: String, voice: String, ids: List<Int>, label: String, chargingOnly: Boolean): JSONObject {
        prefs(context).edit().putBoolean("chargingOnly", chargingOnly).apply()
        val (accepted, offeredChapters, offeredParagraphs) = select(context, bookId, voice, ids)
        WorkManager.getInstance(context).cancelUniqueWork(WORK)
        // Việc mới thay việc cũ: đoạn ghim của việc cũ chưa nghe tới trở lại là đoạn thường.
        runCatching { ReadAloud.cache().clearPins() }
        if (accepted.isEmpty()) {
            replace(context, null)
            return status(context)
        }
        val next = PrepareJob(UUID.randomUUID().toString(), bookId, voice, label, PreparePlan.online(voice), accepted, offeredChapters, offeredParagraphs,
            chargingOnly, System.currentTimeMillis())
        replace(context, next)
        enqueue(context, next, ExistingWorkPolicy.REPLACE)
        return status(context)
    }

    fun cancel(context: Context): JSONObject {
        WorkManager.getInstance(context).cancelUniqueWork(WORK)
        current(context)?.let {
            if (it.state == "running") {
                it.state = "cancelled"
                save(context, it)
            }
        }
        NotificationManagerCompat.from(context).cancel(NOTIFICATION)
        return status(context)
    }

    /** Đổi "Chỉ khi đang sạc": việc đang có xếp lại với điều kiện mới. */
    fun setChargingOnly(context: Context, on: Boolean): JSONObject {
        prefs(context).edit().putBoolean("chargingOnly", on).apply()
        val running = current(context)?.takeIf { it.state == "running" }
        if (running != null && running.chargingOnly != on) {
            running.chargingOnly = on
            save(context, running)
            enqueue(context, running, ExistingWorkPolicy.REPLACE)
        }
        return status(context)
    }

    fun status(context: Context): JSONObject {
        val now = current(context) ?: return JSONObject().put("state", "idle").put("chargingOnly", chargingOnly(context))
        if (now.state != "running" && !working) recheck(now)
        val perChar = runCatching { ReadAloud.speeds().secondsPerChar(now.voice) }.getOrNull()
        val device = conditions(context)
        val waiting = PreparePlan.waitingFor(now, working, ReadAloud.liveJobs() > 0, device.first, device.second, device.third)
        return now.status(perChar, waiting)
    }

    /** Việc đã xong từ trước: Android có thể đã dọn thư mục cache - "sẵn sàng" phải đúng với bộ đệm lúc này (dấu ở danh sách chương). */
    private fun recheck(done: PrepareJob) {
        val cache = runCatching { ReadAloud.cache() }.getOrNull() ?: return
        val texts = ReadAloud.textChapters(done.bookId, done.chapters.map { it.id })
        val origin = ReadAloud.originOf(done.bookId)
        for (chapter in done.chapters) {
            val paragraphs = texts[chapter.id]?.second ?: continue
            chapter.done = paragraphs.count { cache.contains(done.voice, it, origin) }.coerceAtMost(chapter.paragraphs - chapter.failed)
        }
    }

    /** (đang sạc, Wi-Fi không tính tiền, pin yếu) lúc này. */
    private fun conditions(context: Context): Triple<Boolean, Boolean, Boolean> {
        val battery = context.getSystemService(BatteryManager::class.java)
        val charging = battery?.isCharging == true
        val level = battery?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: 100
        val connectivity = context.getSystemService(ConnectivityManager::class.java)
        val unmetered = connectivity?.getNetworkCapabilities(connectivity.activeNetwork)?.let {
            it.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) && it.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED)
        } == true
        // WorkManager coi "pin yếu" như hệ thống (ACTION_BATTERY_LOW, ~15%).
        return Triple(charging, unmetered, !charging && level in 0..15)
    }

    private fun enqueue(context: Context, job: PrepareJob, policy: ExistingWorkPolicy) {
        val needs = PreparePlan.needs(job.online, job.chargingOnly)
        val constraints = Constraints.Builder()
            .setRequiresCharging(needs.charging)
            .setRequiredNetworkType(if (needs.unmetered) NetworkType.UNMETERED else NetworkType.NOT_REQUIRED)
            .setRequiresBatteryNotLow(needs.batteryNotLow)
            .build()
        val request = OneTimeWorkRequestBuilder<PrepareWorker>().setConstraints(constraints).addTag(WORK).build()
        WorkManager.getInstance(context).enqueueUniqueWork(WORK, policy, request)
    }

    private fun emit(context: Context) {
        if (listeners.isEmpty()) return
        val status = runCatching { status(context) }.getOrNull() ?: return
        Playback.onMain { listeners.forEach { runCatching { it(status) } } }
    }

    // ---- một lượt của WorkManager -----------------------------------------------------------------------------------------------------------

    internal fun work(context: Context, stopped: () -> Boolean): Boolean {
        val mine = current(context)?.takeIf { it.state == "running" } ?: return true
        val cache = ReadAloud.cache()
        val budget = (cache.cap * PreparePlan.SHARE).toLong()
        val texts = ReadAloud.textChapters(mine.bookId, mine.chapters.map { it.id })
        val origin = ReadAloud.originNow(mine.bookId) // luồng của WorkManager: chờ đoán xong để cả việc dùng đúng gốc từ đoạn đầu
        val runner = PrepareRunner(
            texts = { chapter -> texts[chapter.id]?.second },
            cached = { cache.contains(mine.voice, it, origin) },
            make = { ReadAloud.readExactly(mine.voice, it, origin) },
            pin = { cache.pin(mine.voice, it, origin) },
            live = { ReadAloud.liveJobs() > 0 },
            stopped = { stopped() || synchronized(lock) { job?.id != mine.id } },
            save = { save(context, it); notify(context, it) },
            full = { cache.pinnedBytes() >= budget },
            timed = { chars, seconds -> runCatching { ReadAloud.speeds().record(mine.voice, chars, seconds) } },
            clock = SystemClock::elapsedRealtime,
            sliceMs = SLICE_MS,
        )
        working = true
        emit(context)
        val outcome = try {
            runner.run(mine)
        } finally {
            working = false
        }
        when (outcome) {
            PrepareRunner.Outcome.SLICE -> enqueue(context, mine, ExistingWorkPolicy.APPEND_OR_REPLACE)
            // Dừng vì mất điều kiện (rút sạc...) hay bị huỷ: WorkManager tự làm tiếp khi đủ điều kiện; thông báo "đang làm" thôi hiện.
            PrepareRunner.Outcome.STOPPED -> NotificationManagerCompat.from(context).cancel(NOTIFICATION)
            else -> Unit
        }
        emit(context)
        return outcome != PrepareRunner.Outcome.STOPPED
    }

    /** Thông báo tiến độ: đang làm (không vuốt đi được), xong, hay dừng vì lỗi. Người nghe tắt thông báo của app thì thôi. */
    private fun notify(context: Context, job: PrepareJob) {
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        if (Build.VERSION.SDK_INT >= 26) {
            val system = context.getSystemService(NotificationManager::class.java)
            if (system.getNotificationChannel(CHANNEL) == null) {
                system.createNotificationChannel(NotificationChannel(CHANNEL, "Làm trước để nghe", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Tiến độ đọc sẵn các chương tới"
                })
            }
        }
        val ready = job.chapters.count { it.ready }
        val (title, text) = when (job.state) {
            "running" -> "Đang làm trước ${job.label}" to "Đã sẵn sàng $ready/${job.chapters.size} chương"
            "done" -> "Đã làm trước ${job.label}" to
                if (job.online) "Nghe được cả khi không có mạng." else "Nghe liền mạch, không phải chờ."
            "error" -> "Đã dừng làm trước" to job.error
            else -> return manager.cancel(NOTIFICATION)
        }
        val open = context.packageManager.getLaunchIntentForPackage(context.packageName)
        val tap = open?.let { PendingIntent.getActivity(context, NOTIFICATION, it, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT) }
        val builder = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher_monochrome)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setOnlyAlertOnce(true)
            .setSilent(true)
        tap?.let { builder.setContentIntent(it) }
        if (job.state == "running") builder.setOngoing(true).setProgress(job.total.coerceAtLeast(1), job.done, false)
        else builder.setAutoCancel(true)
        runCatching { manager.notify(NOTIFICATION, builder.build()) }
    }
}

/** Một lượt "Làm trước" của WorkManager - chạy cả khi app đã đóng. */
class PrepareWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        Playback.init(applicationContext)
        return if (PrepareAhead.work(applicationContext) { isStopped }) Result.success() else Result.retry()
    }
}
