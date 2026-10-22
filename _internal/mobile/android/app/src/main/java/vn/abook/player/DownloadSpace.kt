package vn.abook.player

import org.json.JSONObject
import java.io.File

/**
 * Chỗ trống cho một lượt tải sách (soát a68 lỗi 10): tính phần CÒN phải tải (file đã đủ, phần `.part` đã về thì không tính lại) và từ chối trước khi
 * tải nếu điện thoại không đủ - chừa [MARGIN] cho Android và chính app, như máy tính chừa chỗ trước khi xuất.
 */
object DownloadSpace {
    const val MARGIN = 100L * 1024 * 1024

    /** Byte còn phải tải của một file cỡ `size` (0 = không biết cỡ, file nhỏ: không tính) đích `target`. */
    fun stillNeeded(size: Long, target: File?, digest: String = ""): Long {
        if (size <= 0) return 0
        if (target == null) return size
        if (target.isFile && target.length() == size && (digest.isEmpty() || AudioRevision.matches(target, size, digest))) return 0
        // Chỉ phần dở còn biết thuộc phiên bản nào mới được tải tiếp (PartResume), nên chỉ phần ấy được trừ.
        val have = PartResume.point(File(target.path + ".part"), size).first
        return (size - have).coerceAtLeast(0)
    }

    /** Cỡ cả cuốn khi tải về theo gói sách (`book.json`): audio các chương đã có + nhạc nền - hiện cạnh nút Tải trước khi bấm (soát a68 lỗi 7).
     *  Chữ, dàn nhân vật, bìa vài trăm KB: không tính. */
    fun bookBytes(manifest: JSONObject): Long {
        val chapters = manifest.optJSONArray("chapters")
        var total = 0L
        for (index in 0 until (chapters?.length() ?: 0)) {
            val chapter = chapters!!.optJSONObject(index) ?: continue
            if (chapter.optBoolean("available")) total += chapter.optLong("size").coerceAtLeast(0)
        }
        return total + BookMusic.tracks(manifest.optJSONObject("music")).sumOf { it.size }
    }

    /** Lời báo khi `free` byte không đủ cho `missing` byte cộng [MARGIN]; đủ thì null. */
    fun shortage(missing: Long, free: Long): String? {
        if (missing <= 0 || missing + MARGIN <= free) return null
        return "Điện thoại không đủ chỗ trống để tải cuốn này: cần khoảng ${megabytes(missing + MARGIN)}, còn ${megabytes(free)}. " +
            "Xoá bớt sách ở mục dung lượng cuối màn này rồi tải lại."
    }

    private fun megabytes(bytes: Long): String = "${(bytes.coerceAtLeast(0) + (1 shl 20) - 1) shr 20} MB"
}
