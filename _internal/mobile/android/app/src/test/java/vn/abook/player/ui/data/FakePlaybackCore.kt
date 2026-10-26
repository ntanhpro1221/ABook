package vn.abook.player.ui.data

import org.json.JSONObject
import vn.abook.player.Playback

/**
 * Lõi phát giả cho test: ghi lại lệnh, giữ danh sách người nghe để test bắn sự kiện vào. `simulate` true: lõi tự theo lệnh như lõi thật - nạp cuốn thì
 * đặt cuốn / chỗ / phát-dừng theo [LoadRequest] rồi bắn sự kiện "load", phát / dừng / đổi qua lại cũng bắn sự kiện - để thử một chuỗi thao tác từ đầu tới cuối.
 */
class FakePlaybackCore(var snapshot: JSONObject, private val simulate: Boolean = false) : PlaybackCore {
    val listeners = ArrayList<(JSONObject) -> Unit>()
    val calls = ArrayList<String>()
    val loads = ArrayList<LoadRequest>()

    /** Hàng chương lõi đang giữ (đổi đối tượng khi test muốn "lõi đổi hàng"), vị trí chính xác (null = theo ảnh chụp, như lõi thật), nhạc nền, giọng. */
    var chapterList: List<Playback.Chapter> = emptyList()
    var position: Long? = null
    var music = false
    var voiceChosen = ""

    override fun addListener(listener: (JSONObject) -> Unit) { listeners += listener }
    override fun removeListener(listener: (JSONObject) -> Unit) { listeners -= listener }
    override fun snapshot() = snapshot
    override fun close() {
        calls += "close"
        snapshot = JSONObject().put("bookId", "").put("chapterId", JSONObject.NULL)
        chapterList = emptyList()
        emit(snapshot)
    }
    override fun play() { calls += "play"; setPlaying(true) }
    override fun pause() { calls += "pause"; setPlaying(false) }
    override fun toggle() { calls += "toggle"; setPlaying(!snapshot.optBoolean("playing")) }
    override fun skip(deltaSeconds: Double) { calls += "skip $deltaSeconds" }
    override fun seekTo(seconds: Double) { calls += "seek $seconds" }
    override fun next() { calls += "next" }
    override fun previous() { calls += "previous" }
    override fun setRate(rate: Double) { calls += "rate $rate" }
    override fun jumpTo(chapterId: Int, seconds: Double) { calls += "jump $chapterId $seconds" }
    override fun load(request: LoadRequest) {
        loads += request
        if (!simulate) return
        chapterList = request.chapters
        snapshot = playerSnapshot(
            book = request.id, chapter = request.startChapterId, playing = request.autoplay, position = request.startSeconds, duration = request.startSeconds + 600.0,
            kind = "load", bookTitle = request.title, chapterTitle = "Chương ${request.startChapterId}",
        )
        emit(snapshot)
    }

    private fun setPlaying(playing: Boolean) {
        if (!simulate || snapshot.optString("bookId").isEmpty()) return
        snapshot = JSONObject(snapshot.toString()).put("playing", playing).put("kind", "state")
        emit(snapshot)
    }

    override fun positionMs() = position ?: Math.round(snapshot.optDouble("position", 0.0) * 1000)
    override fun chapters() = chapterList
    override fun setSleep(mode: String, minutes: Int) { calls += "sleep $mode $minutes" }
    override fun autoMusic() = music
    override fun setAutoMusic(enabled: Boolean) { calls += "music $enabled"; music = enabled }
    override fun voiceId() = voiceChosen
    override fun setVoice(voiceId: String) { calls += "voice $voiceId"; voiceChosen = voiceId }

    fun emit(json: JSONObject) = listeners.toList().forEach { it(json) }
}

/** JSON y như `Playback.state()` / sự kiện của lõi phát, đủ trường mà [PlayerState.from] đọc. */
fun playerSnapshot(
    book: String = "b1",
    chapter: Int? = 1,
    playing: Boolean = false,
    position: Double = 12.5,
    duration: Double = 600.0,
    kind: String = "state",
    bookTitle: String = "Tắt đèn",
    chapterTitle: String = "Chương 1",
): JSONObject = JSONObject()
    .put("kind", kind).put("bookId", book).put("bookTitle", bookTitle).put("chapterId", chapter ?: JSONObject.NULL)
    .put("chapterTitle", chapterTitle).put("playing", playing).put("position", position).put("duration", duration).put("rate", 1.0)
