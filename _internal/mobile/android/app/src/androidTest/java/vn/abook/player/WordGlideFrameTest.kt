package vn.abook.player

import android.content.Intent
import android.media.MediaPlayer
import android.net.Uri
import android.os.Handler
import android.os.HandlerThread
import android.view.Choreographer
import android.view.FrameMetrics
import android.view.Window
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.ui.Modifier
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import vn.abook.player.ui.nowplaying.*
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.DarkPalette
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CopyOnWriteArrayList

/** Opt-in, synthetic audio and original text. Always run on a dedicated emulator. */
class WordGlideFrameTest {
    private class Clock : PlayerPosition {
        val now = mutableLongStateOf(0)
        override val milliseconds: State<Long> = now
        override val sleepRemainingMs: State<Long> = mutableLongStateOf(0)
        override fun sample() {}
    }
    @Test fun playingWordFrames() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("wordGlide") == "true")
        check(android.os.Build.HARDWARE in setOf("ranchu", "goldfish")) { "Emulator only" }
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val activity = instrumentation.startActivitySync(Intent(context, ComponentActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as ComponentActivity
        val output = File(context.getExternalFilesDir(null), "wordglide").apply { mkdirs() }
        val text = "“Nghĩ về luồng gió, chiếc lá nghiêng mình theo nhịp bước nhẹ-nhàng. ...!? Mây trôi qua mái hiên, ánh nắng chạm vào trang giấy.”"
        val tokens = Regex("\\S+").findAll(text).toList()
        val span = tokens.size * 180L
        val paragraphs = List(16) { p -> ReadParagraph(p, text, p * span, (p + 1) * span, true,
            tokens.mapIndexed { w, token -> WordTiming(p * span + w * 180L, p * span + (w + 1) * 180L, token.range.first, token.range.last + 1) }) }
        val clock = Clock()
        val audio = File(context.cacheDir, "wordglide-tone.wav")
        val samples = 32 * 16000
        val wave = ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN)
        wave.put("RIFF".toByteArray()).putInt(36 + samples * 2).put("WAVEfmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
            .putInt(16000).putInt(32000).putShort(2).putShort(16).put("data".toByteArray()).putInt(samples * 2)
        repeat(samples) { i ->
            val envelope = minOf(1.0, i / 800.0, (samples - i - 1) / 800.0).coerceAtLeast(0.0)
            wave.putShort((kotlin.math.sin(2 * Math.PI * 220 * i / 16000) * 400 * envelope).toInt().toShort())
        }
        audio.writeBytes(wave.array())
        val player = MediaPlayer.create(context, Uri.fromFile(audio))!!
        val metrics = CopyOnWriteArrayList<Long>()
        val lostMetrics = java.util.concurrent.atomic.AtomicInteger()
        val handlerThread = HandlerThread("word-frame-metrics").apply { start() }
        val listener = Window.OnFrameMetricsAvailableListener { _, frame, dropped ->
            lostMetrics.addAndGet(dropped)
            frame.getMetric(FrameMetrics.TOTAL_DURATION).takeIf { it >= 0 }?.let { metrics += it }
        }
        var running = true
        val callback = object : Choreographer.FrameCallback {
            override fun doFrame(frameTimeNanos: Long) {
                if (running) {
                    clock.now.longValue = player.currentPosition.toLong()
                    Choreographer.getInstance().postFrameCallback(this)
                }
            }
        }
        try {
            instrumentation.runOnMainSync {
                activity.setContent { AbookTheme(true) { ReadAlongPane(ReadAlongState("synthetic", 1, paragraphs), clock, Modifier.fillMaxSize()) } }
                player.start()
                Choreographer.getInstance().postFrameCallback(callback)
            }
            Thread.sleep(3000) // warm layout and class loading before counting
            instrumentation.runOnMainSync { activity.window.addOnFrameMetricsAvailableListener(listener, Handler(handlerThread.looper)) }
            Thread.sleep(24000)
            instrumentation.runOnMainSync { activity.window.removeOnFrameMetricsAvailableListener(listener) }
            val sorted = metrics.sorted()
            check(sorted.size > 100) { "No valid frame sample" }
            val report = JSONObject().put("frames", sorted.size).put("over16667us", sorted.count { it > 16_666_667L })
                .put("missedVsyncs", sorted.sumOf { ((it + 16_666_666L) / 16_666_667L - 1L).coerceAtLeast(0) })
                .put("lostMetrics", lostMetrics.get()).put("refreshHz", activity.display?.refreshRate)
                .put("p50Ms", sorted[sorted.size / 2] / 1e6).put("p95Ms", sorted[(sorted.size * .95).toInt()] / 1e6)
                .put("durationsNs", JSONArray(metrics)).put("audioPlaying", player.isPlaying)
            File(output, "frames.json").writeText(report.toString(2))
            // Separate capture pass: screenshot overhead is excluded from the measured window.
            instrumentation.runOnMainSync {
                activity.window.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(DarkPalette.BG.toInt()))
                androidx.core.view.WindowCompat.getInsetsController(activity.window, activity.window.decorView)
                    .hide(androidx.core.view.WindowInsetsCompat.Type.systemBars())
                player.seekTo(900)
            }
            Thread.sleep(500) // Let the asynchronous seek and follow placement settle before capturing motion.
            repeat(12) { i ->
                Thread.sleep(25)
                instrumentation.uiAutomation.takeScreenshot().also { bitmap ->
                    File(output, "word-%02d.png".format(i)).outputStream().use { bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it) }
                    bitmap.recycle()
                }
            }
        } finally {
            instrumentation.runOnMainSync { running = false; Choreographer.getInstance().removeFrameCallback(callback); player.release(); activity.finish() }
            handlerThread.quitSafely()
        }
    }
}
