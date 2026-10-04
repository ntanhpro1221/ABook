package vn.abook.player.readaloud

/**
 * Độ to cố định của từng giọng khi phát, để mọi giọng đọc to nằm cùng -20 LUFS với âm thanh Studio (đo BS.1770, 03-10): chỉ nhân biên độ lúc phát
 * (`ExoPlayer.volume`), không bao giờ mã hoá lại file.
 */
object VoiceGain {
    // = abook/readaloud/loudness.py gain_db (giọng 0 dB không ghi); tests/test_vieneu_android.py so hai bảng.
    private val table = mapOf(
        "edge:vi-VN-HoaiMyNeural" to -1.7,
        "edge:vi-VN-NamMinhNeural" to -0.3,
        "vieneu:turbo/Adam bựa" to -0.9,
        "vieneu:turbo/Trúc Ly" to -0.6,
        "vieneu:turbo/Thiện Minh" to -0.1,
        "vieneu:turbo/Hải Đăng" to -0.2,
        "vieneu:turbo/Thiền Tâm Đức" to -0.3,
        "vieneu:turbo/Ngọc Huyền" to -0.2,
        "vieneu:turbo/Quang Sơn" to -0.3,
        "vieneu:turbo/Ngọc Trân" to -0.2,
        "vieneu:turbo/Thanh Bình" to -0.3,
        "vieneu:turbo/Ngọc Linh" to -0.5,
        "vieneu:turbo/Đoan Trang" to -0.1,
        "vieneu:turbo/Mỹ Duyên" to -0.1,
        "vieneu:turbo/Quỳnh Anh" to -0.1,
        "vieneu:turbo/Adam" to -0.2,
        "vieneu:turbo/Quốc Tuấn" to -0.2,
        "vieneu:nano/Adam" to -0.5,
        "vieneu:nano/Ái Hân" to -1.8,
        "vieneu:nano/Mỹ Duyên" to -2.3,
        "vieneu:nano/Đức Trí" to -1.4,
        "vieneu:nano/Hữu Quân" to -2.2,
        "vieneu:nano/Xuân Tiên" to -1.5,
        "vieneu:nano/Mai Anh" to -1.5,
        "vieneu:nano/Trúc Ly" to -1.9,
        "vieneu:nano/Anh Khôi" to -1.6,
        "vieneu:nano/Minh Quân" to -2.9,
        "vieneu:nano/Mạnh Dũng" to -2.1,
    )

    fun db(voiceId: String): Double = table[voiceId] ?: 0.0

    /** Hệ số biên độ của `db` decibel. */
    fun factor(db: Double): Float = Math.pow(10.0, db / 20.0).toFloat()
}
