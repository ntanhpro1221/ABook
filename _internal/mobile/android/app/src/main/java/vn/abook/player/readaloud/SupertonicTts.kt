package vn.abook.player.readaloud

import ai.onnxruntime.OnnxTensor
import android.content.Context
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.AndroidMusicStudent
import vn.abook.player.OrtRuntime
import vn.abook.player.vieneu.NumpyRandomState
import vn.abook.player.vieneu.SeaG2p
import vn.abook.player.vieneu.Tensors
import vn.abook.player.vieneu.VieneuAudio
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuUnits
import vn.abook.player.vieneu.VieneuVoices
import vn.abook.player.vieneu.VoiceModule
import vn.abook.player.vieneu.sessionOptions
import vn.abook.player.vieneu.timed
import java.io.File
import java.text.Normalizer

/**
 * Supertonic 3 text -> model input, the phone's copy of `abook/readaloud/supertonic.py` (`clean`, `speed_for`, `SupertonicEngine.ids`): the
 * desktop and the phone read the same chunk with the same characters (shared fixture tests/fixtures/readaloud/supertonic.json).
 */
object SupertonicText {
    const val LANGUAGE = "vi"
    /** Denoising steps (desktop STEPS) and the speed of a long chunk (SPEED); a chunk of at most [SHORT_SYLLABLES] syllables is read at [SHORT_SPEED]. */
    const val STEPS = 8
    const val SPEED = 1.54
    const val SHORT_SPEED = 1.05
    const val SHORT_SYLLABLES = 3
    const val LONG_SYLLABLES = 12
    const val MAX_CHARS = 300

    private const val EMOJI = "[\\x{1f600}-\\x{1f64f}\\x{1f300}-\\x{1f5ff}\\x{1f680}-\\x{1f6ff}\\x{1f700}-\\x{1f77f}\\x{1f780}-\\x{1f7ff}\\x{1f800}-\\x{1f8ff}" +
        "\\x{1f900}-\\x{1f9ff}\\x{1fa00}-\\x{1fa6f}\\x{1fa70}-\\x{1faff}\\x{2600}-\\x{26ff}\\x{2700}-\\x{27bf}\\x{1f1e6}-\\x{1f1ff}]+"
    private val emoji = Regex(EMOJI)
    private val symbols = linkedMapOf("–" to "-", "‑" to "-", "—" to "-", "¯" to " ", "_" to " ", "“" to "\"", "”" to "\"", "‘" to "'", "’" to "'",
        "´" to "'", "`" to "'", "[" to " ", "]" to " ", "|" to " ", "/" to " ", "#" to " ", "→" to " ", "←" to " ")
    private val decoration = Regex("[♥☆♡©\\\\]")
    private val spaceBefore = Regex(" ([,.!?;:'])")
    private val doubledQuote = Regex("([\"'`])\\1+")
    // Python's `\s` on str (what str.isspace() calls space); Android's ICU regex must not get UNICODE_CHARACTER_CLASS
    private val whitespace = Regex("[\\s\\x{1c}-\\x{1f}\\x{85}\\x{a0}\\x{1680}\\x{2000}-\\x{200a}\\x{2028}\\x{2029}\\x{202f}\\x{205f}\\x{3000}]+")
    private const val END_MARKS = ".!?;:,'\")]}…。」』】〉》›»"
    private val tag = Regex("</?[a-z]{2,3}>")

    /** `supertonic.clean`: the text as the model wants it - decomposed (NFKD), emoji and decorations gone, punctuation and spaces settled, a final mark. */
    fun clean(text: String): String {
        var out = Normalizer.normalize(tag.replace(text, ""), Normalizer.Form.NFKD)
        out = emoji.replace(out, "")
        for ((old, new) in symbols) out = out.replace(old, new)
        out = decoration.replace(out, "").replace("@", " at ")
        out = doubledQuote.replace(spaceBefore.replace(out, "$1"), "$1")
        out = whitespace.replace(out, " ").trim(' ')
        return if (out.isEmpty() || out.last() in END_MARKS) out else "$out."
    }

    /** Python's `\w` (letters, numbers, "_") for the syllable count of [speedFor]. */
    private fun word(point: Int): Boolean = point == '_'.code || Character.isLetter(point) || when (Character.getType(point).toByte()) {
        Character.DECIMAL_DIGIT_NUMBER, Character.LETTER_NUMBER, Character.OTHER_NUMBER -> true
        else -> false
    }

    /** `supertonic.speed_for`: speed of one (normalised) chunk, from [SHORT_SPEED] for a few syllables up to [SPEED] from [LONG_SYLLABLES] on. */
    fun speedFor(text: String): Double {
        var syllables = 0
        var inside = false
        text.codePoints().forEach { point ->
            val now = word(point)
            if (now && !inside) syllables++
            inside = now
        }
        val share = ((syllables - SHORT_SYLLABLES).toDouble() / (LONG_SYLLABLES - SHORT_SYLLABLES)).coerceIn(0.0, 1.0)
        return Math.round((SHORT_SPEED + (SPEED - SHORT_SPEED) * share) * 1000) / 1000.0
    }

    // The ten voices come out at -24.1..-25.6 LUFS, 4-5 dB under every voice's -20 target, and the player can only turn down: +4 dB when the clip
    // is made, never past -1 dBFS (desktop GAIN_DB, PEAK_CEILING).
    const val GAIN_DB = 4.0
    private val PEAK_CEILING = Math.pow(10.0, -1.0 / 20)

    /** `supertonic.louder`: [wave] raised [GAIN_DB], less when its peak would pass -1 dBFS (in place; float32 like numpy). */
    fun louder(wave: FloatArray): FloatArray {
        val peak = wave.maxOfOrNull { Math.abs(it) }?.toDouble() ?: 0.0
        var gain = Math.pow(10.0, GAIN_DB / 20)
        if (peak > 0 && peak * gain > PEAK_CEILING) gain = maxOf(1.0, PEAK_CEILING / peak)
        val factor = gain.toFloat()
        for (i in wave.indices) wave[i] *= factor
        return wave
    }

    /** `SupertonicEngine.ids`: model ids of [text] (already [clean]) inside the language tags; characters the model does not know are dropped. */
    fun ids(text: String, indexer: IntArray): LongArray {
        val out = ArrayList<Long>()
        "<$LANGUAGE>$text</$LANGUAGE>".codePoints().forEach { point ->
            if (point < indexer.size && indexer[point] >= 0) out.add(indexer[point].toLong())
        }
        return out.toLongArray()
    }
}

/** What reads one chunk ([SupertonicEngine]; tests use a fake). */
interface SupertonicSynth {
    val sampleRate: Int
    /** One chunk (normalised text) -> mono float audio at [sampleRate]; [random] draws the start noise. */
    fun infer(text: String, name: String, random: NumpyRandomState, speed: Double): FloatArray
}

/**
 * Supertonic 3 (Supertone, 99M parameters, OpenRAIL-M) on ONNX Runtime CPU, a port of the desktop's `SupertonicEngine`: duration predictor ->
 * text encoder -> [SupertonicText.STEPS] denoising steps of the vector estimator from legacy-numpy noise -> vocoder, 44.1 kHz. [folder] holds the
 * pinned repo files (onnx/, voice_styles/) exactly as the desktop module downloads them.
 */
class SupertonicEngine(private val folder: File, threads: Int) : SupertonicSynth, AutoCloseable {
    class Style(val ttl: FloatArray, val ttlShape: LongArray, val dp: FloatArray, val dpShape: LongArray)

    /** Wall time of the last [infer] per stage (ns): duration + text encoder, vector estimator, vocoder. */
    val clock = LongArray(3)

    private val env = OrtEnvironment.getEnvironment()
    private val config = JSONObject(File(folder, CONFIG_FILE).readText(Charsets.UTF_8))
    override val sampleRate: Int = config.getJSONObject("ae").getInt("sample_rate")
    private val chunk = config.getJSONObject("ae").getInt("base_chunk_size") * config.getJSONObject("ttl").getInt("chunk_compress_factor")
    private val latentDim = config.getJSONObject("ttl").getInt("latent_dim") * config.getJSONObject("ttl").getInt("chunk_compress_factor")
    val indexer: IntArray = JSONArray(File(folder, INDEXER_FILE).readText(Charsets.UTF_8)).let { array -> IntArray(array.length()) { array.getInt(it) } }
    private val options = sessionOptions(threads)
    private val sessions: Map<String, OrtSession> = ONNX.associateWith { env.createSession(File(folder, "onnx/$it.onnx").absolutePath, options) }
    private val styles = HashMap<String, Style>()

    /** (style_ttl, style_dp) of voice [name], read once. */
    @Synchronized
    fun style(name: String): Style = styles.getOrPut(name) { readStyle(File(folder, "$STYLE_DIR/$name.json")) }

    /** One chunk -> mono float audio at [sampleRate] (edges trimmed and faded); [random] draws the start noise like the desktop's RandomState. */
    override fun infer(text: String, name: String, random: NumpyRandomState, speed: Double): FloatArray {
        val steps = SupertonicText.STEPS
        clock.fill(0)
        val cleaned = SupertonicText.clean(text)
        val ids = SupertonicText.ids(cleaned, indexer)
        if (cleaned.isEmpty() || ids.isEmpty()) return FloatArray(0)
        val style = style(name)
        val length = ids.size.toLong()
        val opened = ArrayList<AutoCloseable>()
        fun <T : AutoCloseable> keep(item: T): T = item.also { opened.add(it) }
        try {
            val textIds = keep(Tensors.longs(env, ids, 1, length))
            val textMask = keep(Tensors.floats(env, FloatArray(ids.size) { 1f }, 1, 1, length))
            val styleTtl = keep(Tensors.floats(env, style.ttl, *style.ttlShape))
            val styleDp = keep(Tensors.floats(env, style.dp, *style.dpShape))
            val seconds = timed(clock, 0) {
                sessions.getValue("duration_predictor").run(mapOf("text_ids" to textIds, "style_dp" to styleDp, "text_mask" to textMask))
                    .use { Tensors.floatData(it.get(0) as OnnxTensor)[0] }
            } / speed.toFloat() // float32 like numpy's array / Python float
            val embedding = keep(timed(clock, 0) { sessions.getValue("text_encoder").run(mapOf("text_ids" to textIds, "style_ttl" to styleTtl, "text_mask" to textMask)) })
            val textEmb = embedding.get(0) as OnnxTensor
            val samples = (seconds.toDouble() * sampleRate).toInt()
            val frames = maxOf(1, (samples + chunk - 1) / chunk)
            val latentMask = keep(Tensors.floats(env, FloatArray(frames) { 1f }, 1, 1, frames.toLong()))
            val total = keep(Tensors.floats(env, floatArrayOf(steps.toFloat()), 1))
            var latent = random.standardNormalFloats(latentDim * frames)
            for (step in 0 until steps) {
                latent = Tensors.floats(env, latent, 1, latentDim.toLong(), frames.toLong()).use { noisy ->
                    Tensors.floats(env, floatArrayOf(step.toFloat()), 1).use { current ->
                        timed(clock, 1) {
                            sessions.getValue("vector_estimator").run(mapOf("noisy_latent" to noisy, "text_emb" to textEmb, "style_ttl" to styleTtl,
                                "text_mask" to textMask, "latent_mask" to latentMask, "current_step" to current, "total_step" to total))
                        }.use { Tensors.floatData(it.get(0) as OnnxTensor) }
                    }
                }
            }
            val wave = Tensors.floats(env, latent, 1, latentDim.toLong(), frames.toLong()).use { input ->
                timed(clock, 2) { sessions.getValue("vocoder").run(mapOf("latent" to input)) }.use { Tensors.floatData(it.get(0) as OnnxTensor) }
            }
            val cut = FloatArray(minOf(samples, wave.size)) { wave[it].coerceIn(-1f, 1f) }
            return VieneuAudio.trimAndFade(cut, sampleRate)
        } finally {
            opened.asReversed().forEach { runCatching { it.close() } }
        }
    }

    override fun close() {
        sessions.values.forEach { runCatching { it.close() } }
        options.close()
    }

    companion object {
        val ONNX = listOf("duration_predictor", "text_encoder", "vector_estimator", "vocoder")
        const val CONFIG_FILE = "onnx/tts.json"
        const val INDEXER_FILE = "onnx/unicode_indexer.json"
        const val STYLE_DIR = "voice_styles"

        private fun flatten(value: Any, out: ArrayList<Float>) {
            if (value is JSONArray) for (i in 0 until value.length()) flatten(value.get(i), out) else out.add((value as Number).toDouble().toFloat())
        }

        private fun tensor(json: JSONObject): Pair<FloatArray, LongArray> {
            val dims = json.getJSONArray("dims").let { array -> LongArray(array.length()) { array.getLong(it) } }
            val values = ArrayList<Float>()
            flatten(json.getJSONArray("data"), values)
            require(values.size.toLong() == dims.fold(1L) { a, b -> a * b }) { "phong cách giọng sai cỡ" }
            return values.toFloatArray() to dims
        }

        /** A voice style file (`loader.load_voice_style_from_json_file`): float32 tensors of the given dims. */
        fun readStyle(file: File): Style {
            val json = JSONObject(file.readText(Charsets.UTF_8))
            val (ttl, ttlShape) = tensor(json.getJSONObject("style_ttl"))
            val (dp, dpShape) = tensor(json.getJSONObject("style_dp"))
            return Style(ttl, ttlShape, dp, dpShape)
        }
    }
}

/**
 * Paragraph -> one clip, the phone's `SupertonicProvider._speak` + `synthesize`: the units of VieNeu ([VieneuUnits], up to
 * [SupertonicText.MAX_CHARS] characters), each unit's text through sea-g2p's normaliser ([normalize]: numbers, dates, times spelled out),
 * one take per unit seeded from voice + text, raised [SupertonicText.louder], joined with the desktop's minimum pauses; word timings spread
 * by syllables ([VieneuSpeaker.timed]).
 */
class SupertonicSpeaker(
    /** Sentences of one unit -> the text to read ([SeaG2p.normalizeUnit]; the sentences joined when sea-g2p is not on the phone). */
    private val normalize: (List<String>) -> String,
) {
    fun speak(engine: SupertonicSynth, name: String, text: String, origin: String? = null): VieneuSpeaker.Spoken {
        val (tokens, units) = VieneuUnits.units(text, SupertonicText.MAX_CHARS, origin)
        val waves = ArrayList<FloatArray>()
        val pauses = ArrayList<Double>()
        for (unit in units) {
            val spoken = normalize(unit.pieces)
            val random = NumpyRandomState(VieneuSpeaker.seedOf(SupertonicVoices.PREFIX, name, unit.pieces.joinToString(" ")))
            waves.add(SupertonicText.louder(engine.infer(spoken, name, random, SupertonicText.speedFor(spoken))))
            val last = spoken.trimEnd().lastOrNull()
            pauses.add(VieneuAudio.GAP_SECONDS.getValue(if (last == null || last in ".!?") "sentence" else "minor"))
        }
        val (joined, spans) = VieneuAudio.join(waves, engine.sampleRate, pauses.dropLast(1))
        return VieneuSpeaker.timed(tokens, units, joined, spans, engine.sampleRate)
    }
}

/**
 * The Supertonic voices of this phone for "Nghe ngay" (provider "supertonic", offline): the module ([SupertonicModule], `files/supertonic`) and
 * the engine, loaded on first use and kept for the process. Synthesis is serialised: one paragraph at a time, on the caller's (background) thread.
 */
object SupertonicVoices {
    const val PREFIX = "supertonic"
    /** Order shown: the four voices the owner liked first (desktop NAMES). F = female, M = male. */
    val NAMES = listOf("F1", "F3", "M4", "M5", "F2", "F4", "F5", "M1", "M2", "M3")
    /** The paragraph the self-benchmark reads (desktop `supertonic.BENCH_TEXT`). */
    const val BENCH_TEXT = "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa. Trời hôm nay đẹp quá."
    /** Emulator 07-10: 1 thread RTF 0.39, 2 -> 0.33, 4 -> 0.32 (docs/research/SUPERTONIC_PHONE.md); more gains nothing on these small graphs. */
    private const val MAX_THREADS = 4

    private var context: Context? = null
    private var module: SupertonicModule? = null
    private var engine: SupertonicEngine? = null

    @Synchronized
    fun module(appContext: Context): SupertonicModule = module ?: run {
        val ctx = appContext.applicationContext
        context = ctx
        val files = ctx.filesDir
        SupertonicModule(File(files, "supertonic"), listOf(File(files, "music/student"), File(files, "vieneu")), File(files, "vieneu"),
            OrtRuntime.deviceAbi(), VieneuVoices.facts(ctx), benchmark = { benchmark() }, forget = ::forget, metered = { AndroidMusicStudent.metered(ctx) })
            .also { module = it }
    }

    /** Drop the loaded engine (the module is about to replace or remove files). */
    @Synchronized
    fun forget() {
        engine?.let { runCatching { it.close() } }
        engine = null
    }

    fun gender(name: String) = if (name.startsWith("F")) "female" else if (name.startsWith("M")) "male" else ""

    /** Voices for the list ("Supertonic F1"); empty when the module is not on this phone. Never loads the engine. */
    fun voices(appContext: Context): List<VoiceInfo> {
        module(appContext).installed() ?: return emptyList()
        return NAMES.map { VoiceInfo("$PREFIX:$it", "Supertonic $it", PREFIX, false, false, gender(it)) }
    }

    fun voice(appContext: Context, id: String): Voice {
        module(appContext)
        return SupertonicVoice(id)
    }

    @Synchronized
    private fun ready(): Pair<SupertonicEngine, SupertonicSpeaker> {
        val ctx = context ?: throw VoiceException("Chưa khởi động", reason = "voice")
        val installed = module(ctx).installed() ?: throw VoiceException("Giọng Supertonic chưa tải trên điện thoại này - tải trong Cài đặt → Giọng đọc.", reason = "voice")
        try {
            OrtRuntime.load(installed.ortFolder)
            val reader = installed.g2p?.let { (library, dictionary) -> SeaG2p.shared(library, dictionary) }
            val loaded = engine ?: SupertonicEngine(installed.model, minOf(Runtime.getRuntime().availableProcessors(), MAX_THREADS)).also { engine = it }
            val normalize: (List<String>) -> String = if (reader != null) reader::normalizeUnit else { pieces -> pieces.joinToString(" ") }
            return loaded to SupertonicSpeaker(normalize)
        } catch (failure: Throwable) {
            if (failure is VoiceException) throw failure
            throw VoiceException("Giọng Supertonic chưa sẵn sàng (${failure.message ?: failure.javaClass.simpleName}) - hãy tải lại Giọng Supertonic trong Cài đặt.",
                cause = failure, reason = "voice")
        }
    }

    /** One paragraph -> [out] (16-bit WAV at 44.1 kHz) + words. */
    @Synchronized
    fun synthesize(id: String, text: String, out: File, origin: String? = null): Clip {
        val name = id.removePrefix("$PREFIX:")
        if (name !in NAMES) throw VoiceException("Không có giọng Supertonic này.", reason = "voice")
        val (loaded, speaker) = ready()
        val spoken = try {
            speaker.speak(loaded, name, text, origin)
        } catch (failure: OutOfMemoryError) {
            forget()
            throw VoiceException("Điện thoại không đủ bộ nhớ cho giọng Supertonic lúc này.", cause = failure, reason = "voice")
        }
        if (spoken.samples.isEmpty()) throw VoiceException("Đoạn này không có chữ nào đọc được.", reason = "empty")
        VieneuAudio.writeWav(spoken.samples, spoken.rate, out)
        return Clip(out, spoken.durationMs, spoken.words, id)
    }

    /** Self-benchmark after a download (desktop `SupertonicProvider.benchmark`): load the engine, read "Xin chào." once (not counted: ONNX
     *  Runtime's first run is slower), then [BENCH_TEXT] with the first voice. */
    fun benchmark(): VoiceModule.Benchmark = synchronized(this) {
        val began = System.nanoTime()
        val (loaded, speaker) = ready()
        speaker.speak(loaded, NAMES[0], "Xin chào.")
        val warmed = System.nanoTime()
        val spoken = speaker.speak(loaded, NAMES[0], BENCH_TEXT)
        VoiceModule.Benchmark.of(began, warmed, System.nanoTime(), spoken.samples.size, spoken.rate)
    }
}

/** A Supertonic voice ("supertonic:F1"): offline, WAV clips, words spread by syllables. */
class SupertonicVoice(override val id: String) : Voice {
    override val extension = "wav"
    override fun synthesize(text: String, out: File): Clip = SupertonicVoices.synthesize(id, text, out)
    override fun synthesize(text: String, out: File, origin: String?): Clip = SupertonicVoices.synthesize(id, text, out, origin)
}
