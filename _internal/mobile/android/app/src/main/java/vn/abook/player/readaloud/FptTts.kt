package vn.abook.player.readaloud

import vn.abook.player.S

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
    override val limits = Limits(4500, S.s_mien_phi_100_000_ky_tu_moi_thang_90b8153a, "estimated")

    companion object {
        const val URL = "https://api.fpt.ai/hmi/tts/v5"
        const val KEY_HEADER = "api_key" // đúng chính tả trong tài liệu
        val VOICES = listOf(
            OnlineKeys.VoiceRow("banmai", S.s_ban_mai_mien_bac_4e6ed6d6, "female"), OnlineKeys.VoiceRow("thuminh", S.s_thu_minh_mien_bac_7c56c7eb, "female"),
            OnlineKeys.VoiceRow("leminh", S.s_le_minh_mien_bac_8a75f278, "male"), OnlineKeys.VoiceRow("myan", S.s_my_an_mien_trung_2fc64d63, "female"),
            OnlineKeys.VoiceRow("giahuy", S.s_gia_huy_mien_trung_3ebc7d70, "male"), OnlineKeys.VoiceRow("lannhi", S.s_lan_nhi_mien_nam_02a7b357, "female"),
            OnlineKeys.VoiceRow("linhsan", S.s_linh_san_mien_nam_630af677, "female"),
        )
        private val QUOTA_WORDS = listOf("quota", "limit", "exceed", "credit", "balance", S.s_het_17348fa3, S.s_vuot_88aa3e3e, S.s_han_muc_6532c99e)
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
            throw VoiceException(S.s_0_khong_doc_duoc_doan_nay_1_77569675(name, detail.take(200).ifEmpty { S.s_khong_ro_ly_do_f42ccdef }), reason = "service")
        }
        if (!link.startsWith("https://") && !link.startsWith("http://")) throw VoiceException(S.s_0_tra_link_la_ab5e8241(name), reason = "service")
        return link
    }

    private fun fetch(link: String): ByteArray {
        val deadline = System.nanoTime() + pollLimitMs * 1_000_000
        while (true) {
            val response = OnlineHttp.request("GET", link, emptyMap(), null, name)
            if (response.status == 200 && response.body.isNotEmpty() && "json" !in response.headers["content-type"].orEmpty()) return response.body
            val pending = response.status in setOf(200, 202, 403, 404)
            if (!pending || System.nanoTime() > deadline) throw VoiceException(S.s_0_chua_lam_xong_file_am_thanh_916a0237(name), reason = if (pending) "timeout" else "service")
            Thread.sleep(pollMs)
        }
    }

    override fun speak(entry: OnlineKeys.Entry, text: String, voice: String, out: File) =
        estimated(text, out) { piece -> fetch(ask(entry.key, voice, if (piece.trim().length >= 3) piece else "$piece...")) }
}
