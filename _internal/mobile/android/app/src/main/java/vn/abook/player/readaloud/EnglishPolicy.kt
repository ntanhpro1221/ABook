package vn.abook.player.readaloud

import java.util.Locale
import vn.abook.player.BuildConfig
import vn.abook.player.VietnameseReading

/** VieNeu policy data comes from english_policy.json at build time; cases are shared with Python. */
object EnglishPolicy {
    private val policy by lazy { org.json.JSONObject(BuildConfig.ENGLISH_READING_POLICY) }
    const val VERSION = BuildConfig.ENGLISH_READING_VERSION
    const val PROVENANCE = BuildConfig.ENGLISH_READING_PROVENANCE
    val ACRONYMS = BuildConfig.ENGLISH_ACRONYMS.split(" ").toSet()
    private val preserveAcronyms = BuildConfig.PRESERVE_ACRONYMS.split(" ").toSet()

    private fun englishLetters(core: String): String {
        val names = policy.getJSONObject("english_letter_words")
        return "<en>" + core.uppercase(Locale.ROOT).map { names.optString(it.toString(), it.toString()) }.joinToString(" ") + "</en>"
    }

    fun vietnamese(surface: String): Boolean {
        val words = surface.split(Regex("\\s+")).filter { it.isNotEmpty() }
        return words.isNotEmpty() && words.all(VietnameseReading::isSyllable)
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
