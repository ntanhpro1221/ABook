package vn.abook.player

import java.util.concurrent.CopyOnWriteArrayList

/**
 * MỘT cửa báo "file của sách này vừa đổi trên đĩa" - mọi chỗ ghi lại chương, book.json hay stream.json của một cuốn ([BookFileImport.importFile], [BookDownloads.downloadBook],
 * [Streaming.fetchManifest]) gọi [changed] ngay khi ghi xong, rồi mọi nơi đang giữ bản chụp của cuốn ấy tự đọc lại:
 *  - trình phát đang nạp đúng cuốn này ([Playback.refreshFromDisk]: hàng chương, độ dài, file đang mở; cùng chương, cùng chỗ, phát/dừng giữ nguyên);
 *  - người nghe đăng ký bằng [listen] (Thư viện, màn sửa sách) - bản chụp của chúng dựng ở [AbookApplication].
 * Chỗ ghi mới KHÔNG tự gọi cửa này sẽ làm trình phát giữ độ dài / file cũ tới khi app bị giết: BookFilesScanTest không cho chỗ ghi nào ngoài danh sách của nó.
 */
object BookFiles {
    private val listeners = CopyOnWriteArrayList<(String) -> Unit>()

    /** Người nghe tin "sách `id` đã đổi file"; trả về hàm gỡ. Gọi ở luồng bất kỳ (người nghe tự chuyển sang luồng của mình). */
    fun listen(listener: (String) -> Unit): () -> Unit {
        listeners.add(listener)
        return { listeners.remove(listener) }
    }

    /** Sách `id` vừa được ghi file xong (cuốn mới, thay, tải thêm, đổi gói). Luồng bất kỳ. */
    fun changed(id: String) {
        if (id.isEmpty()) return
        edited(id)
        for (listener in listeners) runCatching { listener(id) }.onFailure { AppLog.w("BookFiles", S.s_nguoi_nghe_tin_doi_file_loi_0_352c518c(it.javaClass.simpleName), it) }
    }

    /** Chỉ lớp sửa (tên chương, bìa, cách đọc) của sách đổi: trình phát đọc lại nhãn của hàng chương. Nơi sửa tự làm mới Thư viện của nó. Luồng bất kỳ. */
    fun edited(id: String) {
        if (id.isEmpty()) return
        Playback.onMain { runCatching { Playback.refreshFromDisk(id) }.onFailure { AppLog.w("BookFiles", S.s_chua_lam_moi_trinh_phat_0_7b8b2e25(it.javaClass.simpleName), it) } }
    }
}
