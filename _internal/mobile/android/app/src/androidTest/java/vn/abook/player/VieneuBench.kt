package vn.abook.player

import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.vieneu.RawFiles
import vn.abook.player.vieneu.UniformSource
import vn.abook.player.vieneu.VieneuNano
import vn.abook.player.vieneu.VieneuTurbo
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * VieNeu (Turbo int8 + Nano) correctness against the desktop and speed per thread count. No Android Context needed, so it runs both
 * inside an instrumented test ([VieneuBenchTest]) and from `app_process` as the shell user ([VieneuBenchMain]) - the latter is what a phone
 * with an app freezer needs (ColorOS freezes an instrumented app that is not in front, which stalls every thread).
 *
 * [pack] holds `models/`, `bundle/` and `ort/` (`scripts/vieneu_phone_bench_export.py`, `scripts/vieneu_phone_bench.sh push`); ONNX Runtime's
 * libraries are loaded from `<pack>/ort` like the real app does ([OrtRuntime.load]). Arguments ([args]): threads (1,2,4,0 - 0 = every core),
 * models (turbo,nano), passes (2 timed passes over the sentences after one warm-up run), cooldown (60 s between configurations), sentences
 * (0,1,2,3,4), headThreads (default = threads), turbo / bundle (folder names; turbo_fp32 + bundle_fp32 is the fp32 reference check).
 * Results are one JSON per line in [results] and echoed to [echo]; the audio the phone made goes to [audioDir] as raw float32.
 */
class VieneuBench(private val args: Map<String, String>, private val pack: File, private val results: File, private val audioDir: File,
                  private val echo: (String) -> Unit, private val extraThermal: () -> JSONObject = { JSONObject() }) {
    private fun arg(name: String, default: String) = args[name] ?: default

    private fun ints(name: String, default: String) = arg(name, default).split(',').filter { it.isNotBlank() }.map { it.trim().toInt() }

    private fun log(line: String) {
        echo(line)
        results.appendText(line + "\n")
    }

    private val turboFolder get() = arg("turbo", "turbo_int8")
    private val bundleFolder get() = arg("bundle", "bundle")

    private fun bundle(name: String) = File(pack, "$bundleFolder/$name")

    fun manifest(): JSONObject {
        OrtRuntime.load(pack)
        return JSONObject(bundle("manifest.json").readText())
    }

    private fun manifestInts(array: JSONArray) = IntArray(array.length()) { array.getInt(it) }

    private fun saveAudio(name: String, audio: FloatArray) {
        val buffer = ByteBuffer.allocate(audio.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        buffer.asFloatBuffer().put(audio)
        audioDir.apply { mkdirs() }.resolve("$name.f32").writeBytes(buffer.array())
    }

    // ---- numbers -----------------------------------------------------------------------------------------------------

    /** RMS per [window] samples. */
    private fun envelope(x: FloatArray, window: Int): DoubleArray = DoubleArray(x.size / window) { w ->
        var sum = 0.0
        for (i in w * window until (w + 1) * window) sum += x[i].toDouble() * x[i]
        sqrt(sum / window)
    }

    private fun correlation(a: DoubleArray, b: DoubleArray): Double {
        val n = minOf(a.size, b.size)
        if (n < 2) return 0.0
        val meanA = a.take(n).average()
        val meanB = b.take(n).average()
        var ab = 0.0
        var aa = 0.0
        var bb = 0.0
        for (i in 0 until n) {
            ab += (a[i] - meanA) * (b[i] - meanB)
            aa += (a[i] - meanA) * (a[i] - meanA)
            bb += (b[i] - meanB) * (b[i] - meanB)
        }
        return if (aa == 0.0 || bb == 0.0) 0.0 else ab / sqrt(aa * bb)
    }

    private fun envelopeCorrelation(a: FloatArray, b: FloatArray, sampleRate: Int) = correlation(envelope(a, sampleRate / 50), envelope(b, sampleRate / 50))

    private fun kb(field: String): Long = runCatching {
        File("/proc/self/status").readLines().first { it.startsWith("$field:") }.split(Regex("\\s+"))[1].toLong()
    }.getOrDefault(-1)

    /** Peak resident memory counts from here on (works where the kernel lets a process clear its own HWM). */
    private fun resetPeak(): Boolean = runCatching { File("/proc/self/clear_refs").writeText("5"); true }.getOrDefault(false)

    private fun cores() = Runtime.getRuntime().availableProcessors()

    private fun read(path: String) = runCatching { File(path).readText().trim() }.getOrDefault("")

    private fun thermal(): JSONObject {
        val freqs = (0 until cores()).map { runCatching { File("/sys/devices/system/cpu/cpu$it/cpufreq/scaling_cur_freq").readText().trim().toLong() / 1000 }.getOrDefault(-1L) }
        return JSONObject().put("loadavg", read("/proc/loadavg")).put("cpuMHz", JSONArray(freqs))
            .put("batteryTempDeciC", read("/sys/class/power_supply/battery/temp")).put("batteryLevel", read("/sys/class/power_supply/battery/capacity"))
            .also { json -> extraThermal().let { extra -> extra.keys().forEach { json.put(it, extra.get(it)) } } }
    }

    private fun device(): JSONObject {
        val max = (0 until cores()).map { runCatching { File("/sys/devices/system/cpu/cpu$it/cpufreq/cpuinfo_max_freq").readText().trim().toLong() }.getOrDefault(0L) }
        val ram = runCatching { File("/proc/meminfo").readLines().first { it.startsWith("MemTotal:") }.split(Regex("\\s+"))[1].toLong() / 1024 }.getOrDefault(-1)
        return JSONObject().put("model", Build.MODEL).put("manufacturer", Build.MANUFACTURER).put("soc", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else "")
            .put("android", Build.VERSION.RELEASE).put("abi", Build.SUPPORTED_ABIS[0]).put("ramMB", ram).put("cores", cores())
            .put("coresAtMaxFreq", max.count { it == (max.maxOrNull() ?: 0L) }).put("maxMHz", (max.maxOrNull() ?: 0L) / 1000)
    }

    // ---- sessions ----------------------------------------------------------------------------------------------------

    private fun resolveThreads(n: Int) = if (n <= 0) cores() else n

    private fun openTurbo(threads: Int, headThreads: Int = threads) = VieneuTurbo(File(pack, "models/$turboFolder"), File(pack, "models/codec"), threads, headThreads)

    private fun openNano(threads: Int) = VieneuNano(File(pack, "models/nano"), threads)

    private class TurboCase(val textIds: IntArray, val maxFrames: Int, val uniforms: DoubleArray, val desktopCodes: IntArray, val desktopAudio: FloatArray, val desktopFrames: Int)

    private fun turboCases(manifest: JSONObject, which: List<Int>): List<TurboCase> = which.map { i ->
        val s = manifest.getJSONArray("turbo").getJSONObject(i)
        TurboCase(manifestInts(s.getJSONArray("text_ids")), s.getInt("max_new_frames"), RawFiles.doubles(bundle("turbo_uniforms_$i.f64")),
            RawFiles.ints(bundle("turbo_codes_$i.i32")), RawFiles.floats(bundle("turbo_audio_$i.f32")), s.getInt("frames"))
    }

    // ---- correctness -------------------------------------------------------------------------------------------------

    /** Turbo loop against the desktop's recorded codes and audio. Returns the report; fails (IllegalStateException) when the port is wrong. */
    fun checkTurbo(manifest: JSONObject): String {
        val sampling = VieneuTurbo.Sampling()
        val speaker = RawFiles.floats(bundle("turbo_speaker_emb.f32"))
        val ref = RawFiles.ints(bundle("turbo_ref_codes.i32"))
        val cases = turboCases(manifest, ints("sentences", "0,1,2,3,4"))
        val report = StringBuilder()
        var exact = 0
        openTurbo(2).use { engine ->
            for ((index, case) in cases.withIndex()) {
                val result = engine.synthesize(case.textIds, speaker, ref, case.maxFrames, sampling, UniformSource.recorded(case.uniforms))
                val n = minOf(result.frames, case.desktopFrames) * 16
                var firstDifferentFrame = -1
                var same = 0
                for (k in 0 until n) if (result.codes[k] == case.desktopCodes[k]) same++ else if (firstDifferentFrame < 0) firstDifferentFrame = k / 16
                saveAudio("${turboFolder}_$index", result.audio)
                if (result.frames == case.desktopFrames && same == n) exact++
                // the vocoder alone, fed the desktop's own codes: isolates ORT/codec differences from sampling divergence
                val vocoder = engine.decode(case.desktopCodes, case.desktopFrames)
                val vocoderCorr = envelopeCorrelation(vocoder, case.desktopAudio, VieneuTurbo.SAMPLE_RATE)
                var maxDiff = 0f
                for (k in 0 until minOf(vocoder.size, case.desktopAudio.size)) maxDiff = maxOf(maxDiff, abs(vocoder[k] - case.desktopAudio[k]))
                val corr = envelopeCorrelation(result.audio, case.desktopAudio, VieneuTurbo.SAMPLE_RATE)
                report.append("turbo[$index] frames ${result.frames}/${case.desktopFrames} codesEqual $same/$n firstDifferentFrame $firstDifferentFrame " +
                    "envelopeCorr %.4f vocoderCorr %.5f vocoderMaxDiff %.5f\n".format(Locale.ROOT, corr, vocoderCorr, maxDiff))
                check(vocoderCorr > 0.999 && maxDiff < 0.01f) { "vocoder differs from the desktop on sentence $index: corr $vocoderCorr" }
                check(result.frames in (case.desktopFrames * 3 / 4)..(case.desktopFrames * 5 / 4 + 1)) { "sentence $index: ${result.frames} frames vs ${case.desktopFrames} on the desktop" }
            }
        }
        log(JSONObject().put("check", "turbo").put("model", turboFolder).put("exactSentences", exact).put("of", cases.size).put("report", report.toString()).toString())
        // fp32 graphs reproduce the desktop's codes until a razor-thin draw flips (ORT 1.30 here vs 1.28 on the desktop fuses differently: the desktop
        // itself diverges at the very same frames when its graph optimisation is reduced). int8 kernels also depend on the CPU, so int8 only has to
        // stay in the length class and keep the vocoder exact.
        if (turboFolder.endsWith("fp32")) check(exact > 0) { "no sentence repeated the desktop's codes exactly\n$report" }
        return report.toString()
    }

    /** Nano is deterministic given the recorded start noise: the audio must equal the desktop's. */
    fun checkNano(manifest: JSONObject): String {
        val speaker = RawFiles.floats(bundle("nano_speaker_emb.f32"))
        val style = RawFiles.floats(bundle("nano_style.f32"))
        val report = StringBuilder()
        openNano(2).use { engine ->
            for (i in ints("sentences", "0,1,2,3,4")) {
                val meta = manifest.getJSONArray("nano_sentences").getJSONObject(i)
                val ids = engine.encodePhones(meta.getString("ph"))
                val wantIds = meta.getJSONArray("ids")
                check(wantIds.length() == ids.size) { "nano ids of sentence $i" }
                for (k in ids.indices) check(wantIds.getLong(k) == ids[k]) { "nano id $k of sentence $i" }
                val want = RawFiles.floats(bundle("nano_audio_$i.f32"))
                val result = engine.synthesize(meta.getString("ph"), speaker, style, RawFiles.floats(bundle("nano_noise_$i.f32")), 0)
                saveAudio("nano_$i", result.audio)
                val corr = envelopeCorrelation(result.audio, want, VieneuNano.SAMPLE_RATE)
                var maxDiff = 0f
                for (k in 0 until minOf(want.size, result.audio.size)) maxDiff = maxOf(maxDiff, abs(want[k] - result.audio[k]))
                report.append("nano[$i] frames ${result.flowFrames}/${meta.getInt("flow_frames")} samples ${result.audio.size}/${want.size} envelopeCorr %.4f maxDiff %.4f\n".format(Locale.ROOT, corr, maxDiff))
                check(meta.getInt("flow_frames") == result.flowFrames) { "flow frames of sentence $i" }
                check(want.size == result.audio.size) { "samples of sentence $i" }
                check(corr > 0.99) { "sentence $i: envelope correlation $corr" }
            }
        }
        log(JSONObject().put("check", "nano").put("report", report.toString()).toString())
        return report.toString()
    }

    // ---- speed -------------------------------------------------------------------------------------------------------

    fun speed(manifest: JSONObject) {
        val models = arg("models", "turbo,nano").split(',')
        val which = ints("sentences", "0,1,2,3,4")
        val passes = arg("passes", "2").toInt()
        val cooldown = arg("cooldown", "60").toLong()
        log(JSONObject().put("bench", "start").put("device", device()).put("thermal", thermal()).put("passes", passes).toString())
        val configs = models.flatMap { model -> ints("threads", "1,2,4,0").map { model to resolveThreads(it) } }.distinct()
        for ((n, config) in configs.withIndex()) {
            if (n > 0 && cooldown > 0) Thread.sleep(cooldown * 1000)
            val (model, threads) = config
            val headThreads = args["headThreads"]?.toInt() ?: threads
            val baseline = kb("VmRSS")
            val peakResettable = resetPeak()
            val before = thermal()
            val rows = JSONArray()
            val loadStart = System.nanoTime()
            if (model == "turbo") {
                val speaker = RawFiles.floats(bundle("turbo_speaker_emb.f32"))
                val ref = RawFiles.ints(bundle("turbo_ref_codes.i32"))
                val cases = turboCases(manifest, which)
                openTurbo(threads, headThreads).use { engine ->
                    val loadMs = (System.nanoTime() - loadStart) / 1e6
                    val cold = cases[0].let { engine.synthesize(it.textIds, speaker, ref, it.maxFrames, VieneuTurbo.Sampling(), UniformSource.recorded(it.uniforms)) }
                    for (pass in 1..passes) for ((k, case) in cases.withIndex()) {
                        val r = engine.synthesize(case.textIds, speaker, ref, case.maxFrames, VieneuTurbo.Sampling(), UniformSource.recorded(case.uniforms))
                        val audioS = r.audio.size / VieneuTurbo.SAMPLE_RATE.toDouble()
                        val t = r.timings
                        rows.put(JSONObject().put("pass", pass).put("sentence", which[k]).put("frames", r.frames).put("audioS", audioS).put("computeS", t.total / 1e9)
                            .put("rtf", t.total / 1e9 / audioS).put("firstAudioS", t.firstAudio / 1e9).put("prefillS", t.prefill / 1e9).put("decodeStepS", t.decodeStep / 1e9)
                            .put("acousticS", t.acoustic / 1e9).put("headsAndSamplingS", t.headsAndSampling / 1e9).put("codecS", t.codec / 1e9).put("rssMB", kb("VmRSS") / 1024))
                    }
                    log(JSONObject().put("model", "turbo").put("threads", threads).put("headThreads", headThreads).put("loadMs", loadMs).put("coldFirstRunS", cold.timings.total / 1e9).toString())
                }
            } else {
                val speaker = RawFiles.floats(bundle("nano_speaker_emb.f32"))
                val style = RawFiles.floats(bundle("nano_style.f32"))
                openNano(threads).use { engine ->
                    val loadMs = (System.nanoTime() - loadStart) / 1e6
                    fun run(i: Int) = engine.synthesize(manifest.getJSONArray("nano_sentences").getJSONObject(i).getString("ph"), speaker, style, RawFiles.floats(bundle("nano_noise_$i.f32")), 0)
                    val cold = run(which[0])
                    for (pass in 1..passes) for (i in which) {
                        val r = run(i)
                        val audioS = r.audio.size / VieneuNano.SAMPLE_RATE.toDouble()
                        val t = r.timings
                        rows.put(JSONObject().put("pass", pass).put("sentence", i).put("frames", r.flowFrames).put("audioS", audioS).put("computeS", t.total / 1e9)
                            .put("rtf", t.total / 1e9 / audioS).put("firstAudioS", t.total / 1e9).put("textDurationS", t.textAndDuration / 1e9)
                            .put("vectorEstimatorS", t.vectorEstimator / 1e9).put("decoderS", t.decoder / 1e9).put("rssMB", kb("VmRSS") / 1024))
                    }
                    log(JSONObject().put("model", "nano").put("threads", threads).put("loadMs", loadMs).put("coldFirstRunS", cold.timings.total / 1e9).toString())
                }
            }
            log(JSONObject().put("model", model).put("threads", threads).put("headThreads", if (model == "turbo") headThreads else JSONObject.NULL)
                .put("sentences", which.size).put("baselineRssMB", baseline / 1024).put("peakRssMB", kb("VmHWM") / 1024).put("peakResettable", peakResettable)
                .put("thermalBefore", before).put("thermalAfter", thermal()).put("rows", rows).toString())
        }
        log(JSONObject().put("bench", "done").toString())
    }
}
