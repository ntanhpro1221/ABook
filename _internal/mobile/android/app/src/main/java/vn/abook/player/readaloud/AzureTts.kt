package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.security.SecureRandom

/**
 * Azure Speech (khoá + vùng của người dùng): nhà chính thức của đúng các giọng thần kinh mà Edge đọc to - bản điện thoại của `abook/readaloud/azure.py`.
 *
 * - Danh sách giọng: REST `GET https://<vùng>.tts.speech.microsoft.com/cognitiveservices/voices/list`, header `Ocp-Apim-Subscription-Key`
 *   (https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech), lọc `Locale == "vi-VN"`.
 * - Đọc: REST không có mốc từng chữ, nên nói WebSocket như Speech SDK: `wss://<vùng>.tts.speech.microsoft.com/tts/cognitiveservices/websocket/v1`,
 *   header khoá + `X-ConnectionId`, tin `speech.config`, `synthesis.context` (bật `wordBoundaryEnabled`), `ssml`; nhận `audio` + `audio.metadata` tới `turn.end` -
 *   cùng khung tin của Edge nên dùng lại [WebSocket] và [EdgeProtocol.readTurn]. Nguồn: https://github.com/microsoft/cognitive-services-speech-sdk-js
 *   (src/common.speech/SpeechSynthesisConnectionFactory.ts, SynthesisAdapterBase.ts, SynthesisContext.ts; đọc 03-10).
 * - 401 khoá sai / sai vùng, 429 hết hạn mức. Bậc F0 miễn phí 0,5 triệu ký tự / tháng.
 */
class AzureTts(
    keys: OnlineKeys,
    private val connect: EdgeTts.Connector = EdgeTts.Connector.Real,
    private val restBase: ((String) -> String)? = null,
) : KeyedProvider(keys) {
    override val id = "azure"
    override val name = "Azure Speech"
    override val limits = Limits(3000, "Bậc miễn phí F0: 500.000 ký tự mỗi tháng", "exact", region = true)

    companion object {
        const val WS_PATH = "/tts/cognitiveservices/websocket/v1"
        const val VOICES_PATH = "/cognitiveservices/voices/list"
        const val OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
        private val REGION = Regex("^[a-z0-9]{2,40}$")
        private val random = SecureRandom()

        fun validRegion(region: String) = REGION.matches(region)

        fun host(region: String) = "$region.tts.speech.microsoft.com"

        private fun stamp(): String {
            val format = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", java.util.Locale.US)
            format.timeZone = java.util.TimeZone.getTimeZone("UTC")
            return format.format(java.util.Date())
        }

        fun message(path: String, requestId: String, contentType: String, body: String) =
            "Path:$path\r\nX-RequestId:$requestId\r\nX-Timestamp:${stamp()}\r\nContent-Type:$contentType\r\n\r\n$body"

        fun speechConfig(): String = JSONObject()
            .put("context", JSONObject()
                .put("system", JSONObject().put("name", "SpeechSDK").put("version", "1.44.0").put("build", "Android").put("lang", "Kotlin"))
                .put("os", JSONObject().put("platform", "Android").put("name", "ABook").put("version", "1")))
            .toString()

        fun synthesisContext(): String = JSONObject()
            .put("synthesis", JSONObject()
                .put("audio", JSONObject()
                    .put("metadataOptions", JSONObject().put("bookmarkEnabled", false).put("punctuationBoundaryEnabled", "false")
                        .put("sentenceBoundaryEnabled", "false").put("sessionEndEnabled", true).put("visemeEnabled", false).put("wordBoundaryEnabled", "true"))
                    .put("outputFormat", OUTPUT_FORMAT))
                .put("language", JSONObject().put("autoDetection", false)))
            .toString()

        fun ssml(voice: String, escapedText: String) =
            "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='vi-VN'><voice name='${EdgeProtocol.escape(voice).replace("'", "&apos;")}'>" +
                "$escapedText</voice></speak>"

        /** Azure đóng kết nối kèm lý do khi hết hạn mức / khoá hỏng giữa lượt. */
        fun closed(message: WebSocket.Message.Closed, name: String): VoiceException? {
            val reason = message.reason.lowercase()
            return when {
                listOf("quota", "429", "throttl", "exceed").any { it in reason } -> VoiceException("Khóa $name đã hết hạn mức hoặc gọi quá dày", reason = "quota")
                listOf("auth", "401", "subscription").any { it in reason } -> VoiceException("$name từ chối khóa của bạn - kiểm tra lại khóa trong Cài đặt", reason = "auth")
                (message.code == 1007 || message.code == 1008) && reason.isNotEmpty() -> VoiceException("$name không nhận yêu cầu: ${message.reason.take(200)}", reason = "rejected")
                else -> null
            }
        }
    }

    private fun region(entry: OnlineKeys.Entry): String =
        entry.region.takeIf(::validRegion) ?: throw VoiceException("Vùng $name chưa đúng (ví dụ: southeastasia)", reason = "auth")

    override fun listVoices(entry: OnlineKeys.Entry): List<OnlineKeys.VoiceRow> {
        val region = region(entry)
        val base = restBase?.invoke(region) ?: "https://${host(region)}"
        val response = OnlineHttp.request("GET", base + VOICES_PATH, mapOf("Ocp-Apim-Subscription-Key" to entry.key), null, name)
        if (response.status != 200) throw OnlineHttp.failure(response.status, name)
        val list = try {
            JSONArray(String(response.body, Charsets.UTF_8))
        } catch (error: org.json.JSONException) {
            throw VoiceException("$name trả danh sách giọng hỏng", cause = error)
        }
        return (0 until list.length()).mapNotNull { list.optJSONObject(it) }
            .filter { it.optString("Locale") == "vi-VN" && it.optString("ShortName").isNotEmpty() }
            .map { item ->
                OnlineKeys.VoiceRow(item.getString("ShortName"), item.optString("LocalName").ifEmpty { item.optString("DisplayName").ifEmpty { item.getString("ShortName") } },
                    OnlineHttp.gender(item.optString("Gender")))
            }
    }

    override fun speak(entry: OnlineKeys.Entry, text: String, voice: String, out: File): Pair<Long, List<Boundary>> {
        val region = region(entry)
        val boundaries = ArrayList<Boundary>()
        var bytes = 0L
        out.outputStream().use { sink ->
            for ((_, part) in TextChunks.split(text, EdgeProtocol.MAX_TEXT_BYTES, EdgeProtocol::escapedBytes)) {
                val socket = try {
                    connect.open("wss://${host(region)}$WS_PATH", mapOf("Ocp-Apim-Subscription-Key" to entry.key, "X-ConnectionId" to EdgeProtocol.connectionId(random)))
                } catch (error: HandshakeException) {
                    throw OnlineHttp.failure(error.status, name)
                } catch (error: IOException) {
                    throw VoiceException("Không có mạng để dùng giọng $name", offline = true, cause = error)
                }
                try {
                    val request = EdgeProtocol.connectionId(random)
                    socket.sendText(message("speech.config", request, "application/json", speechConfig()))
                    socket.sendText(message("synthesis.context", request, "application/json", synthesisContext()))
                    socket.sendText(message("ssml", request, "application/ssml+xml", ssml(voice, EdgeProtocol.escape(part))))
                    bytes += EdgeProtocol.readTurn(socket, sink, EdgeProtocol.durationMs(bytes) + EdgeProtocol.BOUNDARY_SHIFT_MS, boundaries, "Giọng $name",
                        EdgeTts.TOTAL_MS, onClose = { closed(it, name) })
                } finally {
                    socket.close()
                }
            }
        }
        if (bytes == 0L) throw VoiceException("$name không trả về âm thanh", reason = "service")
        return EdgeProtocol.durationMs(bytes) to boundaries
    }
}
