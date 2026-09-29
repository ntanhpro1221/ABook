package vn.ebookreader.player

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Báo về điện thoại khi máy tính sản xuất có tin: sách xong, dừng vì lỗi, dừng giữa chừng, có thêm "việc cần duyệt".
 *
 * Máy tính trả trạng thái gọn của mọi dự án (`GET /sync/v1/studio`, webui/sync.py SyncApp.studio_view) - chỉ cho thiết bị
 * được phép điều khiển sản xuất, khi công tắc Studio từ xa đang bật. Điện thoại tự so với lần hỏi trước (ảnh chụp trong
 * SharedPreferences "studio_alerts") nên máy tính không phải nhớ gì cho từng máy. Lần hỏi đầu chỉ chụp, không báo: bật
 * công tắc không được đổ ra một loạt tin cũ.
 *
 * Hỏi mỗi 15 phút (WorkManager, mức ngắn nhất Android cho) khi có mạng, và mỗi lần mở app. Bấm thông báo mở Studio từ xa
 * (StudioActivity) đúng cuốn, đúng tab.
 */
object StudioAlerts {
    private const val CHANNEL = "studio"
    private const val WORK = "studio-alerts"
    private val io = Executors.newSingleThreadExecutor()

    private fun state(context: Context) = context.getSharedPreferences("studio_alerts", Context.MODE_PRIVATE)

    fun enabled(context: Context): Boolean = state(context).getBoolean("enabled", false)

    fun permitted(context: Context): Boolean = NotificationManagerCompat.from(context).areNotificationsEnabled()

    fun setEnabled(context: Context, on: Boolean) {
        // Bật lại là bắt đầu một đợt mới: ảnh chụp cũ có thể đã cũ cả ngày, so với nó là báo tin cũ.
        state(context).edit().putBoolean("enabled", on).remove("snapshot").putBoolean("seeded", false).apply()
        val work = WorkManager.getInstance(context)
        if (!on) {
            work.cancelUniqueWork(WORK)
            return
        }
        val request = PeriodicWorkRequestBuilder<StudioAlertWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        work.enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.UPDATE, request)
        checkSoon(context)
    }

    /** Mở app: hỏi ngay trên luồng nền (không đợi tới lượt 15 phút). */
    fun checkSoon(context: Context) {
        if (!enabled(context)) return
        val app = context.applicationContext
        io.execute { runCatching { check(app) } }
    }

    /** Hỏi máy tính, so với lần trước, đăng thông báo. Không có mạng / máy tính tắt / hết quyền: im lặng, lần sau hỏi lại. */
    fun check(context: Context) {
        if (!enabled(context) || !SyncLink.paired(context)) return
        val reply = runCatching {
            JSONObject(SyncLink.request(context, "GET", "/sync/v1/studio", readTimeoutMs = 20_000, connectTimeoutMs = 4000))
        }.getOrNull() ?: return
        val books = reply.optJSONArray("books") ?: return
        val prefs = state(context)
        val before = runCatching { JSONObject(prefs.getString("snapshot", "{}") ?: "{}") }.getOrElse { JSONObject() }
        val seeded = prefs.getBoolean("seeded", false)
        val after = JSONObject()
        for (index in 0 until books.length()) {
            val book = books.optJSONObject(index) ?: continue
            val id = book.optString("id")
            if (id.isBlank()) continue
            after.put(id, JSONObject()
                .put("phase", book.optString("phase"))
                .put("running", book.optBoolean("running"))
                .put("paused", pausedOf(book))
                .put("work", if (book.isNull("work")) JSONObject.NULL else book.optInt("work")))
            val old = before.optJSONObject(id)
            if (seeded && old != null) alert(context, book, old)
        }
        prefs.edit().putString("snapshot", after.toString()).putBoolean("seeded", true).apply()
    }

    private fun alert(context: Context, book: JSONObject, old: JSONObject) {
        val id = book.optString("id")
        val title = book.optString("title").ifBlank { "Sách" }
        val phase = book.optString("phase")
        val chapters = book.optJSONObject("chapters")
        val progress = "${chapters?.optInt("completed") ?: 0}/${chapters?.optInt("total") ?: 0} chương"
        val wasPhase = old.optString("phase")
        when {
            phase == "done" && wasPhase != "done" ->
                post(context, "$id:done", "Đã xong: $title", "$progress nghe được. Bấm để mở Studio.", "/#/studio/$id")
            phase == "error" && wasPhase != "error" ->
                post(context, "$id:error", "Dừng vì lỗi: $title",
                    book.optString("lastError").ifBlank { book.optString("statusLabel") }.take(160), "/#/studio/$id?tab=activity")
            old.optBoolean("running") && !book.optBoolean("running") && phase != "done" && phase != "error" ->
                post(context, "$id:stopped", "Đã dừng: $title", "${book.optString("statusLabel")} · $progress", "/#/studio/$id")
            // Máy tính rút sạc nên Studio tự tạm dừng (power_source.py): báo để người ta biết máy tuột sạc - 24-09 sạc tuột
            // 22:50 mà 00:07 mới có người thấy.
            pausedOf(book) == "battery" && pausedOf(old) != "battery" ->
                post(context, "$id:battery", "Máy tính đang chạy pin",
                    "Đã tạm dừng $title · $progress. Cắm sạc là tự làm tiếp.", "/#/studio/$id")
        }
        if (!book.isNull("work") && !old.isNull("work")) {
            val now = book.optInt("work")
            val was = old.optInt("work")
            if (now > was) {
                post(context, "$id:work", "$title: $now việc cần duyệt",
                    "Thêm ${now - was} chỗ máy chưa chắc. Sửa không phải dừng sách.", "/#/studio/$id?tab=work")
            }
        }
    }

    /** "battery" / "listener" / "" - JSON null của máy tính đọc bằng optString ra chữ "null", nên đọc riêng. */
    private fun pausedOf(book: JSONObject): String = if (book.isNull("paused")) "" else book.optString("paused")

    private fun post(context: Context, key: String, title: String, text: String, path: String) {
        if (!permitted(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, "Studio trên máy tính", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Sách xong, dừng vì lỗi, có việc mới cần duyệt"
                },
            )
        }
        val open = Intent(context, StudioActivity::class.java)
            .putExtra("path", path)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val tap = PendingIntent.getActivity(context, key.hashCode(), open,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher_monochrome)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(tap)
            .setAutoCancel(true)
            .build()
        // Một thông báo cho mỗi (cuốn, loại tin): tin mới cùng loại thay tin cũ thay vì chồng lên.
        runCatching { NotificationManagerCompat.from(context).notify(key.hashCode(), notification) }
    }
}

/** Lượt hỏi định kỳ của WorkManager - chạy cả khi app đã đóng. */
class StudioAlertWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        runCatching { StudioAlerts.check(applicationContext) }
        return Result.success()
    }
}
