package vn.abook.player

import android.os.SystemClock
import androidx.media3.exoplayer.ExoPlayer
import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.ui.music.library.AndroidLibrarySource
import vn.abook.player.ui.music.library.ExoPreviewPlayer
import java.io.File
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(AndroidJUnit4::class)
class MusicPreviewOnDeviceTest {
    private val inst = InstrumentationRegistry.getInstrumentation()
    private val context = inst.targetContext

    @Test fun realSourcesAndFailedPrimaryReachAudioOutput() {
        val monitor = inst.addMonitor("vn.abook.player.ui.NativeActivity", null, false)
        context.startActivity(Intent().setClassName(context.packageName, "vn.abook.player.ui.NativeActivity")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        assertNotNull(monitor.waitForActivityWithTimeout(10000))
        inst.removeMonitor(monitor)
        SystemClock.sleep(1000)
        val source = AndroidLibrarySource(context)
        val index = source.load()
        val jungle = "https://prod-1.storage.jamendo.com/?trackid=2269875&format=mp32"
        val tracks = listOf(jungle) + listOf("incompetech", "freesound").map { host ->
            index.tracks.first { it.link.contains(host) }.link
        }
        val report = JSONArray()
        for (link in tracks) {
            val track = index.byLink.getValue(link)
            val row = JSONObject().put("source", link).put("start", track.audibleStart)
            val ready = CountDownLatch(1)
            var error = ""
            lateinit var player: ExoPreviewPlayer
            val begin = SystemClock.elapsedRealtime()
            inst.runOnMainSync {
                player = ExoPreviewPlayer(context, source)
                player.play(link, track.audibleStart, 0.2f, {}, { if (it) ready.countDown() }, { error = it; ready.countDown() })
            }
            try {
                assertTrue("Source did not finish loading: $link", ready.await(50, TimeUnit.SECONDS))
                row.put("readyMs", SystemClock.elapsedRealtime()-begin).put("error", error)
                assertEquals("Cannot play $link", "", error)
                SystemClock.sleep(1000)
                inst.runOnMainSync {
                    val field = ExoPreviewPlayer::class.java.getDeclaredField("player").apply { isAccessible = true }
                    val output = field.get(player) as ExoPlayer
                    val buffers = output.audioDecoderCounters?.renderedOutputBufferCount ?: 0
                    row.put("positionMs", output.currentPosition).put("renderedAudioBuffers", buffers)
                        .put("usage", output.audioAttributes.usage).put("contentType", output.audioAttributes.contentType).put("volume", output.volume)
                    assertTrue("Audio output did not advance", output.currentPosition > track.audibleStart * 1000 + 100)
                    assertTrue("No decoded audio reached the renderer", buffers > 0)
                }
            } finally {
                inst.runOnMainSync { player.stop() }; report.put(row)
                File(context.getExternalFilesDir(null), "music-preview.json").writeText(report.toString(2))
            }
        }
        // Real HTTP 503 then the signed mirror: no mock player or prepared callback.
        val socket = ServerSocket(0)
        val requested = CountDownLatch(1)
        val server = Thread {
            socket.accept().use { client ->
                client.getInputStream().bufferedReader().readLine()
                client.getOutputStream().write("HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
                requested.countDown()
            }
        }.apply { isDaemon = true; start() }
        val ready = CountDownLatch(1)
        var error = ""
        lateinit var player: ExoPreviewPlayer
        inst.runOnMainSync {
            player = ExoPreviewPlayer(context, source) { listOf("http://127.0.0.1:${socket.localPort}/bad.mp3", "https://archive.org/download/abook-music-jamendo-cc-by-3.0/8c0b41be-ef88-410c-ab89-4990562a4e4e.mp3") }
            player.play(jungle, 3.434, 0.2f, {}, { if (it) ready.countDown() }, { error=it; ready.countDown() })
        }
        try {
            assertTrue("Primary must receive the real HTTP request", requested.await(10, TimeUnit.SECONDS))
            assertTrue(ready.await(50, TimeUnit.SECONDS))
            assertEquals("Mirror failed", "", error)
            report.put(JSONObject().put("case", "503 then mirror").put("error", error))
        } finally {
            inst.runOnMainSync { player.stop() }
            socket.close()
            File(context.getExternalFilesDir(null), "music-preview.json").writeText(report.toString(2))
        }
    }
}
