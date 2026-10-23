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
    @PluginMethod
    fun updateMetadata(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val array = call.getArray("chapters")
        val titles = (0 until (array?.length() ?: 0)).associate { index ->
            val chapter = array!!.getJSONObject(index)
            chapter.getInt("id") to chapter.getString("title")
        }
        Playback.onMain {
            call.getArray("queue")?.toList<JSONObject>()?.map {
                Playback.Chapter(it.getInt("id"), it.getString("title"), it.optString("file"), it.optDouble("duration", 0.0), LibraryTree.textEntry(it))
            }?.let { Playback.refreshQueue(id, it) }
            Playback.updateMetadata(id, call.getString("title") ?: "", call.getString("narrator") ?: "", titles)
            call.resolve(JSObject.fromJSONObject(Playback.state()))
        }
    }

    private var controller: ListenableFuture<MediaController>? = null
    private val listener: (JSONObject) -> Unit = { state ->
        notifyListeners("state", JSObject.fromJSONObject(state))
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

    /**
     * KHÔNG chờ quyền thông báo: hộp hệ thống ở đây chặn tiếng cho tới khi người nghe trả lời (soát điện thoại 03-10 - lần nghe đầu im lặng). Phát trước;
     * giao diện (android/notifications.ts) giải thích rồi mới xin, sau khi đã có tiếng ([requestNotificationAccess]).
     */
    @PluginMethod
    fun load(call: PluginCall) {
        val book = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val chapters = call.getArray("chapters")?.toList<JSONObject>()?.map {
            // Chương chỉ có chữ (state "text"): không có file audio, `text` = mục chữ trong gói; giọng máy đọc to (ReadAloud).
            Playback.Chapter(it.getInt("id"), it.getString("title"), it.optString("file"), it.optDouble("duration", 0.0), LibraryTree.textEntry(it))
        } ?: return call.reject("thiếu chapters")
        withService {
            call.getString("readAloudVoice")?.let { ReadAloud.rememberFor(book, it, call.getString("readAloudRecord") ?: "") } // Playback.load đặt giọng của cuốn (useVoiceOf)
            Playback.load(
                book, call.getString("bookTitle") ?: "", call.getString("narrator") ?: "", chapters,
                call.getInt("chapterId") ?: chapters.first().id, call.getDouble("seconds") ?: 0.0, call.getDouble("rate") ?: 1.0,
                call.getBoolean("autoplay") ?: true,
            )
            call.resolve(JSObject.fromJSONObject(Playback.state()))
        }
    }

    /** Quyền hiện thông báo (Android 13+): "granted" (hay máy cũ không cần), "off" (chưa cho: không có thông báo sách xong / việc cần duyệt / xuất MP3; nút tạm dừng, tua của phiên media vẫn có - Android miễn quyền cho chúng). */
    @PluginMethod
    fun notificationAccess(call: PluginCall) {
        call.resolve(JSObject().put("state", if (needsNotificationPermission()) "off" else "granted"))
    }

    /** Hiện hộp xin quyền của hệ thống; trả như [notificationAccess] sau khi người nghe trả lời. Giao diện chỉ gọi sau khi đã nói vì sao và đã có tiếng. */
    @PluginMethod
    fun requestNotificationAccess(call: PluginCall) {
        if (needsNotificationPermission()) requestPermissionForAlias("notifications", call, "notificationAccessAnswered") else notificationAccess(call)
    }

    @com.getcapacitor.annotation.PermissionCallback
    private fun notificationAccessAnswered(call: PluginCall) = notificationAccess(call)

    /** Mở trang cài đặt thông báo của ABook trong Cài đặt Android (sau khi từ chối, hộp xin quyền không hiện lại được). */
    @PluginMethod
    fun openNotificationSettings(call: PluginCall) {
        val intent = android.content.Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
            .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, context.packageName)
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(intent)
            call.resolve()
        } catch (error: Exception) {
            call.reject("Không mở được cài đặt thông báo")
        }
    }

    private fun act(call: PluginCall, block: () -> Unit) = withService {
        block()
        call.resolve(JSObject.fromJSONObject(Playback.state()))
    }

    @PluginMethod fun play(call: PluginCall) = act(call) { Playback.play() }
    @PluginMethod fun pause(call: PluginCall) = act(call) { Playback.pause() }
    /** Đóng sách: tạm dừng giọng và nhả bộ phát nhạc nền ([MusicBed.release]) - không giữ bài nhạc tới lần mở sách sau. */
    @PluginMethod fun release(call: PluginCall) = act(call) {
        Playback.pause()
        MusicBed.release()
    }
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
        val mark = Playback.addBookmark(call.getString("note") ?: "", call.getInt("index"), call.getString("quote") ?: "", call.getObject("anchor"))
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
        // Tuỳ chọn nghe mà Kotlin cần cả khi không có WebView (nút tai nghe, tự lùi, lắc / úp, lịch ngủ, số phút thêm, dừng an toàn): áp VÀ nhớ ở kho native.
        ListenPrefs.apply(call.data)
        // `readAloudBook`: cuốn mà người nghe vừa đổi giọng (nhớ cho cuốn ấy); không có thì cuốn đang nạp. `readAloudRecord`: hồ sơ nghe của giọng ấy (giọng riêng theo từng hồ sơ).
        call.getString("readAloudVoice")?.let { ReadAloud.chooseFor(call.getString("readAloudBook") ?: Playback.bookId, it, call.getString("readAloudRecord") ?: "") }
        call.getString("readAloudDefault")?.let { ReadAloud.chooseDefault(it) }
        // Nhà cung cấp giọng trực tuyến người nghe đã đồng ý gửi chữ tới: lõi tự sang chương chữ chỉ khi giọng đang chọn đã được đồng ý.
        call.getArray("readAloudOnlineOk")?.let { list -> ReadAloud.allowOnline((0 until list.length()).map { list.optString(it) }) }
        call.getBoolean("autoMusic")?.let {
            // Sách chữ đang nghe mà chưa chọn nhạc: bật / tắt "Tự chọn nhạc nền" đổi nhạc theo cảnh ngay, không đợi mở lại sách.
            if (it != Playlists.autoEnabled) MusicBed.invalidate(Playback.bookId)
            Playlists.autoEnabled = it
            MusicBed.rememberAuto(it)
        }
        // Tuỳ chọn thử nghiệm (mặc định tắt): nhạc lặp qua MỘT trình phát nối chính xác từng mẫu (MusicBed.musicSeamP3); chỉ ảnh hưởng bài mở sau đó.
        call.getBoolean("musicSeamP3")?.let { MusicBed.rememberSeamP3(it) }
    }

    /** Tuỳ chọn nghe native đã nhớ ([ListenPrefs.stored]): giao diện lúc mở app lấy làm chuẩn khi bản localStorage của WebView cũ hơn hay không ghi được. */
    @PluginMethod
    fun listenPrefs(call: PluginCall) {
        call.resolve(JSObject().put("prefs", JSObject.fromJSONObject(ListenPrefs.stored())))
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
