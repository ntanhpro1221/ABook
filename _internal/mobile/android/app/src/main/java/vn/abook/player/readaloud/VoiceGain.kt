package vn.abook.player.readaloud

/**
 * Độ to cố định của từng giọng khi phát, để mọi giọng đọc to nằm cùng -20 LUFS với âm thanh Studio (đo BS.1770, 03-10): chỉ nhân biên độ lúc phát
 * (`ExoPlayer.volume`), không bao giờ mã hoá lại file.
 */
object VoiceGain {
    private val table = mapOf(
        "edge:vi-VN-HoaiMyNeural" to -1.7,
        "edge:vi-VN-NamMinhNeural" to -0.3,
    )

    fun db(voiceId: String): Double = table[voiceId] ?: 0.0

    /** Hệ số biên độ của `db` decibel. */
    fun factor(db: Double): Float = Math.pow(10.0, db / 20.0).toFloat()
}
