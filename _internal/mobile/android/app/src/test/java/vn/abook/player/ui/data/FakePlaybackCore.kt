package vn.abook.player.ui.data

import org.json.JSONObject

/** Lõi phát giả cho test: ghi lại lệnh, giữ danh sách người nghe để test bắn sự kiện vào. */
class FakePlaybackCore(var snapshot: JSONObject) : PlaybackCore {
    val listeners = ArrayList<(JSONObject) -> Unit>()
    val calls = ArrayList<String>()
    val loads = ArrayList<LoadRequest>()

    override fun addListener(listener: (JSONObject) -> Unit) { listeners += listener }
    override fun removeListener(listener: (JSONObject) -> Unit) { listeners -= listener }
    override fun snapshot() = snapshot
    override fun play() { calls += "play" }
    override fun pause() { calls += "pause" }
    override fun toggle() { calls += "toggle" }
    override fun skip(deltaSeconds: Double) { calls += "skip $deltaSeconds" }
    override fun seekTo(seconds: Double) { calls += "seek $seconds" }
    override fun next() { calls += "next" }
    override fun previous() { calls += "previous" }
    override fun setRate(rate: Double) { calls += "rate $rate" }
    override fun jumpTo(chapterId: Int, seconds: Double) { calls += "jump $chapterId $seconds" }
    override fun load(request: LoadRequest) { loads += request }

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
