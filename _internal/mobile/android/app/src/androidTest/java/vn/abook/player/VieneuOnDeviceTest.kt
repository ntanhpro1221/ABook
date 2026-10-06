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
import vn.abook.player.vieneu.SeaG2p
import vn.abook.player.vieneu.VieneuModule
import vn.abook.player.vieneu.VieneuVoices
import vn.abook.player.vieneu.VoiceModule
import java.io.File
import java.io.RandomAccessFile
import java.security.MessageDigest

/**
 * "Giọng VieNeu" on a REAL Android device, no Activity, nothing played: the module's files staged by `scripts/vieneu_phone_module_stage.py`
 * (`adb push <out> /data/local/tmp/vieneu`; without them the test is skipped) are copied into `files/vieneu` exactly as the module lays them out,
 * accepted against the app's pins (hashed once, no network), then:
 * - sea-g2p (the JNI build for this ABI) gives the desktop's phonemes for the shared set (tests/fixtures/vieneu/android/text.json);
 * - the paragraph of two sentences of clips.json is synthesized with the first Nano voice - same tokens as the desktop (length and per-sentence loudness; byte for byte on the same CPU kind) -
 *   and with the first Turbo voice when Turbo is staged (int8 kernels differ on ARM: same length within 15%, same loudness range, no NaN);
 * - the self-benchmark of each staged tier runs and its numbers are printed (`VIENEU_ON_DEVICE` in logcat, also files/vieneu-on-device.txt).
 *
 *     adb shell am instrument -w -e class vn.abook.player.VieneuOnDeviceTest com.ngdtuanh.abook.test/androidx.test.runner.AndroidJUnitRunner
 */
@RunWith(AndroidJUnit4::class)
class VieneuOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val staged = File("/data/local/tmp/vieneu")

    private fun asset(name: String): JSONObject = JSONObject(instrumentation.context.assets.open(name).use { String(it.readBytes(), Charsets.UTF_8) })

    private fun sha(file: File): String = MessageDigest.getInstance("SHA-256").let { digest ->
        file.inputStream().use { input -> val buffer = ByteArray(1 shl 16); while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer, 0, n) } }
        digest.digest().joinToString("") { "%02x".format(it) }
    }

    /** 16-bit samples of a WAV written by VieneuAudio (44-byte header). */
    private fun samples(file: File): ShortArray = RandomAccessFile(file, "r").use { handle ->
        val bytes = ByteArray((handle.length() - 44).toInt()).also { handle.seek(44); handle.readFully(it) }
        ShortArray(bytes.size / 2) { ((bytes[2 * it].toInt() and 0xFF) or (bytes[2 * it + 1].toInt() shl 8)).toShort() }
    }

    @Test
    fun twoSentencesAreReadWithTheDesktopsPhonemesAndNanoMatchesTheDesktop() {
        assumeTrue("chưa đẩy mô-đun vào ${staged.path} (scripts/vieneu_phone_module_stage.py)", File(staged, "g2p/libabook_sea_g2p.so").isFile)
        val tiers = VieneuModule.TIERS.filter { File(staged, "$it/config.json").isFile }
        assumeTrue("mô-đun đẩy lên chưa có giọng nào", tiers.isNotEmpty())
        val dir = File(context.filesDir, "vieneu")
        val runtime = SharedRuntime.of(context)
        // the runtime parts (ort/, g2p/) live in the folder every voice shares, the rest in VieNeu's own
        fun home(path: String) = if (path.substringBefore('/') in SharedRuntime.PARTS) runtime.dir else dir
        staged.walkTopDown().filter { it.isFile }.forEach { source ->
            val path = source.relativeTo(staged).invariantSeparatorsPath
            val target = File(home(path), path)
            if (target.length() != source.length()) {
                target.parentFile!!.mkdirs()
                target.delete()
                source.copyTo(target, overwrite = true)
            }
            if (target.name.endsWith(".so")) target.setReadOnly()
        }
        val module = VieneuVoices.module(context)
        // Same check as a real download: every file hashed against this app's pins (nothing fetched: they are all here already).
        for ((folder, parts) in module.parts(tiers).groupBy { home(it.name) }) PinnedFiles(folder, "", VoiceModule.STAMP).download(parts, object : PinnedFiles.Progress {
            override fun current(bytes: Long) = Unit
            override fun done(part: PinnedFiles.Part) = Unit
        })
        val installed = module.installed()
        assertNotNull("the staged module is not usable: ${module.status()}", installed)
        val report = StringBuilder("abi=${OrtRuntime.deviceAbi()} cores=${Runtime.getRuntime().availableProcessors()}\n")

        // 1. text -> phonemes on this device
        OrtRuntime.load(module.ortFolder())
        val text = asset("text.json")
        val cases = text.getJSONArray("g2p")
        var wrong = 0
        fun memory() = "PSS %.0f MB, native heap %.0f MB".format(android.os.Debug.getPss() / 1024.0, android.os.Debug.getNativeHeapAllocatedSize() / 1e6)
        report.append("before g2p: ${memory()}\n")
        val started = System.nanoTime()
        SeaG2p(installed!!.g2pLibrary, installed.dictionary).use { g2p ->
            for (n in 0 until cases.length()) {
                val case = cases.getJSONObject(n)
                val sentences = case.getJSONArray("sentences").let { array -> (0 until array.length()).map { array.getString(it) } }
                if (g2p.phonemize(sentences) != case.getString("phonemes")) wrong++
            }
            report.append("g2p open + all units: ${memory()}\n")
        }
        report.append("g2p: ${cases.length() - wrong}/${cases.length()} identical, ${(System.nanoTime() - started) / 1_000_000} ms\n")
        assertEquals("phonemes differing from the desktop", 0, wrong)

        // 2. the two-sentence paragraph, compared with the desktop's clip
        val clips = asset("clips.json")
        val paragraph = clips.getString("text")
        val all = clips.getJSONArray("clips")
        for (n in 0 until all.length()) {
            val want = all.getJSONObject(n)
            val tier = want.getString("tier")
            if (tier !in tiers) continue
            val out = File(context.cacheDir, "vieneu-$tier.wav").apply { delete() }
            val began = System.nanoTime()
            val clip = VieneuVoices.synthesize(want.getString("voice"), paragraph, out)
            val seconds = (System.nanoTime() - began) / 1e9
            val pcm = samples(out)
            val rms = Math.sqrt(pcm.sumOf { (it / 32768.0) * (it / 32768.0) } / pcm.size.coerceAtLeast(1))
            report.append("after $tier: ${memory()}\n")
            report.append("$tier: ${pcm.size} samples (desktop ${want.getInt("samples")}), ${clip.durationMs} ms, rms %.4f, made in %.1f s (RTF %.2f), wav %s\n"
                .format(rms, seconds, seconds * 1000 / clip.durationMs, if (sha(out) == want.getString("wavSha256")) "IDENTICAL" else "differs"))
            assertEquals(tier, vn.abook.player.readaloud.WordTokens.count(paragraph), clip.words.size)
            if (tier == "nano") {
                assertEquals("Nano: same length as the desktop", want.getInt("samples"), pcm.size)
                // Cùng token với máy tính (cùng độ dài, cùng khoảng mẫu từng câu); bước giải mã ra sóng có thể lệch vài bit thấp nhất khi ONNX Runtime
                // chọn nhân tính khác (máy ảo x86 03-10: 1,9% mẫu lệch, tối đa 5/32768, tương quan 0,9999999986) - không nghe ra. Trùng từng byte
                // thì báo cáo ghi IDENTICAL ở trên.
                val units = want.getJSONArray("units")
                for (u in 0 until units.length()) {
                    val unit = units.getJSONObject(u)
                    val span = unit.getJSONArray("span")
                    val piece = pcm.copyOfRange(span.getInt(0), span.getInt(1))
                    val unitRms = Math.sqrt(piece.sumOf { (it / 32768.0) * (it / 32768.0) } / piece.size.coerceAtLeast(1))
                    val desktop = unit.getDouble("rms")
                    assertTrue("Nano câu $u: rms $unitRms, máy tính $desktop", Math.abs(unitRms - desktop) <= 0.01 * desktop + 1e-4)
                }
            } else {
                val ratio = pcm.size.toDouble() / want.getInt("samples")
                assertTrue("Turbo length ratio $ratio", ratio in 0.85..1.15)
                assertTrue("Turbo loudness $rms", rms in 0.05..0.2)
            }
        }

        // 3. the self-benchmark the module runs after a download
        for (tier in tiers) {
            val bench = VieneuVoices.benchmark(tier)
            report.append("benchmark $tier: RTF ${bench.rtf}, paragraph ${bench.firstAudioMs} ms for ${bench.audioSeconds} s, load ${bench.loadMs} ms\n")
        }
        println("VIENEU_ON_DEVICE\n$report")
        File(context.filesDir, "vieneu-on-device.txt").writeText(report.toString())
    }
}
