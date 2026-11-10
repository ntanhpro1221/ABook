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
    private val knownNames by lazy { list("known_names").toSet() }
    private val honorifics by lazy { list("honorifics").toSet() }
    private val particles by lazy { list("particles").toSet() }

    private fun lexicallyGuarded(head: String): Boolean {
        val low = head.lowercase(Locale.ROOT)
        val marked = (list("onsets") + "wa").any { it in low }
        return low in lexicalGuard && !marked && low !in knownNames
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
            VietnameseReading.isSyllable(head) || (low in EnglishWords.ALL && !(origin == "ja" && low in knownNames)) || (origin == "ja" && lexicallyGuarded(head)) || low in list("common") || Regex("(.)\\1\\1").containsMatchIn(low)) return 0 to false
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
        // A suffix only Korean has settles the whole name, even in a Japanese book.
        if (Names.termOrigin(core) == "ko" && '-' in core) return Names.nameReading(core, "ko")
        // Lexical Japanese and joined addresses are independent of name inference.
        if (core.lowercase(Locale.ROOT) in list("common")) Names.loanwordReading(core)?.let { return it }
        if (Names.termOrigin(core) != "ko") Names.honorificReading(core, origin)?.let { return it }
        if (source.any(Char::isUpperCase) && source.none(Char::isLowerCase) && source.length <= 4 && !contextual) return null
        val (count, honorific) = candidate(core, origin)
        val minimum = data.getJSONObject("routing").getInt(if (origin == "ja") "known_ja_min_syllables" else "min_syllables")
        if (origin == null && !(contextual || honorific)) return null
        val longSound = origin == "ja" && count == 1 && Regex("([aiueo])\\1").containsMatchIn(core.lowercase(Locale.ROOT))
        if (count == 0 || !(contextual || honorific || count >= minimum || longSound))
            return if (origin == "ja" && !lexicallyGuarded(head(core).first)) Names.nameReading(core, origin)?.let(Shouts::distinctFromEnglish) else null
        val (head, _) = head(core)
        val parts = core.split("-")
        if (parts.size > 1 && parts.dropLast(1).all { it.length == 1 && it.equals(head.take(1), ignoreCase = true) }) {
            Names.loneSyllable(Romanization.reading(head, "ja"))?.let { full ->
                val mora = full.substringBefore("-")
                return (List(parts.size - 1) { mora } + full.lowercase(java.util.Locale.ROOT)).joinToString("-")
            }
        }
        return Names.loneSyllable(Romanization.reading(core, "ja"))?.let(Shouts::distinctFromEnglish)
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

    private fun allCaps(word: String) = word.any(Char::isUpperCase) && word.none(Char::isLowerCase)
    private fun titled(word: String) = word.firstOrNull()?.isUpperCase() == true && word.length > 1 && word.drop(1).let { rest -> rest.any(Char::isLetter) && rest.none(Char::isUpperCase) }

    /** What letter TN already emitted for a capitalized word, if anything. */
    private fun spelledOutput(core: String, before: String, after: String): String? =
        Abbreviations.spelled(core)?.let { before + it + Names.closing(after, it) }

    /** A Korean-only suffix ("Ji-eun-ssi") or a hyphenated name beside a Korean surname ("Park Seo-joon") is Korean in any book. */
    private fun koreanReading(toks: List<String>, index: Int, core: String): String? {
        if ('-' in core && Names.termOrigin(core) == "ko") return Names.nameReading(core, "ko")
        if (index == 0) return null
        val (_, surname, tail) = Names.splitToken(toks[index - 1])
        if (tail.isNotEmpty() || surname.lowercase(Locale.ROOT) !in Names.KOREAN_SURNAMES ||
            surname != surname.lowercase(Locale.ROOT).replaceFirstChar { it.uppercaseChar() }) return null
        return Names.koreanHyphenatedName(core)
    }

    internal fun applyTokens(toks: List<String>, out: MutableList<String>, origin: String?) {
        val contextual = if (origin != "ko") contextualNames(toks, origin) else emptySet()
        // Words of this text written as a readable name ("Yui"): evidence for their capitals ("YUI").
        val titledHere = if (origin == "ja") toks.map { Names.splitToken(it).second }
            .filter { titled(it) && readingWord(it, origin, false) != null }.map { it.lowercase(Locale.ROOT) }.toSet() else emptySet()
        val saidHere = HashMap<String, String>()
        val readIndices = HashSet<Int>()
        for ((index, token) in toks.withIndex()) {
            val source = if (origin == "ja") notePattern.replace(token, "") else token
            val (before, core, after) = Names.splitToken(source)
            if (core.isEmpty() || before.lastOrNull()?.isDigit() == true || Regex("^[-–]?[0-9]").containsMatchIn(after)) continue
            val korean = if (origin == "ja") koreanReading(toks, index, core) else null
            if (korean != null) {
                out[index] = before + korean + after
                continue
            }
            val previousName = Names.nameReading(core, origin)
            // Letter TN only lowercased a word it had judged readable ("YUUKI"), or a
            // capitalized form stands beside its own titled spelling ("Yui ... YUI").
            val evidence = origin == "ja" && allCaps(core) && out[index] == spelledOutput(core, before, after) &&
                ((Abbreviations.spelled(core) == core.lowercase(Locale.ROOT) && core.length >= 4) || core.lowercase(Locale.ROOT) in titledHere)
            // Structural TN and non-name readings retain ownership of their output.
            if (out[index] != token && out[index] != before + previousName + after && !evidence) continue
            val said = reading(core, origin, index in contextual || evidence)
            if (said != null) {
                out[index] = before + said + after
                saidHere[core.lowercase(Locale.ROOT)] = said
                readIndices.add(index)
            } else if (origin == "ja" && lexicallyGuarded(head(normalized(core, origin)).first) && out[index] == before + previousName + after) out[index] = token
        }
        if (origin == "ja") echoes(toks, out, saidHere, readIndices)
    }

    /** A lowercase word repeats a reading this text already gave ("Doki doki"), and a sentence particle stays Japanese right after a read word ("Ii yo"). */
    private fun echoes(toks: List<String>, out: MutableList<String>, read: Map<String, String>, readIndices: Set<Int>) {
        val saidHere = HashMap(read)
        for ((index, token) in toks.withIndex()) { // "D-Doki doki": the stutter already read the word
            if ("… " !in out[index]) continue
            saidHere.getOrPut(Names.splitToken(token).second.substringAfterLast('-').lowercase(Locale.ROOT)) { Names.splitToken(out[index].substringAfterLast("… ")).second }
        }
        for ((index, token) in toks.withIndex()) {
            val (before, core, after) = Names.splitToken(token)
            if (core.isEmpty() || core.any(Char::isUpperCase) || core.none(Char::isLowerCase) || out[index] != token) continue
            val said = saidHere[core] ?: if (core in particles && index - 1 in readIndices && Names.splitToken(toks[index - 1]).third.isEmpty()) Romanization.reading(core, "ja") else null
            if (said != null) out[index] = before + said.lowercase(Locale.ROOT) + after
        }
    }

    /** The reading of a guarded word once the book shows it is a name; it must equal what the same word says with an honorific. */
    private fun evidencedReading(word: String): String? {
        if (!titled(word) || VietnameseReading.isSyllable(word) || syllables(word) == 0) return null
        val said = Names.loneSyllable(Romanization.reading(word, "ja")) ?: return null
        val address = Names.honorificReading("$word-san", "ja") ?: return null
        return if (address.lowercase(Locale.ROOT).startsWith(said.lowercase(Locale.ROOT) + "-")) said else null
    }

    /** {surface: reading} for names a Japanese book proves by itself, so that one character is never read two ways - `book_name_readings`. */
    fun bookNameReadings(texts: Sequence<String>, characterNames: List<String> = emptyList()): Map<String, String> {
        val guarded = LinkedHashSet<String>()
        val titledWords = HashSet<String>()
        val capitals = LinkedHashSet<String>()
        for (text in texts) for (token in text.split(Regex("\\s+"))) {
            val core = Names.splitToken(notePattern.replace(token, "")).second
            if (core.isEmpty() || core.any { it.code >= 128 }) continue
            val parts = core.split("-")
            if (parts.size == 2 && parts[1].lowercase(Locale.ROOT) in honorifics) guarded.add(parts[0])
            else if (parts.size == 1 && allCaps(core)) { if (core.length in 2..4) capitals.add(core) }
            else if (parts.size == 1 && titled(core)) titledWords.add(core)
        }
        for (surface in characterNames) {
            // The character list writes names in capitals ("ABE TAKESHI").
            val words = surface.split(" ").filter { it.isNotEmpty() }.map { if (allCaps(it)) it.lowercase(Locale.ROOT).replaceFirstChar { c -> c.uppercaseChar() } else it }
            if (words.size > 1 && words.all { w -> w.all { it.code < 128 } } && words.any { readingWord(it, "ja", false) != null }) guarded.addAll(words)
        }
        val found = LinkedHashMap<String, String>()
        for (word in guarded) {
            val said = (if (readingWord(word, "ja", false) != null) null else evidencedReading(word)) ?: continue
            found[word] = said
            found[word.uppercase(Locale.ROOT)] = said
        }
        for (capital in capitals) {
            val word = capital.lowercase(Locale.ROOT).replaceFirstChar { it.uppercaseChar() }
            if (word !in titledWords && word !in found) continue
            (found[word] ?: readingWord(word, "ja", false))?.let { found[capital] = it }
        }
        return found
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
