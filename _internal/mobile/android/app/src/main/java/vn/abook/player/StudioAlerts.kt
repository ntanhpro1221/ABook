package vn.abook.player

import vn.abook.player.ui.data.dotJoin
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
import vn.abook.player.ui.NativeActivity
import vn.abook.player.ui.studio.StudioRoute
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
 * (màn native) đúng cuốn, đúng tab.
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
        if (reply.optJSONArray("books") == null) return
        val prefs = state(context)
        val before = runCatching { JSONObject(prefs.getString("snapshot", "{}") ?: "{}") }.getOrElse { JSONObject() }
        // Giá trị của lần hỏi TRƯỚC: đọc trước khi ghi lần này (ghi trước rồi đọc lại thì luôn thấy chính lần này và tin "tạm dừng vì
        // pin" của từng cuốn không bao giờ tới - soát a88 V6).
        val poll = evaluate(reply, before, prefs.getBoolean("seeded", false), prefs.getBoolean("onBattery", false))
        prefs.edit().putBoolean("onBattery", poll.onBattery).putString("snapshot", poll.snapshot.toString()).putBoolean("seeded", true).apply()
        for (note in poll.alerts) post(context, note.key, note.title, note.text, note.path)
    }

    /** Kết quả một lần hỏi: các tin cần đăng, ảnh chụp để so lần sau, máy tính có đang chạy pin không. */
    data class Poll(val alerts: List<Alert>, val snapshot: JSONObject, val onBattery: Boolean)

    /**
     * So câu trả lời của máy tính với ảnh chụp lần trước. Hàm thuần (không Context) để test JVM.
     * `seeded`: đã có ảnh chụp trước (lần đầu chỉ chụp, không báo); `wasOnBattery`: máy tính đã chạy pin ở lần hỏi trước.
     */
    fun evaluate(reply: JSONObject, before: JSONObject, seeded: Boolean, wasOnBattery: Boolean): Poll {
        val out = mutableListOf<Alert>()
        // Máy tính tuột sạc (cấp máy, kể cả khi không có sách nào chạy): báo một lần mỗi lần rút; máy bàn gửi false/null.
        val unplugged = !reply.isNull("onBattery") && reply.optBoolean("onBattery")
        if (seeded && unplugged && !wasOnBattery) {
            out += Alert("machine:battery", S.s_may_tinh_dung_pin_3a090a56,
                S.s_0_dang_dung_pin_ban_kiem_tra_sac_56250fc9(reply.optString("name").ifBlank { S.s_may_tinh_828ebb9d }), "/#/studio")
        }
        val books = reply.optJSONArray("books")
        val after = JSONObject()
        for (index in 0 until (books?.length() ?: 0)) {
            val book = books?.optJSONObject(index) ?: continue
            val id = book.optString("id")
            if (id.isBlank()) continue
            after.put(id, JSONObject()
                .put("phase", book.optString("phase"))
                .put("running", book.optBoolean("running"))
                .put("paused", pausedOf(book))
                .put("held", heldOf(book))
                .put("work", if (book.isNull("work")) JSONObject.NULL else book.optInt("work")))
            val old = before.optJSONObject(id)
            if (seeded && old != null) out += alerts(book, old, wasOnBattery)
        }
        return Poll(out, after, unplugged)
    }

    /** Một tin sắp đăng: `key` = (cuốn, loại tin) - tin mới cùng loại thay tin cũ. */
    data class Alert(val key: String, val title: String, val text: String, val path: String)

    /**
     * Những tin cần báo khi so trạng thái một cuốn với ảnh chụp lần trước (`old`). Hàm thuần (không Context) để test JVM.
     * `machineOnBattery`: máy tính đã chạy pin từ lần hỏi TRƯỚC (đã được báo ở cấp máy) - không báo lại cho từng cuốn.
     */
    fun alerts(book: JSONObject, old: JSONObject, machineOnBattery: Boolean): List<Alert> {
        val out = mutableListOf<Alert>()
        val id = book.optString("id")
        val title = book.optString("title").ifBlank { S.s_sach_0c2b3e9b }
        val phase = book.optString("phase")
        val chapters = book.optJSONObject("chapters")
        val progress = S.s_0_1_chuong_8d58e1df(chapters?.optInt("completed") ?: 0, chapters?.optInt("total") ?: 0)
        val wasPhase = old.optString("phase")
        when {
            phase == "done" && wasPhase != "done" ->
                out += Alert("$id:done", S.s_da_xong_0_7aedf485(title), S.s_0_nghe_duoc_ban_mo_studio_de_nghe_eceb538a(progress), "/#/studio/$id")
            phase == "error" && wasPhase != "error" ->
                out += Alert("$id:error", S.s_dung_vi_loi_0_c02f0076(title),
                    S.s_lam_sach_gap_loi_ban_mo_studio_de_xem_dfb62d3c, "/#/studio/$id?tab=activity")
            // Phân tích xong, máy giữ cuốn chờ duyệt trước khi thu (webui/precast.py). Đứng trước "Đã dừng": cuốn đứng chờ
            // người duyệt không phải là dừng.
            heldOf(book) && !old.optBoolean("held") ->
                out += Alert("$id:precast", S.s_san_sang_duyet_0_41c6c743(title),
                    S.s_ban_duyet_giong_ten_va_cau_chua_chac_truoc_630fd971, "/#/studio/$id?tab=precast")
            old.optBoolean("running") && !book.optBoolean("running") && phase != "done" && phase != "error" &&
                !heldOf(book) ->
                // Máy tính nói lượt chạy kết thúc ra sao (`end`): bạn bấm Dừng khác với máy sập - tin sau cần mở Studio xem nguyên nhân
                // (soát a88 T4). Máy tính đời cũ không gửi `end` thì giữ tin cũ.
                out += when (book.optString("end")) {
                    "failed", "lost" -> Alert("$id:crashed", S.s_su_co_0_f2a511ec(title),
                        (if (book.optString("end") == "lost") S.s_lam_sach_bi_ngat_dot_ngot_497f7190
                        else S.s_lam_sach_gap_su_co_3d9065b0) +
                            S.s_0_ban_mo_studio_5c0b13a2(progress), "/#/studio/$id")
                    "stopped" -> Alert("$id:stopped", S.s_da_dung_0_b9714c73(title), S.s_ban_da_bam_dung_0_0400929a(progress), "/#/studio/$id")
                    else -> Alert("$id:stopped", S.s_da_dung_0_b9714c73(title), dotJoin(book.optString("statusLabel"), progress), "/#/studio/$id")
                }
            // Máy tính rút sạc nên Studio tự tạm dừng (power_source.py): báo để người ta biết máy tuột sạc - 24-09 sạc tuột
            // 22:50 mà 00:07 mới có người thấy.
            pausedOf(book) == "battery" && pausedOf(old) != "battery" && !machineOnBattery ->
                out += Alert("$id:battery", S.s_chay_pin_0_ca28e520(title),
                    S.s_tam_dung_0_cam_sac_de_tu_lam_tiep_f6929a3d(progress), "/#/studio/$id")
        }
        if (!book.isNull("work") && !old.isNull("work")) {
            val now = book.optInt("work")
            val was = old.optInt("work")
            if (now > was) {
                out += Alert("$id:work", S.s_0_1_viec_can_duyet_ace8198b(title, now),
                    S.s_them_0_cho_chua_chac_ban_sua_khi_sach_van_d53927eb(now - was), "/#/studio/$id?tab=work")
            }
        }
        return out
    }

    /** Máy tính đang giữ cuốn chờ duyệt trước khi thu (`precast.held`); máy tính đời cũ không gửi = không giữ. */
    private fun heldOf(book: JSONObject): Boolean = book.optJSONObject("precast")?.optBoolean("held") == true

    /** "battery" / "listener" / "" - JSON null của máy tính đọc bằng optString ra chữ "null", nên đọc riêng. */
    private fun pausedOf(book: JSONObject): String = if (book.isNull("paused")) "" else book.optString("paused")

    private fun post(context: Context, key: String, title: String, text: String, path: String) {
        if (!permitted(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, S.s_studio_tren_may_tinh_6c00d830, NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = S.s_sach_xong_dung_vi_loi_co_viec_moi_can_duye_8ebdb9f2
                },
            )
        }
        // Mở thẳng dự án ở đúng tab bằng màn native (mã máy, mã sách, tab - không bao giờ mã thiết bị).
        val open = StudioRoute.put(Intent(context, NativeActivity::class.java), StudioLink.MAIN, StudioRoute.parse(path))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val tap = PendingIntent.getActivity(context, key.hashCode(), open,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
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
