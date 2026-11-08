package vn.abook.player.readaloud

import org.json.JSONObject
import java.util.Locale
import java.util.zip.GZIPInputStream
import vn.abook.player.VietnameseReading
import vn.abook.player.BuildConfig

/** The Japanese fallback table is generated from Python's JSON by Gradle. */
object JapanesePolicy {
    internal val data = JSONObject(BuildConfig.JAPANESE_READING_POLICY)
    val VERSION = data.getInt("version")
    val NAMESPACE = data.getString("namespace")
    val PROVENANCE = data.getString("provenance")
    private val lexicalGuard by lazy {
        GZIPInputStream(WebSocket.unbase64(BuildConfig.JAPANESE_LEXICON_GZIP).inputStream())
            .bufferedReader(Charsets.UTF_8).use { it.readText().split(Regex("\\s+")).toSet() }
    }
    private const val LETTERS = "A-Za-zāīūēōâîûêôĀĪŪĒŌÂÎÛÊÔ"
    private val wordPattern = Regex("[$LETTERS]+(?:[-'][$LETTERS]+)*")
    private val notePattern = Regex("\\[note[0-9]+\\]", RegexOption.IGNORE_CASE)

    private fun lexicallyGuarded(head: String): Boolean {
        val low = head.lowercase(Locale.ROOT)
        val marked = (list("onsets") + "wa").any { it in low }
        return low in lexicalGuard && !marked
    }

    private fun normalized(core: String, origin: String?): String {
        if (origin != "ja") return core
        return core.split("-").mapIndexed { index, part ->
            val low = part.lowercase(Locale.ROOT)
            val suffix = if (index > 0) list("suffixes").firstOrNull {
                Regex(it.map { ch -> Regex.escape(ch.toString()) + "+" }.joinToString("")).matches(low)
            } else null
            suffix ?: if (part.any(Char::isUpperCase) && part.none(Char::isLowerCase))
                low.replaceFirstChar { it.uppercaseChar() } else part
        }.joinToString("-")
    }
    private fun head(core: String): Pair<String, Boolean> {
        val parts = core.split("-").toMutableList()
        val honorific = parts.size > 1 && parts.last().lowercase(Locale.ROOT) in list("honorifics")
        while (parts.size > 1 && parts.last().lowercase(Locale.ROOT) in list("suffixes")) parts.removeAt(parts.lastIndex)
        while (parts.size > 1 && parts.first().length < parts.last().length && parts.last().startsWith(parts.first(), true)) parts.removeAt(0)
        return parts.joinToString("-") to honorific
    }

    internal fun syllables(core: String): Int {
        val long = strings("long_vowels")
        val word = Romanization.jaSpelling(core.lowercase(Locale.ROOT).map { long[it.toString()] ?: it.toString() }.joinToString(""), mutableListOf())
        val allowed = strings("allowed")
        val onsets = list("onsets")
        val geminates = strings("geminate_coda")
        var count = 0
        var i = 0
        while (i < word.length) {
            val c = word[i]
            val after = word.getOrNull(i + 1)
            if (c == 'n' && (after == null || after !in "aiueoy")) {
                if (count == 0) return 0
                i += if (after == '\'') 2 else 1
                continue
            }
            if (c == 'm' && after != null && after in "bmp") {
                if (count == 0) return 0
                i++
                continue
            }
            if (c.toString() in geminates && (after == c || (c == 't' && word.startsWith("ch", i + 1)))) {
                if (count == 0) return 0
                i++
                continue
            }
            val onset = if (c in "aiueoŏ") "" else onsets.firstOrNull { word.startsWith(it, i) } ?: c.toString()
            val at = i + onset.length
            val vowel = word.getOrNull(at)?.let { if (it == 'ŏ') 'o' else it } ?: return 0
            if (vowel !in "aiueo" || (onset.isNotEmpty() && vowel !in (allowed[onset] ?: ""))) return 0
            count++
            i = at + 1
            val next = word.getOrNull(i)
            if (next == vowel || (vowel == 'o' && next == 'u') || (vowel == 'e' && next == 'i')) i++
        }
        return count
    }

    private fun candidate(core: String, origin: String? = null): Pair<Int, Boolean> {
        val (head, honorific) = head(normalized(core, origin))
        val low = head.lowercase(Locale.ROOT)
        val parts = head.split("-")
        if (head.length < 2 || !head.first().isUpperCase() || parts.any { it.drop(1) != it.drop(1).lowercase(Locale.ROOT) } ||
            VietnameseReading.isSyllable(head) || low in EnglishWords.ALL || (origin == "ja" && lexicallyGuarded(head)) || low in list("common") || Regex("(.)\\1\\1").containsMatchIn(low)) return 0 to false
        val counts = parts.map(::syllables)
        val count = if (counts.all { it > 0 }) counts.sum() else 0
        return if (count > 0 && Romanization.reading(head, "ja") != null) count to honorific else 0 to false
    }

    internal fun routingOrigin(surface: String, origin: String?): String? {
        if (origin != null) return origin
        val words = surface.split(" ")
        return if (contextualNames(words).isNotEmpty() || words.any {
            val (count, honorific) = candidate(it)
            it.lowercase(Locale.ROOT) in list("common") || (Names.termOrigin(it) == "ja" && Names.honorificReading(it, null) != null) || (count > 0 && honorific)
        }) "ja" else null
    }

    private fun readingWord(source: String, origin: String?, contextual: Boolean): String? {
        val core = normalized(source, origin)
        if (origin == "ko") return null
        // Lexical Japanese and joined addresses are independent of name inference.
        if (core.lowercase(Locale.ROOT) in list("common")) Names.loanwordReading(core)?.let { return it }
        if (Names.termOrigin(core) != "ko") Names.honorificReading(core, origin)?.let { return it }
        if (source.any(Char::isUpperCase) && source.none(Char::isLowerCase) && source.length <= 4 && !contextual) return null
        val (count, honorific) = candidate(core, origin)
        val minimum = data.getJSONObject("routing").getInt(if (origin == "ja") "known_ja_min_syllables" else "min_syllables")
        if (origin == null && !(contextual || honorific)) return null
        val longSound = origin == "ja" && count == 1 && Regex("([aiueo])\\1").containsMatchIn(core.lowercase(Locale.ROOT))
        if (count == 0 || !(contextual || honorific || count >= minimum || longSound))
            return if (origin == "ja" && !lexicallyGuarded(head(core).first)) Names.nameReading(core, origin) else null
        val (head, _) = head(core)
        val parts = core.split("-")
        if (parts.size > 1 && parts.dropLast(1).all { it.length == 1 && it.equals(head.take(1), ignoreCase = true) }) {
            Names.loneSyllable(Romanization.reading(head, "ja"))?.let { full ->
                val mora = full.substringBefore("-")
                return (List(parts.size - 1) { mora } + full.lowercase(java.util.Locale.ROOT)).joinToString("-")
            }
        }
        return Names.loneSyllable(Romanization.reading(core, "ja"))
    }

    internal fun reading(core: String, origin: String?, contextual: Boolean = false): String? {
        if (origin != "ja") return readingWord(core, origin, contextual)
        val notes = notePattern.findAll(core).toList()
        val result = StringBuilder()
        var end = 0
        var found = false
        for (match in wordPattern.findAll(core)) {
            val start = match.range.first
            val stop = match.range.last + 1
            if (notes.any { start in it.range }) continue
            if (core.getOrNull(start - 1)?.isLetter() == true || core.getOrNull(stop)?.isLetter() == true) continue
            val said = readingWord(match.value, origin, contextual) ?: continue
            result.append(core.substring(end, start)).append(said)
            end = stop
            found = true
        }
        return if (found) result.append(core.substring(end)).toString() else null
    }

    internal fun applyTokens(toks: List<String>, out: MutableList<String>, origin: String?) {
        val contextual = if (origin != "ko") contextualNames(toks, origin) else emptySet()
        for ((index, token) in toks.withIndex()) {
            val source = if (origin == "ja") notePattern.replace(token, "") else token
            val (before, core, after) = Names.splitToken(source)
            if (core.isEmpty() || before.lastOrNull()?.isDigit() == true || Regex("^[-–]?[0-9]").containsMatchIn(after)) continue
            val previousName = Names.nameReading(core, origin)
            // Structural TN and non-name readings retain ownership of their output.
            if (out[index] != token && out[index] != before + previousName + after) continue
            val said = reading(core, origin, index in contextual)
            if (said != null) out[index] = before + said + after
            else if (origin == "ja" && lexicallyGuarded(head(normalized(core, origin)).first) && out[index] == before + previousName + after) out[index] = token
        }
    }

    /** Only source words beside a vocalization; never reparse its emitted sound. */
    internal fun readUnmodified(source: String, spoken: String, origin: String?, contextual: Boolean = false): String {
        val matches = wordPattern.findAll(source).toList()
        val replacements = mutableListOf<Triple<Int, Int, String>>()
        for (match in matches) {
            val raw = match.value
            if (matches.count { it.value == raw } != 1 ||
                source.getOrNull(match.range.first - 1)?.isLetter() == true ||
                source.getOrNull(match.range.last + 1)?.isLetter() == true ||
                notePattern.findAll(source).any { match.range.first in it.range }) continue
            val vocal = mutableListOf(raw)
            Shouts.readShouts(listOf(raw), vocal, origin)
            if (vocal != listOf(raw)) continue
            val old = Names.nameReading(raw, origin)
            val locations = mutableSetOf<Pair<Int, Int>>()
            for (form in setOfNotNull(raw, old)) {
                for (found in Regex(Regex.escape(form)).findAll(spoken)) {
                    val start = found.range.first
                    val stop = found.range.last + 1
                    if (spoken.getOrNull(start - 1)?.isLetter() != true && spoken.getOrNull(stop)?.isLetter() != true)
                        locations.add(start to stop)
                }
            }
            if (locations.size != 1) continue
            val said = readingWord(raw, origin, contextual)
            if (said == null && !(origin == "ja" && lexicallyGuarded(head(normalized(raw, origin)).first))) continue
            val (start, stop) = locations.single()
            replacements.add(Triple(start, stop, said ?: raw))
        }
        var result = spoken
        for ((start, stop, said) in replacements.sortedByDescending { it.first })
            result = result.substring(0, start) + said + result.substring(stop)
        return result
    }

    internal fun contextualNames(toks: List<String>, origin: String? = null): Set<Int> {
        val result = mutableSetOf<Int>()
        val parts = toks.map(Names::splitToken)
        val valid = parts.map { candidate(it.second, origin).first > 0 }
        for (index in 0 until parts.size - 1) {
            if (valid[index] && valid[index + 1] && parts[index].third.isEmpty() && parts[index + 1].first.isEmpty()) {
                result.add(index)
                result.add(index + 1)
            }
        }
        return result
    }

    internal fun strings(key: String): Map<String, String> {
        val obj = data.getJSONObject(key)
        return obj.keys().asSequence().associateWith { obj.getString(it) }
    }

    internal fun list(key: String): List<String> {
        val arr = data.getJSONArray(key)
        return (0 until arr.length()).map { arr.getString(it) }
    }

    internal fun choice(key: String) = data.getJSONObject("choices").getString(key)

    internal fun fixed(): Map<String, List<Triple<String, String, String>>> {
        val obj = data.getJSONObject("fixed")
        return obj.keys().asSequence().associateWith { key ->
            val arr = obj.getJSONArray(key)
            (0 until arr.length()).map {
                val syl = arr.getJSONArray(it)
                Triple(syl.getString(0), syl.getString(1), syl.optString(2, ""))
            }
        }
    }
}
