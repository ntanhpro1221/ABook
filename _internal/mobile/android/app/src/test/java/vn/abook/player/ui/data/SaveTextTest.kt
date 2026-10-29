package vn.abook.player.ui.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Chữ của "Lưu thay đổi" / "Lưu thành": đúng câu của bản web (BookScreen.tsx useSaveBook, EditBook.tsx SaveAsDialog). */
class SaveTextTest {
    @Test
    fun `a save with changes says only that the file was saved`() {
        assertEquals("Đã lưu file sách", SaveText.done(3))
    }

    @Test
    fun `a save with no changes warns that the file equals the original`() {
        assertEquals("Đã lưu file sách. Chưa có thay đổi nào - file giống bản gốc.", SaveText.done(0))
    }

    @Test
    fun `a failed save adds the reason only when the core gave one`() {
        assertEquals("Chưa lưu được file sách", SaveText.failed(null))
        assertEquals("Chưa lưu được file sách", SaveText.failed("  "))
        assertEquals("Chưa lưu được file sách. Thiếu chỗ lưu.", SaveText.failed(" Thiếu chỗ lưu. "))
    }

    @Test
    fun `the note under the file kind follows kind and workshop`() {
        assertEquals("Cả dự án kèm thay đổi của bạn; mở bằng Studio để áp.", SaveText.kindNote(true, "present", 0))
        assertEquals("Chỉ có phần nghe và thay đổi của bạn. Studio dựng lại được dự án từ file này.", SaveText.kindNote(true, "pending", 0))
        assertEquals("Chỉ có phần nghe và thay đổi của bạn. Studio dựng lại được dự án từ file này.", SaveText.kindNote(true, null, 4))
        val book = SaveText.kindNote(false, null, 0)
        assertTrue(book.startsWith("Sách nghe mở được bằng ABook") && book.endsWith("nhạc bạn đã sửa."))
        assertTrue(SaveText.kindNote(false, null, 2).endsWith("nhạc bạn đã sửa, cùng 2 việc đang chờ máy làm sách (chưa làm gì trong giọng đọc)."))
    }
}
