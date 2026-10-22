package vn.abook.player

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud
import java.io.File

/**
 * Giây (giao diện, vị trí đã lưu) -> ms: LÀM TRÒN, không cắt - 1,001 giây nhân 1000 ra 1000,999… và cắt thành 1000, rơi về ms cuối đoạn TRƯỚC khi mốc đầu câu đúng
 * là 1001 (soát a59p: 0,66 % mốc đầu câu). Âm thành 0.
 */
internal fun msOf(seconds: Double): Long = Math.round(seconds * 1000).coerceAtLeast(0)

/**
 * Lõi phát - sống trong tiến trình app, dùng chung giữa PlaybackService (thông báo, màn hình khoá, nút tai nghe)
 * và PlayerPlugin (giao diện). Mọi thao tác trên ExoPlayer chạy ở luồng chính.
 *
 * Vì sao hàng đợi, lưu vị trí, hẹn giờ đều ở ĐÂY chứ không ở JavaScript: tắt màn hình thì WebView bị treo, nên
 * tự sang chương kế hay tắt nhạc lúc ngủ mà nằm trong JS thì sẽ không bao giờ chạy.
 */
/** Artist line of the media card: the narrator, or the book title when there is none ("Nghe ngay", a book without a narrator). The system
 *  speaks the card as "<chapter> by <artist> is playing from ABook" - a null artist came out as "by null" (a67). */
fun mediaArtist(narratorName: String, bookTitle: String): String? = narratorName.ifBlank { bookTitle }.ifBlank { null }

/** Giữ URI, tag và cấu hình phát của mục; chỉ thay nhãn của thẻ media. */
internal fun withBookMetadata(item: MediaItem, title: String, narrator: String, chapter: String, artwork: ByteArray): MediaItem =
    item.buildUpon().setMediaMetadata(item.mediaMetadata.buildUpon()
        .setTitle(chapter).setDisplayTitle(chapter).setAlbumTitle(title).setSubtitle(title)
        .setArtist(mediaArtist(narrator, title)).setArtworkData(artwork, MediaMetadata.PICTURE_TYPE_FRONT_COVER).build()).build()

/** Cả hàng đợi mang nhãn mới (tên chương lấy theo mã mục, mục không có trong `titles` giữ tên cũ) - để thay MỘT lần. */
internal fun relabelled(items: List<MediaItem>, title: String, narrator: String, titles: Map<Int, String>, artwork: ByteArray): List<MediaItem> =
    items.map { item -> withBookMetadata(item, title, narrator, titles[item.mediaId.toIntOrNull()] ?: item.mediaMetadata.title?.toString().orEmpty(), artwork) }

/** Thẻ media có gì khác không: tên sách, giọng kể, tên chương hay bìa (`shownArtwork` = bìa mục đang có, null khi hàng đợi rỗng). */
internal fun labelsChanged(title: String, narrator: String, chapters: List<Playback.Chapter>,
                           newTitle: String, newNarrator: String, renamed: List<Playback.Chapter>,
                           shownArtwork: ByteArray?, artwork: ByteArray): Boolean =
    title != newTitle || narrator != newNarrator || chapters != renamed || (shownArtwork != null && !shownArtwork.contentEquals(artwork))

internal fun refreshedChapters(old: List<Playback.Chapter>, fresh: List<Playback.Chapter>, currentId: Int?): List<Playback.Chapter> {
    val current = old.firstOrNull { it.id == currentId }
    val result = fresh.map { if (it.id == currentId && current != null) current.copy(title = it.title) else it }.toMutableList()
    if (current != null && result.none { it.id == current.id }) result.add(old.indexOf(current).coerceAtMost(result.size), current)
    return result
}

object Playback {
    /** Thêm chương vừa có audio; mục đang nghe giữ nguyên nguồn và vị trí. */
    @androidx.annotation.OptIn(UnstableApi::class)
    fun refreshQueue(id: String, fresh: List<Chapter>) {
        if (id != bookId || fresh.isEmpty()) return
        val current = currentChapter
        val updated = refreshedChapters(chapters, fresh, current?.id).let { items ->
            if (ReadAloud.active) items + chapters.filter { old -> items.none { it.id == old.id } } else items
        }
        if (updated == chapters) return
        val old = chapters
        if (ReadAloud.active) {
            ReadAloud.remapChapters(old, updated)
            chapters = updated
            return
        }
        val exo = player
        chapters = updated
        if (exo != null && current != null && exo.currentMediaItem != null) {
            val items = mediaItems(id, bookTitle, narrator, updated)
            val index = updated.indexOfFirst { it.id == current.id }
            // Thay hai phía của mục đang phát, không nạp/tua lại mục ấy.
            exo.replaceMediaItems(exo.currentMediaItemIndex + 1, exo.mediaItemCount, items.drop(index + 1))
            exo.replaceMediaItems(0, exo.currentMediaItemIndex, items.take(index))
        }
        emit("metadata")
    }

    /** Sửa sách đang nghe: thay metadata của cả hàng đợi, không nạp lại tiếng hay tua. Giao diện gửi nhãn mỗi khi dữ liệu sách đổi,
     *  nên không có gì khác thì thôi - thay hàng đợi 2.500 chương là dựng lại timeline và MediaSession đẩy lại cả hàng đợi trên luồng chính. */
    @androidx.annotation.OptIn(UnstableApi::class)
    fun updateMetadata(id: String, title: String, narratorName: String, titles: Map<Int, String>) {
        if (bookId != id) return
        val renamed = chapters.map { chapter -> titles[chapter.id]?.let { chapter.copy(title = it) } ?: chapter }
        val artwork = Artwork.cover(title, id)
        val exo = player
        val shown = exo?.takeIf { it.mediaItemCount > 0 }?.getMediaItemAt(0)?.mediaMetadata?.artworkData
        // Trước khi thôi: hàng đọc to rỗng (đang tìm đoạn đầu) thì không có bìa nào để so - đổi bìa lúc ấy vẫn phải tới các đoạn dựng sau.
        ReadAloud.refreshArtwork(artwork)
        if (!labelsChanged(bookTitle, narrator, chapters, title, narratorName, renamed, shown, artwork)) return
        bookTitle = title
        narrator = narratorName
        chapters = renamed
        if (exo != null && exo.mediaItemCount > 0) {
            val items = (0 until exo.mediaItemCount).map(exo::getMediaItemAt)
            exo.replaceMediaItems(0, items.size, relabelled(items, title, narratorName, titles, artwork))
        }
        emit("metadata")
    }

    /** `text` = tên mục chữ trong gói (`texts/<n>.txt`) của chương CHỈ CÓ CHỮ (state "text"): không có file audio, giọng máy đọc to (ReadAloud). */
    data class Chapter(val id: Int, val title: String, val file: String, val duration: Double, val text: String = "") {
        val isText: Boolean get() = text.isNotEmpty()
    }

    private val main = Handler(Looper.getMainLooper())
    var player: ExoPlayer? = null
        internal set
    lateinit var appContext: Context
        private set
    /** Nút Trước/Sau từ ngoài app (tai nghe, đồng hồ, xe hơi) = lùi/tới 15 giây thay vì nhảy chương (Cài đặt). */
    var headsetSkips = true

    var bookId: String = ""
        private set
    /**
     * Hồ sơ nghe mà phiên phát này ghi vào - chốt lúc nạp cuốn (load / onQueueReplaced), không bao giờ lấy "hồ sơ đang dùng" lúc ghi: máy
     * khác xoá hay đổi hồ sơ giữa chừng thì lần lưu kế vẫn về đúng hồ sơ ấy, hoặc bị bỏ nếu hồ sơ đã mất ([recordsGone]). Rỗng: chưa nạp cuốn nào.
     */
    @Volatile
    var recordId: String = ""
        private set
    var bookTitle: String = ""
        private set
    var narrator: String = ""
        private set
    var chapters: List<Chapter> = emptyList()
        private set
    private var pausedAtMs = 0L
    /** Đang phát - đọc được từ luồng khác (đồng bộ); ExoPlayer chỉ được hỏi trên luồng chính. */
    @Volatile
    var isPlaying = false
        private set
    /** Chỗ lần gần nhất đã lưu (hay vừa nạp từ chỗ đã lưu): (chương, mili giây). Đổi hồ sơ mà trình phát chưa nhúc nhích
     *  từ đó thì khỏi lưu lại - lưu lại là đóng dấu giờ mới lên chỗ CŨ, đè chỗ mới hơn mà máy khác vừa đồng bộ tới. */
    private var savedPlace: Pair<Int, Long>? = null
    /** Cuốn trình điều khiển bên ngoài vừa chọn (`adopt`), chờ ExoPlayer nhận hàng đợi của nó (`onQueueReplaced`). */
    private var pending: Pending? = null

    private class Pending(val id: String, val title: String, val narrator: String, val items: List<Chapter>,
                          val place: Pair<Int, Long>, val rate: Double)
    /** "Tự lùi khi nghe lại" (Cài đặt); how far: [AutoRewind]. */
    private var autoRewind = true
    private val listeners = mutableSetOf<(JSONObject) -> Unit>()
    private var ticking = false
    /** Lần cuối người nghe chạm vào trình phát (nút, thông báo, widget) - cho lưới an toàn ngủ quên. */
    var lastInteractionMs = System.currentTimeMillis()
        private set
    var lastInteractionChapter: Int? = null
        private set
    var lastInteractionSeconds = 0.0
        private set

    // Phiên nghe: mở lúc bắt đầu phát, đóng lúc dừng; dưới 20 giây nghe thật thì bỏ (bấm phát rồi dừng ngay).
    private var sessionStartMs = 0L
    private var sessionListenedMs = 0L
    private var sessionMarkMs = 0L
    private var sessionFrom: JSONObject? = null
    private var sessionBook = ""
    private var sessionRecord = ""

    private fun place(): JSONObject = JSONObject().put("chapterId", currentChapter?.id ?: 0).put("seconds", positionSeconds)

    private fun openSession() {
        val now = System.currentTimeMillis()
        if (sessionFrom != null && sessionBook == bookId) {
            sessionMarkMs = now
            return
        }
        sessionStartMs = now
        sessionListenedMs = 0
        sessionMarkMs = now
        sessionFrom = place()
        sessionBook = bookId
        sessionRecord = recordId
    }

    private fun closeSession() {
        val from = sessionFrom ?: return
        val now = System.currentTimeMillis()
        sessionListenedMs += now - sessionMarkMs
        sessionFrom = null
        if (sessionListenedMs < 20_000 || sessionBook.isEmpty() || sessionBook != bookId) return
        val session = JSONObject()
            .put("id", java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 12))
            .put("device", "phone")
            .put("startedAt", sessionStartMs / 1000.0)
            .put("endedAt", now / 1000.0)
            .put("listened", sessionListenedMs / 1000.0)
            .put("from", from)
            .put("to", place())
        runCatching { Store.addSession(sessionBook, session, sessionRecord.ifEmpty { null }) }
    }

    fun touched() {
        lastInteractionMs = System.currentTimeMillis()
        lastInteractionChapter = currentChapter?.id
        lastInteractionSeconds = positionSeconds
    }

    fun init(context: Context) {
        appContext = context.applicationContext
        Store.init(appContext)
        Remote.init(appContext)
        MusicBed.init(appContext)
        ReadAloud.init(appContext)
        ListenPrefs.loadOnce() // tuỳ chọn nghe + hẹn giờ ngủ còn dở: tiến trình dậy từ tai nghe / widget / xe chưa có WebView đẩy chúng xuống
    }

    fun onMain(block: () -> Unit) {
        if (Looper.myLooper() == Looper.getMainLooper()) block() else main.post(block)
    }

    fun addListener(listener: (JSONObject) -> Unit) { listeners += listener }
    fun removeListener(listener: (JSONObject) -> Unit) { listeners -= listener }

    fun emit(kind: String) {
        if (kind == "sleep") ReadAloud.pump() // hẹn giờ "hết chương" vừa tắt / đổi: đọc to nạp tiếp sang chương kế được rồi
        val event = state().put("kind", kind)
        listeners.toList().forEach { runCatching { it(event) } }
        if (::appContext.isInitialized) runCatching { PlayerWidget.refresh(appContext, tick = kind == "tick") }
        // Máy tính đang xem điện thoại phát gì (Remote): mọi đổi trừ nhịp đồng hồ đều báo ngay.
        if (kind != "tick") Remote.kick()
    }

    /** Cuốn nghe gần nhất trên máy (kể cả sách nghe thẳng từ máy tính): (gói sách, mốc "last") - cho widget và cho tiếp
     *  tục phát sau khi khởi động lại. */
    fun lastListened(): Pair<JSONObject, JSONObject>? =
        Store.playableBooks().mapNotNull { manifest ->
            val last = Store.state(manifest.getString("id")).optJSONObject("last") ?: return@mapNotNull null
            manifest to last
        }.maxByOrNull { it.second.optDouble("at") }

    fun chaptersOf(manifest: JSONObject): List<Chapter> = LibraryTree.chapters(manifest)

    /** Nạp lại cuốn nghe gần nhất đúng chỗ đang dở rồi phát (bấm phát trên widget khi app không chạy). */
    fun resumeLast(): Boolean {
        val (manifest, last) = lastListened() ?: return false
        val id = manifest.getString("id")
        val items = chaptersOf(manifest)
        if (items.isEmpty()) return false
        val rate = Store.state(id).optDouble("rate", 1.0)
        load(id, manifest.optString("title"), manifest.optString("narrator"), items, last.optInt("chapterId"), last.optDouble("seconds"), rate)
        return true
    }

    /** Cuốn của một mục audio trong hàng đợi ([mediaItems]): mục còn lại của cuốn trước không bao giờ được đọc thành chỗ nghe của cuốn đang nạp (soát a68 lỗi 2). */
    data class BookTag(val id: String)

    /** Mục ExoPlayer đang đứng là của cuốn khác cuốn đang nạp (hàng đợi chưa kịp thay). Mục không gắn cuốn (xe hơi đặt hàng đợi - [adopt]) thì coi là của cuốn này. */
    private fun foreignItem(): Boolean = (player?.currentMediaItem?.localConfiguration?.tag as? BookTag)?.let { it.id != bookId } == true

    val currentChapter: Chapter?
        get() = ((if (foreignItem()) null else player?.currentMediaItem?.mediaId?.toIntOrNull()) ?: ReadAloud.waitingChapterId())
            ?.let { id -> chapters.firstOrNull { it.id == id } }

    /** Vị trí trong chương (ms). Chương đọc to: đồng hồ ảo của cả chương (mốc đầu đoạn + vị trí trong đoạn), không phải vị trí trong đoạn âm thanh. */
    val positionMs: Long
        get() = ReadAloud.positionMs() ?: (if (foreignItem()) 0L else player?.currentPosition ?: 0L)

    val positionSeconds: Double
        get() = positionMs / 1000.0

    /** Độ dài chương (ms) mà ExoPlayer biết; chương đọc to: độ dài ảo; 0 nếu chưa biết. */
    private fun durationMs(): Long = ReadAloud.durationMs() ?: player?.duration?.takeIf { it > 0 && !foreignItem() } ?: 0L

    fun state(): JSONObject {
        val chapter = currentChapter
        val exo = player
        return JSONObject()
            .put("bookId", bookId)
            .put("bookTitle", bookTitle)
            .put("chapterId", chapter?.id ?: JSONObject.NULL)
            .put("chapterTitle", chapter?.title ?: "")
            .put("position", positionSeconds)
            // Độ dài không bao giờ ngắn hơn chỗ đang nghe: ExoPlayer chưa đo xong thì là độ dài ghi trong gói, có thể hụt vài giây (soát a68 lỗi 17: "0:08 / 0:07").
            .put("duration", maxOf(durationMs().takeIf { it > 0 }?.div(1000.0) ?: chapter?.duration ?: 0.0, positionSeconds))
            .put("playing", exo?.isPlaying == true || (ReadAloud.isWaiting && ReadAloud.wantsPlay()) || ReadAloud.starved())
            .put("buffering", exo?.playbackState == Player.STATE_BUFFERING || ReadAloud.isWaiting || ReadAloud.starved())
            .put("rate", exo?.playbackParameters?.speed?.toDouble() ?: 1.0)
            .put("sleep", SleepTimer.describe())
            .put("error", lastError)
            .put("saveError", if (saveFailing) SAVE_FAILED else "")
            .put("musicCredit", MusicBed.credit() ?: JSONObject.NULL)
            .put("musicBroken", MusicBed.brokenHere())
            .put("musicOffline", MusicBed.offlineNotice())
            .put("musicScene", MusicBed.sceneActive())
    }

    /** Lỗi phát gần nhất, cho giao diện - rỗng khi đang ổn. */
    var lastError: String = ""
        private set

    /** ExoPlayer dừng vì lỗi: chương phát qua mạng thì gần như chắc là mất kết nối với máy tính - nói đúng lý do. */
    fun onError(error: Throwable? = null) {
        // Đoạn đọc to hỏng (file bị Android dọn khỏi bộ nhớ đệm...): đọc lại đúng chỗ, tối đa vài lần liền.
        if (ReadAloud.recoverFromPlayerError()) return
        val streamed = player?.currentMediaItem?.localConfiguration?.uri?.scheme == "https"
        val retrying = reconnectDelayMs > 0
        lastError = if (streamed && error != null && Pin.isCertificateProblem(error)) {
            Pin.CHANGED // máy tính đã đổi chứng chỉ: không phải Wi-Fi hỏng, người nghe phải ghép lại
        } else if (streamed && error != null && NetErrors.unpaired(error)) {
            "${SyncLink.holderName(appContext, bookId).replaceFirstChar { it.uppercase() }} đã thôi ghép với điện thoại này - ghép lại để nghe tiếp"
        } else if (streamed) {
            // Phần đã đệm đã phát hết: không bỏ cuộc - hỏi lại thưa dần, máy kia trả lời là phát tiếp đúng chỗ (soát a68 lỗi 3).
            scheduleReconnect()
            "Mất kết nối với ${SyncLink.holderName(appContext, bookId)} - đang thử lại…"
        } else {
            "Không phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại."
        }
        saveNow()
        // Lần thử lại hỏng nữa: chỉ cập nhật lời đang hiện, không báo lần nữa.
        emit(if (retrying && lastError.startsWith("Mất kết nối")) "state" else "error")
    }

    /** Chờ trước lần nối lại kế (0 = không đang nối lại): 3 giây rồi gấp đôi, tối đa 30 giây. */
    private var reconnectDelayMs = 0L
    private val reconnect = Runnable { tryReconnect() }

    private fun scheduleReconnect() {
        reconnectDelayMs = if (reconnectDelayMs == 0L) 3_000L else (reconnectDelayMs * 2).coerceAtMost(30_000L)
        main.removeCallbacks(reconnect)
        main.postDelayed(reconnect, reconnectDelayMs)
    }

    /** Thử nối lại chương nghe thẳng vừa hỏng. Người nghe đã bấm dừng thì thôi (bấm phát là tự chuẩn bị lại - [play]); hỏng nữa thì [onError] hẹn lần sau. */
    private fun tryReconnect() {
        val exo = player ?: return
        if (exo.playbackState != Player.STATE_IDLE || exo.playerError == null || !exo.playWhenReady) {
            reconnectDelayMs = 0L
            return
        }
        exo.prepare()
    }

    /** ExoPlayer sẵn sàng phát (PlaybackService): vừa nối lại được sau khi mất kết nối thì gỡ lời báo. */
    fun onReady() {
        if (reconnectDelayMs == 0L) return
        reconnectDelayMs = 0L
        main.removeCallbacks(reconnect)
        if (lastError.startsWith("Mất kết nối")) lastError = ""
    }

    /**
     * Giọng đọc không đọc nổi một đoạn (cả giọng mạng lẫn giọng máy): dừng, nói thẳng lý do cho người nghe; bấm phát thử lại (ReadAloud.retryAfterFailure). `notify` false: chỗ này đã báo rồi
     * (máy tự hỏi lại mà hỏng nữa - ReadAloud, [vn.abook.player.readaloud.FailureNotice]) - chỉ cập nhật lời báo đang có, không báo lần nữa.
     */
    fun fail(message: String, notify: Boolean = true) {
        lastError = message
        player?.pause()
        saveNow()
        emit(if (notify) "error" else "state")
    }

    fun clearError() {
        lastError = ""
    }

    /** Hệ số mờ dần của hẹn giờ ngủ (1 = không mờ); âm lượng thật của giọng = mờ dần × độ to cố định của giọng đọc to; nhạc nền nhân cùng hệ số mờ ([MusicBed.setSleepFade]). */
    var fadeLevel = 1f
        private set

    fun applyVolume(fade: Float = fadeLevel) {
        fadeLevel = fade
        player?.volume = fade * ReadAloud.gainFactor()
        MusicBed.setSleepFade(fade) // nhạc nền nhỏ dần cùng giọng; trả 1 (huỷ / gia hạn / hết giờ) thì nhạc về mức cũ
    }

    /** Hẹn giờ "hết chương": ExoPlayer dừng ở cuối mục. Chương đọc to gồm nhiều mục (mỗi đoạn một mục) nên không dùng được - ReadAloud tự dừng nạp ở cuối chương. */
    fun holdAtItemEnd(on: Boolean) {
        if (on && ReadAloud.inText()) ReadAloud.stopAtChapterEnd()
        player?.pauseAtEndOfMediaItems = on && !ReadAloud.inText()
    }

    /** Thời gian nghe thực còn lại của chương (ms); chương đọc to tính từ đồng hồ ảo, rồi chia tốc độ phát. */
    fun remainingInChapterMs(): Long = ChapterSleepTime.remainingMs(durationMs(), positionMs,
        player?.playbackParameters?.speed?.toDouble() ?: 1.0)

    /** Hàng đợi của một cuốn: chương có file trên máy phát file, chưa có thì phát thẳng từ máy tính (Streaming). */
    @androidx.annotation.OptIn(UnstableApi::class)
    fun mediaItems(id: String, title: String, narratorName: String, items: List<Chapter>): List<MediaItem> {
        val artwork = Artwork.cover(title, id)
        return items.map { chapter ->
            MediaItem.Builder()
                .setMediaId(chapter.id.toString())
                .setTag(BookTag(id))
                .setUri(Streaming.chapterUri(appContext, id, chapter.file))
                .setCustomCacheKey(Streaming.cacheKey(id, chapter.file))
                .setMediaMetadata(
                    MediaMetadata.Builder()
                        .setTitle(chapter.title)
                        .setArtist(mediaArtist(narratorName, title))
                        .setAlbumTitle(title)
                        .setDisplayTitle(chapter.title)
                        .setSubtitle(title)
                        .setArtworkData(artwork, MediaMetadata.PICTURE_TYPE_FRONT_COVER)
                        .build(),
                )
                .build()
        }
    }

    /** Nạp một cuốn: cả danh sách chương vào hàng đợi, bắt đầu ở chương/giây đã chọn. */
    fun load(id: String, title: String, narratorName: String, items: List<Chapter>, startChapterId: Int, startSeconds: Double, rate: Double, autoplay: Boolean = true) {
        val exo = player ?: return
        pending = null
        saveNow()
        lastError = ""
        main.removeCallbacks(reconnect) // cuốn khác: thôi nối lại cuốn cũ
        reconnectDelayMs = 0L
        // Giọng "Nghe ngay" của cuốn này, nhớ trong lõi: phát tiếp từ widget / xe hơi sau khi khởi động lại vẫn đúng giọng người nghe đã chọn.
        val record = Store.activeRecord(id)
        ReadAloud.useVoiceOf(id, record)
        bookId = id
        recordId = record
        bookTitle = title
        narrator = narratorName
        chapters = items
        val index = items.indexOfFirst { it.id == startChapterId }.coerceAtLeast(0)
        if (items.any { it.isText }) {
            // Sách có chương chỉ-có-chữ: ReadAloud đọc đoạn nào đặt đoạn ấy vào hàng đợi (giọng Edge cần mạng, nên giữ Wi-Fi thức khi tắt màn hình).
            exo.setWakeMode(C.WAKE_MODE_NETWORK)
            savedPlace = items.getOrNull(index)?.let { it.id to msOf(startSeconds) }
            applySpeed(exo, rate)
            ReadAloud.begin(index, msOf(startSeconds), autoplay)
            if (autoplay) startTicking()
            emit("load")
            return
        }
        ReadAloud.stop()
        applyVolume()
        val media = mediaItems(id, title, narratorName, items)
        // Có chương phát qua mạng thì giữ Wi-Fi thức khi tắt màn hình; sách đã tải hết thì không tốn pin cho việc ấy.
        exo.setWakeMode(if (media.any { it.localConfiguration?.uri?.scheme == "https" }) C.WAKE_MODE_NETWORK else C.WAKE_MODE_LOCAL)
        // Chỗ vừa nạp ghi TRƯỚC khi đặt hàng đợi: sự kiện tua của ExoPlayer ([onSeekSettled]) đến ngay trong lời gọi, thấy chỗ cũ của cuốn trước thì sẽ lưu chỗ vừa nạp như người nghe vừa tua.
        savedPlace = items.getOrNull(index)?.let { it.id to msOf(startSeconds) }
        exo.setMediaItems(media, index, msOf(startSeconds))
        applySpeed(exo, rate)
        exo.prepare()
        // Mở lại app: nạp sẵn đúng chỗ đang nghe dở ở trạng thái dừng, người nghe bấm phát khi sẵn sàng.
        if (autoplay) {
            exo.play()
            startTicking()
        }
        emit("load")
    }

    /**
     * Trình điều khiển bên ngoài (Android Auto, trình duyệt media của hệ thống) chọn một cuốn trong cây duyệt
     * (PlaybackService.onSetMediaItems): phiên media tự đặt hàng đợi lên ExoPlayer ngay sau đó. Ở đây lưu chỗ của cuốn
     * đang nạp rồi thôi nhận chỗ nghe cho tới khi hàng đợi mới vào ExoPlayer (`onQueueReplaced`) - nhịp lưu 5 giây rơi
     * vào khoảng giữa mà đã đổi `bookId` thì sẽ ghi chỗ của cuốn cũ vào cuốn mới.
     */
    fun adopt(id: String, title: String, narratorName: String, items: List<Chapter>, startChapterId: Int, startSeconds: Double, rate: Double) {
        saveNow()
        closeSession()
        ReadAloud.stop()
        bookId = ""
        recordId = ""
        pending = Pending(id, title, narratorName, items, startChapterId to msOf(startSeconds), rate)
    }

    /** ExoPlayer vừa nhận một hàng đợi mới (onTimelineChanged, PLAYLIST_CHANGED): là cuốn `adopt` đang chờ thì nhận
     *  nó như `load` làm - tốc độ, giữ Wi-Fi thức khi nghe thẳng, phiên nghe, lưu chỗ. */
    fun onQueueReplaced() {
        val next = pending ?: return
        pending = null
        val exo = player ?: return
        lastError = ""
        bookId = next.id
        recordId = Store.activeRecord(next.id)
        ReadAloud.useVoiceOf(next.id, recordId)
        bookTitle = next.title
        narrator = next.narrator
        chapters = next.items
        val streamed = next.items.any { Streaming.chapterUri(appContext, next.id, it.file).scheme == "https" }
        exo.setWakeMode(if (streamed) C.WAKE_MODE_NETWORK else C.WAKE_MODE_LOCAL)
        applySpeed(exo, next.rate)
        savedPlace = next.place
        if (exo.isPlaying) {
            openSession()
            startTicking()
        }
        emit("load")
    }

    fun play() {
        val exo = player ?: return
        // Đọc to: sau lỗi đọc thì thử lại đúng đoạn hỏng; đã chạy hết hàng đợi thì đọc lại từ chỗ đang đứng; đang chờ đọc đoạn thì ghi nhớ là người nghe muốn phát.
        if (ReadAloud.onPlay()) {
            Bedtime.interaction("play")
            return
        }
        val back = if (autoRewind && pausedAtMs > 0) AutoRewind.seconds(System.currentTimeMillis() - pausedAtMs) else 0.0
        if (back > 0) seekToMs((positionMs - (back * 1000).toLong()).coerceAtLeast(0))
        // Sau một lỗi (mất mạng khi nghe thẳng) ExoPlayer nằm ở IDLE: phải chuẩn bị lại thì mới phát tiếp đúng chỗ.
        if (exo.playbackState == Player.STATE_IDLE) {
            lastError = ""
            main.removeCallbacks(reconnect)
            reconnectDelayMs = 0L
            exo.prepare()
        }
        exo.play()
        Bedtime.interaction("play")
    }

    fun pause() {
        ReadAloud.onPause()
        player?.pause()
        Bedtime.interaction("pause")
    }

    fun toggle() = if (player?.isPlaying == true || (ReadAloud.isWaiting && ReadAloud.wantsPlay())) pause() else play()

    /** Tua tới `ms` trong chương: chương đọc to tua theo đồng hồ ảo (đúng chỗ trong đoạn), chương audio tua ExoPlayer. */
    private fun seekToMs(ms: Long, segment: Int = -1, word: Int = -1) {
        if (!ReadAloud.seekMs(ms, segment, word)) player?.seekTo(ms)
    }

    /**
     * Tua trong chương. Chương đọc to có thêm cách chỉ chỗ KHÔNG qua giây: `segment` (thứ tự đoạn, như `index` của `ReadAloud.script`) và `word` (thứ tự chữ trong
     * đoạn) - đoạn chưa đọc thì đọc xong rồi phát đúng từ chữ ấy; hai tham số này thắng `seconds`.
     */
    fun seekTo(seconds: Double, segment: Int = -1, word: Int = -1) {
        touched()
        seekToMs(msOf(seconds), segment, word)
        saveIfParked()
        Bedtime.interaction("seek")
        emit("seek")
    }

    fun skip(deltaSeconds: Double) = seekTo(positionSeconds + deltaSeconds)

    fun jumpTo(chapterId: Int, seconds: Double, segment: Int = -1, word: Int = -1) {
        touched()
        val exo = player ?: return
        val index = chapters.indexOfFirst { it.id == chapterId }
        if (index < 0) return
        saveNow()
        if (ReadAloud.active) {
            ReadAloud.jump(index, msOf(seconds), segment, word)
        } else {
            exo.seekTo(index, msOf(seconds))
            exo.play()
        }
        saveIfParked()
        Bedtime.interaction("chapter")
        emit("chapter")
    }

    fun next() {
        val exo = player ?: return
        if (ReadAloud.active) {
            // Hàng đợi có mục mỗi đoạn: "chương sau" là theo danh sách chương, không phải mục kế của ExoPlayer.
            val index = chapters.indexOfFirst { it.id == currentChapter?.id }
            if (index >= 0 && index + 1 < chapters.size) {
                saveNow()
                ReadAloud.jump(index + 1, 0)
                saveIfParked()
                Bedtime.interaction("next")
            }
            return
        }
        if (exo.hasNextMediaItem()) {
            saveNow()
            exo.seekToNextMediaItem()
            saveIfParked()
            Bedtime.interaction("next")
        }
    }

    fun previous() {
        val exo = player ?: return
        saveNow()
        if (ReadAloud.active) {
            val index = chapters.indexOfFirst { it.id == currentChapter?.id }
            if (positionMs > 5000 || index <= 0) seekToMs(0) else ReadAloud.jump(index - 1, 0)
            saveIfParked()
            Bedtime.interaction("previous")
            return
        }
        if (exo.currentPosition > 5000 || !exo.hasPreviousMediaItem()) exo.seekTo(0) else exo.seekToPreviousMediaItem()
        saveIfParked()
        Bedtime.interaction("previous")
    }

    fun setRate(rate: Double) {
        touched()
        player?.let { applySpeed(it, rate) }
        if (bookId.isNotEmpty()) Store.setRate(bookId, rate, recordId.ifEmpty { null })
        emit("rate")
    }

    /** [index] + [quote]: the sentence being read aloud (the web layer knows it from the chapter's timings), like a mark set in the reader. */
    fun addBookmark(note: String, index: Int? = null, quote: String = ""): JSONObject? {
        val chapter = currentChapter ?: return null
        val mark = Store.addBookmark(bookId, chapter.id, positionSeconds, note, index, quote, recordId = recordId.ifEmpty { null })
        Bedtime.interaction("bookmark")
        emit("bookmark")
        pushHeld(force = true)
        return mark
    }

    /** `rewind` null: lần `configure` này không mang `autoRewind` (đổi giọng...) - giữ nguyên lựa chọn đang có (soát a77 #7). */
    fun configure(rewind: Boolean?) {
        if (rewind != null) autoRewind = rewind
    }

    // ---- sự kiện từ ExoPlayer ------------------------------------------------------------------------------

    fun onPlayingChanged(playing: Boolean) {
        isPlaying = playing
        // Phát/dừng hầu như luôn do người nghe bấm (app, thông báo, tai nghe, widget): tính là còn thức.
        touched()
        SleepTimer.onPlaying(playing)
        Motion.refresh()
        Remote.onPlaying(playing)
        syncMusic(playing)
        if (!playing) {
            pausedAtMs = System.currentTimeMillis()
            saveNow()
            pushHeld(force = true)
            closeSession()
        } else {
            openSession()
            pausedAtMs = 0
            startTicking()
            SleepTimer.maybeSchedule()
        }
        emit(if (playing) "play" else "pause")
    }

    /** Báo nhạc nền giọng đang chạy hay không. Đọc to mà hàng đợi cạn (Edge chậm, đang chờ đoạn kế - [ReadAloud.starved]) thì người nghe vẫn đang nghe: nhạc theo cảnh không ngắt rồi phải
     *  vào lại ở từng khe im (trước đây `isPlaying` rơi về false ngay khi ExoPlayer ENDED nên nhạc dừng cùng giọng). Người nghe bấm dừng thì `starved` tắt ngay. */
    private fun syncMusic(playing: Boolean) {
        val voiceOn = playing || ReadAloud.starved()
        // Giọng dừng vì người nghe (nút, rút tai nghe, mất focus, cuộc gọi: playWhenReady = false) thì nhạc dừng ngay; giọng chỉ đang đệm / chờ đoạn kế (playWhenReady vẫn true) là khe nối - nhạc chờ.
        MusicBed.sync(bookId, currentChapter?.id, positionSeconds, voiceOn, stopNow = !voiceOn && player?.playWhenReady != true)
    }

    private const val STALL_LOG_MS = 3_000L
    private var stalledSince = 0L

    /** Đọc to: giọng đứng chờ đoạn kế từ [STALL_LOG_MS] trở lên thì ghi logcat lúc có tiếng lại (soát a69: một lần đứng 19,2 s không để lại dấu vết nào). */
    private fun noteStall(playing: Boolean) {
        val now = SystemClock.elapsedRealtime()
        if (!playing) {
            if (stalledSince == 0L) stalledSince = now
            return
        }
        if (stalledSince != 0L && now - stalledSince >= STALL_LOG_MS) {
            Log.i("ABookStall", "giọng chờ đoạn kế ${now - stalledSince} ms (chương ${currentChapter?.id}, ${"%.1f".format(positionSeconds)} s)")
        }
        stalledSince = 0L
    }

    /** Người nghe đổi ý phát / dừng mà `isPlaying` không đổi (đang chờ đoạn kế của đọc to, hay giọng đang đệm): nhạc cũng theo. */
    fun onWantsChanged() {
        if (!isPlaying && player != null) syncMusic(false)
    }

    /** ExoPlayer vừa tua (nút trong app, màn khoá, controller ngoài): đang dừng thì lưu chỗ mới - nhịp lưu chỉ chạy khi đang phát, nên dừng ở phút 30, tua về phút 10, để máy nghỉ
     *  rồi bị giết tiến trình là mở lại ở phút 30 (soát a77 #3). Chuyển mục tự động, thay hàng đợi (REMOVE) không phải tua của người nghe. */
    /** Tốc độ ExoPlayer đang dùng mà lõi đã biết (đã lưu / đã báo): chính lõi đặt nó qua [applySpeed]. Lệnh khác với nó là của controller ngoài. */
    private var knownSpeed = 1f

    private fun applySpeed(exo: ExoPlayer, rate: Double) {
        knownSpeed = rate.toFloat() // trước khi đặt: ExoPlayer báo onPlaybackParametersChanged ngay trong lời gọi
        exo.playbackParameters = PlaybackParameters(knownSpeed)
    }

    /**
     * ExoPlayer báo tốc độ đổi (PlaybackService). Tốc độ do lõi tự đặt ([applySpeed]: nút trong app, nạp sách) đã lưu / báo đúng chỗ của nó. Controller ngoài (xe, đồng hồ, Android Auto) đổi thì
     * tiếng đổi mà sách vẫn nhớ tốc độ cũ và giao diện còn hiện tốc độ cũ (soát a77 #9): lưu vào sách và báo "rateChanged" để giao diện cập nhật độc lập với đổi chương.
     */
    fun onRateChanged(speed: Float) {
        if (speed == knownSpeed) return
        knownSpeed = speed
        if (bookId.isNotEmpty()) runCatching { Store.setRate(bookId, speed.toDouble(), recordId.ifEmpty { null }) }.onFailure { Log.w("ABookSave", "không lưu được tốc độ", it) }
        emit("rateChanged")
    }

    fun onSeekSettled(reason: Int) {
        if (reason == Player.DISCONTINUITY_REASON_SEEK || reason == Player.DISCONTINUITY_REASON_SEEK_ADJUSTMENT) saveIfParked()
    }

    /** Lưu chỗ vừa tua khi giọng đang dừng. [moved]: chỗ vừa nạp trùng chỗ đã lưu (nạp hàng đợi, đổi hồ sơ) thì không lưu - lưu lại là đóng dấu giờ mới lên chỗ cũ ([savedPlace]);
     *  [saveNow] vẫn chặn lúc thay hàng đợi (`bookId` rỗng khi `adopt`), chữ chương chưa về, chỗ của cuốn khác. */
    private fun saveIfParked() {
        if (!isPlaying && moved()) saveNow()
    }

    fun onChapterChanged() {
        SleepTimer.onChapterChanged()
        emit("chapter")
    }

    private var lastClipChapter = -1

    /**
     * ExoPlayer sang mục khác. Đoạn đọc to (có `ReadAloud.Slot`) mà cùng chương với đoạn trước chỉ là đổi đoạn - không phải đổi chương, nên không báo "chapter" và
     * không kết thúc hẹn giờ "hết chương" (ReadAloud tự dừng nạp ở cuối chương). Mọi mục khác như cũ.
     */
    fun onMediaTransition(item: MediaItem?) {
        if (item == null) return // hàng đợi vừa được xoá (ReadAloud bắt đầu lại ở chỗ khác): chưa có mục nào để báo
        val slot = item?.localConfiguration?.tag as? ReadAloud.Slot
        if (slot == null || slot.segment < 0) {
            lastClipChapter = -1
            ReadAloud.onClipChanged()
            applyVolume()
            onChapterChanged()
            if (slot == null) item.mediaId.toLongOrNull()?.let { Streaming.keepScript(appContext, bookId, it) }
            return
        }
        val sameChapter = slot.chapterIndex == lastClipChapter
        lastClipChapter = slot.chapterIndex
        ReadAloud.onClipChanged()
        applyVolume()
        if (!sameChapter) emit("chapter")
    }

    fun onEnded() {
        // Đọc to: hàng đợi cạn vì đọc chưa kịp (chờ đoạn kế), hay dừng đúng cuối chương theo hẹn giờ, hay sang chương kế - không phải hết cuốn.
        if (ReadAloud.handleEnded()) return
        saveNow()
        emit("ended")
    }

    /** Lưu vị trí: mỗi 5 giây khi đang phát, và ngay khi dừng/đổi chương. Cùng nhịp đó nhật ký đêm ghi mốc. */
    private fun startTicking() {
        if (ticking) return
        ticking = true
        main.post(object : Runnable {
            var beats = 0
            override fun run() {
                val exo = player
                // Đọc to chờ đoạn kế (hàng đợi cạn vì Edge chậm) vẫn là "đang nghe": nhịp nhạc nền không đứt (starved).
                if (exo == null || !(exo.isPlaying || ReadAloud.starved())) {
                    ticking = false
                    stalledSince = 0L // người nghe dừng: lần dừng không phải lần đứng chờ
                    return
                }
                beats += 1
                if (beats % 10 == 0) {
                    saveNow()
                    pushHeld(force = false)
                }
                if (beats % 60 == 0) SleepTimer.maybeSafetyStop(lastInteractionMs)
                Bedtime.checkpoint()
                noteStall(exo.isPlaying)
                syncMusic(true)
                emit("tick")
                main.postDelayed(this, 500)
            }
        })
    }

    /**
     * Đổi hồ sơ nghe của cuốn đang nạp (chọn hồ sơ khác, nghe lại từ đầu bằng hồ sơ mới, xoá hồ sơ đang dùng): chỗ đang
     * nghe và phiên nghe ghi vào hồ sơ CŨ, đổi, rồi nạp lại đúng chỗ của hồ sơ mới ở trạng thái dừng. Cả lượt chạy trên
     * luồng chính và `bookId` rỗng trong lúc đổi, nên lần lưu muộn nào (sự kiện dừng của ExoPlayer) cũng không rơi sang
     * hồ sơ mới. Cuốn không nạp thì chỉ việc đổi.
     */
    fun <T> switchRecord(id: String, change: () -> T): T {
        val exo = player
        if (exo == null || id.isEmpty() || bookId != id) return change()
        val playing = exo.isPlaying
        pause()
        if (playing || moved()) saveNow()
        closeSession()
        return reloadAfter(id, change)
    }

    /** Đẩy chỗ nghe của ĐÚNG hồ sơ phiên phát đang giữ lên máy giữ sách (không phải hồ sơ đang dùng); hồ sơ đã mất thì không đẩy gì. */
    private fun pushHeld(force: Boolean) {
        if (recordId.isNotEmpty() && !Store.holds(bookId, recordId)) return
        StateSync.pushSoon(appContext, bookId, force, recordId.ifEmpty { null })
    }

    /**
     * Máy khác xoá hồ sơ [ids] (bia mộ tới qua Store.applySync / mergeRecord, ở luồng nền): phiên phát đang giữ một trong số đó thì dừng,
     * bỏ phiên nghe của nó, rồi nạp lại cuốn ở hồ sơ thay thế (Store đã chọn) ở trạng thái dừng. Cả lượt chạy trên luồng chính, và [saveNow] /
     * [closeSession] / [pushHeld] không ghi vào hồ sơ đã mất - chỗ nghe và phiên của hồ sơ bị xoá không bị chuyển sang người còn lại.
     */
    fun recordsGone(ids: Set<String>) {
        val id = bookId
        if (recordId.isEmpty() || recordId !in ids) return
        onMain {
            if (bookId != id || recordId !in ids) return@onMain
            pause()
            sessionFrom = null
            reloadAfter(id) { }
            emit("record")
        }
    }

    /** Máy khác đổi hồ sơ nghe của cuốn đang nạp, lúc đang dừng (Store.applySync đã đổi): nạp lại đúng chỗ của hồ sơ
     *  mới, không lưu gì - chỗ của hồ sơ cũ đã lưu lúc dừng, lưu bây giờ là ghi nó vào hồ sơ mới. */
    fun follow(id: String) {
        if (player == null || bookId != id || player?.isPlaying == true) return
        reloadAfter(id) { }
        emit("record")
    }

    private fun <T> reloadAfter(id: String, change: () -> T): T {
        val items = chapters
        val title = bookTitle
        val narratorName = narrator
        bookId = ""
        recordId = ""
        try {
            return change()
        } finally {
            val state = Store.state(id)
            val last = state.optJSONObject("last")?.takeIf { last -> items.any { it.id == last.optInt("chapterId") } }
            load(id, title, narratorName, items, last?.optInt("chapterId") ?: items.firstOrNull()?.id ?: 0,
                last?.optDouble("seconds") ?: 0.0, state.optDouble("rate", 1.0), autoplay = false)
        }
    }

    private fun moved(): Boolean {
        val chapter = currentChapter ?: return false
        val saved = savedPlace ?: return true
        return saved.first != chapter.id || kotlin.math.abs(saved.second - positionMs) > 1000
    }

    /** Lần lưu chỗ nghe gần nhất hỏng (bộ nhớ đầy, ghi/đổi tên lỗi): đang báo người nghe rồi, chưa báo lần nữa tới khi lưu được. */
    private var saveFailing = false
    private const val SAVE_FAILED = "Chưa lưu được chỗ bạn đang nghe - bộ nhớ trong máy có thể đã đầy. Bạn cứ nghe tiếp, ABook sẽ thử lưu lại sau ít giây."

    /**
     * Lưu chỗ nghe. Lỗi ghi (Store.progress: ghi file, sync, đổi tên) KHÔNG được thoát ra khỏi đây - các nơi gọi chạy ở luồng chính (nhịp 5 giây, sự kiện dừng/lỗi của ExoPlayer), ném là văng cả
     * bộ phát (soát a77 #4). Hỏng thì chỗ đã lưu trước đó còn nguyên (ghi nguyên tử), ghi logcat, báo bạn MỘT lần ("saveFailed"); `savedPlace` không đổi nên lần lưu kế (nhịp sau) tự thử lại.
     */
    fun saveNow() {
        val chapter = currentChapter ?: return
        if (bookId.isEmpty() || ReadAloud.unknownPlace() || foreignItem()) return
        val duration = durationMs().takeIf { it > 0 }?.div(1000.0) ?: chapter.duration
        // Chỗ nghe phải khớp chương: vượt quá độ dài chương là đồng hồ của thứ khác (cuốn trước) - không lưu, không đồng bộ đi (soát a68 lỗi 2).
        if (!PlacePolicy.fits(positionSeconds, duration)) return
        try {
            // Hồ sơ đã mất (máy khác xoá, đang chờ [recordsGone] dọn): không có chỗ để ghi - không rơi sang hồ sơ còn lại.
            if (recordId.isNotEmpty() && !Store.holds(bookId, recordId)) return
            Store.progress(bookId, chapter.id, positionSeconds, duration, ReadAloud.anchor(), recordId.ifEmpty { null })
        } catch (error: Exception) {
            Log.w("ABookSave", "không lưu được chỗ nghe (chương ${chapter.id}, ${"%.1f".format(positionSeconds)} s)", error)
            if (!saveFailing) {
                saveFailing = true
                emit("saveFailed")
            }
            return
        }
        saveFailing = false
        savedPlace = chapter.id to positionMs
    }

    fun chaptersJson(): JSONArray = JSONArray().also { array ->
        chapters.forEach { array.put(JSONObject().put("id", it.id).put("title", it.title).put("duration", it.duration)) }
    }

    fun localFile(relative: String): File = Store.file(bookId, relative)
}
