package vn.abook.player.readaloud

import android.content.Context
import android.content.ContextWrapper
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.SharedRuntime
import vn.abook.player.vieneu.VieneuModule
import vn.abook.player.vieneu.VieneuVoices
import vn.abook.player.vieneu.VoiceModule
import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Soát a77 #12: danh sách giọng của VieNeu / Supertonic (voices(), module()) được gọi từ luồng chính khi đổi sách / giọng; synthesize() giữ monitor của object suốt cả đoạn đang đọc.
 * Metadata dùng khoá riêng - đổi giọng lúc máy đang tổng hợp phải trả ngay, không treo luồng chính (nghi ANR).
 */
class VoiceMetadataLockTest {
    private val root: File = Files.createTempDirectory("abook-voice-meta").toFile()
    private val context: Context = ContextWrapper(null)

    private fun field(owner: Any, name: String) = owner.javaClass.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setup() {
        val runtime = SharedRuntime.inFiles(root)
        val facts = VoiceModule.Facts(8, 7.6)
        field(VieneuVoices, "module").set(VieneuVoices, VieneuModule(File(root, VieneuModule.FOLDER), runtime, "arm64-v8a", facts))
        field(SupertonicVoices, "module").set(SupertonicVoices, SupertonicModule(File(root, SupertonicModule.FOLDER), runtime, "arm64-v8a", facts))
    }

    @After fun cleanup() {
        field(VieneuVoices, "module").set(VieneuVoices, null)
        field(SupertonicVoices, "module").set(SupertonicVoices, null)
        root.deleteRecursively()
    }

    /** Chạy [call] ở luồng khác trong lúc luồng này giữ monitor của [owner] (như synthesize() giữa một đoạn dài); trả true nếu nó xong trong 200 ms. */
    private fun answersWhileSynthesizing(owner: Any, call: () -> Unit): Boolean {
        val done = CountDownLatch(1)
        synchronized(owner) {
            Thread { call(); done.countDown() }.apply { isDaemon = true }.start()
            return done.await(200, TimeUnit.MILLISECONDS)
        }
    }

    @Test fun vieneuVoiceListAnswersWhileASynthesisHoldsTheEngine() {
        assertTrue(answersWhileSynthesizing(VieneuVoices) { VieneuVoices.voices(context) })
        assertTrue(answersWhileSynthesizing(VieneuVoices) { VieneuVoices.module(context) })
    }

    @Test fun supertonicVoiceListAnswersWhileASynthesisHoldsTheEngine() {
        assertTrue(answersWhileSynthesizing(SupertonicVoices) { SupertonicVoices.voices(context) })
        assertTrue(answersWhileSynthesizing(SupertonicVoices) { SupertonicVoices.module(context) })
    }
}
