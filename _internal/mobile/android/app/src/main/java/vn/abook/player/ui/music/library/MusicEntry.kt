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
 * `moodsOf`: {khoá mốc: cảm xúc cảnh} của cuốn (LocalStudio.sceneMoods) - chạm bài mở "Vì sao bài này" của đoạn đầu tiên dùng bài.
 * `namesOf`: {link: tên bài} theo book.json (LocalStudio.bookTrackNames) - bài không có trong kho nhạc (`local:` đi kèm sách) vẫn có dòng.
 */
@Composable
fun BookMusicFor(
    state: LibraryState,
    sheets: SheetHost,
    bookId: String,
    moodsOf: (String) -> Map<String, Map<String, Double>> = { emptyMap() },
    namesOf: (String) -> Map<String, MusicLibrary.TrackName> = { emptyMap() },
    scenesOf: (String) -> List<Pair<String?, String>>,
): LazyListScope.() -> Unit {
    DisposableEffect(state, bookId) { onDispose { state.stopPreview() } }
    var retry by remember(bookId) { mutableIntStateOf(0) }
    val loaded by produceState<Result<Pair<List<MusicLibrary.BookTrack>, Map<String, Map<String, Double>>>>?>(null, bookId, retry) {
        value = null
        value = withContext(Dispatchers.IO) {
            try { Result.success(MusicLibrary.bookTracks(scenesOf(bookId), trackNames(namesOf, bookId)) to sceneMoods(moodsOf, bookId)) }
            catch (error: CancellationException) { throw error }
            catch (error: Exception) { Result.failure(error) }
        }
    }
    return BookMusicSection(state, sheets, loaded?.map { it.first }, loaded?.getOrNull()?.second.orEmpty()) { retry++; state.open() }
}

/** Tên bài là phần thêm: đọc hỏng thì dòng bài ngoài kho lấy tên theo link. */
private fun trackNames(namesOf: (String) -> Map<String, MusicLibrary.TrackName>, bookId: String): Map<String, MusicLibrary.TrackName> =
    try { namesOf(bookId) } catch (error: CancellationException) { throw error } catch (_: Exception) { emptyMap() }

/** Cảm xúc cảnh là phần thêm: đọc hỏng thì "Vì sao bài này" ẩn, danh sách bài vẫn hiện. */
private fun sceneMoods(moodsOf: (String) -> Map<String, Map<String, Double>>, bookId: String): Map<String, Map<String, Double>> =
    try { moodsOf(bookId) } catch (error: CancellationException) { throw error } catch (_: Exception) { emptyMap() }

/** Cảm xúc cảnh của đoạn `scene` (khoá mốc) trong cuốn `bookId`, đọc trên IO - sheet "Bài đang phát"; chưa đọc xong / không có -> rỗng (ẩn khối). */
@Composable
fun rememberSceneMood(bookId: String, scene: String, moodsOf: (String) -> Map<String, Map<String, Double>>): Map<String, Double> {
    val mood by produceState(emptyMap<String, Double>(), bookId, scene) {
        if (bookId.isNotEmpty() && scene.isNotEmpty()) value = withContext(Dispatchers.IO) { sceneMoods(moodsOf, bookId)[scene].orEmpty() }
    }
    return mood
}
