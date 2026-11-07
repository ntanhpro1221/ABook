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
        while (parts.size > 1 && parts.first().length == 1 && parts.first().equals(parts.last().take(1), true)) parts.removeAt(0)
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
        if (head.length < 2 || !head.first().isUpperCase() || head.drop(1) != head.drop(1).lowercase(Locale.ROOT) ||
            VietnameseReading.isSyllable(head) || low in EnglishWords.ALL || (origin == "ja" && low in lexicalGuard) || low in list("common") || Regex("(.)\\1\\1").containsMatchIn(low)) return 0 to false
        val count = syllables(head)
        return if (count > 0 && Romanization.reading(head, "ja") != null) count to honorific else 0 to false
    }

    internal fun routingOrigin(surface: String, origin: String?): String? {
        if (origin != null) return origin
        val words = surface.split(" ")
        return if (contextualNames(words).isNotEmpty() || words.any {
            val (count, honorific) = candidate(it)
            count > 0 && (honorific || count >= data.getJSONObject("routing").getInt("min_syllables"))
        }) "ja" else null
    }

    private fun readingWord(source: String, origin: String?, contextual: Boolean): String? {
        val core = normalized(source, origin)
        val (count, honorific) = candidate(core, origin)
        val minimum = data.getJSONObject("routing").getInt(if (origin == "ja") "known_ja_min_syllables" else "min_syllables")
        if (origin == "ko" || count == 0 || !(contextual || honorific || count >= minimum)) return null
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
            val said = reading(core, origin, index in contextual)
            if (said != null) out[index] = before + said + after
            else if (origin == "ja" && out[index] == before + Names.nameReading(core, origin) + after) out[index] = token
        }
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
