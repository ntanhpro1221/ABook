package vn.abook.player

import android.content.Context
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.annotation.OptIn
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.PI
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sin

/** PLAN_loop §46.27: silent, activity-free playback; measure first isPlaying -> STATE_ENDED.
 * Args: durS (positive whole seconds, default 600), runid (optional safe filename).
 * Private files/playdur/<runid>.txt contains metadata, 10-second samples and final result.
 * No timing verdict here: the host script applies the duration-scaled thresholds.
 */
@OptIn(UnstableApi::class)
@RunWith(AndroidJUnit4::class)
class PlaybackDurationOnDeviceTest {
    @Test
    fun playbackDuration() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val args = InstrumentationRegistry.getArguments()
        val durS = (args.getString("durS") ?: "600").toLong()
        // RIFF's 32-bit size includes 36 bytes in addition to PCM data.
        require(durS in 1..((0xffffffffL - 36) / (44100 * 2)))
        val runid = args.getString("runid") ?: "${System.currentTimeMillis()}_${UUID.randomUUID()}"
        require(runid.matches(Regex("[A-Za-z0-9_-]{1,100}")))
        val dir = File(context.filesDir, "playdur").apply { mkdirs() }
        val result = File(dir, "$runid.txt")
        val wav = File(dir, "$runid.wav")
        require(!result.exists() && !wav.exists()) { "runid already exists: $runid" }
        val out = result.bufferedWriter(Charsets.UTF_8)
        fun log(line: String) {
            Log.i("ABOOK_DUR", line)
            out.write(line)
            out.newLine()
            out.flush()
        }
        fun sec(value: Double) = String.format(Locale.ROOT, "%.9f", value)
        val done = CountDownLatch(1)
        val handler = Handler(Looper.getMainLooper())
        var player: ExoPlayer? = null
        // These are owned by the main looper; read only after onMain synchronization below.
        var startNs: Long? = null
        var endNs: Long? = null
        var failure: String? = null
        var completed = false
        var poll: Runnable? = null
        fun <T> onMain(block: () -> T): T = SeamTestSupport.onMain(instrumentation, block)
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            log("runid=$runid")
            log("dur_s=$durS")
            log("sample_count=${44100L * durS}")
            log("source_sample_rate=44100")
            log("source_channels=1")
            log("source_pcm_bits=16")
            log("source_frequency_hz=440")
            log("source_peak_dbfs=-30")
            log("player_volume=0.0")
            log("model=${Build.MODEL}")
            log("manufacturer=${Build.MANUFACTURER}")
            log("fingerprint=${Build.FINGERPRINT}")
            log("is_emulator=${Build.FINGERPRINT.startsWith("generic") || Build.HARDWARE in listOf("goldfish", "ranchu") || Build.MODEL.contains("Emulator", true) || Build.MODEL.contains("sdk_gphone", true)}")
            log("output_sample_rate=${audioManager.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE) ?: "unknown"}")
            log("audio_track_timestamp=unavailable (no private AudioTrack reflection)")
            writeWav(wav, durS)
            assertEquals(44 + 44100L * durS * 2, wav.length())
            onMain {
                val p = ExoPlayer.Builder(context).build()
                player = p
                p.volume = 0f
                poll = object : Runnable {
                    override fun run() {
                        if (endNs != null || failure != null) return
                        val ns = System.nanoTime()
                        log("SAMPLE nano_time=$ns current_position_ms=${p.currentPosition} is_playing=${p.isPlaying}")
                        handler.postDelayed(this, 10000)
                    }
                }
                p.addListener(object : Player.Listener {
                    override fun onIsPlayingChanged(isPlaying: Boolean) {
                        val ns = System.nanoTime()
                        if (isPlaying && startNs == null) {
                            startNs = ns
                            log("start_ns=$ns")
                            log("SAMPLE nano_time=$ns current_position_ms=${p.currentPosition} is_playing=true")
                            handler.postDelayed(poll!!, 10000)
                        }
                        log("IS_PLAYING nano_time=$ns value=$isPlaying current_position_ms=${p.currentPosition}")
                    }

                    override fun onPlaybackStateChanged(playbackState: Int) {
                        val ns = System.nanoTime()
                        if (playbackState == Player.STATE_ENDED && endNs == null) {
                            endNs = ns
                            log("end_ns=$ns")
                            log("end_position_ms=${p.currentPosition}")
                            done.countDown()
                        }
                        log("STATE nano_time=$ns value=$playbackState current_position_ms=${p.currentPosition}")
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        failure = error.toString()
                        log("error=$error")
                        done.countDown()
                    }
                })
                p.setMediaItem(MediaItem.fromUri(Uri.fromFile(wav)))
                p.prepare()
                p.play()
            }
            completed = done.await(durS + 120, TimeUnit.SECONDS)
        } finally {
            try {
                onMain {
                    poll?.let { handler.removeCallbacks(it) }
                    player?.release()
                    player = null
                }
                val start = startNs
                val end = endNs
                if (start != null && end != null) {
                    val wallS = (end - start) / 1e9
                    log("wall_s=${sec(wallS)}")
                    log("ratio=${sec(wallS / durS)}")
                }
                log("status=${if (completed && failure == null && start != null && end != null) "ended" else "failed"}")
                if (!completed) log("error=timeout or setup failure; playback allowance=${durS + 120}s")
            } finally {
                out.close()
            }
        }
        assertTrue("Playback timed out after ${durS + 120}s; see $result", completed)
        assertTrue("Player error: $failure; see $result", failure == null)
        assertTrue("Missing start/end timestamps; see $result", startNs != null && endNs != null)
    }

    /** One second repeats exactly (440 full cycles); stream DUR blocks, never allocate full WAV. */
    private fun writeWav(file: File, durS: Long) {
        val dataBytes = 44100L * durS * 2
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
            .put("RIFF".toByteArray(Charsets.US_ASCII)).putInt((36 + dataBytes).toInt())
            .put("WAVEfmt ".toByteArray(Charsets.US_ASCII)).putInt(16)
            .putShort(1.toShort()).putShort(1.toShort()).putInt(44100).putInt(88200)
            .putShort(2.toShort()).putShort(16.toShort())
            .put("data".toByteArray(Charsets.US_ASCII)).putInt(dataBytes.toInt()).array()
        val block = ByteBuffer.allocate(44100 * 2).order(ByteOrder.LITTLE_ENDIAN)
        val amplitude = 32767 * 10.0.pow(-30.0 / 20)
        repeat(44100) { i ->
            block.putShort((amplitude * sin(2 * PI * 440 * i / 44100)).roundToInt().toShort())
        }
        file.outputStream().buffered().use { stream ->
            stream.write(header)
            var remaining = durS
            while (remaining-- > 0) stream.write(block.array())
        }
    }
}
