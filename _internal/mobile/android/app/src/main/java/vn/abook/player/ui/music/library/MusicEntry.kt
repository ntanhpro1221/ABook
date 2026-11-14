package vn.abook.player.ui.music.library

import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.withContext
import vn.abook.player.MusicLibrary
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.music.MusicCredit

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
 * Load and group scenes on IO, then contribute lazy rows to the dedicated Music tab.
 * Empty books and read failures have distinct states; retry never runs on the UI thread.
 */
@Composable
fun BookMusicFor(state: LibraryState, sheets: SheetHost, bookId: String, scenesOf: (String) -> List<Pair<String?, String>>): LazyListScope.() -> Unit {
    DisposableEffect(state, bookId) { onDispose { state.stopPreview() } }
    var retry by remember(bookId) { mutableIntStateOf(0) }
    val entries by produceState<Result<List<MusicLibrary.BookTrack>>?>(null, bookId, retry) {
        value = null
        value = withContext(Dispatchers.IO) {
            try { Result.success(MusicLibrary.bookTracks(scenesOf(bookId))) }
            catch (error: CancellationException) { throw error }
            catch (error: Exception) { Result.failure(error) }
        }
    }
    return BookMusicSection(state, sheets, entries) { retry++; state.open() }
}
