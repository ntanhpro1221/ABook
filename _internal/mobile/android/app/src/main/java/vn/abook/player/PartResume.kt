package vn.abook.player

import java.io.File

/**
 * Tải tiếp một file dở (`<tên>.part`) bằng `Range` mà không ghép nhầm đầu cũ với đuôi mới - bản cài của `remote_books._save` /
 * `_resume_point` bên máy tính: phiên bản (ETag) của file nguồn mà phần dở đang giữ nằm cạnh nó (`<tên>.part.etag`, ghi SAU khi cắt
 * `.part`), yêu cầu tiếp gửi `Range` kèm `If-Range`, và trả lời chỉ được nối khi là 206 đúng chỗ xin mà ETag vẫn khớp. Thiếu ETag cạnh
 * phần dở = không biết nó thuộc phiên bản nào = không tải tiếp.
 */
object PartResume {
    /** Phải làm gì với trả lời của một yêu cầu tải (tiếp). */
    enum class Answer {
        /** 206 đúng chỗ xin, cùng ETag: nối vào phần dở. */
        RESUME,

        /** Máy kia gửi cả file (200: không hiểu Range hay file đã đổi): bỏ phần dở, ghi đè từ đầu. */
        WHOLE,

        /** 206 nhưng không phải đuôi của file mà phần dở thuộc về (ETag lệch, hay chỗ lạ): bỏ phần dở, hỏi lại KHÔNG kèm Range. */
        STALE_TAIL,
    }

    fun tagFile(partial: File): File = File(partial.path + ".etag")

    /** (số byte, ETag) của phần dở có thể tải tiếp; (0, "") khi không: không có, rỗng, đã đủ cỡ (`size` > 0), hay không rõ phiên bản. */
    fun point(partial: File, size: Long = 0): Pair<Long, String> {
        if (!partial.isFile) return 0L to ""
        val have = partial.length()
        val tag = runCatching { tagFile(partial).readText(Charsets.UTF_8).trim() }.getOrDefault("")
        return if (tag.isNotEmpty() && have > 0 && (size <= 0 || have < size)) have to tag else 0L to ""
    }

    fun answer(code: Int, contentRange: String?, etag: String?, have: Long, tag: String): Answer {
        if (code != 206) return Answer.WHOLE
        val placed = have > 0 && contentRange.orEmpty().trim().startsWith("bytes $have-")
        return if (placed && etag.orEmpty().trim() == tag) Answer.RESUME else Answer.STALE_TAIL
    }

    /** Cỡ file sau khi tải xong so với cỡ sách (book.json) ghi: thiếu = đứt giữa chừng (giữ phần dở, tải tiếp được), khác = không phải file này (bỏ). */
    enum class Final { OK, SHORT, WRONG }

    fun finish(length: Long, expected: Long): Final = when {
        expected <= 0 || length == expected -> Final.OK
        length < expected -> Final.SHORT
        else -> Final.WRONG
    }

    /** Ghi phiên bản của file đang tải vào `<tên>.part.etag` (gọi SAU khi `.part` đã bị cắt); không có ETag thì xoá ghi chú cũ. */
    fun stamp(partial: File, etag: String?) {
        val tag = etag.orEmpty().trim()
        if (tag.isEmpty()) tagFile(partial).delete() else tagFile(partial).writeText(tag, Charsets.UTF_8)
    }

    /** Bỏ cả phần dở lẫn ghi chú phiên bản của nó. */
    fun discard(partial: File) {
        partial.delete()
        tagFile(partial).delete()
    }
}
