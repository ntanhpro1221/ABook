package vn.abook.player

import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.vieneu.RawFiles
import vn.abook.player.vieneu.UniformSource
import vn.abook.player.vieneu.VieneuBackend
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
 * (0,1,2,3,4), ep (cpu,xnnpack,nnapi - see [VieneuBackend]), headThreads / codecThreads (default = threads), spin (0/1), seconds (sustain,
 * 120), turbo / bundle (folder names; turbo_fp32 + bundle_fp32 is the fp32 reference check).
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
            .put("maxMHzPerCore", JSONArray(max.map { it / 1000 })).put("cpuset", read("/proc/self/cpuset"))
            .put("cpusAllowed", runCatching { File("/proc/self/status").readLines().first { it.startsWith("Cpus_allowed_list:") }.substringAfter(':').trim() }.getOrDefault(""))
            .put("providers", JSONArray(runCatching { ai.onnxruntime.OrtEnvironment.getAvailableProviders().map { it.name } }.getOrDefault(emptyList<String>())))
    }

    // ---- sessions ----------------------------------------------------------------------------------------------------

    private fun resolveThreads(n: Int) = if (n <= 0) cores() else n

    private fun openTurbo(threads: Int, headThreads: Int = threads, codecThreads: Int = threads, backend: VieneuBackend = VieneuBackend.CPU, spinning: Boolean = false) =
        VieneuTurbo(File(pack, "models/$turboFolder"), File(pack, "models/codec"), threads, headThreads, codecThreads, backend, spinning)

    private fun openNano(threads: Int, backend: VieneuBackend = VieneuBackend.CPU, spinning: Boolean = false) = VieneuNano(File(pack, "models/nano"), threads, backend, spinning)

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

    private fun rms(audio: FloatArray): Double {
        var sum = 0.0
        for (x in audio) sum += x.toDouble() * x
        return if (audio.isEmpty()) 0.0 else sqrt(sum / audio.size)
    }

    /** One engine configuration, opened: [run] synthesizes one bench sentence and returns its row (timings, length, loudness, memory). */
    private inner class Runner(private val manifest: JSONObject, val model: String, val threads: Int, val backend: VieneuBackend) : AutoCloseable {
        val headThreads = args["headThreads"]?.toInt() ?: threads
        val codecThreads = args["codecThreads"]?.toInt()?.let(::resolveThreads) ?: threads
        private val spinning = arg("spin", "0") == "1"
        private val sentences = manifest.getJSONArray("sentences")
        private val nanoSentences = manifest.optJSONArray("nano_sentences")
        private val turboSpeaker by lazy { RawFiles.floats(bundle("turbo_speaker_emb.f32")) }
        private val turboRef by lazy { RawFiles.ints(bundle("turbo_ref_codes.i32")) }
        private val turboCase = HashMap<Int, TurboCase>()
        private val nanoSpeaker by lazy { RawFiles.floats(bundle("nano_speaker_emb.f32")) }
        private val nanoStyle by lazy { RawFiles.floats(bundle("nano_style.f32")) }
        private val loadStart = System.nanoTime()
        private val turbo = if (model == "turbo") openTurbo(threads, headThreads, codecThreads, backend, spinning) else null
        private val nano = if (model == "nano") openNano(threads, backend, spinning) else null
        val loadMs = (System.nanoTime() - loadStart) / 1e6

        fun describe(): JSONObject = JSONObject().put("model", model).put("threads", threads).put("ep", backend.name.lowercase()).put("spin", spinning)
            .put("headThreads", if (turbo != null) headThreads else JSONObject.NULL).put("codecThreads", if (turbo != null) codecThreads else JSONObject.NULL)

        fun run(i: Int): JSONObject {
            val chars = sentences.getString(i).length
            val row = JSONObject().put("sentence", i).put("chars", chars)
            if (turbo != null) {
                val case = turboCase.getOrPut(i) { turboCases(manifest, listOf(i)).single() }
                val r = turbo.synthesize(case.textIds, turboSpeaker, turboRef, case.maxFrames, VieneuTurbo.Sampling(), UniformSource.recorded(case.uniforms))
                val audioS = r.audio.size / VieneuTurbo.SAMPLE_RATE.toDouble()
                val t = r.timings
                row.put("frames", r.frames).put("audioS", audioS).put("computeS", t.total / 1e9).put("rtf", t.total / 1e9 / audioS).put("firstAudioS", t.firstAudio / 1e9)
                    .put("prefillS", t.prefill / 1e9).put("decodeStepS", t.decodeStep / 1e9).put("acousticS", t.acoustic / 1e9)
                    .put("headsAndSamplingS", t.headsAndSampling / 1e9).put("codecS", t.codec / 1e9).put("rms", rms(r.audio)).put("desktopAudioS", case.desktopAudio.size / VieneuTurbo.SAMPLE_RATE.toDouble())
            } else {
                val meta = nanoSentences!!.getJSONObject(i)
                val r = nano!!.synthesize(meta.getString("ph"), nanoSpeaker, nanoStyle, RawFiles.floats(bundle("nano_noise_$i.f32")), 0)
                val audioS = r.audio.size / VieneuNano.SAMPLE_RATE.toDouble()
                val t = r.timings
                row.put("frames", r.flowFrames).put("audioS", audioS).put("computeS", t.total / 1e9).put("rtf", t.total / 1e9 / audioS).put("firstAudioS", t.total / 1e9)
                    .put("textDurationS", t.textAndDuration / 1e9).put("vectorEstimatorS", t.vectorEstimator / 1e9).put("decoderS", t.decoder / 1e9)
                    .put("rms", rms(r.audio)).put("desktopAudioS", meta.getInt("audio_samples") / VieneuNano.SAMPLE_RATE.toDouble())
            }
            return row.put("rssMB", kb("VmRSS") / 1024)
        }

        override fun close() {
            turbo?.close()
            nano?.close()
        }
    }

    /**
     * Every configuration of models x threads x ep (cpu, xnnpack, nnapi): open it (load time), one cold run of the first sentence, then
     * [passes] timed passes over the sentences; [cooldown] seconds between configurations. Other arguments: codecThreads (Turbo's codec;
     * default = threads), headThreads, spin (1 = let ORT's pool spin between ops).
     */
    fun speed(manifest: JSONObject) {
        val which = ints("sentences", "0,1,2,3,4")
        val passes = arg("passes", "2").toInt()
        val cooldown = arg("cooldown", "60").toLong()
        log(JSONObject().put("bench", "start").put("device", device()).put("thermal", thermal()).put("passes", passes).toString())
        val configs = arg("models", "turbo,nano").split(',').flatMap { model ->
            arg("ep", "cpu").split(',').flatMap { ep -> ints("threads", "1,2,4,0").map { Triple(model, resolveThreads(it), VieneuBackend.parse(ep)) } }
        }.distinct()
        for ((n, config) in configs.withIndex()) {
            if (n > 0 && cooldown > 0) Thread.sleep(cooldown * 1000)
            val (model, threads, backend) = config
            val baseline = kb("VmRSS")
            val peakResettable = resetPeak()
            val before = thermal()
            val rows = JSONArray()
            val described = try {
                Runner(manifest, model, threads, backend).use { runner ->
                    val coldStart = System.nanoTime()
                    runner.run(which[0])
                    log(runner.describe().put("loadMs", runner.loadMs).put("coldFirstRunS", (System.nanoTime() - coldStart) / 1e9).toString())
                    for (pass in 1..passes) for (i in which) rows.put(runner.run(i).put("pass", pass))
                    runner.describe()
                }
            } catch (failure: Exception) { // an EP that cannot take the graph is a result, not the end of the run
                log(JSONObject().put("model", model).put("threads", threads).put("ep", backend.name.lowercase()).put("error", failure.toString()).toString())
                continue
            }
            log(described.put("sentences", which.size).put("baselineRssMB", baseline / 1024).put("peakRssMB", kb("VmHWM") / 1024).put("peakResettable", peakResettable)
                .put("thermalBefore", before).put("thermalAfter", thermal()).put("rows", rows).toString())
        }
        log(JSONObject().put("bench", "done").toString())
    }

    /**
     * Continuous synthesis for [seconds] (default 120) with ONE configuration (models/threads/ep: the first of each list), cycling over the
     * sentences: does the phone slow down as it heats? One row per sentence with its start time and the CPU clocks / battery temperature.
     */
    fun sustain(manifest: JSONObject) {
        val which = ints("sentences", "0,1,2,3,4")
        val seconds = arg("seconds", "120").toDouble()
        val model = arg("models", "turbo").split(',').first()
        val threads = resolveThreads(ints("threads", "2").first())
        val backend = VieneuBackend.parse(arg("ep", "cpu").split(',').first())
        log(JSONObject().put("bench", "sustain-start").put("device", device()).put("thermal", thermal()).put("seconds", seconds).toString())
        resetPeak()
        Runner(manifest, model, threads, backend).use { runner ->
            runner.run(which[0])
            val started = System.nanoTime()
            var k = 0
            while ((System.nanoTime() - started) / 1e9 < seconds) {
                val at = (System.nanoTime() - started) / 1e9
                val row = runner.run(which[k++ % which.size]).put("atS", at).put("thermal", thermal())
                log(runner.describe().put("sustainRow", row).toString())
            }
            log(runner.describe().put("bench", "sustain-done").put("peakRssMB", kb("VmHWM") / 1024).put("thermal", thermal()).toString())
        }
    }
}
