package vn.abook.player

import android.Manifest
import android.content.ComponentName
import android.os.Build
import android.os.Looper
import androidx.core.content.ContextCompat
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.MoreExecutors
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud

/**
 * Cầu nối giao diện <-> lõi phát. Giao diện gửi lệnh; lõi phát (Playback) báo trạng thái qua sự kiện "state".
 * Kết nối một MediaController tới PlaybackService để dịch vụ được khởi động/giữ sống theo đúng cách Media3.
 */
@CapacitorPlugin(
    name = "EbookPlayer",
    permissions = [Permission(strings = [Manifest.permission.POST_NOTIFICATIONS], alias = "notifications")],
)
class PlayerPlugin : Plugin() {
    private var controller: ListenableFuture<MediaController>? = null
    private val listener: (JSONObject) -> Unit = { state ->
        notifyListeners("state", JSObject.fromJSONObject(state))
        if (state.optString("kind") == "sleep") PlaybackService.instance?.refreshButtons()
    }

    override fun load() {
        Playback.init(context)
        Playback.addListener(listener)
    }

    override fun handleOnDestroy() {
        Playback.removeListener(listener)
        controller?.let { MediaController.releaseFuture(it) }
        super.handleOnDestroy()
    }

    /**
     * Bảo đảm dịch vụ phát đã chạy rồi mới làm việc (lần đầu mất vài chục ms).
     *
     * Lệnh plugin của Capacitor chạy trên luồng nền của nó, còn MediaController gắn với luồng đã dựng nó: dựng ở đó thì
     * `handleOnDestroy` (luồng chính) giải phóng nó là Media3 ném "called from a wrong thread" - app crash mỗi lần thoát
     * (thấy 27-09 trên máy ảo). Nên ghim controller vào luồng chính.
     */
    private fun withService(block: () -> Unit) {
        val future = controller ?: MediaController.Builder(
            context, SessionToken(context, ComponentName(context, PlaybackService::class.java)),
        ).setApplicationLooper(Looper.getMainLooper()).buildAsync().also { controller = it }
        future.addListener({ Playback.onMain(block) }, MoreExecutors.directExecutor())
    }

    private fun needsNotificationPermission(): Boolean =
        Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            android.content.pm.PackageManager.PERMISSION_GRANTED

    @PluginMethod
    fun load(call: PluginCall) {
        if (needsNotificationPermission()) requestPermissionForAlias("notifications", call, "loadAfterPermission")
        else loadAfterPermission(call)
    }

    @com.getcapacitor.annotation.PermissionCallback
    private fun loadAfterPermission(call: PluginCall) {
        val book = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val chapters = call.getArray("chapters")?.toList<JSONObject>()?.map {
            // Chương chỉ có chữ (state "text"): không có file audio, `text` = mục chữ trong gói; giọng máy đọc to (ReadAloud).
            Playback.Chapter(it.getInt("id"), it.getString("title"), it.optString("file"), it.optDouble("duration", 0.0), LibraryTree.textEntry(it))
        } ?: return call.reject("thiếu chapters")
        withService {
            call.getString("readAloudVoice")?.let { ReadAloud.chooseFor(book, it) }
            Playback.load(
                book, call.getString("bookTitle") ?: "", call.getString("narrator") ?: "", chapters,
                call.getInt("chapterId") ?: chapters.first().id, call.getDouble("seconds") ?: 0.0, call.getDouble("rate") ?: 1.0,
                call.getBoolean("autoplay") ?: true,
            )
            call.resolve(JSObject.fromJSONObject(Playback.state()))
        }
    }

    private fun act(call: PluginCall, block: () -> Unit) = withService {
        block()
        call.resolve(JSObject.fromJSONObject(Playback.state()))
    }

    @PluginMethod fun play(call: PluginCall) = act(call) { Playback.play() }
    @PluginMethod fun pause(call: PluginCall) = act(call) { Playback.pause() }
    @PluginMethod fun toggle(call: PluginCall) = act(call) { Playback.toggle() }
    @PluginMethod fun next(call: PluginCall) = act(call) { Playback.next() }
    @PluginMethod fun previous(call: PluginCall) = act(call) { Playback.previous() }
    /** `segment` + `word` (chương đọc to): tua tới đúng chữ ấy của đoạn ấy, thắng `seconds` (xem Playback.seekTo). */
    @PluginMethod
    fun seekTo(call: PluginCall) = act(call) {
        Playback.seekTo(call.getDouble("seconds") ?: 0.0, call.getInt("segment") ?: -1, call.getInt("word") ?: -1)
    }
    @PluginMethod fun skip(call: PluginCall) = act(call) { Playback.skip(call.getDouble("delta") ?: 0.0) }
    @PluginMethod fun setRate(call: PluginCall) = act(call) { Playback.setRate(call.getDouble("rate") ?: 1.0) }

    @PluginMethod
    fun jumpTo(call: PluginCall) = act(call) {
        Playback.jumpTo(call.getInt("chapterId") ?: return@act, call.getDouble("seconds") ?: 0.0, call.getInt("segment") ?: -1, call.getInt("word") ?: -1)
    }

    /** Trên luồng chính: Playback.state() đọc ExoPlayer, mà ExoPlayer chỉ cho luồng chính. Gọi thẳng từ luồng plugin thì
     *  văng "Player is accessed on the wrong thread" - thử 28-09: mở app khi dịch vụ phát còn giữ trình phát (giao diện
     *  hỏi trạng thái ngay lúc mở, nativeEngine.ts) là app chết, dịch vụ tự bật lại, mở lại lại chết. */
    @PluginMethod
    fun getState(call: PluginCall) = Playback.onMain { call.resolve(JSObject.fromJSONObject(Playback.state())) }

    @PluginMethod
    fun addBookmark(call: PluginCall) = withService {
        val mark = Playback.addBookmark(call.getString("note") ?: "")
        if (mark == null) call.reject("chưa phát gì") else call.resolve(JSObject.fromJSONObject(mark))
    }

    @PluginMethod
    fun setSleep(call: PluginCall) = act(call) {
        when (call.getString("mode")) {
            "minutes" -> SleepTimer.setMinutes(call.getInt("minutes") ?: 30)
            "chapter" -> SleepTimer.setEndOfChapter()
            else -> SleepTimer.cancel()
        }
    }

    @PluginMethod fun extendSleep(call: PluginCall) = act(call) { SleepTimer.extend(call.getInt("minutes") ?: SleepTimer.extendMinutes) }

    @PluginMethod
    fun configure(call: PluginCall) = act(call) {
        call.getInt("sleepExtendMinutes")?.let { SleepTimer.extendMinutes = it }
        call.getInt("sleepFadeSeconds")?.let { SleepTimer.fadeMs = it * 1000L }
        call.getBoolean("shakeToExtend")?.let { SleepTimer.shakeEnabled = it }
        call.getString("shakeAction")?.let { SleepTimer.shakeResets = it == "reset" }
        call.getBoolean("headsetSkips")?.let { Playback.headsetSkips = it }
        // `readAloudBook`: cuốn mà người nghe vừa đổi giọng (nhớ cho cuốn ấy); không có thì cuốn đang nạp.
        call.getString("readAloudVoice")?.let { ReadAloud.chooseFor(call.getString("readAloudBook") ?: Playback.bookId, it) }
        // Nhà cung cấp giọng trực tuyến người nghe đã đồng ý gửi chữ tới: lõi tự sang chương chữ chỉ khi giọng đang chọn đã được đồng ý.
        call.getArray("readAloudOnlineOk")?.let { list -> ReadAloud.allowOnline((0 until list.length()).map { list.optString(it) }) }
        call.getBoolean("flipToPause")?.let {
            Motion.flipEnabled = it
            Motion.refresh()
        }
        call.getString("shakeSensitivity")?.let {
            SleepTimer.shakeThresholdG = when (it) { "gentle" -> 1.6; "firm" -> 2.8; else -> 2.2 }
        }
        call.getDouble("safetyStopHours")?.let { SleepTimer.safetyStopHours = it }
        if (call.data.has("schedule")) {
            val schedule = call.getObject("schedule")
            fun minutesOf(clock: String?) = clock?.split(":")?.let { (it[0].toIntOrNull() ?: 0) * 60 + (it.getOrNull(1)?.toIntOrNull() ?: 0) }
            val from = minutesOf(schedule?.getString("from"))
            val to = minutesOf(schedule?.getString("to"))
            val planned = schedule?.getInteger("minutes")
            SleepTimer.schedule = if (from != null && to != null && planned != null) Triple(from, to, planned) else null
        }
        Playback.configure(call.getDouble("rewindAfterMinutes") ?: 5.0, call.getDouble("rewindSeconds") ?: 5.0)
    }

    @PluginMethod
    fun lastNight(call: PluginCall) {
        val latest = Bedtime.latest()
        call.resolve(JSObject().put("session", latest?.let { JSObject.fromJSONObject(it) }))
    }

    @PluginMethod
    fun dismissLastNight(call: PluginCall) {
        Bedtime.dismiss()
        call.resolve()
    }
}
