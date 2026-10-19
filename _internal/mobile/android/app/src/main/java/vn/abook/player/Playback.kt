package vn.abook.player

import android.content.Context
import android.os.Handler
import android.os.Looper
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

object Playback {
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
    var headsetSkips = false

    var bookId: String = ""
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
    private var autoRewindAfterMs = 5 * 60_000L
    private var autoRewindSeconds = 5.0
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
        runCatching { Store.addSession(sessionBook, session) }
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

    /** Hệ số mờ dần của hẹn giờ ngủ (1 = không mờ); âm lượng thật = mờ dần × độ to cố định của giọng đọc to. */
    var fadeLevel = 1f
        private set

    fun applyVolume(fade: Float = fadeLevel) {
        fadeLevel = fade
        player?.volume = fade * ReadAloud.gainFactor()
    }

    /** Hẹn giờ "hết chương": ExoPlayer dừng ở cuối mục. Chương đọc to gồm nhiều mục (mỗi đoạn một mục) nên không dùng được - ReadAloud tự dừng nạp ở cuối chương. */
    fun holdAtItemEnd(on: Boolean) {
        if (on && ReadAloud.inText()) ReadAloud.stopAtChapterEnd()
        player?.pauseAtEndOfMediaItems = on && !ReadAloud.inText()
    }

    /** Thời gian còn lại của chương (ms); chương đọc to tính trên đồng hồ ảo. */
    fun remainingInChapterMs(): Long = (durationMs() - positionMs).coerceAtLeast(0L)

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
        ReadAloud.useVoiceOf(id)
        bookId = id
        bookTitle = title
        narrator = narratorName
        chapters = items
        val index = items.indexOfFirst { it.id == startChapterId }.coerceAtLeast(0)
        if (items.any { it.isText }) {
            // Sách có chương chỉ-có-chữ: ReadAloud đọc đoạn nào đặt đoạn ấy vào hàng đợi (giọng Edge cần mạng, nên giữ Wi-Fi thức khi tắt màn hình).
            exo.setWakeMode(C.WAKE_MODE_NETWORK)
            savedPlace = items.getOrNull(index)?.let { it.id to msOf(startSeconds) }
            exo.playbackParameters = PlaybackParameters(rate.toFloat())
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
        exo.setMediaItems(media, index, msOf(startSeconds))
        savedPlace = items.getOrNull(index)?.let { it.id to msOf(startSeconds) }
        exo.playbackParameters = PlaybackParameters(rate.toFloat())
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
        bookTitle = next.title
        narrator = next.narrator
        chapters = next.items
        val streamed = next.items.any { Streaming.chapterUri(appContext, next.id, it.file).scheme == "https" }
        exo.setWakeMode(if (streamed) C.WAKE_MODE_NETWORK else C.WAKE_MODE_LOCAL)
        exo.playbackParameters = PlaybackParameters(next.rate.toFloat())
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
        if (pausedAtMs > 0 && System.currentTimeMillis() - pausedAtMs > autoRewindAfterMs) {
            seekToMs((positionMs - (autoRewindSeconds * 1000).toLong()).coerceAtLeast(0))
        }
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
                Bedtime.interaction("next")
            }
            return
        }
        if (exo.hasNextMediaItem()) {
            saveNow()
            exo.seekToNextMediaItem()
            Bedtime.interaction("next")
        }
    }

    fun previous() {
        val exo = player ?: return
        saveNow()
        if (ReadAloud.active) {
            val index = chapters.indexOfFirst { it.id == currentChapter?.id }
            if (positionMs > 5000 || index <= 0) seekToMs(0) else ReadAloud.jump(index - 1, 0)
            Bedtime.interaction("previous")
            return
        }
        if (exo.currentPosition > 5000 || !exo.hasPreviousMediaItem()) exo.seekTo(0) else exo.seekToPreviousMediaItem()
        Bedtime.interaction("previous")
    }

    fun setRate(rate: Double) {
        touched()
        player?.playbackParameters = PlaybackParameters(rate.toFloat())
        if (bookId.isNotEmpty()) Store.setRate(bookId, rate)
        emit("rate")
    }

    fun addBookmark(note: String): JSONObject? {
        val chapter = currentChapter ?: return null
        val mark = Store.addBookmark(bookId, chapter.id, positionSeconds, note)
        Bedtime.interaction("bookmark")
        emit("bookmark")
        return mark
    }

    fun configure(rewindAfterMinutes: Double, rewindSeconds: Double) {
        autoRewindAfterMs = (rewindAfterMinutes * 60_000).toLong()
        autoRewindSeconds = rewindSeconds
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
            StateSync.pushSoon(appContext, bookId, force = true)
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
        MusicBed.sync(bookId, currentChapter?.id, positionSeconds, playing || ReadAloud.starved())
    }

    /** Người nghe đổi ý phát / dừng mà `isPlaying` không đổi (đang chờ đoạn kế của đọc to): nhạc cũng theo. */
    fun onWantsChanged() {
        if (ReadAloud.active && !isPlaying) syncMusic(false)
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
                    return
                }
                beats += 1
                if (beats % 10 == 0) {
                    saveNow()
                    StateSync.pushSoon(appContext, bookId, force = false)
                }
                if (beats % 60 == 0) SleepTimer.maybeSafetyStop(lastInteractionMs)
                Bedtime.checkpoint()
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

    fun saveNow() {
        val chapter = currentChapter ?: return
        if (bookId.isEmpty() || ReadAloud.unknownPlace() || foreignItem()) return
        val duration = durationMs().takeIf { it > 0 }?.div(1000.0) ?: chapter.duration
        // Chỗ nghe phải khớp chương: vượt quá độ dài chương là đồng hồ của thứ khác (cuốn trước) - không lưu, không đồng bộ đi (soát a68 lỗi 2).
        if (!PlacePolicy.fits(positionSeconds, duration)) return
        Store.progress(bookId, chapter.id, positionSeconds, duration)
        savedPlace = chapter.id to positionMs
    }

    fun chaptersJson(): JSONArray = JSONArray().also { array ->
        chapters.forEach { array.put(JSONObject().put("id", it.id).put("title", it.title).put("duration", it.duration)) }
    }

    fun localFile(relative: String): File = Store.file(bookId, relative)
}
