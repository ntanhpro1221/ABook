package vn.abook.player.vieneu

import vn.abook.player.readaloud.ClipBudget
import vn.abook.player.readaloud.Shouts
import vn.abook.player.BuildConfig
import org.json.JSONObject

/** Native counterpart of readaloud/vieneu_input.py; limits match Studio's vieneu_limits.py.
 * Display units remain intact, including when one word needs several inference calls. */
object VieneuInput {
    private val policy = JSONObject(BuildConfig.VIENEU_INPUT_POLICY)
    val VERSION = policy.getString("version")
    val MAX_UNBROKEN = policy.getInt("max_unbroken_chars")
    val HALVING_DEPTH = policy.getInt("halving_depth")
    private val repetitions = policy.getInt("max_letter_repetitions")
    private val longWord = Regex("(?U)\\S{${MAX_UNBROKEN + 1},}")
    private val repeats = Regex("(?U)" + policy.getString("long_letter_run_pattern"), RegexOption.IGNORE_CASE)
    private fun markers(key: String): List<String> = policy.getJSONArray(key).let { array ->
        (0 until array.length()).map { array.getString(it) }
    }
    private val lengthErrors = markers("length_error_markers")
    private val memoryErrors = markers("memory_error_markers")
    private val fatalErrors = markers("fatal_error_markers")

    fun unitLimit(maxChars: Int): Int = maxChars + policy.getInt("short_unit_slack_chars")

    fun boundedPieces(pieces: List<String>, limit: Int): List<List<String>> {
        val prepared = pieces.map { piece ->
            longWord.replace(piece) { match ->
                // Reuse the existing native cry normalizer, then Studio's four-letter cap.
                val said = Shouts.stretchReading(match.value) ?: repeats.replace(match.value) {
                    val chars = it.value.codePoints().limit(repetitions.toLong()).toArray()
                    String(chars, 0, chars.size)
                }
                said.codePoints().toArray().toList().chunked(MAX_UNBROKEN)
                    .joinToString(" ") { String(it.toIntArray(), 0, it.size) }
            }
        }
        var text = prepared.joinToString(" ")
        if (text.codePointCount(0, text.length) <= limit) return listOf(prepared)
        val chunks = ArrayList<List<String>>()
        while (text.codePointCount(0, text.length) > limit) {
            val end = text.offsetByCodePoints(0, limit)
            val gap = text.lastIndexOf(' ', end)
            val cut = if (gap > 0) gap else end
            chunks.add(listOf(text.substring(0, cut)))
            text = text.substring(cut).trimStart()
        }
        if (text.isNotEmpty()) chunks.add(listOf(text))
        return chunks
    }

    fun halves(text: String): List<String>? {
        val clean = text.trim()
        val count = clean.codePointCount(0, clean.length)
        if (count < 2) return null
        val middle = clean.offsetByCodePoints(0, count / 2)
        val gap = Regex("(?U)\\s+").findAll(clean).minByOrNull {
            kotlin.math.abs((clean.codePointCount(0, it.range.first) + clean.codePointCount(0, it.range.last + 1)) / 2.0 - count / 2)
        }
        return if (gap == null) listOf(clean.substring(0, middle), clean.substring(middle))
            else listOf(clean.substring(0, gap.range.first), clean.substring(gap.range.last + 1))
    }

    private fun mustHalve(error: Throwable, text: String): Boolean {
        val message = error.message.orEmpty().lowercase(java.util.Locale.ROOT)
        if (lengthErrors.any { it in message }) return true
        val oom = error is OutOfMemoryError || (fatalErrors.none { it in message } && memoryErrors.any { it in message })
        return oom && text.codePointCount(0, text.length) > policy.getInt("oom_halving_min_chars")
    }

    fun readUnit(pieces: List<String>, source: String, limit: Int, rate: Int,
                 phonemize: (List<String>, String) -> String, infer: (String) -> FloatArray): Pair<FloatArray, String> {
        fun join(results: List<Pair<FloatArray, String>>): Pair<FloatArray, String> {
            if (results.size == 1) return results.single()
            return VieneuAudio.join(results.map { it.first }, rate, results.dropLast(1).map { VieneuAudio.gapAfter(it.second) }).first to results.last().second
        }
        fun read(group: List<String>, original: String, depth: Int): Pair<FloatArray, String> {
            ClipBudget.stopIfCancelled()
            val text = group.joinToString(" ")
            val ph = phonemize(group, original)
            if (ph.isEmpty()) return FloatArray(0) to ph
            val split = try { return infer(ph) to ph } catch (error: Exception) {
                if (depth >= HALVING_DEPTH || !mustHalve(error, text)) throw error
                halves(text) ?: throw error
            } catch (error: OutOfMemoryError) {
                if (depth >= HALVING_DEPTH || !mustHalve(error, text)) throw error
                halves(text) ?: throw error
            }
            return join(split.map { read(listOf(it), it, depth + 1) })
        }
        val chunks = boundedPieces(pieces, limit)
        return join(chunks.map { read(it, if (chunks.size == 1) source else it.joinToString(" "), 0) })
    }
}
