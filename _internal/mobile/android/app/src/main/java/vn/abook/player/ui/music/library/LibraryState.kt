package vn.abook.player.ui.music.library

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.MusicLibrary
import vn.abook.player.S

/** Một nhãn của danh mục (phong cách / cảm xúc: mã + chữ tiếng Việt của `taxonomy`). */
@Immutable
data class Label(val id: String, val label: String)

@Immutable
data class LibraryPlaylist(val id: String, val name: String, val links: List<String>)

/** Chỉ mục của Kho nhạc: mọi bài của danh mục + danh sách phát + nhãn tiếng Việt. Dựng một lần mỗi lần mở (nền). */
@Immutable
class LibraryIndex(val tracks: List<MusicLibrary.Track>, val playlists: List<LibraryPlaylist>, val styles: List<Label>, val emotions: List<Label>) {
    val byLink: Map<String, MusicLibrary.Track> = tracks.associateBy { it.link }
    val playlistLinks: Map<String, List<String>> = playlists.associate { it.id to it.links }
    fun styleLabel(id: String): String = styles.firstOrNull { it.id == id }?.label ?: id
    fun emotionLabel(id: String): String = emotions.firstOrNull { it.id == id }?.label ?: id
}

/**
 * Nguồn của Kho nhạc - mọi lời gọi CHẶN (chạy ở luồng nền). Bản thật: [AndroidLibrarySource] (MusicCatalog + SavedTracks của máy);
 * test JVM dùng bản giả.
 */
interface LibrarySource {
    /** Chỉ mục; danh mục chưa từng tải được (mất mạng lần đầu) thì ném lỗi có lời báo. */
    fun load(): LibraryIndex
    fun downloaded(links: Collection<String>): Set<String>
    fun saved(): List<String>
    fun save(links: List<String>)
    fun unsave(links: List<String>)
    /** Tải một bài (kiểm byte + sha1, tải tiếp `.part`, bản sao - [vn.abook.player.MusicCatalog.download]). Huỷ: ném lỗi, phần đã tải giữ lại. */
    fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean)
    fun forget(link: String)
    fun partial(link: String): Long
    /** Mạng tính phí (dữ liệu di động): hỏi trước khi tải. */
    fun metered(): Boolean
    fun online(): Boolean
}

/** Phát nghe thử (Android: MediaPlayer). `volume` 0..1 đưa bài về một mức to ([PREVIEW_LUFS]). */
interface PreviewPlayer {
    fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit)
    fun stop()
}

@Immutable
data class Loading(val done: Long, val total: Long?) {
    /** Phần trăm (tới 99 khi chưa xong hẳn), null khi chưa biết cỡ. */
    val percent: Int? get() = total?.takeIf { it > 0 }?.let { ((done * 100) / it).toInt().coerceIn(0, 99) }
}

@Immutable
data class LibraryUi(
    val loading: Boolean = true,
    val error: String = "",
    val index: LibraryIndex? = null,
    val filters: MusicLibrary.Filters = MusicLibrary.Filters(),
    val shown: List<MusicLibrary.Track> = emptyList(),
    val saved: List<String> = emptyList(),
    val downloaded: Set<String> = emptySet(),
    val active: Map<String, Loading> = emptyMap(),
    val failed: Map<String, String> = emptyMap(),
    val previewing: String? = null,
    val online: Boolean = true,
    /** Thời gian lọc lần gần nhất (ms) - đo "lọc dưới 50 ms". */
    val filterMs: Double = 0.0,
    /** Các bài chờ người dùng đồng ý tải qua dữ liệu di động. */
    val meteredAsk: List<String> = emptyList(),
    /** Tăng mỗi lần nơi khác xin mở Kho nhạc ("Xem trong kho" của Bài đang phát): màn Nhạc chuyển sang phần Kho nhạc. */
    val libraryRequest: Int = 0,
) {
    val savedSet: Set<String> get() = saved.toSet()
    fun savedTracks(): List<MusicLibrary.Track> = index?.let { index -> saved.asReversed().mapNotNull(index.byLink::get) } ?: emptyList()
    /** "Đã tải X bài · Y": bài đã lưu có file trên máy. */
    fun savedOnDevice(): Pair<Int, Long> {
        val kept = savedTracks().filter { it.link in downloaded }
        return kept.size to kept.sumOf { it.bytes }
    }
    fun missingBytes(tracks: List<MusicLibrary.Track>): Long = tracks.filter { it.link !in downloaded }.sumOf { it.bytes }
}

/**
 * Trạng thái màn Nhạc (Đã lưu + Kho nhạc) của điện thoại: lọc ngay trên máy (MusicLibrary.select - cả danh mục ~2.400 bài, vài ms),
 * lưu = ghim + tải (một luồng, lần lượt, huỷ được, đứt mạng thì giữ phần đã tải để "Tải tiếp"), nghe thử 30 giây.
 */
@Stable
class LibraryState(
    private val source: LibrarySource,
    private val scope: CoroutineScope,
    private val preview: PreviewPlayer,
    private val pauseBook: () -> Unit = {},
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {
    private val flow = MutableStateFlow(LibraryUi())
    val ui: StateFlow<LibraryUi> = flow

    private val queue = ArrayDeque<String>()
    private var worker: Job? = null
    @Volatile private var cancelling: String? = null
    @Volatile private var currentLink: String? = null
    private var previewJob: Job? = null
    private var opened = false

    fun open() {
        if (opened && flow.value.error.isEmpty()) return
        opened = true
        flow.update { it.copy(loading = true, error = "") }
        scope.launch {
            val result = withContext(io) {
                runCatching {
                    val index = source.load()
                    Triple(index, source.downloaded(index.tracks.map { it.link }), source.saved()) to source.online()
                }
            }
            result.onSuccess { (data, online) ->
                val (index, downloaded, saved) = data
                flow.update { it.copy(loading = false, index = index, downloaded = downloaded, saved = saved, online = online) }
                refilter()
            }.onFailure { error ->
                flow.update { it.copy(loading = false, error = error.message?.takeIf(String::isNotBlank) ?: S.s_chua_tai_duoc_kho_nhac_9577b7c7) }
            }
        }
    }

    fun setFilters(filters: MusicLibrary.Filters) {
        flow.update { it.copy(filters = filters) }
        refilter()
    }

    fun setQuery(query: String) = setFilters(flow.value.filters.copy(q = query))

    /** "Xem trong kho": Kho nhạc đã tìm sẵn `query` (bộ lọc khác bỏ đi). */
    fun showInLibrary(query: String) {
        setFilters(MusicLibrary.Filters(q = query))
        flow.update { it.copy(libraryRequest = it.libraryRequest + 1) }
    }

    fun clearFilters() = setFilters(MusicLibrary.Filters(q = flow.value.filters.q))

    private fun refilter() {
        val ui = flow.value
        val index = ui.index ?: return
        val started = System.nanoTime()
        val shown = MusicLibrary.select(index.tracks, ui.filters, index.playlistLinks, ui.downloaded)
        val ms = (System.nanoTime() - started) / 1e6
        flow.update { it.copy(shown = shown, filterMs = ms) }
    }

    // ---- Lưu / tải ----

    /** "Lưu" / "Tải về" / "Tải cả danh sách": ghim + tải. Mạng tính phí thì hỏi trước ([meteredAsk]) - trừ khi `confirmed`. */
    fun save(links: List<String>, confirmed: Boolean = false) {
        if (links.isEmpty()) return
        scope.launch {
            val metered = withContext(io) { runCatching { source.metered() }.getOrDefault(false) }
            val missing = links.filter { it !in flow.value.downloaded }
            if (metered && !confirmed && missing.isNotEmpty()) {
                flow.update { it.copy(meteredAsk = links) }
                return@launch
            }
            withContext(io) { source.save(links) }
            flow.update { ui -> ui.copy(saved = (ui.saved - links.toSet()) + links, meteredAsk = emptyList()) }
            enqueue(missing)
        }
    }

    /** Hộp hỏi dữ liệu di động: "Để sau" - không lưu gì. */
    fun dismissMetered() = flow.update { it.copy(meteredAsk = emptyList()) }

    /** "Bỏ lưu": huỷ tải, gỡ ghim, xoá bản tải. */
    fun unsave(links: List<String>) {
        cancel(links)
        scope.launch {
            withContext(io) { source.unsave(links) }
            flow.update { ui -> ui.copy(saved = ui.saved - links.toSet(), downloaded = ui.downloaded - links.toSet()) }
            if (flow.value.filters.downloaded) refilter()
        }
    }

    /** "Xoá bản tải" (bài vẫn ở kho, không còn ghim). */
    fun forget(link: String) = unsave(listOf(link))

    /** "Huỷ tải": bài đang chờ ra khỏi hàng; bài đang tải dừng ở lần đọc kế (phần đã tải giữ lại - "Tải tiếp"). */
    fun cancel(links: List<String>) {
        val gone = links.toSet()
        synchronized(queue) { queue.removeAll(gone) }
        val current = currentLink
        if (current != null && current in gone) cancelling = current
        flow.update { ui -> ui.copy(active = ui.active.filterKeys { it !in gone || it == current }, failed = ui.failed - gone) }
    }

    private fun enqueue(links: List<String>) {
        synchronized(queue) { for (link in links) if (link !in queue && link != currentLink) queue.addLast(link) }
        flow.update { ui -> ui.copy(active = ui.active + links.filter { it !in ui.active }.associateWith { Loading(0, null) }, failed = ui.failed - links.toSet()) }
        if (worker?.isActive == true) return
        worker = scope.launch {
            while (true) {
                val link = synchronized(queue) { queue.removeFirstOrNull() } ?: break
                currentLink = link
                cancelling = null
                var last = 0L
                val outcome = withContext(io) {
                    runCatching {
                        source.download(link, { done, total ->
                            val now = System.nanoTime()
                            if (now - last > 150_000_000L) {
                                last = now
                                flow.update { ui -> ui.copy(active = ui.active + (link to Loading(done, total))) }
                            }
                        }) { cancelling == link }
                    }
                }
                val wasCancelled = cancelling == link
                currentLink = null
                cancelling = null
                flow.update { ui ->
                    when {
                        outcome.isSuccess -> ui.copy(active = ui.active - link, downloaded = ui.downloaded + link)
                        wasCancelled -> ui.copy(active = ui.active - link)
                        else -> ui.copy(active = ui.active - link, failed = ui.failed + (link to (outcome.exceptionOrNull()?.message ?: S.s_chua_tai_xong_b257419d)))
                    }
                }
            }
        }
    }

    // ---- Nghe thử ----

    /** Nghe thử: từ `audibleStart`, tối đa [PREVIEW_SECONDS] giây, mức to chuẩn; dừng sách đang đọc; một bài một lúc. Mất mạng: chỉ bài đã tải. */
    fun togglePreview(link: String) {
        if (flow.value.previewing == link) return stopPreview()
        val ui = flow.value
        val track = ui.index?.byLink?.get(link) ?: return
        if (!ui.online && link !in ui.downloaded) return
        stopPreview()
        pauseBook()
        flow.update { it.copy(previewing = link) }
        preview.play(link, track.audibleStart, previewVolume(track.lufs)) { if (flow.value.previewing == link) stopPreview() }
        previewJob = scope.launch {
            delay(PREVIEW_SECONDS * 1000L)
            if (flow.value.previewing == link) stopPreview()
        }
    }

    fun stopPreview() {
        previewJob?.cancel()
        previewJob = null
        if (flow.value.previewing != null) {
            preview.stop()
            flow.update { it.copy(previewing = null) }
        }
    }

    fun setOnline(online: Boolean) = flow.update { it.copy(online = online) }

    companion object {
        const val PREVIEW_SECONDS = 30
        const val PREVIEW_LUFS = -18.0

        /** Như `previewVolume` của web: bài to hơn mức chuẩn thì giảm, không khuếch đại quá 1. */
        fun previewVolume(lufs: Double?): Float {
            if (lufs == null) return 1f
            val gain = Math.pow(10.0, (PREVIEW_LUFS - lufs) / 20.0)
            return gain.coerceIn(0.05, 1.0).toFloat()
        }
    }
}
