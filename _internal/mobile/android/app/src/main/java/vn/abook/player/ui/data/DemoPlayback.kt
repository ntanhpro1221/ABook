package vn.abook.player.ui.data

import android.os.SystemClock
import org.json.JSONObject
import vn.abook.player.Playback

/**
 * Lõi phát giả cho chế độ đo (`abook.demo.books`): một cuốn 12 chương đứng sẵn ở trình phát, KHÔNG chạm `Playback`, thư viện hay mạng.
 * Thanh phát nhỏ, cửa sổ Đang nghe và Đọc theo chạy đúng đường thật ([PlayerRepo] -> RepoNowPlayingModel), chỉ nguồn là cuốn giả này - số đo khung là của đường thật.
 */
class DemoPlaybackCore : PlaybackCore {
    private val listeners = ArrayList<(JSONObject) -> Unit>()
    private val queue = List(12) { Playback.Chapter(it + 1, "Chương ${it + 1} · ${if (it == 0) "Một buổi sớm" else "Trên con đường"}", "", 360.0, "texts/${it + 1}.txt") }
    private var chapterIndex = 0
    private var playing = false
    private var rate = 1.0
    private var anchorMs = 12_000L
    private var anchorAt = SystemClock.elapsedRealtime()
    private var sleepMode = "off"
    private var sleepMinutes = 0
    private var voice = ""

    private fun now(): Long {
        val elapsed = SystemClock.elapsedRealtime() - anchorAt
        return (anchorMs + if (playing) (elapsed * rate).toLong() else 0L).coerceIn(0, (queue[chapterIndex].duration * 1000).toLong())
    }

    private fun move(ms: Long, index: Int = chapterIndex) {
        chapterIndex = index.coerceIn(0, queue.lastIndex)
        anchorMs = ms.coerceAtLeast(0)
        anchorAt = SystemClock.elapsedRealtime()
        emit("state")
    }

    private fun emit(kind: String) {
        val event = snapshot().put("kind", kind)
        listeners.toList().forEach { it(event) }
    }

    override fun addListener(listener: (JSONObject) -> Unit) { listeners += listener }
    override fun removeListener(listener: (JSONObject) -> Unit) { listeners -= listener }

    override fun snapshot(): JSONObject {
        val chapter = queue[chapterIndex]
        return JSONObject().put("kind", "state").put("bookId", BOOK_ID).put("bookTitle", "Những ngày gió hát").put("chapterId", chapter.id)
            .put("chapterTitle", chapter.title).put("playing", playing).put("position", now() / 1000.0).put("duration", chapter.duration)
            .put("rate", rate).put("sleep", JSONObject().put("mode", sleepMode).put("minutes", sleepMinutes).put("counting", playing).put("remaining", sleepMinutes * 60.0))
    }

    private fun setPlaying(on: Boolean) {
        if (playing == on) return
        anchorMs = now()
        playing = on
        anchorAt = SystemClock.elapsedRealtime()
        emit("state")
    }

    override fun play() = setPlaying(true)
    override fun pause() = setPlaying(false)
    override fun close() = pause()
    override fun toggle() = if (playing) pause() else play()
    override fun skip(deltaSeconds: Double) = move(now() + (deltaSeconds * 1000).toLong())
    override fun seekTo(seconds: Double) = move((seconds * 1000).toLong())
    override fun next() = move(0, chapterIndex + 1)
    override fun previous() = move(0, chapterIndex - 1)
    override fun setRate(rate: Double) { val at = now(); this.rate = rate; move(at) }
    override fun jumpTo(chapterId: Int, seconds: Double) = move((seconds * 1000).toLong(), queue.indexOfFirst { it.id == chapterId }.coerceAtLeast(0))
    override fun load(request: LoadRequest) {}
    override fun positionMs(): Long = now()
    override fun chapters(): List<Playback.Chapter> = queue
    override fun setSleep(mode: String, minutes: Int) { sleepMode = mode; sleepMinutes = minutes; emit("sleep") }
    override fun voiceId(): String = voice
    override fun setVoice(voiceId: String) { voice = voiceId }

    companion object {
        const val BOOK_ID = "native-player-demo"
    }
}
