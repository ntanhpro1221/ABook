package vn.abook.player.vieneu

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import kotlin.math.sqrt

/**
 * VieNeu-TTS v3 Turbo (int8 backbone) on ONNX Runtime, a port of `vieneu/_v3_turbo_engine/onnx_runtime_lite.py`: prefill the prompt
 * (style, phoneme ids, then the voice's reference codes), then per frame the acoustic decoder emits the 16 codebook codes one by one
 * (a 1-layer cached transformer + the tied output heads, plain float maths here) and the 12-layer backbone steps with its KV cache;
 * the MOSS codec decodes all codes to 48 kHz audio. The caller gives the token ids ([ByteBpe] over [SeaG2p] phonemes: [VieneuSpeaker]).
 *
 * [dir] holds the repo's `onnx_int8` files as pinned: `vieneu_{prefill,decode_step,acoustic_cached}.onnx` + `vieneu_backbone_shared.data`,
 * `config.json` and the heads in `vieneu_v3_heads.npz` (read in place, [NpzFile]); [codecDir] holds the codec decode graph.
 * [threads] runs the per-frame graphs (small, latency-bound: on a phone more threads than big cores makes them slower), [codecThreads]
 * the codec (one large graph per chunk, gains from every core), [headThreads] the output-head dot products.
 */
class VieneuTurbo(dir: File, codecDir: File, threads: Int, private val headThreads: Int = threads, codecThreads: Int = threads,
                  backend: VieneuBackend = VieneuBackend.CPU, spinning: Boolean = false) : AutoCloseable {
    class Sampling(val temperature: Float = 0.8f, val topK: Int = 25, val topP: Double = 0.95, val repetitionPenalty: Float = 1.2f, val repetitionWindow: Int = 64)

    /** Wall times in ns: ORT time per graph, and the rest of the loop (embeddings, output heads, sampling). */
    class Timings {
        var prefill = 0L
        var decodeStep = 0L
        var acoustic = 0L
        var codec = 0L
        var total = 0L
        var firstAudio = 0L
        val ortTotal get() = prefill + decodeStep + acoustic + codec
        val headsAndSampling get() = total - ortTotal
    }

    class Result(val codes: IntArray, val frames: Int, val audio: FloatArray, val timings: Timings)

    private val env = OrtEnvironment.getEnvironment()
    private val cfg = JSONObject(File(dir, "config.json").readText())
    private val nVq = cfg.getInt("n_vq")
    private val hidden = cfg.getInt("hidden_size")
    private val layers = cfg.getInt("num_hidden_layers")
    private val localLayers = cfg.optInt("local_num_hidden_layers", 1)
    private val localHeads = cfg.optInt("local_num_attention_heads", 8)
    private val localHeadDim = hidden / localHeads
    private val audioPad = cfg.getInt("audio_pad_token_id")
    private val audioVocab = cfg.getInt("audio_vocab_size")
    private val refSlot = cfg.getInt("audio_ref_slot_token_id")
    private val speechStart = cfg.getInt("speech_generation_start_token_id")
    private val speechEnd = cfg.getInt("speech_generation_end_token_id")
    private val textVocab = cfg.getInt("text_vocab_size")

    private val useSpeaker = cfg.optBoolean("use_speaker_embedding", false)
    /** Prompt text column ids around the phoneme tokens: style, prompt start ... prompt end. */
    val styleId = cfg.optInt("default_style_token_id", 16)
    val promptStart = cfg.getInt("text_prompt_start_token_id")
    val promptEnd = cfg.getInt("text_prompt_end_token_id")
    val codebooks get() = nVq

    private val heads = NpzFile(File(dir, "vieneu_v3_heads.npz"))
    private val textEmb = heads.floats("text_emb").data
    private val audioEmb = heads.floats("audio_emb").data   // [n_vq][audioVocab][hidden]
    private val xvecW = heads.floats("xvec_w").data         // [hidden][speaker dim]
    private val xvecB = heads.floats("xvec_b").data
    private val xvecLnW = heads.floats("xvec_ln_w").data
    private val xvecLnB = heads.floats("xvec_ln_b").data
    private val xvecLnEps = heads.floats("xvec_ln_eps").data[0]

    private val options = sessionOptions(threads, backend, spinning)
    private val codecOptions = if (codecThreads == threads) options else sessionOptions(codecThreads, backend, spinning)
    private val prefill = env.createSession(File(dir, "vieneu_prefill.onnx").absolutePath, options)
    private val decodeStep = env.createSession(File(dir, "vieneu_decode_step.onnx").absolutePath, options)
    private val acoustic = env.createSession(File(dir, "vieneu_acoustic_cached.onnx").absolutePath, options)
    private val codec = env.createSession(File(codecDir, "moss_audio_tokenizer_decode_full.onnx").absolutePath, codecOptions)
    private val pool = if (headThreads > 1) Executors.newFixedThreadPool(headThreads - 1) { task -> Thread(task, "vieneu-heads").apply { isDaemon = true } } else null

    /** 192-d x-vector -> hidden-size anchor added to every prompt/step embedding (xvec_proj: Linear + LayerNorm); zero when the model has none. */
    private fun speakerAnchor(speaker: FloatArray): FloatArray {
        if (!useSpeaker) return FloatArray(hidden)
        val dim = speaker.size
        val projected = FloatArray(hidden) { row ->
            var sum = xvecB[row]
            val at = row * dim
            for (i in 0 until dim) sum += speaker[i] * xvecW[at + i]
            sum
        }
        var mean = 0.0
        for (x in projected) mean += x
        mean /= hidden
        var variance = 0.0
        for (x in projected) variance += (x - mean) * (x - mean)
        variance /= hidden
        val scale = 1.0 / sqrt(variance + xvecLnEps)
        return FloatArray(hidden) { ((projected[it] - mean) * scale).toFloat() * xvecLnW[it] + xvecLnB[it] }
    }

    /** Embedding of one prompt row: text token + the audio codes of the row (skipping the pad code) + the speaker anchor. */
    private fun embedRow(textId: Int, codes: IntArray?, codesAt: Int, anchor: FloatArray, into: FloatArray, intoAt: Int) {
        System.arraycopy(textEmb, textId * hidden, into, intoAt, hidden)
        if (codes != null) {
            for (ch in 0 until nVq) {
                val id = codes[codesAt + ch]
                if (id == audioPad) continue
                val from = (ch * audioVocab + id) * hidden
                for (i in 0 until hidden) into[intoAt + i] += audioEmb[from + i]
            }
        }
        for (i in 0 until hidden) into[intoAt + i] += anchor[i]
    }

    /** logits[v] = vec . audio_emb[ch][v] for the whole codebook, split across the head threads. */
    private fun codebookLogits(vec: FloatArray, ch: Int): FloatArray {
        val out = FloatArray(audioVocab)
        val base = ch * audioVocab * hidden
        fun part(from: Int, to: Int) {
            for (v in from until to) {
                var a0 = 0f
                var a1 = 0f
                var a2 = 0f
                var a3 = 0f
                val at = base + v * hidden
                var i = 0
                while (i < hidden) {
                    a0 += vec[i] * audioEmb[at + i]
                    a1 += vec[i + 1] * audioEmb[at + i + 1]
                    a2 += vec[i + 2] * audioEmb[at + i + 2]
                    a3 += vec[i + 3] * audioEmb[at + i + 3]
                    i += 4
                }
                out[v] = (a0 + a1) + (a2 + a3)
            }
        }
        val workers = pool
        if (workers == null) {
            part(0, audioVocab)
        } else {
            val slices = headThreads
            val futures = (1 until slices).map { s -> workers.submit(Callable { part(audioVocab * s / slices, audioVocab * (s + 1) / slices) }) }
            part(0, audioVocab / slices)
            futures.forEach { it.get() }
        }
        return out
    }

    private fun endOfSpeech(slot: FloatArray): Boolean {
        var best = -1
        var bestValue = Float.NEGATIVE_INFINITY
        for (v in 0 until textVocab) {
            var sum = 0f
            val at = v * hidden
            for (i in 0 until hidden) sum += slot[i] * textEmb[at + i]
            if (sum > bestValue) {
                bestValue = sum
                best = v
            }
        }
        return best == speechEnd
    }

    /** One run of the cached acoustic decoder over [count] tokens; [past] is the previous run (its present_k/v become past_k/v), null = empty cache. */
    private fun acousticStep(tokens: FloatArray, count: Int, firstPosition: Long, past: OrtSession.Result?, clock: LongArray): OrtSession.Result {
        val inputs = HashMap<String, OnnxTensor>()
        val owned = ArrayList<OnnxTensor>()
        fun own(tensor: OnnxTensor) = tensor.also { owned.add(it) }
        inputs["token_emb"] = own(Tensors.floats(env, tokens, 1, count.toLong(), hidden.toLong()))
        inputs["position_ids"] = own(Tensors.longs(env, LongArray(count) { firstPosition + it }, 1, count.toLong()))
        for (i in 0 until localLayers) {
            if (past == null) {
                inputs["past_k_$i"] = own(Tensors.emptyFloats(env, 1, localHeads.toLong(), 0, localHeadDim.toLong()))
                inputs["past_v_$i"] = own(Tensors.emptyFloats(env, 1, localHeads.toLong(), 0, localHeadDim.toLong()))
            } else {
                inputs["past_k_$i"] = past.get(1 + i) as OnnxTensor
                inputs["past_v_$i"] = past.get(1 + localLayers + i) as OnnxTensor
            }
        }
        try {
            return timed(clock, ACOUSTIC) { acoustic.run(inputs) }
        } finally {
            owned.forEach { it.close() }
        }
    }

    /** One acoustic frame: the 16 codes (appended to [out] at [outAt]) and whether the speech ended. */
    private fun acousticFrame(h: FloatArray, sampling: Sampling, history: Array<RepetitionWindow>?, uniforms: UniformSource, out: IntArray, outAt: Int, clock: LongArray): Boolean {
        val tokens = FloatArray(2 * hidden)
        System.arraycopy(h, 0, tokens, 0, hidden)
        System.arraycopy(textEmb, speechStart * hidden, tokens, hidden, hidden)
        var step = acousticStep(tokens, 2, 0, null, clock)
        val slot0: FloatArray
        try {
            val hiddenOut = step.get(0) as OnnxTensor
            val all = Tensors.floatData(hiddenOut)
            slot0 = all.copyOfRange(0, hidden)
            out[outAt] = draw(all.copyOfRange(hidden, 2 * hidden), 0, sampling, history, uniforms)
        } catch (failure: Throwable) {
            step.close()
            throw failure
        }
        for (ch in 1 until nVq) {
            val from = ((ch - 1) * audioVocab + out[outAt + ch - 1]) * hidden
            val next = try {
                acousticStep(audioEmb.copyOfRange(from, from + hidden), 1, (ch + 1).toLong(), step, clock)
            } finally {
                step.close()
            }
            step = next
            out[outAt + ch] = draw(Tensors.floatData(step.get(0) as OnnxTensor), ch, sampling, history, uniforms)
        }
        step.close()
        return endOfSpeech(slot0)
    }

    private fun draw(vec: FloatArray, ch: Int, sampling: Sampling, history: Array<RepetitionWindow>?, uniforms: UniformSource): Int {
        val code = VieneuSampler.sample(codebookLogits(vec, ch), history?.get(ch), sampling.repetitionPenalty, sampling.temperature, sampling.topK, sampling.topP, uniforms.next())
        history?.get(ch)?.add(code)
        return code
    }

    /** Decode [frames] frames of [codes] with the MOSS codec; mono 48 kHz (the two output channels averaged, like the desktop). */
    fun decode(codes: IntArray, frames: Int, clock: LongArray = LongArray(SLOTS)): FloatArray {
        return Tensors.ints(env, codes.copyOf(frames * nVq), 1, frames.toLong(), nVq.toLong()).use { audioCodes ->
            Tensors.ints(env, intArrayOf(frames), 1).use { lengths ->
                timed(clock, CODEC) { codec.run(mapOf("audio_codes" to audioCodes, "audio_code_lengths" to lengths)) }.use { result ->
                    val audio = result.get(0) as OnnxTensor
                    val channels = audio.info.shape[1].toInt()
                    val samples = audio.info.shape[2].toInt()
                    val data = audio.floatBuffer
                    FloatArray(samples) { i ->
                        var sum = 0f
                        for (c in 0 until channels) sum += data.get(c * samples + i)
                        sum / channels
                    }
                }
            }
        }
    }

    /**
     * Synthesize one chunk. [textIds] is the prompt's text column (style, start, phoneme ids, end), [refCodes] the voice's reference
     * codes `[frames][n_vq]` flattened, [maxNewFrames] the cap from `max_expected_frames`. [firstChunkFrames] > 0 also records when
     * a streaming player would have had its first audio (prefill + that many frames + decoding them).
     */
    fun synthesize(textIds: IntArray, speaker: FloatArray, refCodes: IntArray, maxNewFrames: Int, sampling: Sampling, uniforms: UniformSource, firstChunkFrames: Int = 4): Result {
        val clock = LongArray(SLOTS)
        val started = System.nanoTime()
        val anchor = speakerAnchor(speaker)
        val refFrames = refCodes.size / nVq
        val rows = textIds.size + refFrames
        val prompt = FloatArray(rows * hidden)
        for (r in textIds.indices) embedRow(textIds[r], null, 0, anchor, prompt, r * hidden)
        for (r in 0 until refFrames) embedRow(refSlot, refCodes, r * nVq, anchor, prompt, (textIds.size + r) * hidden)

        var state: OrtSession.Result = timed(clock, PREFILL) { Tensors.floats(env, prompt, 1, rows.toLong(), hidden.toLong()).use { prefill.run(mapOf("inputs_embeds" to it)) } }
        var h = Tensors.lastRow(state.get(0) as OnnxTensor, hidden)
        val history = if (sampling.repetitionPenalty != 1f) Array(nVq) { RepetitionWindow(sampling.repetitionWindow, audioVocab) } else null
        val codes = IntArray(maxNewFrames * nVq)
        var frames = 0
        var firstAudioAt = 0L
        try {
            for (t in 0 until maxNewFrames) {
                val eos = acousticFrame(h, sampling, history, uniforms, codes, frames * nVq, clock)
                frames++
                if (frames == firstChunkFrames) firstAudioAt = System.nanoTime() - started
                if (eos) break
                val step = FloatArray(hidden)
                embedRow(speechStart, codes, (frames - 1) * nVq, anchor, step, 0)
                val inputs = HashMap<String, OnnxTensor>()
                val owned = ArrayList<OnnxTensor>()
                owned.add(Tensors.floats(env, step, 1, 1, hidden.toLong()).also { inputs["inputs_embeds"] = it })
                owned.add(Tensors.longs(env, longArrayOf((rows + t).toLong()), 1, 1).also { inputs["position_ids"] = it })
                for (i in 0 until layers) {
                    inputs["past_k_$i"] = state.get(1 + i) as OnnxTensor
                    inputs["past_v_$i"] = state.get(1 + layers + i) as OnnxTensor
                }
                val next = try {
                    timed(clock, DECODE) { decodeStep.run(inputs) }
                } finally {
                    owned.forEach { it.close() }
                }
                state.close()
                state = next
                h = Tensors.lastRow(state.get(0) as OnnxTensor, hidden)
            }
        } finally {
            state.close()
        }
        val audio = decode(codes, frames, clock)
        val timings = Timings().apply {
            prefill = clock[PREFILL]
            decodeStep = clock[DECODE]
            acoustic = clock[ACOUSTIC]
            codec = clock[CODEC]
            total = System.nanoTime() - started
        }
        if (firstChunkFrames > 0 && frames >= 1) {
            val chunk = minOf(firstChunkFrames, frames)
            if (firstAudioAt == 0L) firstAudioAt = timings.total - clock[CODEC]
            val decodeClock = LongArray(SLOTS)
            decode(codes, chunk, decodeClock)
            timings.firstAudio = firstAudioAt + decodeClock[CODEC]
        }
        return Result(codes, frames, audio, timings)
    }

    override fun close() {
        pool?.shutdownNow()
        listOf(prefill, decodeStep, acoustic, codec).forEach { runCatching { it.close() } }
        options.close()
        if (codecOptions !== options) codecOptions.close()
    }

    companion object {
        const val SAMPLE_RATE = 48_000
        private const val PREFILL = 0
        private const val DECODE = 1
        private const val ACOUSTIC = 2
        private const val CODEC = 3
        private const val SLOTS = 4
    }
}
