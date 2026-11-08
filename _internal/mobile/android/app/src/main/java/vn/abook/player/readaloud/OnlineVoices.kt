package vn.abook.player.readaloud

import vn.abook.player.S

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.SocketTimeoutException
import vn.abook.player.net.FastConnect

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
            val connection = FastConnect.open(url, timeoutMs) // không theo chuyển hướng: 3xx là lỗi, khoá không bao giờ đi sang máy khác
            try {
                connection.requestMethod = method
                connection.readTimeout = timeoutMs
                connection.setRequestProperty("User-Agent", S.s_abook_readaloud_fd127dde)
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
                        if (out.size() > MAX_RESPONSE) throw IOException(S.s_tra_loi_qua_lon_1c99a5e8)
                    }
                    out.toByteArray()
                } ?: ByteArray(0)
                val received = connection.headerFields.filterKeys { it != null }.mapKeys { it.key.lowercase() }.mapValues { it.value.joinToString(",") }
                return Response(status, data, received)
            } finally {
                connection.disconnect()
            }
        } catch (error: SocketTimeoutException) {
            throw VoiceException(S.s_0_khong_tra_loi_qua_gio_e4796eee(name), cause = error, reason = "timeout") // có mạng mà dịch vụ không trả lời: không phải "mất mạng" (như byok.py)
        } catch (error: IOException) {
            throw VoiceException(S.s_khong_co_mang_de_dung_giong_0_e88a3cb4(name), offline = true, cause = error)
        }
    }

    /** Mã HTTP lỗi -> lỗi có lý do (như `byok.failure`). */
    fun failure(status: Int, name: String, detail: String = ""): VoiceException {
        val tail = if (detail.isNotBlank()) " (${detail.take(200)})" else ""
        return when {
            status == 401 || status == 403 -> VoiceException(S.s_0_tu_choi_khoa_cua_ban_kiem_tra_lai_khoa_t_d92c96f9(name, tail), reason = "auth")
            status == 402 || status == 429 -> VoiceException(S.s_khoa_0_da_het_han_muc_hoac_goi_qua_day_1_470a25c1(name, tail), reason = "quota")
            status >= 500 -> VoiceException(S.s_0_dang_truc_trac_http_1_2_de54479f(name, status, tail), reason = "service")
            else -> VoiceException(S.s_0_khong_nhan_yeu_cau_http_1_2_c8cb886f(name, status, tail), reason = "rejected")
        }
    }

    fun gender(value: String?): String = when (value?.trim()?.lowercase()) {
        "female", S.s_nu_316c30fd -> "female"
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
        val entry = keys.get(id)?.takeIf { it.valid } ?: throw VoiceException(S.s_khoa_0_chua_dung_duoc_kiem_tra_lai_trong_c_033e7c72(name), reason = "auth")
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
        val entry = keys.get(id) ?: return JSONObject().put("ok", false).put("reason", "auth").put("message", S.s_chua_nhap_khoa_7ae5f64c)
        return try {
            val voices = listVoices(entry)
            if (voices.isEmpty()) throw VoiceException(S.s_tai_khoan_0_nay_khong_co_giong_tieng_viet_c80e1eff(name), reason = "voice")
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
        if (offset == 0L) throw VoiceException(S.s_0_khong_tra_ve_am_thanh_b0fc54e9(name), reason = "service")
        return offset to boundaries
    }

    companion object {
        const val PROBE_TEXT = S.s_xin_chao_0dcb19e7
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
    val NAMES = linkedMapOf("azure" to S.s_azure_speech_8bd84d93, "google" to S.s_google_cloud_69bd2211, "fpt" to "FPT.AI", "viettel" to S.s_viettel_ai_9094e708)

    @Volatile private var all: List<KeyedProvider>? = null

    fun providers(context: Context): List<KeyedProvider> = all ?: synchronized(this) {
        all ?: OnlineKeys.onDevice(context.applicationContext).let { keys ->
            listOf(AzureTts(keys), GoogleTts(keys), FptTts(keys), ViettelTts(keys))
        }.also { all = it }
    }

    fun provider(context: Context, id: String): KeyedProvider =
        providers(context).firstOrNull { it.id == id } ?: throw IllegalArgumentException(S.s_nha_cung_cap_la_0_971204b7(id))

    fun voices(context: Context): List<VoiceInfo> = providers(context).flatMap { it.voices() }

    /** Giọng `provider:mã` nếu là giọng dùng khoá, không thì null. */
    fun voiceFor(context: Context, id: String): Voice? {
        val provider = id.substringBefore(':')
        if (provider !in NAMES) return null
        return provider(context, provider).voice(id.substringAfter(':'))
    }

    fun describe(context: Context): JSONArray = JSONArray().apply { providers(context).forEach { put(it.describe()) } }

    /** "Lưu" khoá (chỉ cất trên máy, không gửi gì ra mạng); `key` rỗng = giữ khoá đã lưu, chỉ đổi vùng. Trả mô tả đã che của nhà cung cấp. */
    fun saveKey(context: Context, provider: String, key: String, region: String): JSONObject {
        val clean = region.trim().lowercase()
        if (provider == "azure" && !AzureTts.validRegion(clean)) throw IllegalArgumentException(S.s_vung_azure_chua_dung_vi_du_southeastasia_f41747f8)
        val keyed = provider(context, provider)
        keyed.keys.put(provider, key, if (provider == "azure") clean else "")
        return keyed.describe()
    }

    fun removeKey(context: Context, provider: String): JSONObject {
        val keyed = provider(context, provider)
        keyed.keys.remove(provider)
        return keyed.describe()
    }

    /** "Kiểm tra": lấy danh sách giọng rồi đọc thử một câu thật ngắn; kèm mô tả mới của nhà cung cấp. */
    fun checkKey(context: Context, provider: String): JSONObject {
        val keyed = provider(context, provider)
        return keyed.check(java.io.File(context.cacheDir, "readaloud-check.mp3")).put("provider", keyed.describe())
    }
}
