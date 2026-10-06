package vn.abook.player

import java.io.File

/**
 * "Chia sẻ…" một cuốn qua bảng chia sẻ của Android (Zalo, Drive, email) - phần không dính Android của [LibraryPlugin.shareBook]:
 * file gửi đi ghi vào `cacheDir/share/<tên sách>.abook` (FileProvider phục vụ cả `cacheDir`, res/xml/file_paths.xml), tên như "Lưu
 * thành…" ([BookDocumentWriter.defaultName]). App nhận đọc file sau khi bảng chia sẻ đã đóng, nên không xoá ngay: dọn lúc mở app.
 */
object BookShare {
    const val FOLDER = "share"

    fun dir(cacheDir: File): File = File(cacheDir, FOLDER)

    /** Chỗ ghi file gửi đi. Mỗi lần chia sẻ một thư mục con riêng: tên file giữ đúng tên sách (app nhận hiện tên ấy), hai cuốn trùng
     *  tên hay hai lần chia sẻ liền nhau không ghi đè file app khác còn đang đọc. */
    fun target(cacheDir: File, title: String, asProject: Boolean, stamp: Long = System.nanoTime()): File =
        File(File(dir(cacheDir), java.lang.Long.toHexString(stamp)), BookDocumentWriter.defaultName(title, asProject))

    fun mimeType(asProject: Boolean): String = if (asProject) BookFileImport.PROJECT_MIMETYPE else BookFileImport.MIMETYPE

    /** Dọn các file đã chia sẻ lần trước. */
    fun sweep(cacheDir: File) {
        dir(cacheDir).deleteRecursively()
    }
}
