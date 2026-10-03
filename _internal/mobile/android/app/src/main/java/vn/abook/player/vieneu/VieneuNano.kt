package vn.abook.player.vieneu

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import org.json.JSONObject
import java.io.File
import kotlin.math.exp

/**
 * VieNeu-TTS v3 Nano on ONNX Runtime, a port of `vieneu/v3nano.py` (`OnnxV3NanoEngine`): a 48M-parameter flow-matching model.
 * Text encoder + duration predictor give the length, then [steps] Euler steps of the vector estimator (two passes each with
 * classifier-free guidance [cfg]) turn noise into a 144-channel latent that the codec decoder turns into 24 kHz audio. Not
 * autoregressive, so the whole chunk is ready at once. [dir] holds the repo's files as pinned (four graphs, `config.json`, `constants.npz`).
 */
class VieneuNano(dir: File, threads: Int, backend: VieneuBackend = VieneuBackend.CPU, spinning: Boolean = false) : AutoCloseable {
    class Timings {
        var textAndDuration = 0L
        var vectorEstimator = 0L
        var decoder = 0L
        var total = 0L
    }

    class Result(val audio: FloatArray, val flowFrames: Int, val timings: Timings)

    private val env = OrtEnvironment.getEnvironment()
    private val cfg = JSONObject(File(dir, "config.json").readText())
    // single characters only: "<pad>" / "<bos>" / "<eos>" are not characters of a phoneme string (the desktop's `ch in vocab` never matches them)
    private val vocab: Map<Int, Int> = cfg.getJSONObject("vocab").let { json ->
        json.keys().asSequence().filter { it.codePointCount(0, it.length) == 1 }.associate { it.codePointAt(0) to json.getInt(it) }
    }
    private val emotionTags: Map<String, String> = cfg.optJSONObject("emotion_tags")?.let { json -> json.keys().asSequence().associateWith { json.getString(it) } }.orEmpty()
    private val bos = cfg.getInt("bos_id")
    private val eos = cfg.getInt("eos_id")
    private val pad = cfg.getInt("pad_id")
    private val fps = cfg.optDouble("flow_fps", 24000.0 / 256 / 6)
    private val latentChannels = 144
    private val nStyle = cfg.getInt("n_style")
    private val styleDim = cfg.getInt("style_dim")
    private val constants = NpzFile(File(dir, "constants.npz"))
    private val nullSpeaker = constants.floats("null_spk").data
    private val nullStyle = constants.floats("null_style").data

    private val options = sessionOptions(threads, backend, spinning)
    private val textEncoder = env.createSession(File(dir, "text_encoder.onnx").absolutePath, options)
    private val duration = env.createSession(File(dir, "duration_predictor.onnx").absolutePath, options)
    private val estimator = env.createSession(File(dir, "vector_estimator.onnx").absolutePath, options)
    private val decoder = env.createSession(File(dir, "codec_decoder.onnx").absolutePath, options)

    /** Phone string (may hold `<|emotion_k|>`) -> ids with begin/end markers; characters outside the vocabulary are dropped. */
    fun encodePhones(phones: String): LongArray {
        var text = phones
        for ((tag, char) in emotionTags) text = text.replace(tag, char)
        val ids = ArrayList<Long>()
        ids.add(bos.toLong())
        var at = 0
        while (at < text.length) {
            val point = text.codePointAt(at)
            at += Character.charCount(point)
            vocab[point]?.let { ids.add(it.toLong()) }
        }
        ids.add(eos.toLong())
        return ids.toLongArray()
    }

    /** One chunk of phonemes -> 24 kHz audio. [noise] is the start latent `[144][frames]` (the bench replays the desktop's); null draws it from [seed]
     *  exactly as the desktop does (`np.random.default_rng(seed).standard_normal`). */
    fun synthesize(phones: String, speaker: FloatArray, style: FloatArray, noise: FloatArray?, seed: Long, steps: Int = 16, cfgScale: Float = 3f, sway: Double = 0.0, speed: Double = 1.0): Result {
        val timings = Timings()
        val started = System.nanoTime()
        val ids = encodePhones(phones)
        val length = ids.size.toLong()
        val mask = arrayOf(BooleanArray(ids.size) { ids[it] != pad.toLong() })
        val clock = LongArray(3)
        val speakerTensor = Tensors.floats(env, speaker, 1, speaker.size.toLong())
        val styleTensor = Tensors.floats(env, style, 1, nStyle.toLong(), styleDim.toLong())
        val maskTensor = Tensors.bools(env, mask)
        val idsTensor = Tensors.longs(env, ids, 1, length)
        val nullSpeakerTensor = Tensors.floats(env, nullSpeaker, 1, nullSpeaker.size.toLong())
        val nullStyleTensor = Tensors.floats(env, nullStyle, 1, nStyle.toLong(), styleDim.toLong())
        val nullIds = Tensors.longs(env, longArrayOf(bos.toLong(), eos.toLong()), 1, 2)
        val nullMask = Tensors.bools(env, arrayOf(booleanArrayOf(true, true)))
        val tensors = listOf(speakerTensor, styleTensor, maskTensor, idsTensor, nullSpeakerTensor, nullStyleTensor, nullIds, nullMask)
        try {
            val ctx = timed(clock, 0) { textEncoder.run(mapOf("ids" to idsTensor, "style" to styleTensor)) }
            val nullCtx = timed(clock, 0) { textEncoder.run(mapOf("ids" to nullIds, "style" to nullStyleTensor)) }
            try {
                val ctxTensor = ctx.get(0) as OnnxTensor
                val nullCtxTensor = nullCtx.get(0) as OnnxTensor
                val logSeconds = timed(clock, 0) {
                    duration.run(mapOf("ctx" to ctxTensor, "ctx_mask" to maskTensor, "spk" to speakerTensor)).use { Tensors.floatData(it.get(0) as OnnxTensor)[0] }
                }
                val seconds = minOf(exp(logSeconds.toDouble()) / maxOf(speed, 1e-3), MAX_CHUNK_SECONDS)
                val frames = maxOf(MIN_FRAMES, Math.rint(seconds * fps).toInt())
                var x = if (noise != null && noise.size == latentChannels * frames) noise.copyOf() else NumpyGenerator(seed).standardNormalFloats(latentChannels * frames)
                for (i in 0 until steps) {
                    val from = swayed(i, steps, sway)
                    val to = swayed(i + 1, steps, sway)
                    val v = estimate(x, frames, from.toFloat(), ctxTensor, maskTensor, speakerTensor, styleTensor, clock)
                    if (cfgScale > 0f) {
                        val unconditional = estimate(x, frames, from.toFloat(), nullCtxTensor, nullMask, nullSpeakerTensor, nullStyleTensor, clock)
                        for (k in v.indices) v[k] = unconditional[k] + cfgScale * (v[k] - unconditional[k])
                    }
                    val dt = (to - from).toFloat()
                    x = FloatArray(x.size) { x[it] + dt * v[it] }
                }
                val audio = Tensors.floats(env, x, 1, latentChannels.toLong(), frames.toLong()).use { latent ->
                    timed(clock, 2) { decoder.run(mapOf("x" to latent)) }.use { Tensors.floatData(it.get(0) as OnnxTensor) }
                }
                for (i in audio.indices) audio[i] = audio[i].coerceIn(-1f, 1f)
                timings.textAndDuration = clock[0]
                timings.vectorEstimator = clock[1]
                timings.decoder = clock[2]
                timings.total = System.nanoTime() - started
                return Result(audio, frames, timings)
            } finally {
                ctx.close()
                nullCtx.close()
            }
        } finally {
            tensors.forEach { it.close() }
        }
    }

    /** Time grid point [i] of the Euler schedule: linspace(0,1) bent by [sway] (0 = uniform). */
    private fun swayed(i: Int, steps: Int, sway: Double): Double {
        val u = i.toDouble() / steps
        return u + sway * (Math.cos(Math.PI / 2 * u) - 1 + u)
    }

    private fun estimate(x: FloatArray, frames: Int, t: Float, ctx: OnnxTensor, mask: OnnxTensor, speaker: OnnxTensor, style: OnnxTensor, clock: LongArray): FloatArray =
        Tensors.floats(env, x, 1, latentChannels.toLong(), frames.toLong()).use { latent ->
            Tensors.floats(env, floatArrayOf(t), 1).use { time ->
                timed(clock, 1) { estimator.run(mapOf("x" to latent, "t" to time, "ctx" to ctx, "ctx_mask" to mask, "spk" to speaker, "style" to style)) }
                    .use { Tensors.floatData(it.get(0) as OnnxTensor) }
            }
        }

    override fun close() {
        listOf(textEncoder, duration, estimator, decoder).forEach { runCatching { it.close() } }
        options.close()
    }

    companion object {
        const val SAMPLE_RATE = 24_000
        private const val MAX_CHUNK_SECONDS = 15.0
        private const val MIN_FRAMES = 2
    }
}
