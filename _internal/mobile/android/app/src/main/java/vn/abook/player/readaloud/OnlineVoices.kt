package vn.abook.player.readaloud

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

/**
 * Giọng trực tuyến dùng khoá của chính người dùng ("Bring your own key", docs/LISTEN_ANYTHING.md mục 3) trên điện thoại - bản Kotlin của `abook/readaloud/byok.py`.
 * Mỗi nhà cung cấp một file (AzureTts.kt, GoogleTts.kt, FptTts.kt, ViettelTts.kt) theo khuôn [KeyedProvider]. Ta không trả tiền, không tạo tài khoản: chữ của sách
 * đi tới nhà cung cấp ấy bằng khoá của người dùng và có thể bị tính tiền vào tài khoản của họ - Cài đặt nói rõ.
 *
 * Khoá chỉ đi trong header của chính nhà cung cấp, không bao giờ trong địa chỉ hay câu báo lỗi; không theo chuyển hướng HTTP. Lỗi là [VoiceException] với
 * `reason` "auth" / "quota" / "offline" / "timeout" / "service" / "rejected" - [ClipReader] dựa vào đó để đọc tạm đoạn ấy bằng giọng kế (Edge, rồi giọng của máy).
 */
object OnlineHttp {
    const val TIMEOUT_MS = 25_000
    private const val MAX_RESPONSE = 64 * 1024 * 1024

    class Response(val status: Int, val body: ByteArray, val headers: Map<String, String>)

    fun request(method: String, url: String, headers: Map<String, String>, body: ByteArray?, name: String, timeoutMs: Int = TIMEOUT_MS): Response {
        try {
            val connection = URL(url).openConnection() as HttpURLConnection
            try {
                connection.instanceFollowRedirects = false // 3xx là lỗi: khoá không bao giờ đi sang máy khác
                connection.requestMethod = method
                connection.connectTimeout = timeoutMs
                connection.readTimeout = timeoutMs
                connection.setRequestProperty("User-Agent", "ABook-ReadAloud")
                headers.forEach { (key, value) -> connection.setRequestProperty(key, value) }
                if (body != null) {
                    connection.doOutput = true
                    connection.outputStream.use { it.write(body) }
                }
                val status = connection.responseCode
                val stream = if (status >= 400) connection.errorStream else connection.inputStream
                val data = stream?.use { input ->
                    val out = java.io.ByteArrayOutputStream()
                    val buffer = ByteArray(16 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        out.write(buffer, 0, read)
                        if (out.size() > MAX_RESPONSE) throw IOException("trả lời quá lớn")
                    }
                    out.toByteArray()
                } ?: ByteArray(0)
                val received = connection.headerFields.filterKeys { it != null }.mapKeys { it.key.lowercase() }.mapValues { it.value.joinToString(",") }
                return Response(status, data, received)
            } finally {
                connection.disconnect()
            }
        } catch (error: SocketTimeoutException) {
            throw VoiceException("$name không trả lời (quá giờ)", offline = true, cause = error, reason = "timeout")
        } catch (error: IOException) {
            throw VoiceException("Không có mạng để dùng giọng $name", offline = true, cause = error)
        }
    }

    /** Mã HTTP lỗi -> lỗi có lý do (như `byok.failure`). */
    fun failure(status: Int, name: String, detail: String = ""): VoiceException {
        val tail = if (detail.isNotBlank()) " (${detail.take(200)})" else ""
        return when {
            status == 401 || status == 403 -> VoiceException("$name từ chối khóa của bạn - kiểm tra lại khóa trong Cài đặt$tail", reason = "auth")
            status == 402 || status == 429 -> VoiceException("Khóa $name đã hết hạn mức hoặc gọi quá dày$tail", reason = "quota")
            status >= 500 -> VoiceException("$name đang trục trặc (HTTP $status)$tail", reason = "service")
            else -> VoiceException("$name không nhận yêu cầu (HTTP $status)$tail", reason = "rejected")
        }
    }

    fun gender(value: String?): String = when (value?.trim()?.lowercase()) {
        "female", "nữ" -> "female"
        "male", "nam" -> "male"
        else -> ""
    }
}

/** `maxChars`: chữ mỗi lượt gọi; `free`: hạn mức miễn phí nói cho người dùng; `timings`: "exact" / "estimated"; `region`: cần vùng (Azure). */
data class Limits(val maxChars: Int, val free: String, val timings: String, val region: Boolean = false) {
    fun json(): JSONObject = JSONObject().put("max_chars", maxChars).put("free", free).put("timings", timings).put("region", region)
}

abstract class KeyedProvider(val keys: OnlineKeys) {
    abstract val id: String
    abstract val name: String
    abstract val limits: Limits

    /** Giọng tiếng Việt của tài khoản này (lúc "Kiểm tra"). */
    protected abstract fun listVoices(entry: OnlineKeys.Entry): List<OnlineKeys.VoiceRow>

    /** Ghi MP3 của `text` vào `out`; trả (độ dài ms, mảnh mốc). */
    protected abstract fun speak(entry: OnlineKeys.Entry, text: String, voice: String, out: File): Pair<Long, List<Boundary>>

    fun voices(): List<VoiceInfo> {
        val entry = keys.get(id)?.takeIf { it.valid } ?: return emptyList()
        return entry.voices.map { VoiceInfo("$id:${it.code}", "${it.name} ($name)", id, true, false, it.gender) }
    }

    fun voice(code: String): Voice = KeyedVoice(this, code)

    fun synthesize(text: String, voice: String, out: File): Clip {
        val entry = keys.get(id)?.takeIf { it.valid } ?: throw VoiceException("Khóa $name chưa dùng được - kiểm tra lại trong Cài đặt", reason = "auth")
        try {
            val (duration, boundaries) = speak(entry, text, voice, out)
            return Clip(out, duration, WordTokens.map(text, boundaries, duration), "$id:$voice")
        } catch (error: VoiceException) {
            if (error.reason == "auth") keys.mark(id, false) // khoá bị thu hồi: giọng thôi hiện tới lần kiểm tra lại
            throw error
        }
    }

    /** "Kiểm tra" trong Cài đặt: lấy danh sách giọng rồi đọc thử một câu thật ngắn vào `scratch`. */
    fun check(scratch: File): JSONObject {
        val entry = keys.get(id) ?: return JSONObject().put("ok", false).put("reason", "auth").put("message", "Chưa nhập khóa.")
        return try {
            val voices = listVoices(entry)
            if (voices.isEmpty()) throw VoiceException("Tài khoản $name này không có giọng tiếng Việt", reason = "voice")
            try {
                speak(entry, PROBE_TEXT, voices[0].code, scratch)
            } finally {
                scratch.delete()
            }
            keys.mark(id, true, voices)
            JSONObject().put("ok", true).put("voices", voices.size)
        } catch (error: VoiceException) {
            if (error.reason in setOf("auth", "quota", "voice", "rejected")) keys.mark(id, false)
            JSONObject().put("ok", false).put("reason", error.reason).put("message", error.message)
        }
    }

    fun describe(): JSONObject {
        val shown = keys.public(id)
        return shown.put("id", id).put("name", name).put("limits", limits.json())
    }

    /**
     * Đọc bằng giọng không báo mốc (FPT.AI, Viettel AI): cắt thành mảnh <= [Limits.maxChars], `say(mảnh)` -> MP3 ghi nối vào `out`; mỗi mảnh tự chia độ dài
     * thật của nó ([Mp3.durationMs]) theo âm tiết ([SyllableSpread]), mốc cộng dồn và vị trí ký tự theo chữ gốc.
     */
    protected fun estimated(text: String, out: File, say: (String) -> ByteArray): Pair<Long, List<Boundary>> {
        val boundaries = ArrayList<Boundary>()
        var offset = 0L
        out.outputStream().use { sink ->
            for ((at, piece) in TextChunks.split(text, limits.maxChars)) {
                val data = say(piece)
                val length = Mp3.durationMs(data)
                val base = text.codePointCount(0, at)
                SyllableSpread.boundaries(piece, length).forEach { boundaries.add(Boundary(it.startMs + offset, it.endMs + offset, it.text, it.char + base)) }
                sink.write(data)
                offset += length
            }
        }
        if (offset == 0L) throw VoiceException("$name không trả về âm thanh", reason = "service")
        return offset to boundaries
    }

    companion object {
        const val PROBE_TEXT = "Xin chào."
    }
}

class KeyedVoice(private val provider: KeyedProvider, private val code: String) : Voice {
    override val id = "${provider.id}:$code"
    override val extension = "mp3"
    override fun synthesize(text: String, out: File): Clip = provider.synthesize(text, code, out)
}

/** Danh sách các nhà cung cấp dùng khoá (Azure đứng đầu: nhà chính thức của chính các giọng Edge) + việc của plugin. */
object OnlineVoices {
    /** Tên để nói với người nghe (cùng bảng `KEYED_PROVIDERS` của giao diện). */
    val NAMES = linkedMapOf("azure" to "Azure Speech", "google" to "Google Cloud", "fpt" to "FPT.AI", "viettel" to "Viettel AI")

    @Volatile private var all: List<KeyedProvider>? = null

    fun providers(context: Context): List<KeyedProvider> = all ?: synchronized(this) {
        all ?: OnlineKeys.onDevice(context.applicationContext).let { keys ->
            listOf(AzureTts(keys), GoogleTts(keys), FptTts(keys), ViettelTts(keys))
        }.also { all = it }
    }

    fun provider(context: Context, id: String): KeyedProvider =
        providers(context).firstOrNull { it.id == id } ?: throw IllegalArgumentException("Nhà cung cấp lạ: $id")

    fun voices(context: Context): List<VoiceInfo> = providers(context).flatMap { it.voices() }

    /** Giọng `provider:mã` nếu là giọng dùng khoá, không thì null. */
    fun voiceFor(context: Context, id: String): Voice? {
        val provider = id.substringBefore(':')
        if (provider !in NAMES) return null
        return provider(context, provider).voice(id.substringAfter(':'))
    }

    fun describe(context: Context): JSONArray = JSONArray().apply { providers(context).forEach { put(it.describe()) } }
}
