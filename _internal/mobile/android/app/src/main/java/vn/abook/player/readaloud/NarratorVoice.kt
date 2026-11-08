package vn.abook.player.readaloud

import java.text.Normalizer

/**
 * Giọng VieNeu mặc định cho người nghe CHƯA chọn giọng: một giọng kể chuyện trung tính của từng bản (turbo, nano), không bao giờ là giọng đầu danh
 * sách ("Adam bựa" / "Adam", giọng có cá tính). Cùng danh sách và luật với `NARRATOR_VOICES` / `narratorVoice` của giao diện
 * (ui/src/listen/readAloudVoice.ts); bộ ví dụ chung tests/fixtures/default_voice (NarratorVoiceTest, readAloudVoice.test.ts). Lý do chọn: ghi ở
 * `NARRATOR_VOICES` bên giao diện.
 */
object NarratorVoice {
    private val policy by lazy { org.json.JSONObject(vn.abook.player.BuildConfig.VOICE_RANK_POLICY) }
    private val neverAuto by lazy { policy.getJSONArray("never_auto").let { a -> (0 until a.length()).map { nfc(a.getString(it)) }.toSet() } }
    val PREFERRED = mapOf(
        "turbo" to (listOf("Đức Trí") + org.json.JSONObject(vn.abook.player.BuildConfig.VOICE_RANK_POLICY)
            .getJSONObject("narrator").getJSONArray("female").let { tiers ->
                (0 until tiers.length()).flatMap { i -> tiers.getJSONArray(i).let { tier -> (0 until tier.length()).map { tier.getString(it) } } }
            } + "Thanh Bình"),
        "nano" to listOf("Ái Hân", "Mỹ Duyên", "Đức Trí"),
    )

    private fun nfc(text: String) = Normalizer.normalize(text, Normalizer.Form.NFC)

    /** Mã giọng nên dùng trong [voices] (mã "vieneu:<bản>/<tên>" + giới, theo thứ tự danh sách): giọng ưu tiên của bản ấy, xét theo bậc (bậc 1 của
     *  mọi bản trước; cùng bậc thì giọng đứng trước); không có thì giọng đầu tiên cùng giới [gender] (giới của giọng đang dùng); không biết giới mới
     *  lấy giọng đầu danh sách; null khi danh sách rỗng. */
    fun pick(voices: List<Pair<String, String>>, gender: String?): String? {
        val available = voices.filter { nfc(it.first.substringAfter('/')) !in neverAuto }
        val ranks = PREFERRED.values.maxOf { it.size }
        for (rank in 0 until ranks) {
            available.firstOrNull { (id, _) ->
                val tier = id.substringAfter(':').substringBefore('/')
                PREFERRED[tier]?.getOrNull(rank)?.let { nfc(it) == nfc(id.substringAfter('/')) } == true
            }?.let { return it.first }
        }
        return (available.firstOrNull { !gender.isNullOrEmpty() && it.second == gender } ?: available.firstOrNull())?.first
    }
}
