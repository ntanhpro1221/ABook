package vn.abook.player

/**
 * Định vị PCM trong bản tham chiếu: lưới an toàn của Nối WAV ([LoopSeam.landOf]: K khung đầu sau một lần tua nằm ở đâu trong WAV Nối) và bộ đo MusicLoopSeamTest
 * (tee, chọn đoạn tee của một lần tua). Thuần số học; test JVM: SeamMatchTest.
 */
internal object SeamMatch {
    /** `w` (n khung xen kênh) trùng `ref` từ khung `p`, lệch từng mẫu <= `tolerance`; người gọi lo `p` hợp lệ. Dừng ở mẫu lệch đầu tiên: vị trí sai thường chỉ tốn một phép so. */
    private fun matchesAt(ref: ShortArray, channels: Int, w: ShortArray, p: Long, tolerance: Int): Boolean {
        val base = (p * channels).toInt()
        var k = 0
        while (k < w.size && Math.abs(ref[base + k] - w[k]) <= tolerance) k++
        return k == w.size
    }

    /**
     * Khung đầu `p` (thấp nhất) trong [lo, hi] mà `w` (n khung xen kênh) trùng `ref` từ khung p, lệch từng mẫu <= `tolerance` (0 = khớp từng bit); -1 nếu không thấy.
     * `lo` / `hi` được kẹp vào phạm vi hợp lệ của `ref`.
     */
    fun locate(ref: ShortArray, channels: Int, w: ShortArray, lo: Long, hi: Long, tolerance: Int): Long {
        val n = w.size / channels
        if (n == 0) return -1
        val from = maxOf(0L, lo)
        val to = minOf((ref.size / channels - n).toLong(), hi)
        var p = from
        while (p <= to) {
            if (matchesAt(ref, channels, w, p, tolerance)) return p
            p++
        }
        return -1
    }

    /**
     * Vị trí khớp từng bit GẦN `expected` nhất, cách nó tối đa `radius` khung: thử đúng `expected` trước (ca thường: O(K)), rồi `expected` ± 1, ± 2, ... xen hai phía.
     * `ref` là một đoạn của trục chung bắt đầu ở khung `refStart` (vd ±1 s quanh đích đọc từ WAV); kết quả tính trên trục chung, null nếu không thấy.
     * Đoạn im lặng (mọi vị trí đều khớp) thì trả đích: không có bằng chứng lệch.
     */
    fun nearest(ref: ShortArray, refStart: Long, channels: Int, w: ShortArray, expected: Long, radius: Long): Long? {
        val n = w.size / channels
        if (n == 0) return null
        val last = (ref.size / channels - n).toLong() // vị trí cục bộ cuối còn chứa đủ n khung
        val e = expected - refStart
        for (d in 0..radius) {
            val up = e + d
            if (up in 0..last && matchesAt(ref, channels, w, up, 0)) return up + refStart
            val down = e - d
            if (d > 0 && down in 0..last && matchesAt(ref, channels, w, down, 0)) return down + refStart
            if (up > last && down < 0) break
        }
        return null
    }

    /**
     * Đoạn tee của một lần tua: mốc flush CUỐI trong [seekNs, seekNs + windowNs] (và trước `limitNs`, vd lệnh tua kế), không có thì mốc đầu tiên trong [seekNs, limitNs).
     * `marks` = (seg, ns, byte trong file tee) theo thứ tự ghi. Chỉ bộ đo dùng.
     */
    fun teeMark(marks: List<Triple<Int, Long, Int>>, seekNs: Long, windowNs: Long, limitNs: Long = Long.MAX_VALUE): Triple<Int, Long, Int>? =
        marks.lastOrNull { it.second >= seekNs && it.second <= seekNs + windowNs && it.second < limitNs }
            ?: marks.firstOrNull { it.second >= seekNs && it.second < limitNs }
}
