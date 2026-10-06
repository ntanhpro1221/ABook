package vn.abook.player

import android.os.Looper
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.MediaSession
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Màn hình khoá / tai nghe điều khiển loa / TV điện thoại đang phát, trên máy Android THẬT (máy ảo): một MediaController -
 * thứ màn hình khoá, tai nghe Bluetooth, đồng hồ dùng - nói với phiên media của CastPlayer, và loa giả (FakeRenderer, dùng
 * chung với DlnaTest) phải dừng, phát, sang chương thật.
 */
@RunWith(AndroidJUnit4::class)
class CastSessionOnDeviceTest {
    private val cleanups = mutableListOf<() -> Unit>()
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    @After
    fun tearDown() {
        cleanups.reversed().forEach { runCatching(it) }
    }

    private fun <T> until(seconds: Double = 10.0, check: () -> T?): T {
        val deadline = System.currentTimeMillis() + (seconds * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            check()?.takeIf { it != false }?.let { return it }
            Thread.sleep(50)
        }
        fail("hết giờ chờ")
        throw IllegalStateException()
    }

    private fun <T> onMain(work: () -> T): T {
        var out: T? = null
        instrumentation.runOnMainSync { out = work() }
        @Suppress("UNCHECKED_CAST")
        return out as T
    }

    @Test
    fun theLockScreenPausesPlaysAndMovesTheRendererOn() {
        val device = FakeRenderer("TV phòng khách").start().also { cleanups += it::stop }
        val context = instrumentation.targetContext
        val folder = File(context.cacheDir, "cast-session-test").apply { mkdirs() }
        cleanups += { folder.deleteRecursively() }
        val chapters = (1..2).map { id ->
            val file = File(folder, "%05d.mp3".format(id)).apply { writeBytes(ByteArray(40_000 + id) { id.toByte() }) }
            DlnaPlayers.Chapter(id, "Chương $id", 60.0, file)
        }
        val players = DlnaPlayers(
            book = { id -> if (id == "sach") DlnaPlayers.Book("Sách thử", chapters) else null },
            save = { _, _, _, _ -> },
            media = Dlna.Media("127.0.0.1"),
            find = { Dlna.search(400, listOf(device.ssdp), multicast = false) },
        ).apply {
            playingPollMs = 150
            idlePollMs = 200
            graceMs = 1000
        }
        cleanups += players::close
        players.scan()
        val id = until { players.view().takeIf { it.length() > 0 }?.getJSONObject(0)?.getString("id") }
        players.send(id, JSONObject().put("action", "load").put("bookId", "sach").put("chapterId", 1).put("seconds", 0.0))
        until { device.state() == "PLAYING" }

        val player = onMain { CastPlayer(players, Looper.getMainLooper()) }
        val session = onMain { MediaSession.Builder(context, player).setId("cast-test").build() }
        cleanups += { onMain { session.release(); player.release() } }
        val controller = MediaController.Builder(context, session.token).setApplicationLooper(Looper.getMainLooper())
            .buildAsync().get(10, TimeUnit.SECONDS)
        cleanups += { onMain { controller.release() } }
        until { onMain { player.refresh(); controller.isPlaying } }
        assertEquals("Chương 1", onMain { controller.mediaMetadata.title?.toString() })
        assertEquals(2, onMain { controller.mediaItemCount })

        onMain { controller.pause() }
        until { device.state() == "PAUSED_PLAYBACK" }
        onMain { controller.play() }
        until { device.state() == "PLAYING" }
        onMain { controller.seekForward() }
        until { device.position() >= 14 }
        onMain { controller.seekToNext() }
        until { device.calls("SetAVTransportURI").size == 2 }
        until { onMain { player.refresh(); controller.currentMediaItemIndex == 1 && controller.playbackState == Player.STATE_READY } }
        assertEquals("Chương 2", onMain { controller.mediaMetadata.title?.toString() })
    }
}
