package vn.abook.player.ui.music.library

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Phần Đã lưu của màn Nhạc: 0 bài đã tải thì không có dòng dung lượng (formatSize(0) = "1 KB" từng hiện "Đã tải 0 bài · 1 KB"). */
class SavedSummaryTest {
    @Test fun noDownloadedSongMeansNoSizeLine() {
        assertNull(savedSummaryText(0, 0L))
        assertNull(savedSummaryText(0, 512L))
    }

    @Test fun downloadedSongsShowCountAndSize() {
        assertEquals("Đã tải 1 bài · 1 KB", savedSummaryText(1, 400L))
        assertEquals("Đã tải 3 bài · 4,8 MB", savedSummaryText(3, 5_000_000L))
    }

    @Test fun anEmptyLibraryHasNoSummary() {
        assertNull(LibraryUi().savedSummary())
    }
}
