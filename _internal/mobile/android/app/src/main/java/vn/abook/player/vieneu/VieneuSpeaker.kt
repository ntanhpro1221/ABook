package vn.abook.player.vieneu

import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.Span
import vn.abook.player.readaloud.SyllableSpread
import vn.abook.player.readaloud.WordTokens
import java.io.File
import java.security.MessageDigest

/** Where the "Giọng VieNeu" module put its parts on this phone ([VieneuModule.installed]). A tier is null when it is not downloaded. */
class VieneuInstalled(
    val g2pLibrary: File,
    val dictionary: File,
    val voices: File,
    val turbo: Pair<File, File>?,
    val nano: File?,
)

/** One ready-made voice of a tier (vieneu 3.8.1 `voices_v3_<tier>.json`): x-vector, Turbo's reference codes `[frames][16]`, Nano's style. */
class VieneuPreset(val name: String, val gender: String, val speaker: FloatArray, val codes: IntArray?, val style: FloatArray?)

object VieneuPresets {
    val TIERS = listOf("turbo", "nano")
    val FILES = mapOf("turbo" to "voices_v3_turbo.json", "nano" to "voices_v3_nano.json")
    val LABEL = mapOf("turbo" to "VieNeu", "nano" to "VieNeu Nano")

    private fun floats(array: JSONArray?): FloatArray? = array?.let { FloatArray(it.length()) { i -> it.getDouble(i).toFloat() } }

    private fun flatFloats(rows: JSONArray?): FloatArray? = rows?.let { (0 until it.length()).flatMap { r -> floats(it.getJSONArray(r))!!.asList() }.toFloatArray() }

    private fun flatInts(rows: JSONArray?): IntArray? =
        rows?.let { (0 until it.length()).flatMap { r -> it.getJSONArray(r).let { row -> (0 until row.length()).map { c -> row.getInt(c) } } }.toIntArray() }

    /** Presets in the order shown (`vieneu.VieneuProvider.presets`): featured ones first by their rank, then the file's order. */
    fun read(json: JSONObject): List<VieneuPreset> {
        val presets = json.optJSONObject("presets") ?: return emptyList()
        val entries = presets.keys().asSequence().toList().mapIndexed { index, name -> Triple(index, name, presets.getJSONObject(name)) }
        return entries.sortedWith(compareBy<Triple<Int, String, JSONObject>>({ it.third.isNull("featured") }, { it.third.optInt("featured", 0) }, { it.first }))
            .map { (_, name, data) ->
                VieneuPreset(name, data.optString("gender"), floats(data.optJSONArray("speaker_emb")) ?: FloatArray(0),
                    flatInts(data.optJSONArray("codes")), flatFloats(data.optJSONArray("style")))
            }
    }

    fun read(file: File): List<VieneuPreset> = read(JSONObject(file.readText(Charsets.UTF_8)))
}

/** One tier's synthesis of ONE unit of phonemes (the [VieneuSpeaker] does the rest). */
interface VieneuTier : AutoCloseable {
    val rate: Int
    fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray
}

/** Nano: one pass, then edges trimmed + faded like the desktop. Bit-identical to the desktop on the same phonemes and seed. */
class NanoTier(private val engine: VieneuNano) : VieneuTier {
    override val rate = VieneuNano.SAMPLE_RATE

    override fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray {
        val style = preset.style ?: throw IllegalArgumentException("giọng Nano thiếu style")
        val audio = engine.synthesize(phonemes, preset.speaker, style, null, seed).audio
        return VieneuAudio.trimAndFade(audio, rate)
    }

    override fun close() = engine.close()
}

/** Turbo: up to [retries] more takes when a short unit sounds like it "said more" (vieneu's babble retry), the better take kept. */
class TurboTier(private val engine: VieneuTurbo, private val tokenizer: ByteBpe, private val retries: Int = 2) : VieneuTier {
    override val rate = VieneuTurbo.SAMPLE_RATE

    override fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray {
        val codes = VieneuAudio.stripEncoderPadFrame(preset.codes ?: IntArray(0), engine.codebooks)
        val ids = intArrayOf(engine.styleId, engine.promptStart) + tokenizer.encode(phonemes) + intArrayOf(engine.promptEnd)
        val cap = minOf(MAX_NEW_FRAMES, VieneuAudio.maxExpectedFrames(phonemes))
        val random = NumpyRandomState(seed)
        fun take(): Pair<FloatArray, Int> = engine.synthesize(ids, preset.speaker, codes, cap, VieneuTurbo.Sampling(), random, firstChunkFrames = 0)
            .let { it.audio to it.frames }
        var (best, frames) = take()
        if (frames == 0) return FloatArray(0)
        var judged = VieneuAudio.babbleSuspect(best, rate, phonemes, cap, frames)
        var tries = 0
        while (judged.suspect && tries < retries) {
            val (again, count) = take()
            tries++
            if (count == 0) continue
            val other = VieneuAudio.babbleSuspect(again, rate, phonemes, cap, count)
            if (other.better(judged)) {
                best = again
                judged = other
            }
        }
        return best
    }

    override fun close() = engine.close()

    companion object {
        const val MAX_NEW_FRAMES = 300
    }
}

/**
 * Paragraph -> one clip, the phone's `vieneu.VieneuProvider._speak` + `synthesize`: units ([VieneuUnits]), phonemes ([SeaG2p]), one take per
 * unit seeded from voice + text (same paragraph, same voice = same audio, so the clip cache and re-reads agree), units joined with the
 * desktop's minimum pauses. Word timings: VieNeu gives none, so each unit's words are spread over ITS exact span of the clip by syllables
 * ([SyllableSpread], like FPT.AI / Viettel AI).
 */
class VieneuSpeaker(
    /** Sentences of one unit -> phonemes ([SeaG2p.phonemize]). */
    private val phonemize: (List<String>) -> String,
) {
    class Spoken(val samples: FloatArray, val rate: Int, val durationMs: Long, val words: List<Span>, val spans: List<IntArray>)

    fun speak(tier: String, tierEngine: VieneuTier, name: String, preset: VieneuPreset, text: String, origin: String? = null,
              readings: Map<String, String>? = null): Spoken {
        val (tokens, units) = VieneuUnits.units(text, MAX_CHARS.getValue(tier), origin, readings)
        val waves = ArrayList<FloatArray>()
        val pauses = ArrayList<Double>()
        for (unit in units) {
            val phonemes = phonemize(unit.pieces)
            val audio = if (phonemes.isEmpty()) FloatArray(0) else tierEngine.infer(phonemes, preset, seedOf(tier, name, unit.pieces.joinToString(" ")))
            waves.add(audio)
            val last = phonemes.trimEnd().lastOrNull()
            pauses.add(VieneuAudio.GAP_SECONDS.getValue(if (last == null || last in ".!?") "sentence" else "minor"))
        }
        val (joined, spans) = VieneuAudio.join(waves, tierEngine.rate, pauses.dropLast(1))
        val rate = tierEngine.rate
        val duration = joined.size * 1000L / rate
        val words = ArrayList<Span>()
        for ((unit, span) in units.zip(spans)) {
            val count = unit.last - unit.first + 1
            val startMs = span[0] * 1000L / rate
            if (span[1] <= span[0]) {
                repeat(count) { words.add(Span(startMs, startMs)) } // a unit with no sound: its words sit where it is
                continue
            }
            val unitText = unit.text(tokens)
            val unitMs = (span[1] - span[0]) * 1000L / rate
            WordTokens.map(unitText, SyllableSpread.boundaries(unitText, unitMs), unitMs).forEach { words.add(Span(it.start + startMs, it.end + startMs)) }
        }
        var previous = 0L
        val clamped = words.map { pair -> // never backwards, never past the clip
            val start = minOf(maxOf(pair.start, previous), duration)
            previous = start
            Span(start, minOf(maxOf(pair.end, start), duration))
        }
        return Spoken(joined, rate, duration, clamped, spans)
    }

    companion object {
        val MAX_CHARS = mapOf("turbo" to 256, "nano" to 140)

        /** `vieneu.seed_of`: the first 8 hex digits of SHA-256 of the parts joined by "|". */
        fun seedOf(vararg parts: String): Long {
            val digest = MessageDigest.getInstance("SHA-256").digest(parts.joinToString("|").toByteArray(Charsets.UTF_8))
            return digest.take(4).fold(0L) { value, byte -> (value shl 8) or (byte.toLong() and 0xFF) }
        }
    }
}
