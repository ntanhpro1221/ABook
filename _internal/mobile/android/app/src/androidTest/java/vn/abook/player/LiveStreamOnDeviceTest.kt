package vn.abook.player

import android.net.ConnectivityManager
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.Log
import androidx.annotation.OptIn
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.readaloud.Boundary
import vn.abook.player.readaloud.Clip
import vn.abook.player.readaloud.EdgeProtocol
import vn.abook.player.readaloud.EdgeTts
import vn.abook.player.readaloud.LiveClips
import vn.abook.player.readaloud.LiveSink
import vn.abook.player.readaloud.LiveWords
import vn.abook.player.readaloud.SeekPlan
import vn.abook.player.readaloud.Span
import vn.abook.player.readaloud.VoiceException
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/**
 * Đường nối ExoPlayer của Nghe ngay phát LUỒNG clip Edge (uxfix57/58: ReadAloud.onLiveStarted / onLiveBroke, [LiveClipDataSource], bộ tách mp3 tốc độ bit không đổi của
 * [Streaming.liveExtractors]) chạy trên máy thật - test JVM không chạy được ExoPlayer. KHÔNG mở Activity, không cần màn hình bật, không giành AudioFocus, âm lượng 0:
 * ExoPlayer dựng trên HandlerThread riêng (không phải luồng chính), phát `abooklive://<id>` qua [Streaming.mediaSourceFactory] như PlaybackService.
 *  1. Edge THẬT (mạng) đọc một đoạn tự viết ~400 ký tự, [LiveSink] ghi vào [LiveClips]: đo ms tới byte đầu / READY / hết, phát tới ENDED, vị trí cuối ~ độ dài clip thật, số lần
 *     BUFFERING sau READY. Không có mạng thì bỏ qua.
 *  2. Tua trong phần đã ghi khi clip CHƯA xong (feeder giả: mp3 tổng hợp ghi dần nhanh hơn thời gian thực): sau khi có >= 3 giây tiếng, tua về 1 giây rồi tới 2,5 giây -> phát tiếp, không lỗi.
 *  3. Đứt giữa luồng giả lập ([LiveClips.Entry.fail] sau 4,8 giây tiếng, không mạng): phát tới byte cuối đã ghi rồi ENDED, không ném lỗi (uxfix58 e); [LiveWords] + [SeekPlan.resumeWord]
 *     cho ra chữ tiếp đúng (chữ đầu tiên chưa nghe).
 * Mp3 của mục 2-3 là khung tổng hợp (MPEG-2 lớp III 48 kbps 24 kHz đơn kênh, thân khung toàn số 0 = im lặng, hợp lệ cho bộ giải mã): đủ để kiểm đường dữ liệu / tách / tua / hết luồng.
 * Kết quả: logcat (thẻ `ABOOK_LIVE`), `INSTRUMENTATION_STATUS` của am instrument và `files/live-stream/result.json` của app để `adb pull`.
 *
 *   adb shell am instrument -w -e class vn.abook.player.LiveStreamOnDeviceTest com.ngdtuanh.abook.test/androidx.test.runner.AndroidJUnitRunner
 */
@OptIn(UnstableApi::class)
@RunWith(AndroidJUnit4::class)
class LiveStreamOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val dir = File(context.cacheDir, "live-stream-test").apply { mkdirs() }
    private val resultDir = File(context.filesDir, "live-stream").apply { mkdirs() }
    private val harnesses = ArrayList<Harness>()

    @After
    fun cleanUp() {
        harnesses.forEach { it.release() }
        dir.deleteRecursively()
    }

    private fun report(name: String, json: JSONObject) {
        json.put("test", name)
        Log.i(TAG, json.toString())
        instrumentation.sendStatus(0, Bundle().apply { putString("stream", "$TAG $json\n") })
        File(resultDir, "$name.json").writeBytes(json.toString(2).toByteArray()) // LF, không qua write_text của Windows
    }

    /** ExoPlayer không đụng luồng chính: mọi lời gọi qua [onPlayer], mọi sự kiện ghi lại kèm mili giây từ lúc [mark]. */
    private inner class Harness : Player.Listener {
        private val thread = HandlerThread("live-stream-test").also { it.start() }
        private val handler = Handler(thread.looper)
        private val player: ExoPlayer
        @Volatile private var t0 = SystemClock.elapsedRealtime()
        @Volatile var readyAt = -1L
        @Volatile var endedAt = -1L
        @Volatile var rebuffers = 0
        @Volatile var error: PlaybackException? = null
        private val ended = CountDownLatch(1)

        init {
            player = onPlayer {
                ExoPlayer.Builder(context)
                    .setLooper(thread.looper)
                    .setMediaSourceFactory(Streaming.mediaSourceFactory(context))
                    .build()
                    .also {
                        it.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_SPEECH).build(), false) // không giành AudioFocus
                        it.volume = 0f
                        it.addListener(this)
                    }
            }
            harnesses += this
        }

        fun mark() {
            t0 = SystemClock.elapsedRealtime()
        }

        fun now() = SystemClock.elapsedRealtime() - t0

        fun <T> onPlayer(block: () -> T): T {
            val out = AtomicReference<Result<T>>()
            val latch = CountDownLatch(1)
            handler.post {
                out.set(runCatching(block))
                latch.countDown()
            }
            assertTrue("luồng ExoPlayer đứng", latch.await(30, TimeUnit.SECONDS))
            return out.get().getOrThrow()
        }

        fun play(uri: String) = onPlayer {
            player.setMediaItem(MediaItem.fromUri(uri))
            player.prepare()
            player.playWhenReady = true
        }

        fun position(): Long = onPlayer { player.currentPosition }
        fun duration(): Long = onPlayer { player.duration }
        fun state(): Int = onPlayer { player.playbackState }
        fun seekTo(ms: Long) = onPlayer { player.seekTo(ms) }

        /** Chờ ENDED (hay lỗi) tối đa `ms`. */
        fun awaitEnd(ms: Long): Boolean = ended.await(ms, TimeUnit.MILLISECONDS)

        fun awaitPosition(atLeastMs: Long, timeoutMs: Long): Boolean {
            val end = SystemClock.elapsedRealtime() + timeoutMs
            while (SystemClock.elapsedRealtime() < end) {
                if (error != null || endedAt >= 0) return position() >= atLeastMs
                if (position() >= atLeastMs) return true
                Thread.sleep(25)
            }
            return false
        }

        fun release() {
            runCatching { onPlayer { player.release() } }
            thread.quitSafely()
        }

        override fun onPlaybackStateChanged(state: Int) {
            val at = now()
            when (state) {
                Player.STATE_READY -> if (readyAt < 0) readyAt = at
                Player.STATE_BUFFERING -> if (readyAt >= 0) rebuffers++
                Player.STATE_ENDED -> {
                    endedAt = at
                    ended.countDown()
                }
            }
        }

        override fun onPlayerError(error: PlaybackException) {
            this.error = error
            ended.countDown()
        }
    }

    /** Mp3 hợp lệ tổng hợp: `count` khung MPEG-2 lớp III 48 kbps 24 kHz đơn kênh (144 byte = 24 ms), thân toàn 0. */
    private fun frames(count: Int): ByteArray {
        val out = ByteArray(count * FRAME)
        for (i in 0 until count) {
            val at = i * FRAME
            out[at] = 0xFF.toByte(); out[at + 1] = 0xF3.toByte(); out[at + 2] = 0x64; out[at + 3] = 0xC0.toByte()
        }
        return out
    }

    /** Ghi `count` khung vào `file` theo từng `chunk` khung, nghỉ `pauseMs` giữa các lần; sau mỗi lần ghi + flush gọi `grew(tổng byte)`. Chạy ở luồng riêng, gọi `then` khi ghi xong. */
    private fun feed(file: File, count: Int, chunk: Int, pauseMs: Long, grew: (Long) -> Unit, then: () -> Unit): Thread = Thread {
        FileOutputStream(file).use { stream ->
            var total = 0L
            var left = count
            while (left > 0) {
                val n = minOf(chunk, left)
                stream.write(frames(n))
                stream.flush()
                total += n * FRAME
                left -= n
                grew(total)
                if (left > 0) Thread.sleep(pauseMs)
            }
        }
        then()
    }.also { it.start() }

    private fun hasNetwork(): Boolean {
        val manager = context.getSystemService(ConnectivityManager::class.java)
        return manager?.activeNetwork != null
    }

    // ---- 1. Edge thật --------------------------------------------------------------------------------------------------------------

    /** [LiveSink] của bài thử: ghi vào [LiveClips] như ReadAloud (qua LiveWords), nhớ lúc byte đầu về. */
    private class RealSink(private val entry: LiveClips.Entry, private val now: () -> Long) : LiveSink {
        val firstByte = CountDownLatch(1)
        val firstByteMs = AtomicLong(-1)
        override fun grew(file: File, totalBytes: Long) {
            entry.grew(file, totalBytes)
            if (firstByteMs.compareAndSet(-1, now())) firstByte.countDown()
        }
        override fun boundaries(found: List<Boundary>) {}
        override fun done(clip: Clip) = entry.finish(clip.file.length())
        override fun failed(error: Exception) {
            entry.fail(error)
            firstByte.countDown() // lỗi trước byte đầu: người chờ không đợi mãi
        }
    }

    @Test
    fun edgeStreamsAParagraphIntoExoPlayerAndPlaysToTheEnd() {
        assumeTrue("không có mạng", hasNetwork())
        val text = "Sáng nay trời trong, nắng vàng trải trên mái ngói. Lan mở cửa sổ, hít một hơi thật sâu rồi mỉm cười với khoảng sân nhỏ. " +
            "Ngoài ngõ, tiếng rao bánh mì vang lên đều đều, hoà cùng tiếng chim hót trên cành xoan trước hiên nhà. " +
            "Cô pha một ấm trà nóng, ngồi xuống bên bậu cửa, nghĩ về những việc cần làm trong ngày hôm nay."
        val harness = Harness()
        val entry = LiveClips.create()
        val out = File(dir, "edge.mp3")
        val sink = RealSink(entry, harness::now)
        val result = AtomicReference<Result<Clip>>()
        val finished = CountDownLatch(1)
        harness.mark()
        Thread {
            result.set(runCatching { EdgeTts("vi-VN-HoaiMyNeural").synthesize(text, out, sink) })
            finished.countDown()
        }.also { it.start() }
        assertTrue("không có byte đầu trong 45 giây", sink.firstByte.await(45, TimeUnit.SECONDS))
        if (sink.firstByteMs.get() < 0) { // lỗi trước khi có byte nào
            val error = result.get()?.exceptionOrNull() ?: (entry.failure)
            assumeTrue("không nối được Edge: $error", !(error is VoiceException && error.offline) && error !is java.io.IOException)
            throw AssertionError("Edge hỏng trước byte đầu: $error")
        }
        harness.play(LiveClips.uri(entry.id)) // như onLiveStarted: phát ngay khi byte đầu về, clip chưa xong
        assertTrue("clip phát luồng hết trong 90 giây", harness.awaitEnd(90_000))
        assertTrue("Edge chưa trả hết", finished.await(10, TimeUnit.SECONDS))
        val clip = result.get().getOrThrow()
        assertNull("ExoPlayer lỗi: ${harness.error}", harness.error)
        assertEquals(Player.STATE_ENDED, harness.state())
        val position = harness.position()
        val duration = harness.duration()
        report("edge", JSONObject()
            .put("chars", text.length)
            .put("clipBytes", clip.file.length()).put("clipMs", clip.durationMs)
            .put("firstByteMs", sink.firstByteMs.get()).put("readyMs", harness.readyAt).put("endedMs", harness.endedAt)
            .put("rebuffersAfterReady", harness.rebuffers)
            .put("finalPositionMs", position).put("playerDurationMs", duration))
        assertTrue("READY phải tới sau byte đầu", harness.readyAt >= sink.firstByteMs.get())
        assertTrue("vị trí cuối $position lệch độ dài clip ${clip.durationMs}", kotlin.math.abs(position - clip.durationMs) <= 300)
    }

    // ---- 2. Tua khi clip chưa xong -------------------------------------------------------------------------------------------------

    @Test
    fun seekingInsideWhatIsWrittenWhileTheClipIsStillGrowingKeepsPlaying() {
        val harness = Harness()
        val entry = LiveClips.create()
        val file = File(dir, "grow.mp3")
        val total = 300 // 7,2 giây tiếng
        val started = CountDownLatch(1)
        // 5 khung (120 ms tiếng) mỗi 60 ms: nhanh gấp đôi thời gian thực, nên clip xong sau 3,6 giây, lúc người nghe mới nghe tới ~giữa.
        val feeder = feed(file, total, 5, 60, { written ->
            entry.grew(file, written)
            started.countDown()
        }, { entry.finish(total * FRAME.toLong()) })
        assertTrue(started.await(5, TimeUnit.SECONDS))
        harness.mark()
        harness.play(LiveClips.uri(entry.id))
        val end = SystemClock.elapsedRealtime() + 8_000
        while (entry.written() < 3_000 * BYTES_PER_MS && SystemClock.elapsedRealtime() < end) Thread.sleep(10)
        assertTrue("chưa có 3 giây tiếng", entry.written() >= 3_000 * BYTES_PER_MS)
        assertTrue("chưa phát tới 1,5 giây", harness.awaitPosition(1_500, 8_000))
        val doneBeforeSeek = entry.done
        harness.seekTo(1_000)
        val back = harness.awaitPosition(1_500, 8_000) // sau khi tua về 1 s phải chạy tiếp qua 1,5 s
        val afterBack = harness.position()
        var forward = false
        var doneBeforeForward = true
        if (harness.error == null && harness.endedAt < 0) {
            doneBeforeForward = entry.done
            harness.seekTo(2_500)
            forward = harness.awaitPosition(3_000, 8_000)
        }
        assertTrue("hết giờ chờ ENDED", harness.awaitEnd(30_000))
        feeder.join(5_000)
        assertNull("ExoPlayer lỗi: ${harness.error}", harness.error)
        val position = harness.position()
        report("seek", JSONObject()
            .put("doneBeforeBackSeek", doneBeforeSeek).put("playedOnAfterBackSeek", back).put("positionAfterBackSeek", afterBack)
            .put("doneBeforeForwardSeek", doneBeforeForward).put("playedOnAfterForwardSeek", forward)
            .put("rebuffersAfterReady", harness.rebuffers).put("finalPositionMs", position).put("clipMs", total * 24L))
        assertFalse("tua về 1 s lúc clip đã xong - bài thử không kiểm được điều cần kiểm", doneBeforeSeek)
        assertTrue("sau tua về 1 s không chạy tiếp", back)
        assertTrue("sau tua tới 2,5 s không chạy tiếp (clip xong trước lúc tua: $doneBeforeForward)", forward)
        assertEquals((total * 24L).toDouble(), position.toDouble(), 300.0)
    }

    // ---- 3. Đứt giữa luồng ---------------------------------------------------------------------------------------------------------

    @Test
    fun aClipThatBreaksMidStreamPlaysToTheLastWrittenByteThenEndsWithoutAnError() {
        val harness = Harness()
        val entry = LiveClips.create()
        val file = File(dir, "broken.mp3")
        val cut = 200 // 4,8 giây tiếng rồi đứt
        val text = "một hai ba bốn năm sáu bảy tám chín mười mười_một mười_hai"
        val heard = ArrayList<Long>()
        var tempWords: List<Span> = emptyList()
        // Chỗ nhận như ReadAloud.LiveJob: clip lớn dần vào entry, mốc chữ tạm + chỗ nghe tới do LiveWords báo.
        val target = object : LiveClips.Target {
            override fun accepting() = true
            override fun grew(file: File, total: Long) = entry.grew(file, total)
            override fun words(words: List<Span>, durationMs: Long, heardMs: Long) {
                tempWords = words
                heard += heardMs
            }
            override fun done(total: Long) = entry.finish(total)
            override fun failed(error: Exception) = entry.fail(error)
        }
        val live = LiveWords(text, { it }, target, clock = { 0L })
        val started = CountDownLatch(1)
        val feeder = feed(file, cut, 5, 40, { written ->
            live.grew(file, written)
            started.countDown()
        }, {
            // 9 chữ đầu có mốc thật (mỗi chữ 500 ms, kết thúc 450 ms sau khi bắt đầu), rồi đứt: 3 chữ cuối chưa có mốc.
            live.boundaries((0 until 9).map { Boundary(it * 500L, it * 500L + 450, text.split(' ')[it]) })
            live.failed(VoiceException("Mất mạng giữa chừng", offline = true))
        })
        assertTrue(started.await(5, TimeUnit.SECONDS))
        harness.mark()
        harness.play(LiveClips.uri(entry.id))
        assertTrue("hết giờ chờ ENDED", harness.awaitEnd(30_000))
        feeder.join(5_000)
        assertNull("clip đứt giữa chừng không được làm ExoPlayer lỗi: ${harness.error}", harness.error)
        assertEquals(Player.STATE_ENDED, harness.state())
        assertNull(entry.failure?.takeIf { it !is VoiceException })
        assertFalse("clip hỏng không được tính là xong", entry.done)
        val position = harness.position()
        val receivedMs = EdgeProtocol.durationMs(entry.written())
        // Chữ tiếp: như ReadAloud.onLiveBroke - chữ đầu tiên chưa nghe hết, theo chỗ đã nghe tới (không quá phần âm thanh đã về).
        val heardMs = minOf(heard.lastOrNull() ?: 0L, receivedMs)
        val resume = SeekPlan.resumeWord(tempWords, heardMs, 0)
        report("break", JSONObject()
            .put("writtenBytes", entry.written()).put("receivedMs", receivedMs).put("finalPositionMs", position)
            .put("endedMs", harness.endedAt).put("heardMs", heardMs).put("tempWords", tempWords.size).put("resumeWord", resume))
        assertEquals("phát tới byte cuối đã ghi", (cut * 24L).toDouble(), position.toDouble(), 300.0)
        assertEquals(cut * FRAME.toLong(), entry.written())
        assertEquals(12, tempWords.size)
        assertEquals(4_450L, heardMs)
        assertEquals("chữ đầu tiên chưa nghe", 9, resume)
    }

    private companion object {
        const val TAG = "ABOOK_LIVE"
        const val FRAME = 144
        /** 48 kbps = 6 byte mỗi mili giây. */
        const val BYTES_PER_MS = 6L
    }
}
