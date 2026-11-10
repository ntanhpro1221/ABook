package vn.abook.player.readaloud

import java.util.Locale
import vn.abook.player.BuildConfig
import vn.abook.player.VietnameseReading

/**
 * VieNeu policy data comes from english_policy.json at build time; cases are shared with Python.
 * A dictionary match alone never makes a Vietnamese syllable English; the sentence can ([englishContext]).
 */
object EnglishPolicy {
    private val policy by lazy { org.json.JSONObject(BuildConfig.ENGLISH_READING_POLICY) }
    const val VERSION = BuildConfig.ENGLISH_READING_VERSION
    const val PROVENANCE = BuildConfig.ENGLISH_READING_PROVENANCE
    val ACRONYMS = BuildConfig.ENGLISH_ACRONYMS.split(" ").toSet()
    private val preserveAcronyms = BuildConfig.PRESERVE_ACRONYMS.split(" ").toSet()
    private fun context(key: String): Set<String> =
        policy.getJSONObject("context").getJSONArray(key).let { a -> (0 until a.length()).map(a::getString).toSet() }
    private val englishOnly by lazy { context("only") }
    private val weak by lazy { context("weak") }
    private val alone by lazy { context("alone") }
    private val single by lazy { context("letters") }
    private val function by lazy { context("function") }
    private val followed by lazy { context("followed") }
    private const val BREAKS = ".!?…,;:"
    private val NUMBER = Regex("^(?:[0-9]|[IVXLCDM]+(?!\\p{L}))")
    private val NUMBER_AFTER = Regex("^\\.?[0-9]")

    private fun englishLetters(core: String): String {
        val names = policy.getJSONObject("english_letter_words")
        return "<en>" + core.uppercase(Locale.ROOT).map { names.optString(it.toString(), it.toString()) }.joinToString(" ") + "</en>"
    }

    fun vietnamese(surface: String): Boolean {
        val words = surface.split(Regex("\\s+")).filter { it.isNotEmpty() }
        return words.isNotEmpty() && words.all(VietnameseReading::isSyllable)
    }

    /** english_policy._kind: v Vietnamese evidence, e certainly English, h English word shaped like a syllable, o other ASCII word, ' ' no word. */
    private class Kind(val kind: Char, val low: String, val case: Char, val before: String, val after: String)

    private fun kind(token: String): Kind {
        val (before, raw, after) = Names.splitToken(token)
        val core = raw.replace('’', '\'')
        if (core.isEmpty() || before.lastOrNull()?.isDigit() == true || NUMBER_AFTER.containsMatchIn(after)) return Kind(' ', "", ' ', before, after)
        val toneMark = after.isNotEmpty() && Character.getType(after.codePointAt(0)) == Character.NON_SPACING_MARK.toInt()
        if (core.any { it.code > 127 } || toneMark) return Kind('v', "", ' ', before, after)
        val low = core.lowercase(Locale.ROOT)
        if (!low.all { it in 'a'..'z' || it == '-' || it == '\'' }) return Kind(' ', "", ' ', before, after)
        val case = if (core.length > 1 && core.none { it in 'a'..'z' }) 'U' else if (core[0] in 'A'..'Z') 'T' else 'l'
        val letters = low.all { it in 'a'..'z' }
        val parts = low.split('-', '\'')
        val kind = when {
            low in englishOnly -> 'e'
            letters && vietnamese(low) -> if (low in EnglishWords.ALL || low in single) 'h' else 'o'
            low in function || (letters && low in EnglishWords.ALL) -> 'e'
            parts.size > 1 && !parts.filter { it.isNotEmpty() }.all(::vietnamese) &&
                (low.replace("-", "") in EnglishWords.ALL || (parts[0].length > 1 && parts[0] in EnglishWords.ALL)) -> 'e'
            else -> 'o'
        }
        return Kind(kind, low, case, before, after)
    }

    /**
     * english_policy.english_context: indices of syllable-shaped English words that the sentence proves English.
     * A run is a stretch of ASCII words with no punctuation and no Vietnamese word inside.
     */
    fun englishContext(toks: List<String>): Set<Int> {
        val kinds = toks.map(::kind)
        if (kinds.none { it.kind == 'h' || it.low in englishOnly }) return emptySet()
        if (kinds.none { it.kind == 'v' }) {
            val toneless = kinds.count { it.kind == 'o' && vietnamese(it.low) }
            val certain = kinds.count { it.kind == 'e' && it.low !in englishOnly }
            if (toneless >= 2 && toneless > certain) return emptySet()
        }
        fun word(i: Int) = kinds[i].kind == 'e' || kinds[i].kind == 'h' || kinds[i].kind == 'o'
        fun joined(left: Int) = kinds[left].after.isEmpty() && kinds[left + 1].before.isEmpty()
        val found = mutableSetOf<Int>()
        var index = 0
        while (index < toks.size) {
            if (!word(index)) {
                index++
                continue
            }
            val start = index
            while (index + 1 < toks.size && word(index + 1) && joined(index)) index++
            val end = index
            index++
            // Touching a Vietnamese word with nothing between: that edge may belong to the Vietnamese sentence.
            val openLeft = start > 0 && kinds[start - 1].kind == 'v' && joined(start - 1)
            val openRight = end + 1 < toks.size && kinds[end + 1].kind == 'v' && joined(end)
            val size = end - start + 1
            val others = (start..end).count { kinds[it].kind == 'o' }
            // A capitalised grammar word may be a name ("Will bay."): one alone is no evidence.
            val functionCases = (start..end).filter { kinds[it].low in function }.map { kinds[it].case }
            val grammar = size >= 2 && 3 * others <= size && (functionCases.size >= 2 || functionCases.any { it != 'T' })
            for (i in start..end) {
                val k = kinds[i]
                if (k.low in englishOnly) {
                    // Two capitals alone are an abbreviation ("ngành IT"); in a shouted run they are the word ("STOP IT!").
                    if (k.case != 'U' || k.low.length > 2 || listOf(i - 1, i + 1).any { it in start..end && kinds[it].case == 'U' }) found += i
                    continue
                }
                if (k.kind != 'h') continue
                if (grammar && (k.low in weak || !((i == start && openLeft) || (i == end && openRight)))) {
                    found += i
                    continue
                }
                if (k.low in weak && listOf(i - 1, i + 1).none { it in toks.indices && kinds[it].low == k.low }) {  // "the the", "hi hi"
                    for (j in listOf(i - 1, i + 1)) {
                        if (j !in start..end || kinds[j].kind != 'e' || (j < i && k.low in followed)) continue
                        val first = minOf(i, j)
                        if (k.low in single || (k.case == 'l') == (kinds[j].case == 'l') ||
                            (kinds[first].case != 'l' && first == start && !openLeft)) found += i
                    }
                }
                // The whole exclamation ("Go!", "[Yes / No]"), not a quoted word inside a Vietnamese sentence.
                if (size == 1 && k.low in alone &&
                    (i == 0 || kinds[i - 1].kind == ' ' || kinds[i - 1].after.any { it in BREAKS }) &&
                    (i + 1 == toks.size || k.after.any { it in BREAKS }) &&
                    !(i + 1 < toks.size && NUMBER.containsMatchIn(toks[i + 1]))) found += i
            }
        }
        return found
    }

    fun keepsWord(core: String, origin: String?): Boolean {
        if (core in preserveAcronyms) return false
        val vocalized = mutableListOf(core)
        Shouts.readShouts(listOf(core), vocalized)
        if (vocalized != listOf(core)) return false
        val parts = core.split(Regex("[-'’]"))
        val minimum = if ('\'' in core || '’' in core) 1 else 2
        if (parts.any { it.length < minimum || it.any { ch -> ch !in 'a'..'z' && ch !in 'A'..'Z' } }) return false
        val lower = core.lowercase(Locale.ROOT)
        if (core.all { it in 'A'..'Z' } && lower.all { it in "ivxlcdm" }) return false
        if (vietnamese(core) || lower in Names.JAPANESE_COMMON) return false
        if (JapanesePolicy.reading(core, origin) != null || Names.nameReading(core, origin) != null || Names.honorificReading(core, origin) != null) return false
        if (lower.replace("-", "") in EnglishWords.ALL || lower in BuildConfig.DIRECT_ENGLISH_WORDS.split(" ")) return true
        return Names.ORIGINS.all { Romanization.reading(core, it) == null }
    }

    fun reading(core: String, origin: String?): Pair<String, String>? {
        if (policy.getJSONObject("contextual_abbreviations").has(core.lowercase(Locale.ROOT)) ||
            policy.getJSONObject("contextual_letter_names").has(core.lowercase(Locale.ROOT)) ||
            policy.getJSONArray("case_sensitive_abbreviations").let { a ->
                (0 until a.length()).any { a.getString(it) == core.lowercase(Locale.ROOT) }
            }) return null
        Abbreviations.standardReading(core, listOf(core), 0)?.let { return it to "owner_abbreviation" }
        if (core in preserveAcronyms) return null
        if (JapanesePolicy.reading(core, origin) != null) return null
        val lower = core.lowercase(Locale.ROOT)
        val letters = core.isNotEmpty() && core.all { it in 'A'..'Z' }
        val generic = letters && !vietnamese(core) && !lower.all { it in "ivx" } &&
            Abbreviations.spelled(core) == lower.map { Abbreviations.LETTERS.getValue(it) }.joinToString(" ")
        if (core in ACRONYMS || generic) return englishLetters(core) to "spell_english"
        return if (keepsWord(core, origin)) (if (letters) lower else core) to "keep_english" else null
    }

    fun applyTokens(toks: List<String>, out: MutableList<String>, origin: String?, protected: Set<Int> = emptySet()) {
        val proposed = out.toMutableList()
        JapanesePolicy.applyTokens(toks, proposed, origin)
        val contextual = if (protected.isNotEmpty() && origin != "ko") JapanesePolicy.contextualNames(toks, origin) else emptySet()
        for ((index, said) in proposed.withIndex()) out[index] = if (index !in protected) said
            else JapanesePolicy.readUnmodified(toks[index], out[index], origin, index in contextual)
        val asian = toks.toMutableList()
        Names.readNames(toks, asian, origin)
        Names.readKoreanNames(toks, asian, origin)
        Names.readHonorifics(toks, asian, origin)
        Names.readLoanwords(toks, asian)
        val english = englishContext(toks)
        for ((index, token) in toks.withIndex()) {
            if (index in protected) continue
            val (before, core, after) = Names.splitToken(token)
            if (Abbreviations.contextualLetters(core, toks, index)) {
                out[index] = before + englishLetters(core) + after
                continue
            }
            if (Abbreviations.pronounAi(toks, index) || Abbreviations.standardReading(core, toks, index, before, after) != null) continue
            if (core.isEmpty() || before.lastOrNull()?.isDigit() == true || Regex("^[-–]?[0-9]").containsMatchIn(after)) continue
            if (core in preserveAcronyms) continue
            if (asian[index] != token && core.lowercase(Locale.ROOT) !in Names.DICTIONARY_WORDS) continue
            if (index in english) {
                val shouted = core.length > 1 && core.all { it in 'A'..'Z' }
                val marked = "<en>" + (if (shouted) core.lowercase(Locale.ROOT) else core) + "</en>"
                val expanded = if (shouted) Abbreviations.spelled(core) else null  // the abbreviation rule already spelled the capitals out
                if (out[index].lowercase(Locale.ROOT) == token.lowercase(Locale.ROOT)) {
                    out[index] = before + marked + after
                    continue
                }
                if (expanded != null && expanded in out[index]) {
                    out[index] = out[index].replaceFirst(expanded, marked)
                    continue
                }
            }
            if (core !in ACRONYMS && vietnamese(core)) {
                if (out[index].lowercase(Locale.ROOT) == token.lowercase(Locale.ROOT)) out[index] = if (core.length >= 2 && core.all { it in 'A'..'Z' }) token.lowercase(Locale.ROOT) else token
                else if (core.all { it in 'A'..'Z' } && vn.abook.player.vieneu.VieneuUnits.romanValue(core) == null) {
                    Abbreviations.spelled(core)?.let { out[index] = out[index].replaceFirst(it, core) }
                }
                continue
            }
            val choice = reading(core, origin) ?: continue
            if (choice.second == "spell_english") {
                val expanded = Abbreviations.spelled(core)
                if (expanded != null && expanded in out[index]) out[index] = out[index].replaceFirst(expanded, choice.first)
                else if (core in out[index]) out[index] = out[index].replaceFirst(core, choice.first)
                continue
            }
            if (choice.second == "keep_english" && out[index] != token &&
                out[index].lowercase(Locale.ROOT) != token.lowercase(Locale.ROOT) &&
                core.lowercase(Locale.ROOT) !in Names.DICTIONARY_WORDS) continue
            if (core.lowercase(Locale.ROOT) in setOf("chap", "vol", "lv", "lvl") && out[index] != token) continue
            out[index] = before + choice.first + after
        }
    }
}
