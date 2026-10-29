package vn.abook.player.ui.data

import android.content.Context
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.Bedtime
import vn.abook.player.Playback
import vn.abook.player.ui.nowplaying.AndroidReadAlongSource
import vn.abook.player.ui.nowplaying.ReadParagraph

/** Nhật ký đêm với lõi (Bedtime.kt), tách khỏi màn để thử bằng nguồn giả. Hàm suspend tự chạy ở luồng nền. */
interface NightSource {
    /** Đêm gần nhất của hồ sơ đang dùng; null = chưa có đêm nào được ghi. */
    suspend fun latest(): NightSession?
    suspend fun dismiss()

    /** Các đoạn chữ có mốc giờ của một chương (để đặt câu văn cạnh mỗi mốc); rỗng khi chưa có chữ. */
    suspend fun paragraphs(bookId: String, chapterId: Int, title: String): List<ReadParagraph>
}

class AndroidNightSource(context: Context) : NightSource {
    private val app = context.applicationContext
    private val text by lazy { AndroidReadAlongSource(app) }

    override suspend fun latest(): NightSession? = withContext(Dispatchers.IO) {
        Playback.init(app)
        Bedtime.latest()?.let(NightSession::parse)
    }

    override suspend fun dismiss() = withContext(Dispatchers.IO) { Bedtime.dismiss() }

    override suspend fun paragraphs(bookId: String, chapterId: Int, title: String): List<ReadParagraph> =
        runCatching { text.paragraphs(bookId, PlayerChapter(chapterId, title, 0)) }.getOrDefault(emptyList())
}

/**
 * Thẻ "Tối qua" sống: đêm gần nhất, và câu văn ở các chương có mốc. Đọc một lần khi Thư viện hiện ([load]); [had] cho tấm Hẹn giờ biết người nghe đã có đêm nào được ghi
 * (thẻ chỉ đáng nhắc khi đã từng có).
 */
@Stable
class NightState(private val source: NightSource, private val scope: CoroutineScope, private val clockMs: () -> Long = System::currentTimeMillis) {
    private val _session = MutableStateFlow<NightSession?>(null)
    val session: StateFlow<NightSession?> = _session

    /** chương -> các đoạn chữ có mốc giờ (rỗng = chưa có chữ, thẻ không có câu văn / "Tìm đúng câu"). */
    private val _lines = MutableStateFlow<Map<Int, List<ReadParagraph>>>(emptyMap())
    val lines: StateFlow<Map<Int, List<ReadParagraph>>> = _lines

    val had: Boolean get() = _session.value != null

    fun load() {
        scope.launch {
            val night = try { source.latest() } catch (cancel: CancellationException) { throw cancel } catch (_: Exception) { null }
            _session.value = night
            if (night == null || !NightRecap.fresh(night, clockMs() / 1000.0)) return@launch
            val chapters = NightRecap.markers(night).associate { it.chapterId to it.chapterTitle }
            _lines.value = chapters.mapValues { (id, title) -> source.paragraphs(night.bookId, id, title) }
        }
    }

    /** Ẩn thẻ: đêm này không hiện nữa. */
    fun dismiss() {
        _session.value = _session.value?.copy(dismissed = true)
        scope.launch { runCatching { source.dismiss() } }
    }
}
