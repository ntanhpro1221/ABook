package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Viettel AI TTS (token của người dùng; 50.000 ký tự miễn phí trong tháng đầu) - bản điện thoại của `abook/readaloud/viettel.py` (định dạng đọc từ trang
 * https://viettelai.vn/tai-lieu và trang thử giọng của viettelai.vn, 03-10):
 * `POST https://viettelai.vn/tts/speech_synthesis` JSON {text, voice, speed: 1.0, tts_return_option: 3 (mp3), token, without_filter: false}, token gửi cả trong header
 * `token` (như trang thử giọng) lẫn trong thân (như bảng điều khiển) - không bao giờ trong địa chỉ. Trả thẳng MP3; lỗi là JSON `vi_message`; 429 = hết lượt.
 * Giọng: `GET https://viettelai.vn/tts/voices`. Không có mốc từng chữ: chia theo âm tiết ([SyllableSpread]).
 */
class ViettelTts(keys: OnlineKeys, private val base: String = BASE) : KeyedProvider(keys) {
    override val id = "viettel"
    override val name = "Viettel AI"
    override val limits = Limits(2000, "Miễn phí 50.000 ký tự trong tháng đầu", "estimated")

    companion object {
        const val BASE = "https://viettelai.vn"

        fun detail(body: ByteArray): String = runCatching {
            val answer = JSONObject(String(body, Charsets.UTF_8))
            answer.optString("vi_message").ifEmpty { answer.optString("en_message").ifEmpty { answer.optString("message") } }.take(200)
        }.getOrDefault("")
    }

    override fun listVoices(entry: OnlineKeys.Entry): List<OnlineKeys.VoiceRow> {
        val response = OnlineHttp.request("GET", "$base/tts/voices", mapOf("token" to entry.key), null, name)
        if (response.status != 200) throw OnlineHttp.failure(response.status, name, detail(response.body))
        val list = runCatching { JSONArray(String(response.body, Charsets.UTF_8)) }.getOrElse { throw VoiceException("$name trả danh sách giọng hỏng", cause = it) }
        return (0 until list.length()).mapNotNull { list.optJSONObject(it) }.filter { it.optString("code").isNotEmpty() }.map { item ->
            val label = item.optString("name").ifEmpty { item.getString("code") }.replace(" chất lượng cao", "")
            val described = item.optString("description").split(' ').filter { it.isNotEmpty() } // "Nữ miền Bắc"
            val region = described.drop(1).joinToString(" ")
            OnlineKeys.VoiceRow(item.getString("code"), if (region.isNotEmpty()) "$label - $region" else label, OnlineHttp.gender(described.firstOrNull()))
        }
    }

    override fun speak(entry: OnlineKeys.Entry, text: String, voice: String, out: File) = estimated(text, out) { piece ->
        val payload = JSONObject().put("text", piece).put("voice", voice).put("speed", 1.0).put("tts_return_option", 3).put("token", entry.key)
            .put("without_filter", false)
        val response = OnlineHttp.request("POST", "$base/tts/speech_synthesis", mapOf("token" to entry.key, "Content-Type" to "application/json"),
            payload.toString().toByteArray(Charsets.UTF_8), name)
        if (response.status != 200) throw OnlineHttp.failure(response.status, name, detail(response.body))
        if ("json" in response.headers["content-type"].orEmpty()) {
            throw VoiceException("$name không đọc được đoạn này (${detail(response.body).ifEmpty { "không rõ lý do" }})", reason = "service")
        }
        response.body
    }
}
