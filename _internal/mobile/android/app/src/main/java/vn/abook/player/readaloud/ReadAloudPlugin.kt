package vn.abook.player.readaloud

import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import vn.abook.player.Playback

/**
 * Cầu nối giao diện <-> đọc to (ReadAloud). Giao diện chọn giọng và hỏi mốc thời gian; việc phát đi qua `EbookPlayer` (lõi phát: `load` với chương
 * `state: "text"`, `readAloudVoice`, `seekTo`/`jumpTo` có `segment` + `word`).
 *
 * - `voices()` -> `{voices: [{id, name, provider: "edge"|"device", online, default, gainDb}]}`; id dạng "edge:vi-VN-HoaiMyNeural" / "device:<tên giọng Android>".
 * - `script({bookId, chapterId})` -> `{segments: [{index, start, end, words, timed}]}`: `start`/`end` giây từ đầu chương, `words` là [bắt đầu_ms, kết thúc_ms] từ
 *   đầu chương (cùng đồng hồ với kịch bản audio của Studio, ui/src/listen/words.ts); đoạn chưa đọc thì `timed` false, `words` rỗng, giây là ước lượng.
 * - Sự kiện `readAloudScript` {bookId, chapterId}: có thêm mốc mới - hỏi lại `script()`.
 */
@CapacitorPlugin(name = "ReadAloud")
class ReadAloudPlugin : Plugin() {
    private val listener: (String, Int) -> Unit = { book, chapter ->
        notifyListeners("readAloudScript", JSObject().put("bookId", book).put("chapterId", chapter))
    }

    override fun load() {
        Playback.init(context)
        ReadAloud.addScriptListener(listener)
    }

    override fun handleOnDestroy() {
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
}
