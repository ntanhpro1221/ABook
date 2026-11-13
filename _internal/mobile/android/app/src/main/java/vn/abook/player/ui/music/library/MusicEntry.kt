package vn.abook.player.ui.music.library

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.music.MusicCredit
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.Reveal

/**
 * Lối vào màn Nhạc từ những chỗ khác (Shell cung cấp; null = bản thử, không có màn Nhạc):
 * `openPick` - Kho nhạc ở chế độ chọn cho đoạn `scene` của cuốn `bookId` ("Xem cả kho" cuối "Đổi bài"; chọn xong ghim như bài gợi ý rồi quay lại);
 * `openPlaying` - sheet "Bài đang phát" (chạm ghi công Nhạc nền của trình phát).
 */
class MusicEntry(
    val openPick: (bookId: String, scene: String) -> Unit,
    val openPlaying: (credit: MusicCredit, bookId: String) -> Unit,
)

val LocalMusicEntry = staticCompositionLocalOf<MusicEntry?> { null }

/** Bài của danh mục (không phải bài tự nhập `local:`): mở được sheet "Bài đang phát". */
fun MusicCredit.inCatalog(): Boolean = link.isNotEmpty() && !link.startsWith("local:")

/**
 * "Nhạc trong sách" của trang sách: đọc (khoá đoạn, bài) của cuốn ở luồng nền qua `scenesOf` rồi vẽ [BookMusicSection]. Cuốn không có nhạc gắn sẵn
 * (hay đọc lỗi) thì không hiện gì.
 */
@Composable
fun BookMusicFor(state: LibraryState, sheets: SheetHost, bookId: String, scenesOf: (String) -> List<Pair<String?, String>>) {
    val scenes by produceState(emptyList<Pair<String?, String>>(), bookId) {
        value = withContext(Dispatchers.IO) { runCatching { scenesOf(bookId) }.getOrDefault(emptyList()) }
    }
    Reveal(scenes.isNotEmpty()) { BookMusicSection(state, sheets, scenes, Modifier.padding(top = Dim.s24)) }
}
