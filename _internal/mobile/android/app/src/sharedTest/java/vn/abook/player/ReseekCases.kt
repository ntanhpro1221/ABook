package vn.abook.player

import kotlin.math.roundToLong

/**
 * Lưới ca RS của MusicLoopSeamTest (PLAN_loop §44.7): các lần tua liền nhau trong CÙNG mục Nối WAV, cách nhau Δ ms đồng hồ thật. Khối WAV = sr/10 khung (100 ms);
 * các mốc lấy theo số đo ls_06 ở 44,1 kHz (khối 4410) và co giãn theo khối ở tần số khác. Test JVM: ReseekCasesTest.
 */
internal object ReseekCases {
    /**
     * `targets` = mẫu đích trên trục Nối (= khung trong WAV) của từng lần tua theo thứ tự; `applicable` = mọi đích còn đủ [tailFrames] khung trong Nối.
     * `edgeFraction` >= 0: ca "edge" - đích của lần B tính lúc chạy bằng [edgeTarget] (khối đang phát + phần lẻ này), tua đúng lúc vị trí vừa qua ranh khối ([atChunkStart]).
     */
    class Case(val name: String, val deltaMs: Long, val targets: List<Long>, val applicable: Boolean, val edgeFraction: Long = -1)

    val DELTAS_MS = longArrayOf(50, 100, 180, 300)
    /** Chuỗi ba lần tua của ls_06 (44,1 kHz), mỗi lần cách nhau [LS06_DELTA_MS]: lần 3 đáp lệch +4365 khung. */
    val LS06 = longArrayOf(12246, 13872, 21703)
    const val LS06_DELTA_MS = 183L
    /** Phần lẻ (khung, ở khối 4410) của lần A và của đích B khác 0: như lần 1 / lần 3 của ls_06. */
    const val A_FRACTION = 3426L
    const val B_FRACTION = 4063L
    /** Lần A nằm ở khối thứ [A_CHUNK]; "in" = B sau A [IN_CHUNKS] khối, "far" = sau [FAR_CHUNKS] khối (> 1,5 s, ngoài vùng đệm). */
    const val A_CHUNK = 2L
    const val IN_CHUNKS = 2L
    const val FAR_CHUNKS = 16L

    fun chunk(sampleRate: Int): Long = (sampleRate / 10).toLong().coerceAtLeast(1)

    /** Mốc đo ở 44,1 kHz (khối 4410) đổi sang khối của `sampleRate`, giữ vị trí tương đối trong khối. */
    fun scaled(frames44k: Long, sampleRate: Int): Long {
        val c = chunk(sampleRate)
        return frames44k / 4410 * c + (frames44k % 4410 * c / 4410.0).roundToLong()
    }

    /** Số khung phải còn sau mỗi đích trong Nối: 400 ms (phát sau tua mà chưa sang mục kế, để đoạn tee của lần tua không lẫn flush chuyển mục). */
    fun tailFrames(sampleRate: Int): Long = sampleRate * 4L / 10

    /**
     * Mọi ca: Δ ∈ [DELTAS_MS] × đích B ∈ {in (đã đọc trước, >= 1 khối sau A), same (cùng khối 100 ms với A), far (ngoài vùng đệm)} × phần lẻ {f = [B_FRACTION], 0};
     * tên `D<Δ>_<in|same|far>_<f|0>`. Thêm ca `LS06` và ca `D<Δ>_edge_<f|0>` (đích B tính lúc chạy, xem [Case]). `seamFrames` = số khung của WAV Nối.
     */
    fun build(sampleRate: Int, seamFrames: Long): List<Case> {
        val c = chunk(sampleRate)
        val tail = tailFrames(sampleRate)
        val a = A_CHUNK * c + scaled(A_FRACTION, sampleRate)
        val bFraction = scaled(B_FRACTION, sampleRate)
        fun case(name: String, delta: Long, targets: List<Long>) = Case(name, delta, targets, targets.all { it >= 0 && it + tail <= seamFrames })
        val out = mutableListOf<Case>()
        for (delta in DELTAS_MS) {
            for ((kind, chunkOfB) in listOf("in" to A_CHUNK + IN_CHUNKS, "same" to A_CHUNK, "far" to A_CHUNK + FAR_CHUNKS)) {
                for ((tag, fraction) in listOf("f" to bFraction, "0" to 0L)) {
                    out += case("D${delta}_${kind}_$tag", delta, listOf(a, chunkOfB * c + fraction))
                }
            }
        }
        out += case("LS06", LS06_DELTA_MS, LS06.map { scaled(it, sampleRate) })
        // Ca thêm (khoanh giả thuyết): lần B đúng lúc vị trí phát vừa qua ranh khối -> LoopSeam.seekIsNoop đúng -> có lệnh tua đệm (vòng 10: ranh - 1 ms, lệch lưới;
        // từ vòng 11 Nối tua đệm ở ranh khối trước, LoopSeam.stepAside(index, ms)).
        for (delta in DELTAS_MS) {
            val latest = a + sampleRate * (delta + EDGE_MAX_WAIT_MS) / 1000 + c
            for ((tag, fraction) in listOf("f" to bFraction, "0" to 0L)) {
                out += Case("D${delta}_edge_$tag", delta, listOf(a), a + tail <= seamFrames && latest + tail <= seamFrames, fraction)
            }
        }
        return out
    }

    /** Ca edge: sau Δ còn chờ tối đa ngần này cho vị trí phát chạm ranh khối. */
    const val EDGE_MAX_WAIT_MS = 1000L

    /** Vị trí phát (ms, trục Nối) vừa qua ranh khối 100 ms tối đa 1 ms: tua tới ranh ấy thì [LoopSeam.seekIsNoop] (±2 ms) đúng. */
    fun atChunkStart(currentMs: Long): Boolean = currentMs >= 100 && currentMs % 100 <= 1

    /** Đích ca edge: khối chứa vị trí phát `currentMs` + `fraction` khung. */
    fun edgeTarget(currentMs: Long, sampleRate: Int, fraction: Long): Long = currentMs / 100 * chunk(sampleRate) + fraction

    /** Lọc theo `-e rs`: danh sách cách nhau dấu phẩy; mỗi mục khớp tên đúng hoặc tiền tố trước dấu `_` (vd `D180`, `D180_in`); rỗng / null = mọi ca. */
    fun select(cases: List<Case>, filter: String?): List<Case> {
        val tokens = filter?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() }.orEmpty()
        if (tokens.isEmpty()) return cases
        return cases.filter { case -> tokens.any { case.name == it || case.name.startsWith(it + "_") } }
    }
}
