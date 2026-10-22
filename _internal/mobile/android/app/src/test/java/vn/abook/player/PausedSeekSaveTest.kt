package vn.abook.player

import android.os.Handler
import androidx.media3.common.MediaItem
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Soát a77 #3: tua lúc đang dừng rồi tiến trình bị giết không được trả người nghe về chỗ trước khi tua. */
class PausedSeekSaveTest {
    private val voice = FakeExo()

    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("paused-seek"))
        voice.item = MediaItem.Builder().setMediaId("1").setTag(Playback.BookTag("seek-book")).build()
        voice.duration = 3_600_000
        voice.position = 1_800_000 // đã nghe tới phút 30 rồi dừng
        voice.state = androidx.media3.common.Player.STATE_READY
        Playback.player = voice.player
        field("bookId").set(Playback, "seek-book")
        field("chapters").set(Playback, listOf(Playback.Chapter(1, "Một", "1.mp3", 3600.0)))
        field("savedPlace").set(Playback, 1 to 1_800_000L) // lần lưu lúc dừng
        Store.progress("seek-book", 1, 1800.0, 3600.0)
    }

    @After fun cleanup() {
        field("bookId").set(Playback, "")
        field("chapters").set(Playback, emptyList<Playback.Chapter>())
        field("savedPlace").set(Playback, null)
        Playback.player = null
        Handler.reset()
    }

    private fun savedSeconds() = Store.state("seek-book").getJSONObject("last").getDouble("seconds")

    @Test fun seekingWhilePausedSavesTheNewPlaceAtOnce() {
        assertFalse(voice.playing)
        Playback.seekTo(600.0) // tua về phút 10 bằng app / màn khoá
        assertEquals("process death ngay sau đây vẫn mở lại ở phút 10", 600.0, savedSeconds(), 0.001)
    }

    @Test fun aSeekDiscontinuityWhilePausedSavesToo() {
        voice.position = 300_000 // controller ngoài tua thẳng player (MediaSession)
        Playback.onSeekSettled(androidx.media3.common.Player.DISCONTINUITY_REASON_SEEK)
        assertEquals(300.0, savedSeconds(), 0.001)
        // Chuyển mục tự động (hết chương) không phải tua: không lưu thêm.
        voice.position = 100_000
        Playback.onSeekSettled(androidx.media3.common.Player.DISCONTINUITY_REASON_AUTO_TRANSITION)
        assertEquals(300.0, savedSeconds(), 0.001)
    }

    @Test fun aDiscontinuityWhileLoadingTheQueueDoesNotStampTheOldPlaceOnTheBook() {
        // Nạp cuốn khác: bookId rỗng (adopt) hay chỗ vừa nạp trùng chỗ đã lưu thì không lưu lại (đóng dấu giờ mới lên chỗ cũ).
        field("savedPlace").set(Playback, 1 to 1_800_000L)
        voice.position = 1_800_500
        val before = Store.state("seek-book").getJSONObject("last").getDouble("at")
        Playback.onSeekSettled(androidx.media3.common.Player.DISCONTINUITY_REASON_SEEK)
        assertEquals(before, Store.state("seek-book").getJSONObject("last").getDouble("at"), 0.0)
        assertEquals(1800.0, savedSeconds(), 0.001)
    }
}
