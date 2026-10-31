package vn.abook.player

import java.io.File
import java.io.OutputStream

/**
 * "Bản lưu cũ": file bản lưu trước mà [BookSave] giữ lại khi lần lưu mới bị gián đoạn hoặc bản trước chưa trả lại vào chỗ đã chọn được
 * (filesDir/ban-luu-cu). Người dùng thấy danh sách ở Cài đặt, lưu ra chỗ khác hoặc xoá - phần thuần ở đây (liệt kê, chặn tên, chép, xoá),
 * phần hộp chọn chỗ lưu của hệ thống nằm ở giao diện.
 */
object OldSaves {
    const val DIR = "ban-luu-cu"

    data class Entry(val name: String, val size: Long, val modified: Long)

    fun dir(filesDir: File) = File(filesDir, DIR)

    /** File trong thư mục, mới nhất đứng đầu. Không có thư mục / thư mục rỗng: danh sách rỗng. */
    fun list(dir: File): List<Entry> =
        dir.listFiles { file -> file.isFile }.orEmpty().map { Entry(it.name, it.length(), it.lastModified()) }.sortedWith(compareByDescending<Entry> { it.modified }.thenBy { it.name })

    /** File tên `name` của thư mục. Tên có dấu gạch chéo, là `..`, rỗng, hay không phải file có sẵn thì bị từ chối - không thoát ra ngoài thư mục (tên có "..." giữa chừng, vd tựa sách, vẫn là tên thường). */
    fun resolve(dir: File, name: String): File {
        require(name.isNotBlank() && name == name.trim() && '/' !in name && '\\' !in name && name != "." && name != ".." && '\u0000' !in name) { "Tên bản lưu cũ không hợp lệ" }
        val file = File(dir, name)
        require(file.isFile && file.canonicalFile.parentFile == dir.canonicalFile) { "Không thấy bản lưu cũ này" }
        return file
    }

    /** Chép file ra `sink` theo từng khối - không giữ cả file trong bộ nhớ. Trả số byte đã chép. */
    fun copyTo(dir: File, name: String, sink: OutputStream): Long = resolve(dir, name).inputStream().use { it.copyTo(sink) }

    /** Xoá file (không lấy lại được). Trả true khi đã xoá. */
    fun delete(dir: File, name: String): Boolean {
        if (!resolve(dir, name).delete()) return false
        val journal = File(dir, ".pending/$name.json")
        if (journal.isFile) journal.delete()
        journal.parentFile?.delete() // only an empty directory; no other recovery intent is removed
        return true
    }

    /** Loại file để hộp "Lưu ra…" của hệ thống đặt đúng đuôi. */
    fun mimeOf(name: String): String =
        if (name.endsWith(BookDocumentWriter.PROJECT_EXTENSION)) BookFileImport.PROJECT_MIMETYPE else BookFileImport.MIMETYPE
}
