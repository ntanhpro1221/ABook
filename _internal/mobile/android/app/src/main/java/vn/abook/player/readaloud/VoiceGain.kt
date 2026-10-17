package vn.abook.player.readaloud

/**
 * Độ to cố định của từng giọng khi phát, để mọi giọng đọc to nằm cùng -20 LUFS với âm thanh Studio (đo BS.1770, 03-10): chỉ nhân biên độ lúc phát
 * (`ExoPlayer.volume`), không mã hoá lại file. Mức đo của giọng VieNeu còn là mốc để nâng câu ngắn nhỏ trong clip ([ClipLift]).
 */
object VoiceGain {
    const val TARGET_LUFS = -20.0

    // = abook/readaloud/loudness.py MEASURED_LUFS; tests/test_vieneu_android.py so hai bảng.
    private val measured = mapOf(
        "edge:vi-VN-HoaiMyNeural" to -18.3,
        "edge:vi-VN-NamMinhNeural" to -19.7,
        "vieneu:turbo/Adam bựa" to -19.1,
        "vieneu:turbo/Trúc Ly" to -19.4,
        "vieneu:turbo/Thiện Minh" to -19.9,
        "vieneu:turbo/Mai Anh" to -20.0,
        "vieneu:turbo/Hải Đăng" to -19.8,
        "vieneu:turbo/Thùy Dung" to -20.1,
        "vieneu:turbo/Thiền Tâm Đức" to -19.7,
        "vieneu:turbo/Ngọc Huyền" to -19.8,
        "vieneu:turbo/Quang Sơn" to -19.7,
        "vieneu:turbo/Ngọc Trân" to -19.8,
        "vieneu:turbo/Minh Đức" to -20.1,
        "vieneu:turbo/Phạm Tuyên" to -20.8,
        "vieneu:turbo/Thái Sơn" to -20.3,
        "vieneu:turbo/Xuân Vĩnh" to -20.6,
        "vieneu:turbo/Thanh Bình" to -19.7,
        "vieneu:turbo/Ngọc Linh" to -19.5,
        "vieneu:turbo/Đoan Trang" to -19.9,
        "vieneu:turbo/Thục Đoan" to -20.1,
        "vieneu:turbo/Minh Triết" to -20.1,
        "vieneu:turbo/Mỹ Duyên" to -19.9,
        "vieneu:turbo/Quỳnh Anh" to -19.9,
        "vieneu:turbo/Đức Trí" to -20.2,
        "vieneu:turbo/Kim Thanh" to -20.5,
        "vieneu:turbo/Adam" to -19.8,
        "vieneu:turbo/Quốc Tuấn" to -19.8,
        "vieneu:nano/Adam" to -19.5,
        "vieneu:nano/Ái Hân" to -18.2,
        "vieneu:nano/Mỹ Duyên" to -17.7,
        "vieneu:nano/Đức Trí" to -18.6,
        "vieneu:nano/Hữu Quân" to -17.8,
        "vieneu:nano/Xuân Tiên" to -18.5,
        "vieneu:nano/Mai Anh" to -18.5,
        "vieneu:nano/Trúc Ly" to -18.1,
        "vieneu:nano/Anh Khôi" to -18.4,
        "vieneu:nano/Minh Quân" to -17.1,
        "vieneu:nano/Mạnh Dũng" to -17.9,
    )

    /** LUFS đã đo của giọng; null: chưa đo. */
    fun measured(voiceId: String): Double? = measured[voiceId]

    /** `loudness.gain_db`: đích - đo, luôn <= 0, làm tròn 0,1 dB; giọng chưa đo 0 dB. */
    fun db(voiceId: String): Double = measured[voiceId]?.let { Math.round(minOf(0.0, TARGET_LUFS - it) * 10) / 10.0 } ?: 0.0

    /** Hệ số biên độ của `db` decibel. */
    fun factor(db: Double): Float = Math.pow(10.0, db / 20.0).toFloat()
}
