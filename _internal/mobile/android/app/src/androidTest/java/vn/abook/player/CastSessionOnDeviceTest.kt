package vn.abook.player

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.media.session.PlaybackState
import android.os.Looper
import androidx.media3.common.DeviceInfo
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.MediaSession
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Màn hình khoá / tai nghe điều khiển loa / TV điện thoại đang phát, trên máy Android THẬT (máy ảo): một MediaController -
 * thứ màn hình khoá, tai nghe Bluetooth, đồng hồ dùng - nói với phiên media của CastPlayer, và loa giả (FakeRenderer, dùng
 * chung với DlnaTest) phải dừng, phát, sang chương thật; phím âm lượng (thanh âm lượng màn hình khoá) chỉnh loa / TV. Loa /
 * TV máy tính phát (mã "cast:") đi cùng phiên ấy: lệnh tới đúng mã ấy.
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

    private val context get() = instrumentation.targetContext

    /** Loa giả đang phát chương 1 của "Sách thử" do điện thoại tự phát. */
    private fun casting(device: FakeRenderer): DlnaPlayers {
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
        return players
    }

    /** Phiên media của CastPlayer như CastService gắn, và một MediaController nói với nó như màn hình khoá. */
    private fun session(source: CastSource): Triple<CastPlayer, MediaSession, MediaController> {
        val player = onMain { CastPlayer(source, Looper.getMainLooper()) }
        val session = onMain { MediaSession.Builder(context, player).setId("cast-test").build() }
        cleanups += { onMain { session.release(); player.release() } }
        val controller = MediaController.Builder(context, session.token).setApplicationLooper(Looper.getMainLooper())
            .buildAsync().get(10, TimeUnit.SECONDS)
        cleanups += { onMain { controller.release() } }
        return Triple(player, session, controller)
    }

    @Test
    fun theLockScreenPausesPlaysAndMovesTheRendererOn() {
        val device = FakeRenderer("TV phòng khách").start().also { cleanups += it::stop }
        val players = casting(device)
        val (player, _, controller) = session(players)
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

    @Test
    fun theVolumeKeysMoveTheRendererVolume() {
        val device = FakeRenderer("TV phòng khách").start().also { cleanups += it::stop }
        val players = casting(device).apply { volumeEveryMs = 200 }
        val (player, session, controller) = session(players)
        until { onMain { player.refresh(); controller.deviceInfo.playbackType == DeviceInfo.PLAYBACK_TYPE_REMOTE } }
        assertEquals(30, onMain { controller.deviceVolume })
        assertEquals(100, onMain { controller.deviceInfo.maxVolume })
        onMain { controller.setDeviceVolume(50, 0) }
        until { device.volume == 50 }
        until { onMain { player.refresh(); controller.deviceVolume == 50 } }
        onMain { controller.increaseDeviceVolume(0) }
        until { device.volume == 55 }

        // Phím âm lượng thật và thanh âm lượng màn hình khoá đi qua phiên của hệ thống (VolumeProvider), không qua Media3.
        val platform = onMain { android.media.session.MediaController(context, session.platformToken) }
        val remote = android.media.session.MediaController.PlaybackInfo.PLAYBACK_TYPE_REMOTE
        until { onMain { player.refresh(); platform.playbackInfo?.playbackType == remote } }
        assertEquals(100, onMain { platform.playbackInfo!!.maxVolume })
        until { onMain { player.refresh(); platform.playbackInfo!!.currentVolume == 55 } }
        onMain { platform.adjustVolume(AudioManager.ADJUST_RAISE, 0) }
        until { device.volume == 60 }
        onMain { platform.setVolumeTo(20, 0) }
        until { device.volume == 20 }
        device.volume = 33 // vặn trên điều khiển TV: màn hình khoá theo
        until { onMain { player.refresh(); controller.deviceVolume == 33 } }
    }

    @Test
    fun aRendererWithoutVolumeControlKeepsThePhoneVolume() {
        val device = FakeRenderer("Loa cũ", volumeControl = false).start().also { cleanups += it::stop }
        val players = casting(device).apply { volumeEveryMs = 100 }
        val (player, session, controller) = session(players)
        until { onMain { player.refresh(); controller.isPlaying } }
        Thread.sleep(300)
        assertEquals(DeviceInfo.PLAYBACK_TYPE_LOCAL, onMain { player.refresh(); controller.deviceInfo.playbackType })
        val platform = onMain { android.media.session.MediaController(context, session.platformToken) }
        val local = android.media.session.MediaController.PlaybackInfo.PLAYBACK_TYPE_LOCAL
        assertEquals(local, onMain { platform.playbackInfo!!.playbackType })
        assertTrue(device.calls("SetVolume").isEmpty())
    }

    /** Như /sync/v1/cast của máy tính trả: loa / TV máy tính đang phát chương 2. */
    private fun computerEntry() = JSONObject().put("id", "abc123").put("name", "TV máy tính").put("age", 0.0).put("state", JSONObject()
        .put("bookId", "sach").put("bookTitle", "Sách thử").put("chapterId", 2).put("chapterTitle", "Chương 2")
        .put("position", 5.0).put("duration", 60.0).put("playing", true).put("buffering", false))

    @Test
    fun theLockScreenControlsABookTheComputerCasts() {
        val entry = computerEntry() // ComputerCasts biến thành bản chụp
        val chapters = (1..3).map { CastChapter(it, "Chương $it", 60.0) }
        val sent = mutableListOf<Pair<String, String>>()
        val source = object : CastSource {
            override fun now() = ComputerCasts.snapshot(entry, chapters, 0)

            override fun send(id: String, command: JSONObject): Any? = synchronized(sent) { sent += id to command.toString() }

            override fun end(id: String) {
                synchronized(sent) { sent += id to "end" }
            }
        }
        val (player, session, controller) = session(source)
        until { onMain { player.refresh(); controller.isPlaying } }
        assertEquals("Chương 2", onMain { controller.mediaMetadata.title?.toString() })
        assertEquals(3, onMain { controller.mediaItemCount })
        assertEquals("máy tính không chỉnh âm lượng loa / TV: phím âm lượng chỉnh điện thoại", DeviceInfo.PLAYBACK_TYPE_LOCAL,
            onMain { controller.deviceInfo.playbackType })
        val platform = onMain { android.media.session.MediaController(context, session.platformToken) }
        until { onMain { platform.playbackState?.state == PlaybackState.STATE_PLAYING } }
        onMain { controller.pause() }
        onMain { controller.seekToNext() }
        onMain { controller.seekBack() }
        onMain { controller.stop() }
        val got = until { synchronized(sent) { sent.toList().takeIf { it.size >= 4 } } }
        assertTrue("mọi lệnh tới đúng loa / TV máy tính: $got", got.all { it.first == "cast:abc123" })
        assertEquals("pause", JSONObject(got[0].second).getString("action"))
        assertEquals("next", JSONObject(got[1].second).getString("action"))
        assertEquals(-15.0, JSONObject(got[2].second).getDouble("seconds"), 1e-9)
        assertEquals("end", got[3].second)
    }

    @Suppress("DEPRECATION") // getRunningServices vẫn trả dịch vụ của chính app
    private fun serviceRunning(): Boolean = (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager)
        .getRunningServices(100).any { it.service.className == CastService::class.java.name }

    @Test
    fun theComputerCastSessionLivesOnlyWhileTheComputerPlays() {
        cleanups += {
            ComputerCasts.observe(context, JSONArray())
            context.stopService(Intent(context, CastService::class.java))
        }
        // Thanh "Đang phát trên…" của loa / TV máy tính hiện (RemotePlayers.all vừa hỏi): dịch vụ + phiên media bật.
        ComputerCasts.observe(context, JSONArray().put(computerEntry()))
        until { serviceRunning() }
        Thread.sleep(1500) // lượt xem lại đầu tiên đã chạy: còn phiên máy tính nên dịch vụ ở lại
        assertTrue(serviceRunning())
        assertEquals("cast:abc123", CastSessions.now()?.id)
        // Máy tính hết phát (bấm "Nghe ở đây", thiết bị rảnh): dịch vụ tự tắt, không hỏi máy tính nữa.
        ComputerCasts.observe(context, JSONArray().put(computerEntry().put("state", JSONObject.NULL)))
        assertEquals(null, CastSessions.now())
        until(12.0) { !serviceRunning() }
    }
}
