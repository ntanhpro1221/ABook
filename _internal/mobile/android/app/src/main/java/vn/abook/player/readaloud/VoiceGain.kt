package vn.abook.player.readaloud

/**
 * Độ to cố định lúc phát: Turbo/Nano dùng ISO 532-1 từ 40 câu trung tính × hai seed (trừ Mai Anh), chỉ nhân biên độ lúc phát
 * (`ExoPlayer.volume`), không mã hoá lại file. Mức đo của giọng VieNeu và Supertonic còn là mốc để nâng câu ngắn nhỏ trong clip ([ClipLift]).
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
        "vieneu:nano/Mỹ Duyên" to -18.4,
        "vieneu:nano/Đức Trí" to -18.6,
        "vieneu:nano/Hữu Quân" to -18.4,
        "vieneu:nano/Xuân Tiên" to -18.5,
        "vieneu:nano/Mai Anh" to -18.5,
        "vieneu:nano/Trúc Ly" to -18.1,
        "vieneu:nano/Anh Khôi" to -18.4,
        "vieneu:nano/Minh Quân" to -17.7,
        "vieneu:nano/Mạnh Dũng" to -17.9,
        "supertonic:F1" to -20.8,
        "supertonic:F2" to -20.8,
        "supertonic:F3" to -21.7,
        "supertonic:F4" to -20.2,
        "supertonic:F5" to -20.7,
        "supertonic:M1" to -21.2,
        "supertonic:M2" to -20.0,
        "supertonic:M3" to -20.1,
        "supertonic:M4" to -20.8,
        "supertonic:M5" to -21.1,
    )

// BEGIN ISO_GAIN_DB
    private val isoGain = mapOf(
        "vieneu:nano/Adam" to -7.1749299,
        "vieneu:nano/Anh Khôi" to -5.6875576,
        "vieneu:nano/Hữu Quân" to -6.4627331,
        "vieneu:nano/Minh Quân" to -9.2682724,
        "vieneu:nano/Mạnh Dũng" to -6.969697,
        "vieneu:nano/Mỹ Duyên" to -5.7483092,
        "vieneu:nano/Trúc Ly" to -5.8490925,
        "vieneu:nano/Xuân Tiên" to -6.4397812,
        "vieneu:nano/Ái Hân" to -7.6493777,
        "vieneu:nano/Đức Trí" to -5.7351194,
        "vieneu:turbo/Adam" to -5.823589,
        "vieneu:turbo/Adam bựa" to -8.5656387,
        "vieneu:turbo/Hải Đăng" to -7.4689457,
        "vieneu:turbo/Kim Thanh" to -6.1783833,
        "vieneu:turbo/Minh Triết" to -5.0567296,
        "vieneu:turbo/Minh Đức" to -4.1024272,
        "vieneu:turbo/Mỹ Duyên" to -5.2095427,
        "vieneu:turbo/Ngọc Huyền" to -5.6594003,
        "vieneu:turbo/Ngọc Linh" to -3.0590848,
        "vieneu:turbo/Ngọc Trân" to -5.1148725,
        "vieneu:turbo/Phạm Tuyên" to -5.0953902,
        "vieneu:turbo/Quang Sơn" to -6.5561637,
        "vieneu:turbo/Quốc Tuấn" to -5.8438354,
        "vieneu:turbo/Quỳnh Anh" to -6.9844304,
        "vieneu:turbo/Thanh Bình" to -7.4990731,
        "vieneu:turbo/Thiền Tâm Đức" to -5.1438573,
        "vieneu:turbo/Thiện Minh" to -4.675821,
        "vieneu:turbo/Thái Sơn" to -5.8174993,
        "vieneu:turbo/Thùy Dung" to -5.7658618,
        "vieneu:turbo/Thục Đoan" to -6.3053222,
        "vieneu:turbo/Trúc Ly" to -7.1000357,
        "vieneu:turbo/Xuân Vĩnh" to -5.0309771,
        "vieneu:turbo/Đoan Trang" to -5.6663398,
        "vieneu:turbo/Đức Trí" to -4.9689108,
    )
    // END ISO_GAIN_DB


    /** LUFS đã đo của giọng; null: chưa đo. */
    fun measured(voiceId: String): Double? = measured[voiceId]

    /** `loudness.gain_db`: ưu tiên hằng số ISO; các giọng khác dùng bảng LUFS, giọng chưa đo 0 dB. */
    fun db(voiceId: String): Double = isoGain[voiceId] ?: (measured[voiceId]?.let { Math.round(minOf(0.0, TARGET_LUFS - it) * 10) / 10.0 } ?: 0.0)

    /** Hệ số biên độ của `db` decibel. */
    fun factor(db: Double): Float = Math.pow(10.0, db / 20.0).toFloat()
}
