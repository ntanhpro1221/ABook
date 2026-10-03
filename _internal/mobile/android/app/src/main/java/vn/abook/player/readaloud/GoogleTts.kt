package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Google Cloud Text-to-Speech (khoá API của người dùng) - bản điện thoại của `abook/readaloud/google.py`: giọng vi-VN Standard / WaveNet / Neural2, mốc từng chữ
 * chính xác nhờ một `<mark name="i"/>` trước mỗi chữ.
 *
 * - Khoá trong header `X-goog-api-key` (https://cloud.google.com/docs/authentication/api-keys-use), không bao giờ `?key=`.
 * - Giọng: `GET https://texttospeech.googleapis.com/v1/voices?languageCode=vi-VN` (https://cloud.google.com/text-to-speech/docs/reference/rest/v1/voices/list);
 *   chỉ giữ Standard / Wavenet / Neural2 (họ Chirp không nhận SSML nên không có mark).
 * - Đọc: `POST .../v1beta1/text:synthesize` {input.ssml, voice, audioConfig.audioEncoding=MP3, enableTimePointing=[SSML_MARK]} -> audioContent (base64) +
 *   timepoints[{markName, timeSeconds}] (https://cloud.google.com/text-to-speech/docs/reference/rest/v1beta1/text/synthesize). Trần 5000 byte mỗi lượt.
 * - Lỗi: 400 API_KEY_INVALID / 403 = khoá; 429 RESOURCE_EXHAUSTED = hạn mức.
 */
class GoogleTts(keys: OnlineKeys, private val base: String = BASE) : KeyedProvider(keys) {
    override val id = "google"
    override val name = "Google Cloud"
    override val limits = Limits(4000, "Miễn phí mỗi tháng: 4 triệu ký tự giọng Standard, 1 triệu WaveNet / Neural2", "exact")

    companion object {
        const val BASE = "https://texttospeech.googleapis.com"
        const val MAX_SSML_BYTES = 4800
        private val FAMILIES = Regex("-(Standard|Wavenet|Neural2)-", RegexOption.IGNORE_CASE)

        fun label(name: String): String {
            val family = FAMILIES.find(name)?.groupValues?.get(1)?.lowercase()?.let { mapOf("standard" to "Standard", "wavenet" to "WaveNet", "neural2" to "Neural2")[it] } ?: ""
            return "$family ${name.substringAfterLast('-')}".trim()
        }

        /** Các chữ hiện (vị trí ký tự, chữ) chia thành nhóm có SSML (mỗi chữ một mark) không quá [MAX_SSML_BYTES]; chữ quá dài cắt thành mảnh 1000 ký tự. */
        fun chunks(text: String): List<List<Pair<Int, String>>> {
            val pieces = ArrayList<Pair<Int, String>>()
            for (range in WordTokens.tokens(text)) {
                val word = text.substring(range.first, range.last + 1)
                var at = 0
                while (at < word.length) {
                    pieces.add(text.codePointCount(0, range.first + at) to word.substring(at, minOf(word.length, at + 1000)))
                    at += 1000
                }
            }
            val groups = ArrayList<MutableList<Pair<Int, String>>>()
            var size = 0
            for (piece in pieces) {
                val cost = EdgeProtocol.escape(piece.second).toByteArray(Charsets.UTF_8).size + 22
                if (groups.isEmpty() || size + cost > MAX_SSML_BYTES - 64) {
                    groups.add(ArrayList())
                    size = 0
                }
                groups.last().add(piece)
                size += cost
            }
            return groups
        }

        fun ssml(group: List<Pair<Int, String>>): String =
            "<speak>" + group.withIndex().joinToString("") { (i, piece) -> "<mark name=\"$i\"/>${EdgeProtocol.escape(piece.second)} " } + "<mark name=\"end\"/></speak>"
    }

    private fun error(status: Int, body: ByteArray): VoiceException {
        val text = String(body, Charsets.UTF_8)
        val error = runCatching { JSONObject(text).optJSONObject("error") }.getOrNull()
        val detail = error?.optString("message").orEmpty()
        return when {
            status == 400 && ("API_KEY_INVALID" in text || "API key not valid" in detail) -> OnlineHttp.failure(401, name, detail)
            error?.optString("status") == "RESOURCE_EXHAUSTED" -> OnlineHttp.failure(429, name, detail)
            else -> OnlineHttp.failure(status, name, detail)
        }
    }

    override fun listVoices(entry: OnlineKeys.Entry): List<OnlineKeys.VoiceRow> {
        val response = OnlineHttp.request("GET", "$base/v1/voices?languageCode=vi-VN", mapOf("X-goog-api-key" to entry.key), null, name)
        if (response.status != 200) throw error(response.status, response.body)
        val list = runCatching { JSONObject(String(response.body, Charsets.UTF_8)).optJSONArray("voices") ?: JSONArray() }
            .getOrElse { throw VoiceException("$name trả danh sách giọng hỏng", cause = it) }
        return (0 until list.length()).mapNotNull { list.optJSONObject(it) }
            .filter { item ->
                val codes = item.optJSONArray("languageCodes") ?: JSONArray()
                (0 until codes.length()).any { codes.optString(it) == "vi-VN" } && FAMILIES.containsMatchIn(item.optString("name"))
            }
            .map { it.getString("name") to OnlineHttp.gender(it.optString("ssmlGender")) }
            .sortedBy { it.first }
            .map { (voice, gender) -> OnlineKeys.VoiceRow(voice, label(voice), gender) }
    }

    override fun speak(entry: OnlineKeys.Entry, text: String, voice: String, out: File): Pair<Long, List<Boundary>> {
        val boundaries = ArrayList<Boundary>()
        var offset = 0L
        out.outputStream().use { sink ->
            for (group in chunks(text)) {
                val payload = JSONObject()
                    .put("input", JSONObject().put("ssml", ssml(group)))
                    .put("voice", JSONObject().put("languageCode", "vi-VN").put("name", voice))
                    .put("audioConfig", JSONObject().put("audioEncoding", "MP3"))
                    .put("enableTimePointing", JSONArray().put("SSML_MARK"))
                val response = OnlineHttp.request("POST", "$base/v1beta1/text:synthesize",
                    mapOf("X-goog-api-key" to entry.key, "Content-Type" to "application/json; charset=utf-8"), payload.toString().toByteArray(Charsets.UTF_8), name)
                if (response.status != 200) throw error(response.status, response.body)
                val (data, marks) = try {
                    val answer = JSONObject(String(response.body, Charsets.UTF_8))
                    val points = answer.optJSONArray("timepoints") ?: JSONArray()
                    WebSocket.unbase64(answer.getString("audioContent")) to (0 until points.length()).associate {
                        val point = points.getJSONObject(it)
                        point.getString("markName") to Math.round(point.getDouble("timeSeconds") * 1000)
                    }
                } catch (error: Exception) {
                    throw VoiceException("$name trả lời hỏng", cause = error)
                }
                val length = Mp3.durationMs(data)
                val endMark = marks["end"] ?: length
                group.forEachIndexed { index, (char, word) ->
                    val start = marks[index.toString()] ?: return@forEachIndexed
                    val stop = marks[(index + 1).toString()] ?: endMark
                    boundaries.add(Boundary(offset + start, offset + maxOf(start, stop), word, char))
                }
                sink.write(data)
                offset += length
            }
        }
        if (offset == 0L) throw VoiceException("$name không trả về âm thanh", reason = "service")
        return offset to boundaries
    }
}
