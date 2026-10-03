package vn.abook.player.readaloud

import org.json.JSONObject
import java.io.File

/**
 * FPT.AI Text to Speech (khoá API của người dùng; 100.000 ký tự miễn phí mỗi tháng) - bản điện thoại của `abook/readaloud/fpt.py`.
 *
 * Theo https://docs.fpt.ai/docs/en/speech/api/text-to-speech/ (đọc 03-10): `POST https://api.fpt.ai/hmi/tts/v5`, thân là chữ thuần (3-5000 ký tự), header `api_key`,
 * `voice`, `speed` (0 = thường), `format` (mp3). Trả JSON `{"async": <link>, "error": 0}`; file có sau "5 giây tới 2 phút" -> hỏi lại link (không kèm khoá) tới khi
 * có. Không có mốc từng chữ: chia theo âm tiết ([SyllableSpread]).
 */
class FptTts(
    keys: OnlineKeys,
    private val url: String = URL,
    private val pollMs: Long = 1000,
    private val pollLimitMs: Long = 120_000,
) : KeyedProvider(keys) {
    override val id = "fpt"
    override val name = "FPT.AI"
    override val limits = Limits(4500, "Miễn phí 100.000 ký tự mỗi tháng", "estimated")

    companion object {
        const val URL = "https://api.fpt.ai/hmi/tts/v5"
        const val KEY_HEADER = "api_key" // đúng chính tả trong tài liệu
        val VOICES = listOf(
            OnlineKeys.VoiceRow("banmai", "Ban Mai - miền Bắc", "female"), OnlineKeys.VoiceRow("thuminh", "Thu Minh - miền Bắc", "female"),
            OnlineKeys.VoiceRow("leminh", "Lê Minh - miền Bắc", "male"), OnlineKeys.VoiceRow("myan", "Mỹ An - miền Trung", "female"),
            OnlineKeys.VoiceRow("giahuy", "Gia Huy - miền Trung", "male"), OnlineKeys.VoiceRow("lannhi", "Lan Nhi - miền Nam", "female"),
            OnlineKeys.VoiceRow("linhsan", "Linh San - miền Nam", "female"),
        )
        private val QUOTA_WORDS = listOf("quota", "limit", "exceed", "credit", "balance", "hết", "vượt", "hạn mức")
    }

    override fun listVoices(entry: OnlineKeys.Entry) = VOICES // danh sách cố định của tài liệu; khoá được kiểm bằng lần đọc thử

    private fun ask(key: String, voice: String, text: String): String {
        val response = OnlineHttp.request("POST", url, mapOf(KEY_HEADER to key, "voice" to voice, "speed" to "0", "format" to "mp3",
            "Content-Type" to "text/plain; charset=utf-8"), text.toByteArray(Charsets.UTF_8), name)
        val answer = runCatching { JSONObject(String(response.body, Charsets.UTF_8)) }.getOrNull()
        val detail = answer?.optString("message").orEmpty()
        if (response.status != 200) throw OnlineHttp.failure(response.status, name, detail)
        val link = answer?.optString("async").orEmpty()
        if (answer == null || answer.optInt("error", -1) != 0 || link.isEmpty()) {
            if (QUOTA_WORDS.any { it in detail.lowercase() }) throw OnlineHttp.failure(429, name, detail)
            throw VoiceException("$name không đọc được đoạn này (${detail.take(200).ifEmpty { "không rõ lý do" }})", reason = "service")
        }
        if (!link.startsWith("https://") && !link.startsWith("http://")) throw VoiceException("$name trả link lạ", reason = "service")
        return link
    }

    private fun fetch(link: String): ByteArray {
        val deadline = System.nanoTime() + pollLimitMs * 1_000_000
        while (true) {
            val response = OnlineHttp.request("GET", link, emptyMap(), null, name)
            if (response.status == 200 && response.body.isNotEmpty() && "json" !in response.headers["content-type"].orEmpty()) return response.body
            val pending = response.status in setOf(200, 202, 403, 404)
            if (!pending || System.nanoTime() > deadline) throw VoiceException("$name chưa làm xong file âm thanh", reason = if (pending) "timeout" else "service")
            Thread.sleep(pollMs)
        }
    }

    override fun speak(entry: OnlineKeys.Entry, text: String, voice: String, out: File) =
        estimated(text, out) { piece -> fetch(ask(entry.key, voice, if (piece.trim().length >= 3) piece else "$piece...")) }
}
