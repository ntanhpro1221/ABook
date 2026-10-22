package vn.abook.player.readaloud

import android.os.Handler
import androidx.media3.exoplayer.ExoPlayer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.BookEditsFixtures
import vn.abook.player.Playback
import vn.abook.player.Store
import java.lang.reflect.Proxy

/**
 * Soát a77 #2: đọc to không được tự phát lại sau lệnh tạm dừng. Hai đường: (1) chữ chương về muộn (lấy từ máy tính) sau khi người nghe đã bấm dừng; (2) hệ thống đổi
 * playWhenReady (rút tai nghe, mất focus hẳn) trong lúc ReadAloud đang chờ đoạn đầu - `waiting.play` phải theo.
 */
class PauseWhileWaitingTest {
    private class Voice {
        var playWhenReady = false
        val player: ExoPlayer = Proxy.newProxyInstance(ExoPlayer::class.java.classLoader, arrayOf(ExoPlayer::class.java)) { proxy, method, args ->
            when (method.name) {
                "setPlayWhenReady" -> { playWhenReady = args!![0] as Boolean; null }
                "getPlayWhenReady" -> playWhenReady
                "play" -> { playWhenReady = true; null }
                "pause" -> { playWhenReady = false; null }
                "equals" -> args!![0] === proxy
                "hashCode" -> System.identityHashCode(this)
                "toString" -> "FakeVoice"
                else -> when (method.returnType) {
                    java.lang.Boolean.TYPE -> false
                    java.lang.Integer.TYPE -> 0
                    java.lang.Long.TYPE -> 0L
                    java.lang.Float.TYPE -> 0f
                    else -> null
                }
            }
        } as ExoPlayer
    }

    private fun field(owner: Class<*>, name: String) = owner.getDeclaredField(name).also { it.isAccessible = true }
    private val voice = Voice()

    @Before fun setup() {
        Handler.reset()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, BookEditsFixtures.tempDir("pause-waiting"))
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        Playback.player = voice.player
        field(Playback::class.java, "bookId").set(Playback, "streamed-book")
        field(Playback::class.java, "chapters").set(Playback, listOf(Playback.Chapter(1, "Một", "", 0.0, text = "texts/1.txt")))
        field(ReadAloud::class.java, "context").set(ReadAloud, FakeContext())
        // Bài này không bàn chuyện đồng ý gửi chữ đi (ConsentHoldTest): giọng Edge mặc định đã được đồng ý.
        ReadAloud.choices = VoiceChoices(java.io.File(BookEditsFixtures.tempDir("pause-waiting-choices"), "readaloud-voices.json")).also { it.allowOnline(listOf("edge")) }
    }

    @After fun cleanup() {
        field(ReadAloud::class.java, "waiting").set(ReadAloud, null)
        field(ReadAloud::class.java, "context").set(ReadAloud, null)
        ReadAloud.choices = null
        field(Playback::class.java, "bookId").set(Playback, "")
        field(Playback::class.java, "chapters").set(Playback, emptyList<Playback.Chapter>())
        Playback.player = null
        Handler.reset()
    }

    /** Context chỉ là phép kiểm "có". Lượt lấy chữ ở luồng nền (Streaming.fetchSmall) hỏi nó trước tiên: giữ luồng ấy ở đây tối đa 20 giây để lời gọi "chữ về" do bài thử tự gọi,
     *  không bị lượt nền thất bại chen vào trước. */
    private class FakeContext : android.content.ContextWrapper(null) {
        override fun getApplicationContext(): android.content.Context {
            java.util.concurrent.CountDownLatch(1).await(20, java.util.concurrent.TimeUnit.SECONDS)
            throw IllegalStateException("không có máy tính")
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun textWaits() = field(ReadAloud::class.java, "textWaits").get(ReadAloud) as HashMap<String, (Boolean) -> Unit>

    @Test fun textArrivingAfterThePauseDoesNotStartThePlaybackAgain() {
        ReadAloud.startAt(0, 0, play = true) // chương chữ mà máy này chưa có chữ: đứng chờ lấy chữ từ máy tính
        assertEquals("chờ chữ", 1, textWaits().size)
        assertTrue(ReadAloud.wantsPlay())
        ReadAloud.onPause() // người nghe bấm dừng lúc chờ (Playback.pause cũng đặt playWhenReady = false)
        voice.playWhenReady = false
        textWaits().values.single().invoke(true) // chữ về (lượt nền còn bị giữ ở FakeContext)
        assertFalse("chữ về muộn không được tự phát lại", voice.playWhenReady)
        assertFalse(ReadAloud.wantsPlay())
    }

    @Test fun systemPausesWhileWaitingForTheFirstSegmentAreNotUndone() {
        ReadAloud.startAt(0, 0, play = true)
        assertTrue(voice.playWhenReady)
        voice.playWhenReady = false // rút tai nghe: ExoPlayer tự đặt playWhenReady = false
        ReadAloud.onPlayWhenReadyChanged(false, userRequested = false)
        assertFalse("đoạn tới rồi deliver() không được bật lại", ReadAloud.wantsPlay())
        // Sự kiện do chính lệnh của người nghe (userRequested) không tự đổi ý: ý phát đi qua onPlay / onPause.
        ReadAloud.onPlayWhenReadyChanged(true, userRequested = true)
        assertFalse(ReadAloud.wantsPlay())
        // Hệ thống tự bật lại (controller ngoài) thì theo.
        ReadAloud.onPlayWhenReadyChanged(true, userRequested = false)
        assertTrue(ReadAloud.wantsPlay())
    }

    @Test fun aTransientFocusLossThatKeepsPlayWhenReadyStillResumesBySelf() {
        ReadAloud.startAt(0, 0, play = true)
        // Mất focus tạm thời: Media3 giữ playWhenReady = true (chỉ chặn phát), nên không có sự kiện đổi ý - ý phát còn nguyên.
        assertTrue(ReadAloud.wantsPlay())
        assertTrue(voice.playWhenReady)
    }
}
