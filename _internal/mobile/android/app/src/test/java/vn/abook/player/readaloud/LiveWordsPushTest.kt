package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/**
 * Mốc chữ tạm của clip phát luồng trên điện thoại ([LiveWords]) theo máy tính (`service.py` `_Live`): đẩy cả khi tiếng về thêm, và đẩy nốt mốc đang chờ trước khi báo hỏng
 * (uxfix60, soát a59p) - clip đứt thì chỗ "đã nghe tới" ([SeekPlan.resumeWord]) là mốc mới nhất, phần nối không đọc lặp thêm chữ.
 */
class LiveWordsPushTest {
    private class Recorder : LiveClips.Target {
        val events = ArrayList<String>()
        val heard = ArrayList<Long>()
        override fun accepting() = true
        override fun grew(file: File, total: Long) {}
        override fun words(words: List<Span>, durationMs: Long, heardMs: Long) {
            heard += heardMs
            events += "words:$heardMs"
        }
        override fun done(total: Long) { events += "done" }
        override fun failed(error: Exception) { events += "failed" }
    }

    @Test
    fun pendingWordsReachTheListenerBeforeTheClipIsReportedBroken() {
        var now = 0L
        val recorder = Recorder()
        val live = LiveWords("Một hai ba bốn", { it }, recorder, clock = { now })
        live.grew(File("x.mp3"), 12_000)
        live.boundaries(listOf(Boundary(0, 400, "Một")))
        now = 100_000_000L // 0,1 giây sau: mốc mới nằm chờ (chưa đủ 0,5 giây)
        live.boundaries(listOf(Boundary(450, 800, "hai"), Boundary(850, 1_200, "ba")))
        live.failed(VoiceException("Mất kết nối giữa chừng", reason = "service"))
        // Chỗ đã nghe tới mới nhất (1200) được báo TRƯỚC lời hỏng, như `done` đã làm (trước uxfix60: [words:400, failed]).
        assertEquals(listOf("words:400", "words:1200", "failed"), recorder.events)
    }

    @Test
    fun tentativeWordsCatchUpWhenAudioKeepsComingWithoutNewBoundaries() {
        var now = 0L
        val recorder = Recorder()
        val live = LiveWords("Một hai ba bốn", { it }, recorder, clock = { now })
        live.grew(File("x.mp3"), 3_000)
        live.boundaries(listOf(Boundary(0, 400, "Một")))
        now = 100_000_000L
        live.boundaries(listOf(Boundary(450, 800, "hai")))
        now = 700_000_000L // 0,7 giây: chỉ có tiếng về thêm (mảnh kế đã có mốc từ trước) - máy tính đẩy ở đây (_Live.audio -> _tell)
        live.grew(File("x.mp3"), 12_000)
        assertEquals(listOf(400L, 800L), recorder.heard)
    }
}
