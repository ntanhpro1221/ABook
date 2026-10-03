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
import java.io.File
import java.io.RandomAccessFile
import java.security.MessageDigest

/**
 * "Giọng VieNeu" on a REAL Android device, no Activity, nothing played: the module's files staged by `scripts/vieneu_phone_module_stage.py`
 * (`adb push <out> /data/local/tmp/vieneu`; without them the test is skipped) are copied into `files/vieneu` exactly as the module lays them out,
 * accepted against the app's pins (hashed once, no network), then:
 * - sea-g2p (the JNI build for this ABI) gives the desktop's phonemes for the shared set (tests/fixtures/vieneu/android/text.json);
 * - the paragraph of two sentences of clips.json is synthesized with the first Nano voice - the WAV must be the desktop's byte for byte -
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
    fun twoSentencesAreReadWithTheDesktopsPhonemesAndNanoMatchesTheDesktopBitForBit() {
        assumeTrue("chưa đẩy mô-đun vào ${staged.path} (scripts/vieneu_phone_module_stage.py)", File(staged, "g2p/libabook_sea_g2p.so").isFile)
        val tiers = VieneuModule.TIERS.filter { File(staged, "$it/config.json").isFile }
        assumeTrue("mô-đun đẩy lên chưa có giọng nào", tiers.isNotEmpty())
        val dir = File(context.filesDir, "vieneu")
        staged.walkTopDown().filter { it.isFile }.forEach { source ->
            val target = File(dir, source.relativeTo(staged).path)
            if (target.length() != source.length()) {
                target.parentFile!!.mkdirs()
                target.delete()
                source.copyTo(target, overwrite = true)
            }
            if (target.name.endsWith(".so")) target.setReadOnly()
        }
        val module = VieneuVoices.module(context)
        // Same check as a real download: every file hashed against this app's pins (nothing fetched: they are all here already).
        PinnedFiles(dir, "", VieneuModule.STAMP).download(module.parts(tiers), object : PinnedFiles.Progress {
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
                assertEquals("Nano: the desktop's WAV byte for byte", want.getString("wavSha256"), sha(out))
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
