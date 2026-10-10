package vn.abook.player.readaloud

import java.text.Normalizer

/**
 * Giọng VieNeu mặc định cho người nghe CHƯA chọn giọng: một giọng kể chuyện trung tính, không phải giọng đầu danh sách ("Adam bựa", giọng có cá
 * tính). Cùng danh sách và luật với `NARRATOR_VOICES` / `narratorVoice` của giao diện (ui/src/listen/readAloudVoice.ts); bộ ví dụ chung
 * tests/fixtures/default_voice (NarratorVoiceTest, readAloudVoice.test.ts). Lý do chọn: ghi ở `NARRATOR_VOICES` bên giao diện.
 */
object NarratorVoice {
    val PREFERRED = listOf("Phạm Tuyên", "Ngọc Linh", "Thanh Bình")

    private fun nfc(text: String) = Normalizer.normalize(text, Normalizer.Form.NFC)

    /** Mã giọng nên dùng trong [ids] (mã "vieneu:<bản>/<tên>" theo thứ tự danh sách): giọng ưu tiên đầu tiên có mặt (ưu tiên theo tên, trước khi xét bản Turbo / Nano), không thì giọng đầu danh sách; null khi danh sách rỗng. */
    fun pick(ids: List<String>): String? {
        for (name in PREFERRED) {
            ids.firstOrNull { nfc(it.substringAfter('/')) == nfc(name) }?.let { return it }
        }
        return ids.firstOrNull()
    }
}
