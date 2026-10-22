package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Tên giọng người nghe thấy cho giọng của máy đọc khác (ZeroTTS, Supertonic): khoá là tên giọng của máy ("baotrang", "F1"), người
 * nghe thấy "Bảo Trang" / "Supertonic F1" - đúng như máy tính (`humanize.voice_label`). MỘT file `abook/webui/assets/voice_labels.json`
 * ({khoá: nhãn}, bản của voice_catalog.ENGINE_VOICES; pytest giữ hai bên khớp), nằm trong assets của app (app/build.gradle):
 * [LibraryPlugin] nạp lúc khởi động ([load]), test JVM nạp đúng file ấy từ đĩa ([parse]). Giọng VieNeu nhãn là chính khoá nên không có
 * trong file; chưa nạp thì mọi giọng hiện khoá, như trước.
 */
object VoiceLabels {
    const val FILE = "voice_labels.json"

    @Volatile
    var labels: Map<String, String> = emptyMap()

    fun parse(text: String): Map<String, String> {
        val json = JSONObject(text)
        return BookEdits.names(json).associateWith { json.getString(it) }
    }

    fun load(context: Context): Map<String, String> = context.assets.open(FILE).use { parse(it.readBytes().toString(Charsets.UTF_8)) }

    /** `humanize.voice_label`: nhãn của khoá giọng, hay chính nó khi không có nhãn riêng. */
    fun label(name: String): String = labels[name] ?: name

    /** `humanize.labelled_voice`: bản sao của giọng `{"preset": khoá, ...}` kèm `label` CHỈ khi nhãn khác khoá (hợp đồng tests/fixtures/book_edits). */
    fun labelled(voice: JSONObject): JSONObject {
        val out = BookEdits.deepCopy(voice) as JSONObject
        val preset = voice.optString("preset", "")
        val label = label(preset)
        if (label != preset) out.put("label", label)
        return out
    }

    /** `humanize.label_cast_voices`: dàn nhân vật kèm `label` cho mỗi giọng (`voice`, `profile`, `pendingVoice`) của người kể và từng nhân vật; không sửa bản gốc. */
    fun labelCast(cast: JSONObject): JSONObject {
        fun one(value: Any?): Any? = if (value is JSONObject && value.opt("preset") is String) labelled(value) else value
        fun person(item: Any?): Any? {
            if (item !is JSONObject) return item
            val out = BookEdits.deepCopy(item) as JSONObject
            for (field in listOf("voice", "profile", "pendingVoice")) if (out.has(field)) out.put(field, one(out.opt(field)))
            return out
        }
        val out = JSONObject()
        for (key in BookEdits.names(cast)) {
            val value = cast.opt(key)
            out.put(key, when {
                value is JSONArray -> JSONArray().also { list -> for (index in 0 until value.length()) list.put(person(value.opt(index))) }
                key == "narrator" -> person(value)
                else -> BookEdits.deepCopy(value)
            })
        }
        return out
    }
}
