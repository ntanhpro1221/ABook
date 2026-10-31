package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.State
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableLongStateOf
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import vn.abook.player.Playback
import vn.abook.player.ui.music.PlayerMusic
import vn.abook.player.ui.voice.OnlineConsent
import vn.abook.player.ui.voice.PlayGate

/** Một chương trong hàng chương của trình phát (Đang nghe: danh sách chương, chương chữ cho Đọc theo). `textPath` rỗng: chương audio. */
@Immutable
data class PlayerChapter(val id: Int, val title: String, val durationMs: Long, val textPath: String = "")

/** Hẹn giờ ngủ đã đặt (chỉ phần đổi chậm; thời gian còn lại chạy theo giây nằm ở [PlayerClock.sleepRemainingMs]). */
@Immutable
data class SleepSetting(val mode: String = "off", val minutes: Int = 0, val counting: Boolean = false, val stoppedAtMs: Long = 0L) {
    val active: Boolean get() = mode != "off"

    companion object {
        val Off = SleepSetting()
    }
}

/**
 * Trạng thái trình phát mà MỌI màn vẽ (thanh nhỏ, trang sách, Đang nghe): bất biến, CHỈ đổi khi có gì đổi thật (cuốn, chương, phát/dừng, tốc độ, hẹn giờ, lỗi,
 * nhạc nền, giọng) - không có vị trí: vị trí chạy hai lần mỗi giây nằm riêng ở [PlayerClock] để chỉ thanh tua và đồng hồ đọc nó.
 * `chapters`: hàng chương của cuốn đang nạp (dựng lại chỉ khi lõi đổi hàng), `music`: nhạc nền đang kêu (ghi công, bài hỏng, mất mạng), `voiceId`: giọng đọc máy đang dùng.
 */
@Immutable
data class PlayerState(
    val bookId: String = "",
    val bookTitle: String = "",
    val chapterId: Int? = null,
    val chapterTitle: String = "",
    val cover: CoverRef? = null,
    val playing: Boolean = false,
    val buffering: Boolean = false,
    val durationMs: Long = 0L,
    val rate: Double = 1.0,
    val sleep: SleepSetting = SleepSetting.Off,
    val error: String = "",
    val chapters: List<PlayerChapter> = emptyList(),
    val music: PlayerMusic = PlayerMusic.None,
    val voiceId: String = "",
    /** Cuốn đã đủ chương (thư viện báo): "cả cuốn" hay mới "phần đã có" ở dòng tiến độ, và hết chương cuối là "hết sách" hay "hết phần đã có". */
    val whole: Boolean = true,
    /** Cuốn còn chương chưa nghe được (chưa có audio) sau hàng chương đang nạp: nút "Chương sau" nói vì sao không bấm được. */
    val moreChapters: Boolean = false,
    /** Phát hết chương cuối của hàng chương (lõi báo "ended") và chưa nghe lại gì: hiện lời "Đã nghe hết ...". */
    val ended: Boolean = false,
) {
    /** Có cuốn trong trình phát (thanh nhỏ hiện). */
    val hasTrack: Boolean get() = bookId.isNotEmpty() && chapterId != null

    companion object {
        val Empty = PlayerState()

        /** Từ sự kiện của lõi phát ([Playback.state]); `cover` do nơi gọi giữ/tra theo mã sách, `chapters` / `voiceId` đọc từ lõi (không nằm trong sự kiện). */
        fun from(
            json: JSONObject,
            cover: CoverRef?,
            chapters: List<PlayerChapter> = emptyList(),
            voiceId: String = "",
        ): PlayerState {
            val sleep = json.optJSONObject("sleep")
            return PlayerState(
                bookId = json.optString("bookId"),
                bookTitle = json.optString("bookTitle"),
                chapterId = if (json.isNull("chapterId")) null else json.optInt("chapterId"),
                chapterTitle = json.optString("chapterTitle"),
                cover = cover,
                playing = json.optBoolean("playing"),
                buffering = json.optBoolean("buffering"),
                durationMs = Math.round(json.optDouble("duration", 0.0) * 1000),
                rate = json.optDouble("rate", 1.0),
                sleep = if (sleep == null) SleepSetting.Off else SleepSetting(
                    sleep.optString("mode", "off"), sleep.optInt("minutes"), sleep.optBoolean("counting"),
                    Math.round(sleep.optDouble("stoppedAt", 0.0) * 1000),
                ),
                error = json.optString("error").ifBlank { json.optString("saveError") },
                chapters = chapters,
                music = PlayerMusic.from(json),
                voiceId = voiceId,
            )
        }
    }
}

/**
 * Nguồn thời gian chạy theo nhịp (nửa giây khi đang phát): MỖI giá trị là một `State` riêng - không composable nào đọc chúng trong thân,
 * chỉ trong pha vẽ / dàn trang (`drawBehind`, `graphicsLayer`, `Modifier.layout`) hay một lambda `() -> Long`, nên mỗi nhịp chỉ vẽ lại thanh tua và
 * đồng hồ, không dựng lại màn nào.
 */
@Stable
class PlayerClock {
    private val position = mutableLongStateOf(0L)
    private val sleepRemaining = mutableLongStateOf(0L)
    val positionMs: State<Long> get() = position
    val sleepRemainingMs: State<Long> get() = sleepRemaining

    internal fun set(positionMs: Long, sleepRemainingMs: Long) {
        position.longValue = positionMs
        sleepRemaining.longValue = sleepRemainingMs
    }

    /** Chỉ vị trí (nhịp theo khung của Đang nghe khi nó mở - [PlayerRepo.sampleClock]); hẹn giờ còn lại vẫn theo nhịp của lõi. */
    internal fun setPosition(positionMs: Long) {
        position.longValue = positionMs
    }
}

/** Một lần nạp cuốn vào trình phát: đúng tham số của [Playback.load]. `autoplay` false: nạp sẵn ở trạng thái dừng (khôi phục cuốn nghe dở lúc mở app). */
data class LoadRequest(
    val id: String,
    val title: String,
    val narrator: String,
    val chapters: List<Playback.Chapter>,
    val startChapterId: Int,
    val startSeconds: Double,
    val rate: Double,
    val autoplay: Boolean = true,
    /** Nạp để KHÔI PHỤC lúc mở app: lõi đã có cuốn (widget, tai nghe, người nghe bấm phát cuốn khác) thì bỏ, không đè. Nạp vì người nghe chọn thì false. */
    val restore: Boolean = false,
)

/** Phần lõi phát mà [PlayerRepo] cần - tách ra để thử bằng lõi giả (lõi thật: [AndroidPlaybackCore]). Mọi lệnh có thể gọi từ luồng bất kỳ. */
interface PlaybackCore {
    fun addListener(listener: (JSONObject) -> Unit)
    fun removeListener(listener: (JSONObject) -> Unit)

    /** Trạng thái hiện tại ([Playback.state]); gọi ở luồng chính. */
    fun snapshot(): JSONObject
    fun play()
    fun pause()
    fun close()
    fun toggle()
    fun skip(deltaSeconds: Double)
    fun seekTo(seconds: Double)
    fun next()
    fun previous()
    fun setRate(rate: Double)
    fun jumpTo(chapterId: Int, seconds: Double)
    fun load(request: LoadRequest)

    /** Vị trí chính xác trong chương (ms), không qua nhịp: Đang nghe đọc nó mỗi khung khi mở. Gọi ở luồng chính. */
    fun positionMs(): Long

    /** Hàng chương của cuốn đang nạp ([Playback.chapters]); cùng một đối tượng chừng nào lõi chưa đổi hàng. */
    fun chapters(): List<Playback.Chapter>

    /** Hẹn giờ ngủ: `mode` = "off" | "minutes" | "chapter". */
    fun setSleep(mode: String, minutes: Int)

    /** "+N phút": nghe thêm khi hẹn giờ sắp tắt (mức N là mức "Mỗi lần nghe thêm" của Cài đặt). Mặc định: không làm gì (lõi giả). */
    fun extendSleep() = Unit

    /** Giọng đọc máy của cuốn đang nạp. */
    fun voiceId(): String
    fun setVoice(voiceId: String)
}

/**
 * Kho dữ liệu trình phát cho giao diện native (NATIVE_PHONE_UI.md §2): dựng [PlayerState] bất biến + [PlayerClock] từ sự kiện của lõi phát
 * ([Playback.addListener]); lệnh chuyển thẳng xuống lõi. Chỉ lắng nghe khi giao diện đang hiện ([attach] / [detach] theo vòng đời Activity) -
 * lúc ẩn (phát nền) không có gì chạy ở đây.
 *
 * `coverOf`: bìa của một cuốn (đọc đĩa - chạy ở `io`); `planOf`: chỗ nghe tiếp + hàng chương của một cuốn (đọc Store - chạy ở `io`);
 * `lastPlan`: như `planOf` cho cuốn nghe gần nhất (null: chưa nghe cuốn nào) - cuốn ấy được nạp sẵn ở trạng thái dừng khi mở app, để thanh phát nhỏ
 * là MỘT cửa "Đang nghe" duy nhất (không có hàng "Đang nghe" thứ hai ở Thư viện).
 * `planAt`: như `planOf` nhưng bắt đầu ở một chương + giây cho trước (trang sách: chạm một chương, "Từ đầu", kết quả tìm).
 * `gate`: cửa trước mọi lệnh làm chữ rời máy - chương chỉ có chữ đọc bằng giọng trực tuyến chưa được đồng ý thì hỏi bạn TRƯỚC khi phát ([PlayGate]).
 */
class PlayerRepo(
    private val core: PlaybackCore,
    private val scope: CoroutineScope,
    private val io: CoroutineDispatcher,
    private val coverOf: (String) -> CoverRef?,
    private val planOf: (String) -> LoadRequest?,
    private val lastPlan: () -> LoadRequest? = { null },
    private val planAt: (String, Int, Double) -> LoadRequest? = { _, _, _ -> null },
    val gate: PlayGate = PlayGate.Open,
) {
    private val flow = MutableStateFlow(PlayerState.Empty)
    val state: StateFlow<PlayerState> get() = flow
    val clock = PlayerClock()

    /**
     * Tên mỗi sự kiện KHÔNG phải nhịp của lõi ("state", "chapter", "record", "sleep"...), kể cả khi nó không đổi gì ở [state] (đọc to đẩy thêm chữ / thời lượng mới
     * cũng bằng sự kiện "state"): Đọc theo nghe nó để nạp lại chữ. Cùng MỘT người nghe lõi - không ai khác gọi [PlaybackCore.addListener].
     */
    val events: SharedFlow<String> get() = changes
    private val changes = MutableSharedFlow<String>(extraBufferCapacity = 8, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    /** Cuốn nào đủ chương, còn thiếu chương nào (từ thư viện, [reconcile]); [apply] đưa vào [PlayerState] của cuốn đang nạp. */
    private var shapes: Map<String, BookShape> = emptyMap()
    private var queue: List<Playback.Chapter>? = null
    private var queueChapters: List<PlayerChapter> = emptyList()
    private val listener: (JSONObject) -> Unit = ::onEvent

    @Volatile
    private var attached = false

    /** Bắt đầu theo dõi lõi phát và lấy ngay trạng thái hiện tại (cuốn đang phát từ trước khi mở app). Gọi ở luồng chính. */
    fun attach() {
        if (attached) return
        attached = true
        core.addListener(listener)
        apply(core.snapshot())
        if (!flow.value.hasTrack) restoreLast()
    }

    /**
     * Lõi chưa giữ cuốn nào (app vừa mở): nạp cuốn nghe gần nhất ĐÚNG chỗ nghe tiếp, ở trạng thái dừng - thanh phát nhỏ hiện sẵn, bấm phát là phát đúng cuốn ấy.
     * Như khi mở lại app (Playback.load autoplay=false). Có gì khác vào lõi trong lúc đọc đĩa thì bỏ (không bao giờ đè cuốn đang có).
     */
    private fun restoreLast() {
        val generation = loadGeneration
        scope.launch {
            val request = withContext(io) { lastPlan() } ?: return@launch
            if (attached && generation == loadGeneration && !flow.value.hasTrack) core.load(request.copy(autoplay = false, restore = true))
        }
    }

    /** Thôi theo dõi (giao diện ẩn). Trạng thái cuối giữ nguyên; [attach] lần sau làm mới nó. */
    fun detach() {
        if (!attached) return
        attached = false
        core.removeListener(listener)
    }

    private fun onEvent(json: JSONObject) {
        // Nhịp đồng hồ: chỉ vị trí (và hẹn giờ còn lại) - không dựng lại trạng thái.
        if (json.optString("kind") == "tick") {
            setClock(json)
            return
        }
        apply(json)
        if (json.optString("kind") == "ended") flow.update { it.copy(ended = it.chapterId != null) }
        changes.tryEmit(json.optString("kind"))
    }

    private fun setClock(json: JSONObject) {
        val remaining = json.optJSONObject("sleep")?.optDouble("remaining", 0.0) ?: 0.0
        clock.set(Math.round(json.optDouble("position", 0.0) * 1000).coerceAtLeast(0), Math.round(remaining.coerceAtLeast(0.0) * 1000))
    }

    private fun apply(json: JSONObject) {
        setClock(json)
        val id = json.optString("bookId")
        val previous = flow.value
        val keep = if (id == previous.bookId) previous.cover else null
        val chapters = core.chapters()
        if (chapters !== queue) {
            queue = chapters
            queueChapters = chapters.map { PlayerChapter(it.id, it.title, Math.round(it.duration * 1000), it.text) }
        }
        val shape = shapes[id]
        val parsed = PlayerState.from(json, keep, queueChapters, core.voiceId())
        // Hết chương cuối: lời "Đã nghe hết ..." ở lại tới khi nghe lại gì (phát, đổi chương hay đổi cuốn).
        val next = parsed.copy(
            whole = shape?.whole ?: true,
            moreChapters = shape != null && shape.total > queueChapters.size,
            ended = previous.ended && !parsed.playing && id == previous.bookId && parsed.chapterId == previous.chapterId,
        )
        flow.value = next
        if (id.isNotEmpty() && id != previous.bookId) {
            scope.launch(io) {
                val cover = coverOf(id)
                flow.update { if (it.bookId == id) it.copy(cover = cover) else it }
            }
        }
    }

    // ---- lệnh (chuyển thẳng xuống lõi) ----------------------------------------------------------------------

    private var loadGeneration = 0

    /** Invalidate in-flight plans as well as the visible player. Undo restores the row, never restarts audio. */
    fun bookRemoved(id: String) {
        loadGeneration++
        gate.cancel()
        if (flow.value.bookId != id) return
        core.close()
        queue = null
        queueChapters = emptyList()
        flow.value = PlayerState.Empty
        clock.set(0, 0)
        changes.tryEmit("closed")
    }

    fun reconcile(books: List<ListenBook>) {
        shapes = books.associate { it.id to BookShape(it.complete, it.chaptersTotal) }
        val id = flow.value.bookId
        if (id.isNotEmpty() && books.none { it.id == id }) bookRemoved(id)
        else shapes[id]?.let { shape -> flow.update { it.copy(whole = shape.whole, moreChapters = shape.total > it.chapters.size) } }
    }

    private class BookShape(val whole: Boolean, val total: Int)

    /** Người nghe làm gì đó với trình phát: lời "Đã nghe hết ..." hết nghĩa. */
    private fun heardAgain() = flow.update { if (it.ended) it.copy(ended = false) else it }

    /** Chương `chapterId` của cuốn đang nạp là chương chỉ có chữ (giọng máy đọc to). */
    private fun isText(chapterId: Int?): Boolean = chapterId != null && core.chapters().any { it.id == chapterId && it.isText }

    /** Cuốn đang nạp đang phát, hay đang chờ đoạn đầu để phát: lệnh phát tới lúc này không làm chữ đi đâu thêm. */
    private fun running(): Boolean = flow.value.let { it.playing || it.buffering }

    /** Chạy `go` (một lệnh làm cuốn ĐANG NẠP bắt đầu phát chương `chapterId`) sau khi qua cửa hỏi đồng ý. */
    private fun before(chapterId: Int?, go: () -> Unit) {
        if (running()) {
            gate.cancel()
            go()
        } else {
            gate.before(flow.value.bookId, isText(chapterId), go)
        }
    }

    fun play() { heardAgain(); before(flow.value.chapterId) { core.play() } }
    fun pause() {
        gate.cancel()
        core.pause()
    }

    fun toggle() { heardAgain(); before(flow.value.chapterId) { core.toggle() } }
    fun skip(deltaSeconds: Double) { heardAgain(); core.skip(deltaSeconds) }
    fun seekTo(seconds: Double) { heardAgain(); core.seekTo(seconds) }
    fun next() { heardAgain(); before(OnlineConsent.stepTarget(core.chapters().map { it.id }, flow.value.chapterId, 1, 0)) { core.next() } }
    fun previous() { heardAgain(); before(OnlineConsent.stepTarget(core.chapters().map { it.id }, flow.value.chapterId, -1, core.positionMs())) { core.previous() } }
    fun setRate(rate: Double) = core.setRate(rate)
    fun jumpTo(chapterId: Int, seconds: Double) { heardAgain(); before(chapterId) { core.jumpTo(chapterId, seconds) } }
    fun setSleep(mode: String, minutes: Int = 0) = core.setSleep(mode, minutes)
    fun extendSleep() = core.extendSleep()

    /** Đổi giọng đọc máy (cũng không có sự kiện riêng). */
    fun setVoice(voiceId: String) {
        core.setVoice(voiceId)
        flow.update { it.copy(voiceId = voiceId) }
    }

    /** Vị trí chính xác lúc này (không qua nhịp) - chỗ để "Về chỗ cũ" nhớ. Gọi ở luồng chính. */
    fun positionMs(): Long = core.positionMs()

    /** Đặt đồng hồ theo vị trí chính xác của lõi: Đang nghe gọi mỗi khung khi nó mở và đang phát (thanh tua, chữ đọc theo chạy mượt hơn nhịp nửa giây). Luồng chính. */
    fun sampleClock() = clock.setPosition(core.positionMs().coerceAtLeast(0))

    /** Nút chính của trang sách: cuốn đang ở trình phát thì phát/dừng, không thì nạp ở chỗ nghe tiếp và phát. */
    fun togglePlay(bookId: String) {
        if (flow.value.bookId == bookId) toggle() else playBook(bookId)
    }

    /** Chạm giữ bìa: phát cuốn ngay. Đang ở trình phát thì phát tiếp (đã phát rồi thì để yên), không thì nạp ở chỗ nghe tiếp. */
    fun playNow(bookId: String) {
        val current = flow.value
        if (current.bookId == bookId) {
            if (!current.playing) play()
        } else {
            playBook(bookId)
        }
    }

    /**
     * Phát một chương từ giây `seconds` (trang sách). Cuốn đang ở trình phát thì nhảy tới đó như mọi cú nhảy khác (trình phát nhớ chỗ cũ); không thì nạp cuốn
     * bắt đầu ở đó và phát.
     */
    fun playChapter(bookId: String, chapterId: Int, seconds: Double) {
        if (flow.value.bookId == bookId) {
            jumpTo(chapterId, seconds)
            return
        }
        val generation = loadGeneration
        scope.launch {
            val request = withContext(io) { planAt(bookId, chapterId, seconds) } ?: return@launch
            if (generation == loadGeneration) load(request)
        }
    }

    /**
     * "Đọc theo" từ trang sách: đưa cuốn vào trình phát Ở TRẠNG THÁI DỪNG tại chỗ nghe tiếp (cuốn đang ở đó rồi thì để yên). Trả về khi cuốn đã vào
     * (hay sau 3 giây nếu lõi không nhận) - true: cuốn ấy đang là cuốn của trình phát. Khác khôi phục lúc mở app: người nghe chủ động chọn nên có thể thay cuốn đang có.
     */
    suspend fun prepare(bookId: String): Boolean {
        if (flow.value.bookId == bookId && flow.value.hasTrack) return true
        val generation = loadGeneration
        val request = withContext(io) { planOf(bookId) } ?: return false
        if (generation != loadGeneration) return false
        core.load(request.copy(autoplay = false))
        return withTimeoutOrNull(3_000) { flow.first { it.bookId == bookId && it.hasTrack } } != null
    }

    private fun playBook(bookId: String) {
        val generation = loadGeneration
        scope.launch {
            val request = withContext(io) { planOf(bookId) } ?: return@launch
            if (generation == loadGeneration) load(request)
        }
    }

    /** Nạp một cuốn để PHÁT (người nghe chọn): chương bắt đầu là chương chữ thì qua cửa hỏi đồng ý trước, chưa nạp gì khi chưa có câu trả lời. */
    private fun load(request: LoadRequest) {
        val text = request.chapters.any { it.id == request.startChapterId && it.isText }
        gate.before(request.id, text) { core.load(request) }
    }
}
