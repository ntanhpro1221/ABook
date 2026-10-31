package vn.abook.player

/**
 * Giọng khựng quá lâu: đang phát ([musicVoice] `on`) mà vị trí đứng yên - chương phát qua mạng đệm, đọc to chờ đoạn kế - từ `afterMs` trở lên
 * ([MusicMix.voiceStallMs]). Khi ấy nhạc nền mờ xuống như lúc giọng tự hết; vị trí chạy lại (có tiếng, hay người nghe tua) thì nhạc lên lại.
 * Cùng luật với web `voiceStall.ts` và Qt `MusicLogic::VoiceStall`.
 */
internal class VoiceStall(private val afterMs: () -> Long) {
    private var since = -1L
    private var at = Double.NaN

    /** `nowMs`: đồng hồ đơn điệu; true = giọng đã khựng quá hạn. */
    fun update(nowMs: Long, position: Double, on: Boolean): Boolean {
        if (!on) {
            since = -1L
            return false
        }
        if (since < 0 || position != at) {
            since = nowMs
            at = position
            return false
        }
        return nowMs - since >= afterMs()
    }
}
