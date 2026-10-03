package vn.abook.player

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Bộ phân tích nhạc trên máy Android THẬT (máy ảo): MediaCodec giải mã mp3, ONNX Runtime chạy tháp CLAP fp16, so với số của
 * `music_student.analyze` của máy tính cho cùng file (tests/fixtures/music_student/golden.json, assets của bài thử). Gói model
 * không nằm trong APK: đẩy bằng `adb push <thư mục gói> /data/local/tmp/student` trước khi chạy (không có thì bài thử bỏ qua).
 * Ngưỡng: V/E/T và 13 cảm xúc lệch < 0,02 (khác biệt bộ đổi tần số so với ffmpeg).
 */
@RunWith(AndroidJUnit4::class)
class MusicStudentOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val model = File("/data/local/tmp/student")

    private fun asset(name: String): File = File(context.cacheDir, "student-fixture").apply { mkdirs() }.resolve(name).also { target ->
        instrumentation.context.assets.open(name).use { input -> target.outputStream().use { input.copyTo(it) } }
    }

    @Test
    fun theRealModelOnTheDeviceAgreesWithTheDesktopStudent() {
        assumeTrue("chưa đẩy gói model vào ${model.path}", File(model, "clap_audio_fp16.onnx").isFile)
        val golden = JSONObject(asset("golden.json").readText())
        val analyze = AndroidMusicStudent.open(model, context.cacheDir)
        val report = StringBuilder()
        for (name in golden.getJSONObject("tracks").keys().asSequence().toList()) {
            val want = golden.getJSONObject("tracks").getJSONObject(name).getJSONObject("result")
            val file = asset(name)
            analyze(file) // lần đầu: nạp phiên ONNX
            val started = System.nanoTime()
            val got = analyze(file)
            val millis = (System.nanoTime() - started) / 1_000_000
            assertNotNull(name, got)
            var worst = 0.0
            for (axis in listOf("valence", "arousal", "tension")) worst = maxOf(worst, Math.abs(got!!.getDouble(axis) - want.getDouble(axis)))
            val vet = worst
            var emotion = 0.0
            for (key in want.getJSONObject("emotions").keys().asSequence()) {
                emotion = maxOf(emotion, Math.abs(got!!.getJSONObject("emotions").getDouble(key) - want.getJSONObject("emotions").getDouble(key)))
            }
            val fits = Math.abs(got!!.getDouble("fitsUnderNarration") - want.getDouble("fitsUnderNarration"))
            report.append("$name: max|dVET|=%.5f max|demotion|=%.5f |dfits|=%.5f family=%s/%s %d ms\n".format(vet, emotion, fits, got.getString("family"), want.getString("family"), millis))
            assertTrue("$name: V/E/T lệch $vet", vet < 0.02)
            assertTrue("$name: cảm xúc lệch $emotion", emotion < 0.02)
            assertEquals(name, want.getString("family"), got.getString("family"))
        }
        println("MUSIC_STUDENT_PARITY\n$report")
        File(context.cacheDir, "parity.txt").writeText(report.toString())
    }
}
