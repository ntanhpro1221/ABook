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
 * `music_student.analyze` của máy tính cho cùng file (tests/fixtures/music_student/golden.json, assets của bài thử). "Gói nhạc" (model +
 * thư viện ONNX Runtime, cả hai đều KHÔNG nằm trong APK): đẩy bằng `adb push <thư mục gói> /data/local/tmp/student` và hai file .so của
 * ABI máy thử vào `/data/local/tmp/student/ort/` trước khi chạy (không có thì bài thử bỏ qua). Bài thử chép gói vào `files/` của app
 * (app không nạp được .so từ /data/local/tmp) đúng bố cục MusicStudentSetup tải về, rồi nạp ONNX Runtime bằng đường tuyệt đối như thật.
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

    /** Phân tích từng bài mẫu bằng `analyze` rồi so với số của máy tính (golden.json); trả bảng đo để in ra. */
    private fun compareWithTheDesktop(analyze: (File) -> JSONObject?): String {
        val golden = JSONObject(asset("golden.json").readText())
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
        return report.toString()
    }

    @Test
    fun theRealModelOnTheDeviceAgreesWithTheDesktopStudent() {
        assumeTrue("chưa đẩy gói model vào ${model.path}", File(model, "clap_audio_fp16.onnx").isFile)
        assumeTrue("chưa đẩy thư viện ONNX Runtime vào ${model.path}/ort", File(model, "ort/libonnxruntime.so").isFile)
        val installed = File(context.filesDir, "music/student-test")
        model.walkTopDown().filter { it.isFile }.forEach { source ->
            val target = File(installed, source.relativeTo(model).path)
            if (target.length() != source.length()) {
                target.parentFile!!.mkdirs()
                source.copyTo(target, overwrite = true)
            }
            if (target.name.endsWith(".so")) target.setReadOnly()
        }
        val report = compareWithTheDesktop(AndroidMusicStudent.open(installed, installed, context.cacheDir))
        println("MUSIC_STUDENT_PARITY\n$report")
        File(context.cacheDir, "parity.txt").writeText(report)
    }

    /**
     * Đường tải THẬT: [MusicStudentSetup] tải model + thư viện ONNX Runtime (bản nén gzip, đúng ABI) từ Hugging Face theo ghim của app
     * (hoặc từ máy chủ khác nếu truyền `-e bundleBase http://10.0.2.2:8123/`), kiểm cỡ + SHA-256, giải nén, đặt chỉ-đọc, nạp bằng đường
     * tuyệt đối, rồi phân tích các bài mẫu và so với máy tính. Không tới được máy chủ thì bài thử bỏ qua.
     */
    @Test
    fun theBundleDownloadedFromAServerLoadsAndAgreesWithTheDesktopStudent() {
        val base = InstrumentationRegistry.getArguments().getString("bundleBase") ?: MusicStudentSetup.BASE
        val abi = OrtRuntime.deviceAbi()
        assumeTrue("máy thử không có thư viện ONNX Runtime cho ABI này", abi != null)
        val reachable = runCatching {
            (java.net.URL(base + "preprocessor_config.json").openConnection() as java.net.HttpURLConnection).apply { connectTimeout = 8000; requestMethod = "HEAD" }.responseCode == 200
        }.getOrDefault(false)
        assumeTrue("không tới được máy chủ gói ở $base", reachable)
        val dir = File(context.filesDir, "music/student-download").apply { deleteRecursively() }
        val store = MusicStore(File(context.filesDir, "music/mine-test").apply { deleteRecursively() }, AndroidMusicTags, AndroidLoudness)
        // thư viện vào một thư mục dùng chung riêng của bài thử, không phải của app
        val runtime = SharedRuntime(File(context.filesDir, "runtime-test").apply { deleteRecursively() }, emptyList())
        val setup = MusicStudentSetup(dir, store, { AndroidMusicStudent.open(it, runtime.dir, context.cacheDir) }, runtime, base,
            MusicStudentSetup.PACKAGE + OrtRuntime.parts(abi))
        val started = System.nanoTime()
        setup.start()
        setup.join(600_000)
        val status = setup.status()
        assertEquals(status.toString(), "ready", status.getString("state"))
        val seconds = (System.nanoTime() - started) / 1_000_000_000
        val so = File(runtime.dir, "ort/libonnxruntime.so")
        assertTrue(so.isFile && !so.canWrite())
        val header = "downloaded ${status.getLong("done")} bytes in $seconds s; libonnxruntime.so ${so.length()} bytes read-only"
        println("MUSIC_BUNDLE_DOWNLOAD_PARITY " + header + " " + compareWithTheDesktop(store.analyzer!!).replace("\n", " | "))
    }
}
