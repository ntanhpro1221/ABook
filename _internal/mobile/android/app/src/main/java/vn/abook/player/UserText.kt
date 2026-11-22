package vn.abook.player

import java.io.FileNotFoundException

/**
 * Một cửa duy nhất từ lỗi (Throwable) ra chữ trên màn hình. Không màn nào của app được hiện nguyên chữ của Java/Android
 * ("Permission Denial: opening provider ... ACTION_OPEN_DOCUMENT", "ENOENT", "Failed to connect to /192.0.2.10"): chủ sách
 * gặp đúng câu ấy ở Thêm sách 0.4.173 khi bấm "Thử lại" sau khi quyền đọc file đã hết.
 *
 * Lời do chính app viết (chữ trong `S`, lời của Studio/máy tính) đi qua nguyên vẹn. Lỗi của nền tảng thành một câu tiếng Việt
 * theo loại (mất quyền, mạng, hết chỗ, mất file), còn lại là `fallback` của nơi gọi. Chữ gốc luôn vào nhật ký ([AppLog]).
 * `tests/test_android_raw_errors.py` chặn mọi đường mới đưa `.message` của lỗi lên giao diện mà không qua đây.
 */
object UserText {
    private const val TAG = "UserText"
    private val vietnamese = Regex("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", RegexOption.IGNORE_CASE)
    private val machine = Regex("""Exception|Error:|Permission Denial|\bjava\.|\bandroid\.|\bkotlin\.|content://|file://|\buid=|\bpid=|\bErrno\b|\bE[A-Z]{3,}\b \(""")

    /** Chữ này viết cho người đọc: có chữ tiếng Việt và không mang dấu vết máy (tên lớp lỗi, URI, uid...). */
    fun readable(text: String?): Boolean = !text.isNullOrBlank() && vietnamese.containsMatchIn(text) && !machine.containsMatchIn(text)

    /** Lỗi do app mất quyền đọc/ghi một URI (quyền tạm của hộp chọn file đã hết, hay chưa bao giờ được giữ lâu dài). */
    fun accessLost(error: Throwable?): Boolean = chain(error).any { it is SecurityException }

    /** Câu cho người dùng về `error`; `fallback` là việc chưa làm được, nói bằng lời của nơi gọi. */
    fun of(error: Throwable?, fallback: String, tag: String = TAG): String {
        if (error == null) return fallback
        val shown = say(error) ?: fallback
        if (shown != error.message) AppLog.w(tag, "${NetErrors.technical(error)} -> $shown")
        return shown
    }

    /** Chữ lỗi đã tách khỏi Throwable từ trước (trường `message` của một kết quả, lời máy kia gửi): chỉ hiện khi viết cho người đọc. */
    fun text(message: String?, fallback: String): String = message?.takeIf(::readable) ?: fallback

    private fun say(error: Throwable): String? {
        error.message?.takeIf(::readable)?.let { return it }
        if (accessLost(error)) return S.s_abook_khong_con_quyen_mo_file_nay_ban_hay_b7276dfc
        NetErrors.kind(error)?.let { return NetErrors.message(it) }
        if (chain(error).any { it is PinnedFiles.SpaceError || it.message.orEmpty().let { m -> "ENOSPC" in m || "No space left" in m } })
            return S.s_ban_giai_phong_bo_nho_tren_dien_thoai_roi_17f5da65
        if (chain(error).any { it is FileNotFoundException }) return S.s_khong_thay_file_nua_co_the_no_da_bi_xoa_371f4e4f
        return chain(error).drop(1).mapNotNull { it.message }.firstOrNull(::readable)
    }

    private fun chain(error: Throwable?) = generateSequence(error) { it.cause }.take(8)
}
