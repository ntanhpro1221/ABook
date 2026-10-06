package vn.abook.player

import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.SupertonicEngine
import vn.abook.player.readaloud.SupertonicText
import vn.abook.player.vieneu.NumpyRandomState
import vn.abook.player.vieneu.VieneuSpeaker
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Speed of the Supertonic voice on this phone (docs/research/SUPERTONIC_PHONE.md): the three fixed paragraphs of
 * tests/fixtures/readaloud/supertonic/supertonic_bench.json, each one chunk read exactly as the app reads it ([SupertonicEngine.infer], seed and speed as the
 * desktop), the same paragraphs `scripts/supertonic_bench.py` times on a computer. No Android Context, so it runs inside an instrumented test
 * ([SupertonicBenchTest]) and from `app_process` ([SupertonicBenchMain]).
 *
 * [pack] holds `model/` (onnx/ + voice_styles/ as the module downloads them) and `ort/` (ONNX Runtime's two libraries for this ABI). Per thread
 * count ([args] `threads`, default 1,2,4): load time, pass 0 = cold (the first runs of a fresh engine), then `passes` (2) warm passes; RTF = compute
 * seconds / audio seconds. One JSON line per thread count in [results], echoed to [echo]; pass 0's audio as raw float32 in [audioDir].
 */
class SupertonicBench(private val args: Map<String, String>, private val pack: File, private val results: File, private val audioDir: File,
                      private val echo: (String) -> Unit) {
    private fun log(line: String) {
        echo(line)
        results.appendText(line + "\n")
    }

    private fun kb(field: String): Long = runCatching {
        File("/proc/self/status").readLines().first { it.startsWith("$field:") }.split(Regex("\\s+"))[1].toLong()
    }.getOrDefault(-1)

    private fun device(): JSONObject {
        val cores = Runtime.getRuntime().availableProcessors()
        val max = (0 until cores).map { runCatching { File("/sys/devices/system/cpu/cpu$it/cpufreq/cpuinfo_max_freq").readText().trim().toLong() / 1000 }.getOrDefault(0L) }
        return JSONObject().put("model", Build.MODEL).put("manufacturer", Build.MANUFACTURER).put("soc", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else "")
            .put("android", Build.VERSION.RELEASE).put("abi", Build.SUPPORTED_ABIS[0]).put("cores", cores).put("maxMHzPerCore", JSONArray(max))
            .put("ramMB", runCatching { File("/proc/meminfo").readLines().first { it.startsWith("MemTotal:") }.split(Regex("\\s+"))[1].toLong() / 1024 }.getOrDefault(-1))
    }

    private fun saveAudio(name: String, audio: FloatArray) {
        val buffer = ByteBuffer.allocate(audio.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        buffer.asFloatBuffer().put(audio)
        audioDir.apply { mkdirs() }.resolve("$name.f32").writeBytes(buffer.array())
    }

    private fun round(value: Double) = Math.round(value * 1000) / 1000.0

    private fun sha256(values: FloatArray): String {
        val buffer = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        buffer.asFloatBuffer().put(values)
        return java.security.MessageDigest.getInstance("SHA-256").digest(buffer.array()).joinToString("") { "%02x".format(it) }
    }

    /**
     * The phone's model inputs and output against the desktop's ([parity]: tests/fixtures/readaloud/supertonic/supertonic.json): every voice style
     * (dims + SHA-256 of its float32 values), the character ids of every cleaned text through the real indexer, and one chunk of audio (same
     * length; largest difference over every `every`-th sample). Returns a report; throws on a mismatch of the inputs.
     */
    fun parity(parity: JSONObject): String {
        OrtRuntime.load(pack)
        val report = StringBuilder()
        SupertonicEngine(File(pack, "model"), (args["threads"] ?: "4").toInt()).use { engine ->
            val styles = parity.getJSONObject("styles")
            for (name in styles.keys()) {
                val style = engine.style(name)
                val want = styles.getJSONObject(name)
                check(want.getJSONObject("style_ttl").getString("sha256") == sha256(style.ttl) && want.getJSONObject("style_dp").getString("sha256") == sha256(style.dp)) { "style $name differs" }
            }
            report.append("styles: ${styles.length()} voices identical\n")
            val ids = parity.getJSONArray("ids")
            for (i in 0 until ids.length()) {
                val case = ids.getJSONObject(i)
                val want = case.getJSONArray("ids").let { array -> LongArray(array.length()) { array.getLong(it) } }
                check(want.contentEquals(SupertonicText.ids(case.getString("cleaned"), engine.indexer))) { "ids of '${case.getString("cleaned")}' differ" }
            }
            report.append("ids: ${ids.length()} texts identical\n")
            val audio = parity.getJSONObject("audio")
            val wave = engine.infer(audio.getString("text"), audio.getString("voice"), NumpyRandomState(audio.getLong("seed")), audio.getDouble("speed"))
            val every = audio.getInt("every")
            val decimated = audio.getJSONArray("decimated")
            var largest = 0.0
            for (i in 0 until minOf(decimated.length(), (wave.size + every - 1) / every)) largest = maxOf(largest, Math.abs(wave[i * every] - decimated.getDouble(i)))
            val rms = Math.sqrt(wave.sumOf { it.toDouble() * it } / maxOf(1, wave.size))
            report.append("audio: ${wave.size} samples (desktop ${audio.getInt("samples")}), RMS ${"%.5f".format(rms)} (desktop ${"%.5f".format(audio.getDouble("rms"))}), " +
                "largest difference over every ${every}th sample ${"%.2e".format(largest)}\n")
            check(wave.size == audio.getInt("samples")) { "audio length differs" }
        }
        log(JSONObject().put("bench", "parity").put("report", report.toString()).toString())
        return report.toString()
    }

    /** [fixture]: the JSON of supertonic_bench.json. */
    fun run(fixture: JSONObject) {
        OrtRuntime.load(pack)
        val voice = fixture.getString("voice")
        val paragraphs = fixture.getJSONArray("paragraphs").let { array -> List(array.length()) { array.getString(it) } }
        val passes = (args["passes"] ?: "2").toInt()
        log(JSONObject().put("bench", "start").put("device", device()).toString())
        for (threads in (args["threads"] ?: "1,2,4").split(',').map { it.trim().toInt() }) {
            val began = System.nanoTime()
            val engine = SupertonicEngine(File(pack, "model"), if (threads <= 0) Runtime.getRuntime().availableProcessors() else threads)
            engine.style(voice)
            val loadMs = (System.nanoTime() - began) / 1_000_000
            val rtf = Array(passes + 1) { DoubleArray(paragraphs.size) }
            val seconds = DoubleArray(paragraphs.size)
            val stages = JSONArray()
            engine.use {
                for (pass in 0..passes) {
                    for ((index, text) in paragraphs.withIndex()) {
                        val random = NumpyRandomState(VieneuSpeaker.seedOf("supertonic", voice, text))
                        val start = System.nanoTime()
                        val audio = engine.infer(text, voice, random, SupertonicText.speedFor(text))
                        val spent = (System.nanoTime() - start) / 1e9
                        seconds[index] = audio.size.toDouble() / engine.sampleRate
                        rtf[pass][index] = spent / seconds[index]
                        if (pass == 0) saveAudio("t${threads}_p$index", audio)
                        if (pass == passes) stages.put(JSONArray(engine.clock.map { it / 1_000_000 }))
                    }
                }
            }
            val warm = DoubleArray(paragraphs.size) { index -> (1..passes).map { rtf[it][index] }.sorted().let { it[it.size / 2] } }
            log(JSONObject().put("bench", "speed").put("threads", threads).put("loadMs", loadMs)
                .put("audioSeconds", JSONArray(seconds.map { round(it) })).put("coldRtf", JSONArray(rtf[0].map { round(it) }))
                .put("warmRtf", JSONArray(warm.map { round(it) })).put("warmRtfMedian", round(warm.sorted()[warm.size / 2]))
                .put("lastPassStageMs", stages).put("peakRssMB", kb("VmHWM") / 1024).toString())
        }
    }
}
