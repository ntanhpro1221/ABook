package vn.abook.player.readaloud

import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import vn.abook.player.Playback
import vn.abook.player.vieneu.VieneuVoices

/**
 * Cầu nối giao diện <-> đọc to (ReadAloud). Giao diện chọn giọng và hỏi mốc thời gian; việc phát đi qua `EbookPlayer` (lõi phát: `load` với chương
 * `state: "text"`, `readAloudVoice`, `seekTo`/`jumpTo` có `segment` + `word`).
 *
 * - `voices()` -> `{voices: [{id, name, provider: "edge"|"device", online, default, gainDb}]}`; id dạng "edge:vi-VN-HoaiMyNeural" / "device:<tên giọng Android>".
 * - `script({bookId, chapterId})` -> `{segments: [{index, start, end, words, timed}]}`: `start`/`end` giây từ đầu chương, `words` là [bắt đầu_ms, kết thúc_ms] từ
 *   đầu chương (cùng đồng hồ với kịch bản audio của Studio, ui/src/listen/words.ts); đoạn chưa đọc thì `timed` false, `words` rỗng, giây là ước lượng.
 * - Sự kiện `readAloudScript` {bookId, chapterId}: có thêm mốc mới - hỏi lại `script()`.
 * - Sự kiện `readAloudNotice` {message}: một đoạn vừa đọc tạm bằng giọng kế (khoá bị từ chối, hết hạn mức, mất mạng) - nói cho người nghe.
 * - `sample({voice, text})` -> `{path}`: "Thử giọng" trong Cài đặt (đúng giọng ấy, không rơi sang giọng khác).
 * - Giọng dùng khoá của người dùng (OnlineVoices.kt): `onlineProviders()` -> `{providers: [...]}` (khoá chỉ ở dạng che), `setOnlineKey({provider, key, region})`,
 *   `removeOnlineKey({provider})`, `checkOnlineKey({provider})` -> `{ok, reason?, message?, voices?, provider}`. Khoá đi vào qua lệnh plugin, không bao giờ ra lại.
 * - Mô-đun "Giọng VieNeu" (vieneu/VieneuModule.kt, cùng hình trạng thái với máy tính - ui/src/listen/vieneuModule.ts): `vieneuStatus()`,
 *   `vieneuStart({choices?})` (không có `choices`: cập nhật phần cũ), `vieneuMeasure()` (đo lại tốc độ), `vieneuRemove({choice})` - đều trả trạng thái mới.
 * - "Làm trước" (PrepareAhead.kt): `preparePlan({bookId, voice, chapterIds})` -> `{chapters, offered, audioSeconds, secondsEstimate}` (ước trước khi bấm);
 *   `prepareStart({bookId, voice, chapterIds, label, chargingOnly})`, `prepareStatus()`, `prepareCancel()`, `prepareOptions({chargingOnly})` -> trạng thái
 *   (`PrepareStatus` của ui/src/listen/prepareAhead.ts). Sự kiện `readAloudPrepare` (trạng thái) sau mỗi đoạn và mỗi lần đổi.
 */
@CapacitorPlugin(name = "ReadAloud")
class ReadAloudPlugin : Plugin() {
    private val listener: (String, Int) -> Unit = { book, chapter ->
        notifyListeners("readAloudScript", JSObject().put("bookId", book).put("chapterId", chapter))
    }

    private val noticeListener: (String) -> Unit = { message -> notifyListeners("readAloudNotice", JSObject().put("message", message)) }

    private val prepareListener: (org.json.JSONObject) -> Unit = { status -> notifyListeners("readAloudPrepare", JSObject.fromJSONObject(status)) }

    override fun load() {
        Playback.init(context)
        ReadAloud.addScriptListener(listener)
        ReadAloud.addNoticeListener(noticeListener)
        PrepareAhead.addListener(prepareListener)
    }

    override fun handleOnDestroy() {
        PrepareAhead.removeListener(prepareListener)
        ReadAloud.removeNoticeListener(noticeListener)
        ReadAloud.removeScriptListener(listener)
        super.handleOnDestroy()
    }

    // Lệnh plugin chạy ở luồng nền của Capacitor: hỏi bộ đọc của máy (có thể chờ vài giây) không làm kẹt luồng chính.
    @PluginMethod
    fun voices(call: PluginCall) {
        val array = JSArray()
        ReadAloud.voices(context).forEach { array.put(JSObject.fromJSONObject(it)) }
        call.resolve(JSObject().put("voices", array))
    }

    @PluginMethod
    fun script(call: PluginCall) {
        val book = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val chapter = call.getInt("chapterId") ?: return call.reject("thiếu chapterId")
        // Cuốn đang nạp: đồng hồ ảo chỉ đọc được ở luồng chính.
        if (book == Playback.bookId) Playback.onMain { call.resolve(JSObject.fromJSONObject(ReadAloud.script(book, chapter))) }
        else call.resolve(JSObject.fromJSONObject(ReadAloud.script(book, chapter)))
    }

    @PluginMethod
    fun sample(call: PluginCall) {
        val voice = call.getString("voice") ?: return call.reject("thiếu voice")
        val text = call.getString("text") ?: return call.reject("thiếu text")
        try {
            call.resolve(JSObject().put("path", ReadAloud.sample(voice, text).absolutePath))
        } catch (error: VoiceException) {
            call.reject(error.message ?: "Không đọc thử được", error.reason)
        }
    }

    private fun chapterIds(call: PluginCall): List<Int>? =
        call.getArray("chapterIds")?.let { array -> (0 until array.length()).mapNotNull { array.opt(it)?.toString()?.toDoubleOrNull()?.toInt() } }

    @PluginMethod
    fun preparePlan(call: PluginCall) {
        val book = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val voice = call.getString("voice") ?: return call.reject("thiếu voice")
        val ids = chapterIds(call) ?: return call.reject("thiếu chapterIds")
        call.resolve(JSObject.fromJSONObject(PrepareAhead.plan(context, book, voice, ids)))
    }

    @PluginMethod
    fun prepareStart(call: PluginCall) {
        val book = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val voice = call.getString("voice") ?: return call.reject("thiếu voice")
        val ids = chapterIds(call) ?: return call.reject("thiếu chapterIds")
        val chargingOnly = call.getBoolean("chargingOnly", PrepareAhead.chargingOnly(context))!!
        call.resolve(JSObject.fromJSONObject(PrepareAhead.start(context, book, voice, ids, call.getString("label", "")!!, chargingOnly)))
    }

    @PluginMethod
    fun prepareStatus(call: PluginCall) {
        call.resolve(JSObject.fromJSONObject(PrepareAhead.status(context)))
    }

    @PluginMethod
    fun prepareCancel(call: PluginCall) {
        call.resolve(JSObject.fromJSONObject(PrepareAhead.cancel(context)))
    }

    @PluginMethod
    fun prepareOptions(call: PluginCall) {
        val on = call.getBoolean("chargingOnly") ?: return call.reject("thiếu chargingOnly")
        call.resolve(JSObject.fromJSONObject(PrepareAhead.setChargingOnly(context, on)))
    }

    @PluginMethod
    fun onlineProviders(call: PluginCall) {
        call.resolve(JSObject().apply { put("providers", OnlineVoices.describe(context)) })
    }

    @PluginMethod
    fun setOnlineKey(call: PluginCall) {
        val provider = call.getString("provider") ?: return call.reject("thiếu provider")
        val region = call.getString("region", "")!!.trim().lowercase()
        if (provider == "azure" && !AzureTts.validRegion(region)) return call.reject("Vùng Azure chưa đúng (ví dụ: southeastasia)")
        try {
            val keyed = OnlineVoices.provider(context, provider)
            keyed.keys.put(provider, call.getString("key", "")!!, if (provider == "azure") region else "")
            call.resolve(JSObject.fromJSONObject(keyed.describe()))
        } catch (error: IllegalArgumentException) {
            call.reject(error.message ?: "Thiếu khóa")
        }
    }

    @PluginMethod
    fun removeOnlineKey(call: PluginCall) {
        val provider = call.getString("provider") ?: return call.reject("thiếu provider")
        try {
            val keyed = OnlineVoices.provider(context, provider)
            keyed.keys.remove(provider)
            call.resolve(JSObject.fromJSONObject(keyed.describe()))
        } catch (error: IllegalArgumentException) {
            call.reject(error.message ?: "Nhà cung cấp lạ")
        }
    }

    @PluginMethod
    fun checkOnlineKey(call: PluginCall) {
        val provider = call.getString("provider") ?: return call.reject("thiếu provider")
        try {
            val keyed = OnlineVoices.provider(context, provider)
            val result = keyed.check(java.io.File(context.cacheDir, "readaloud-check.mp3"))
            call.resolve(JSObject.fromJSONObject(result.put("provider", keyed.describe())))
        } catch (error: IllegalArgumentException) {
            call.reject(error.message ?: "Nhà cung cấp lạ")
        }
    }

    private fun resolveVieneu(call: PluginCall) = call.resolve(JSObject.fromJSONObject(VieneuVoices.module(context).status()))

    @PluginMethod
    fun vieneuStatus(call: PluginCall) = resolveVieneu(call)

    @PluginMethod
    fun vieneuStart(call: PluginCall) {
        val picked = call.getArray("choices")?.toList<String>()
        try {
            VieneuVoices.module(context).start(picked)
            resolveVieneu(call)
        } catch (error: IllegalArgumentException) {
            call.reject(error.message ?: "Lựa chọn lạ")
        }
    }

    @PluginMethod
    fun vieneuMeasure(call: PluginCall) {
        VieneuVoices.module(context).measureAgain()
        resolveVieneu(call)
    }

    @PluginMethod
    fun vieneuRemove(call: PluginCall) {
        val choice = call.getString("choice") ?: return call.reject("thiếu choice")
        try {
            VieneuVoices.module(context).remove(choice)
            Playback.onMain { ReadAloud.voicesChanged() } // cuốn đang đọc bằng giọng vừa gỡ thì đọc tiếp bằng giọng mặc định, không chờ lần nạp kế
            resolveVieneu(call)
        } catch (error: IllegalArgumentException) {
            call.reject(error.message ?: "Lựa chọn lạ")
        }
    }
}
