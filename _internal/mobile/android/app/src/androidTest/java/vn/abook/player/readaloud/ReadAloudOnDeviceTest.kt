package vn.abook.player.readaloud

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Giọng của "Nghe ngay" trên máy thật, KHÔNG phát gì ra loa và không mở màn hình nào: chỉ đọc thành file (Edge qua mạng, TextToSpeech.synthesizeToFile) rồi
 * kiểm độ dài + mốc từng chữ (`words` đúng số chữ của đoạn - ReaderScreen sáng chữ theo thứ tự ấy). Chạy: `gradlew connectedDebugAndroidTest
 * -Pandroid.testInstrumentationRunnerArguments.class=vn.abook.player.readaloud.ReadAloudOnDeviceTest`.
 */
@RunWith(AndroidJUnit4::class)
class ReadAloudOnDeviceTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val dir = File(context.cacheDir, "readaloud-test").apply { mkdirs() }
    private val paragraph = "Sáng nay trời trong, nắng vàng trải trên mái ngói. Lan mở cửa sổ, hít một hơi thật sâu rồi mỉm cười với khoảng sân nhỏ."
    private val tokens = paragraph.split(Regex("\\s+")).filter { it.isNotEmpty() }.size

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private fun checkClip(clip: Clip, file: File) {
        assertTrue("độ dài ${clip.durationMs}", clip.durationMs > 2_000)
        assertTrue(file.length() > 1_000)
        assertEquals("một mốc mỗi chữ", tokens, clip.words.size)
        var last = 0L
        for (word in clip.words) {
            assertTrue("mốc tăng dần: $word sau $last", word.start >= last && word.end >= word.start)
            last = word.start
        }
        assertTrue(clip.words.last().end <= clip.durationMs + 50)
    }

    @Test
    fun edgeReadsAParagraphWithWordTimes() {
        val out = File(dir, "edge.mp3")
        val clip = EdgeTts("vi-VN-HoaiMyNeural").synthesize(paragraph, out)
        checkClip(clip, out)
    }

    @Test
    fun theDeviceVoiceReadsAParagraphWithWordTimes() {
        val id = DeviceTts.defaultId(context)
        assumeTrue("máy không có giọng tiếng Việt", id != null)
        val out = File(dir, "device.wav")
        val clip = DeviceTts(context, id!!.removePrefix("device:")).synthesize(paragraph, out)
        checkClip(clip, out)
    }

    @Test
    fun withoutEdgeTheParagraphFallsBackToTheDeviceVoice() {
        val id = DeviceTts.defaultId(context)
        assumeTrue("máy không có giọng tiếng Việt", id != null)
        // Giọng Edge "mất mạng" (máy chủ không tìm thấy) - như tắt Wi-Fi, mà không đụng cài đặt của máy.
        val offlineEdge = EdgeTts("vi-VN-HoaiMyNeural", { _, _ -> throw java.net.UnknownHostException("speech.platform.bing.com") })
        val reader = ClipReader(ClipCache(File(dir, "cache")), { offlineEdge }, { DeviceTts(context, id!!.removePrefix("device:")) })
        val clip = reader.read(paragraph, offlineEdge.id)
        assertTrue(clip.voice, clip.voice.startsWith("device:"))
        checkClip(clip, clip.file)
        assertTrue(DeviceTts.voices(context).all { it.id.startsWith("device:") })
    }
}
