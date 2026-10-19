package vn.abook.player.readaloud

import java.text.Normalizer

/**
 * Giọng VieNeu mặc định cho người nghe CHƯA chọn giọng: một giọng kể chuyện trung tính của từng bản (turbo, nano), không bao giờ là giọng đầu danh
 * sách ("Adam bựa" / "Adam", giọng có cá tính). Cùng danh sách và luật với `NARRATOR_VOICES` / `narratorVoice` của giao diện
 * (ui/src/listen/readAloudVoice.ts); bộ ví dụ chung tests/fixtures/default_voice (NarratorVoiceTest, readAloudVoice.test.ts). Lý do chọn: ghi ở
 * `NARRATOR_VOICES` bên giao diện.
 */
object NarratorVoice {
    val PREFERRED = mapOf(
        "turbo" to listOf("Phạm Tuyên", "Ngọc Linh", "Thanh Bình"),
        "nano" to listOf("Ái Hân", "Mỹ Duyên", "Đức Trí"),
    )

    private fun nfc(text: String) = Normalizer.normalize(text, Normalizer.Form.NFC)

    /** Mã giọng nên dùng trong [voices] (mã "vieneu:<bản>/<tên>" + giới, theo thứ tự danh sách): giọng ưu tiên của bản ấy, xét theo bậc (bậc 1 của
     *  mọi bản trước; cùng bậc thì giọng đứng trước); không có thì giọng đầu tiên cùng giới [gender] (giới của giọng đang dùng); không biết giới mới
     *  lấy giọng đầu danh sách; null khi danh sách rỗng. */
    fun pick(voices: List<Pair<String, String>>, gender: String?): String? {
        val ranks = PREFERRED.values.maxOf { it.size }
        for (rank in 0 until ranks) {
            voices.firstOrNull { (id, _) ->
                val tier = id.substringAfter(':').substringBefore('/')
                PREFERRED[tier]?.getOrNull(rank)?.let { nfc(it) == nfc(id.substringAfter('/')) } == true
            }?.let { return it.first }
        }
        return (voices.firstOrNull { !gender.isNullOrEmpty() && it.second == gender } ?: voices.firstOrNull())?.first
    }
}
