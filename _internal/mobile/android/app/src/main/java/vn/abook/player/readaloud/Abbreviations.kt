package vn.abook.player.readaloud

import vn.abook.player.VietnameseReading
import java.util.Locale

/**
 * Spoken abbreviations, with unchanged display text. Owner readings, Vietnamese
 * expansions and contextual cues come from the same english_policy.json as Python.
 * Dictionary words in capitals remain words; unresolved short codes use letters.
 */
object Abbreviations {
    val LETTERS = mapOf(
        'a' to "a", 'b' to "bê", 'c' to "xê", 'd' to "đê", 'e' to "e", 'f' to "ép", 'g' to "giê", 'h' to "hát", 'i' to "i", 'j' to "gi", 'k' to "ca", 'l' to "e-lờ",
        'm' to "em", 'n' to "en", 'o' to "ô", 'p' to "pê", 'q' to "quy", 'r' to "e-rờ", 's' to "ét", 't' to "tê", 'u' to "u", 'v' to "vê", 'w' to "vê-kép", 'x' to "ích",
        'y' to "i-dài", 'z' to "dét",
    )
    private val policy by lazy { org.json.JSONObject(vn.abook.player.BuildConfig.ENGLISH_READING_POLICY) }
    private val AS_WORDS by lazy {
        mapOf("id" to "ai-đi") + listOf("spoken_abbreviations").flatMap { key ->
            val table = policy.getJSONObject(key)
            table.keys().asSequence().map { it to table.getString(it) }.toList()
        }.toMap()
    }

    fun standardReading(core: String, toks: List<String>, index: Int, before: String = "", after: String = ""): String? {
        val lower = core.lowercase(java.util.Locale.ROOT)
        val sensitive = policy.getJSONArray("case_sensitive_abbreviations")
        if ((0 until sensitive.length()).any { sensitive.getString(it) == lower } && core != core.uppercase(java.util.Locale.ROOT)) return null
        if (pronounAi(toks, index)) return null
        if (contextualLetters(core, toks, index)) return null
        val contextual = policy.getJSONObject("contextual_abbreviations").optJSONObject(lower)
        if (contextual != null) {
            val cues = policy.getJSONArray("code_context")
            val previous = toks.subList(maxOf(0, index - 2), index).map { Names.splitToken(it).second.lowercase(java.util.Locale.ROOT) }
            val code = (0 until cues.length()).any { cues.getString(it) in previous } ||
                Regex("[\\w]$").containsMatchIn(before) || Regex("^([-_/]?[0-9]|[-_/][\\w])").containsMatchIn(after)
            return contextual.getString(if (code) "code" else "prose")
        }
        return policy.getJSONObject("spoken_abbreviations").optString(lower, "").ifEmpty {
            policy.getJSONObject("vietnamese_abbreviations").optString(lower, "")
        }.ifEmpty { null }
    }

    fun pronounAi(toks: List<String>, index: Int): Boolean {
        if (Names.splitToken(toks[index]).second != "AI" || index + 1 >= toks.size) return false
        val next = Names.splitToken(toks[index + 1]).second.lowercase(java.util.Locale.ROOT)
        val following = policy.getJSONArray("pronoun_following")
        return (0 until following.length()).any { following.getString(it) == next }
    }

    fun contextualLetters(core: String, toks: List<String>, index: Int): Boolean {
        if (core.lowercase(Locale.ROOT) in setOf("n", "r")) {
            if (core !in setOf("N", "R")) return false
            val (before, _, after) = Names.splitToken(toks[index])
            if ((before + after).any { it.isLetterOrDigit() }) return false
            // "thứ N", "N lần": N stands for an unspecified count and is said by its letter name.
            val count = policy.getJSONObject("count_letter_cues").optJSONObject(core)
            if (count != null) {
                fun cue(at: Int, key: String): Boolean {
                    if (at !in toks.indices) return false
                    val word = Names.splitToken(toks[at]).second.lowercase(java.util.Locale.ROOT)
                    val cues = count.getJSONArray(key)
                    return (0 until cues.length()).any { cues.getString(it) == word }
                }
                if (cue(index - 1, "previous") || cue(index + 1, "next")) return true
            }
            val nearby = toks.subList(maxOf(0, index - 3), index) + toks.subList(index + 1, minOf(toks.size, index + 4))
            if (nearby.any { Names.splitToken(it).second in setOf("SR", "SSR", "UR") }) return true
        }
        val cues = policy.getJSONObject("contextual_letter_names").optJSONArray(core.lowercase(java.util.Locale.ROOT)) ?: return false
        val previous = toks.subList(maxOf(0, index - 3), index).map { Names.splitToken(it).second.lowercase(java.util.Locale.ROOT) }
        return (0 until cues.length()).any { cues.getString(it) in previous }
    }

    fun readRankLetters(toks: List<String>, out: MutableList<String>) {
        val readings = policy.getJSONObject("rank_letter_readings")
        for ((index, token) in toks.withIndex()) {
            val (before, core, after) = Names.splitToken(token)
            if (out[index] == token && readings.has(core) && contextualLetters(core, toks, index))
                out[index] = before + readings.getString(core) + after
        }
    }
    private val SPELLED_ENGLISH = "abc ceo cia dna exp fbi hiv ibm nba usa".split(" ").toSet()
    private val SHOUT_WORDS = "no oh ah eh uh um ha ho yo hi he we me my up so to of or on ya ye go do if in is an by at".split(" ").toSet()
    private val LAUGH = Regex("(?:ha|he|hi|ho)+")
    private val ROMAN_LETTERS = "ivx".toSet()
    /** "đó.”(GM)": viết tắt trong ngoặc dính vào chữ trước. */
    private val PAREN_ABBREVIATION = Regex("""(?<=.)\(([A-Z]{2,5})\)""")
    /** Chủ sách 04-10: Lv không chắc là cấp độ thì đọc tên chữ cái, l = lờ, v = vê. */
    private val LEVEL_NAMES = mapOf("lv" to "lờ vê", "lvl" to "lờ vê lờ")
    /** Every abbreviation the reading tables know (english_policy.json, the tables here), lower-cased - `shouts.listed_abbreviations`: never a cry ("CCCD"). */
    val LISTED: Set<String> by lazy {
        val root = Locale.ROOT
        val keys = listOf("vietnamese_abbreviations", "spoken_abbreviations", "contextual_abbreviations").flatMap { policy.getJSONObject(it).keys().asSequence().toList() }
        val acronyms = listOf("preserve_acronyms", "acronyms", "capital_codes").flatMap { key -> policy.getJSONArray(key).let { a -> (0 until a.length()).map { a.getString(it).lowercase(root) } } }
        (keys + acronyms + AS_WORDS.keys + SPELLED_ENGLISH + LEVEL_NAMES.keys).toSet()
    }
    private const val MIN_LETTERS = 2
    private val MAX_LETTERS = Shouts.POLICY.getInt("max_acronym_letters")
    private const val ROMAJI_FROM = 4

    private fun caps(core: String) = core.count { it.isLetter() } >= 2 && core.none { it.isLowerCase() }

    private fun shouty(core: String) = caps(core) && (core.any { it.code >= 128 } || '-' in core)

    private fun word(lower: String): Boolean {
        if (lower.length == 2) return lower in SHOUT_WORDS
        return lower in EnglishWords.ALL && lower !in SPELLED_ENGLISH && lower.any { it in "aeiouy" }
    }

    private fun letterNames(lower: String) = lower.map { LETTERS.getValue(it) }.joinToString(" ")

    /** Tên / từ hét viết hoa ("YUI!", "BUG!") ngắn nhất; hai chữ hoa luôn là viết tắt. */
    internal const val WORD_FROM = 3
    /** Chữ đứng riêng: không dính số, gạch nối tên, đường dẫn. */
    private val CAPITALS = Regex("""(?<![\p{L}\p{N}_'’/@#&+])(?<!(?<!\.)\.)(?<![\p{L}\p{N}_]-)[A-Z]{3,}(?![\p{L}\p{N}_'’/@#&+])(?![-.][\p{L}\p{N}_])""")
    /** Dấu kêu ngay sau chữ: "YUI!", "YUI…!", "YUI~!?"; "(AOE)!" là chú giải. */
    private val CRY = Regex("""^[^\p{L}\p{N}_()]*[!?]""")
    /** "y" sau phụ âm là nguyên âm ("MYTHS", "LYNX"); "YYDS" không có nguyên âm nào. */
    private val VOWEL = Regex("[aeiou]|(?<=[^aeiouy])y")
    /** "WAH!?", "YAH!", "UOH!": thán từ kết bằng "h". */
    private val INTERJECTION = Regex("[^aeiou]{0,2}[aeiou]+h")
    private val STRETCH = Regex("""(.)\1{2,}""") // chữ kéo dài: "NORDDDDD", "WUTTTT"
    private val CRY_SHAPED = Regex("(.)\\1\\1|[aeiouh]\$") // tiếng kêu: chữ kéo dài ("AHHH") hay kết bằng nguyên âm / "h"; "UKG", "EEG" là mã
    private val ONSETS = ("bl br by ch cl cr dr dw fl fr gh gl gr gw gy hy jh kh kl kn kr kw ky my ny ph pl pr py rh ry sc sh sk sl sm sn sp st sv sw th tr ts tw vl wh wr zh" +
        " chr sch scr shr spl spr str thr thw").split(" ").toSet()
    private val CODAS = ("bb ch ck ct dd ds ff ft gg gh gs ht ks ld lf lk ll lm lp ls lt mb mm mp ms nd ng nk nn ns nt ph pp ps pt rb rc rd rf rg rk rl rm rn rp rs rt sh sk sp ss st th ts tt tz wk wl wn ws xt zz" +
        " cks ght lls lms lts mph mps nch nds ngh ngs nks nth nts rch rds rgh rks rld rms rns rst rth rts sts tch").split(" ").toSet()

    /** "KAEL" -> "Kael". */
    fun capitalized(word: String) = word.lowercase(Locale.ROOT).replaceFirstChar { it.uppercaseChar() }

    /** A per-book reading that is only the capitals' own capitalized spelling ("KAEL": "Kael") is the book's proof that the capitals are a name, not a sound to say - `proves_name`. */
    fun provesName(surface: String, said: String) =
        surface.all { it.code < 128 } && surface.any(Char::isUpperCase) && surface.none(Char::isLowerCase) && said == capitalized(surface)

    /** Chữ có dáng một từ đọc được ("kwang", "thud", "combo", "lyra"), không phải một mã ("crce", "ussr", "lmao", "oecd") - `_word_shaped`. */
    private fun wordShaped(lower: String): Boolean {
        val runs = lower.split(Regex("[aeiouy]+"))
        if (runs.size < 2) return false
        val first = runs.first()
        val last = runs.last()
        return (first.length < 2 || first in ONSETS) && (last.length < 2 || last in CODAS) && runs.subList(1, runs.size - 1).all { it.length <= 3 }
    }

    /** Chữ HOA cả đang bị đọc tên chữ cái mà CÓ THỂ là một tên / từ - `_capital_word`. */
    internal fun capitalWord(core: String): Boolean {
        val lower = core.lowercase(Locale.ROOT)
        return core.length <= MAX_LETTERS && VOWEL.containsMatchIn(lower) && lower.toSet().size > 1 && lower !in LISTED &&
            !lower.all { it in ROMAN_LETTERS } && spelled(core) == letterNames(lower) && !VietnameseReading.isSyllable(lower)
    }

    /** Không có bằng chứng trong cuốn: romaji trọn vẹn (gốc Nhật hay chưa rõ gốc), từ Anh trong bộ từ vựng chung, từ bốn chữ trở lên có dáng một từ, thán từ kết "h", hay chữ bộ đọc tiếng kêu nhận - `_reads_as_word`. */
    private fun writtenAsWord(lower: String, origin: String?): String? {
        val word = capitalized(lower)
        val short = STRETCH.replace(lower) { it.groupValues[1] }
        if (short != lower && short.length >= WORD_FROM && VOWEL.containsMatchIn(short) && (short in JapanesePolicy.lexicalGuard || wordShaped(short))) {
            // "NORDDDDD!" là "Nord" kéo dài: viết "Nord…". Chữ mà bộ đọc tiếng kêu đã tự đọc ở dạng HOA ("YESSSS" -> "yes…", "MARYYYY" -> "mary…") thì để nó.
            val capitals = listOf(lower.uppercase(Locale.ROOT))
            val read = capitals.toMutableList()
            Shouts.readShouts(capitals, read, origin)
            if (read != capitals) return null
            return capitalized(short) + if (STRETCH.findAll(lower).last().range.last == lower.length - 1) "…" else ""
        }
        if ((origin == null || origin == "ja") && JapanesePolicy.syllables(lower) > 0 && Romanization.reading(lower, "ja") != null) return word
        if (lower in JapanesePolicy.lexicalGuard || (lower.length >= 4 && wordShaped(lower)) || INTERJECTION.matches(lower)) return word
        if (!CRY_SHAPED.containsMatchIn(lower)) return null
        val source = listOf(word)
        val cry = source.toMutableList()
        Shouts.readShouts(source, cry, origin)
        return if (cry != source) word else null
    }

    /** Chữ HOA cả bên cạnh là một từ đang gào: có dấu ("CÚT"), hay từ Anh / Nhật / tên từ bốn chữ ("LOVE", "MISAKI") - không phải một viết tắt khác ("STR, AGI") - `_shouted_word`. */
    private fun shoutedWord(core: String): Boolean {
        if (!caps(core)) return false
        if (core.any { it.code >= 128 }) return true
        return core.all { it in 'A'..'Z' } && core.length >= 4 && spelled(core) != letterNames(core.lowercase(Locale.ROOT))
    }

    /**
     * Tên / từ bị hét viết HOA cả ("YUI!", "KAEL!", "BUG!") viết lại ở dạng viết hoa đầu ("Yui!") để đọc như chính từ ấy ở chỗ khác của cuốn, không đọc tên chữ cái. null khi không có chữ nào.
     * Có bằng chứng thì luôn đổi: cuốn chứng minh nó là tên ([readings] mang cách đọc là chính dạng viết hoa đầu, [JapanesePolicy.bookNameReadings]) hay dạng viết hoa đầu đứng ngay trong đoạn này.
     * Không bằng chứng: chỉ khi đọc được thành từ VÀ đang hét - dấu "!" / "?" ngay sau, hay đứng cạnh một từ viết hoa cả khác ("I LOVE YUI"). `capital_words`.
     */
    fun capitalWords(toks: List<String>, origin: String? = null, readings: Map<String, String>? = null): List<String>? {
        var named: MutableList<String>? = null
        var cores: List<String>? = null
        for ((index, token) in toks.withIndex()) {
            if (token.none { it in 'A'..'Z' }) continue
            var rewritten = token
            for (match in CAPITALS.findAll(token).toList().asReversed()) {
                val core = match.value
                if (!capitalWord(core)) continue
                val before = token.substring(0, match.range.first)
                val after = token.substring(match.range.last + 1)
                val known = cores ?: toks.map { Names.splitToken(it).second }.also { cores = it }
                var titled = capitalized(core)
                if (readings?.get(core) != titled && titled !in known) {
                    titled = writtenAsWord(core.lowercase(Locale.ROOT), origin) ?: continue
                    val cried = CRY.containsMatchIn(after) && !before.endsWith("(")
                    val beside = (before.isEmpty() && index > 0 && shoutedWord(known[index - 1])) ||
                        (after.isEmpty() && index + 1 < toks.size && shoutedWord(known[index + 1]))
                    if (!(cried || beside)) continue
                }
                rewritten = rewritten.substring(0, match.range.first) + titled + rewritten.substring(match.range.last + 1)
            }
            if (rewritten != token) (named ?: toks.toMutableList().also { named = it })[index] = rewritten
        }
        return named
    }

    /** Cách đọc của [core] (đã bỏ dấu câu quanh) khi nó là chữ HOA cả cần đổi để đọc, null khi để nguyên: viết tắt thì tên chữ cái; từ Anh / Nhật / tiếng cười viết hoa cả thì chữ thường. */
    fun spelled(core: String): String? {
        if (!(core.length >= MIN_LETTERS && core.all { it in 'A'..'Z' })) return null
        val lower = core.lowercase()
        AS_WORDS[lower]?.let { return it }
        if (lower.all { it in ROMAN_LETTERS }) return letterNames(lower)
        if (word(lower) || (lower.length >= 4 && LAUGH.matches(lower))) return lower
        if (lower.length > MAX_LETTERS) return null
        if (lower.length > 5 && lower.count { it in "aeiou" } >= 2) return null
        if (lower.length >= ROMAJI_FROM && Romanization.reading(lower, "ja") != null) return if (lower.length <= 5) lower else null
        return letterNames(lower)
    }

    /**
     * "Lv" / "Lvl" / "LV" liền trước một số ("Lv 5", "Lv.5", "Lv5", "Lvl.10") là cấp độ: đọc như chữ "level" viết đủ - cách đọc Việt của bảng từ mượn ([Names.LOANWORDS]). Không đi với số thì không chắc nghĩa gì: đọc tên chữ cái ("lờ vê").
     * Thay tại chỗ, giữ dấu câu quanh; số chữ không đổi - `read_levels`.
     */
    fun readLevels(toks: List<String>, out: MutableList<String>) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = Names.splitToken(token)
            val word = core.lowercase()
            val name = LEVEL_NAMES[word] ?: continue
            val glued = after.trimStart { it == '.' || it == ':' }
            val following = if (index + 1 < toks.size) toks[index + 1].trimStart { it in "([“\"'" } else ""
            out[index] = if (glued.firstOrNull()?.isDigit() == true || (after in listOf("", ".", ":") && following.firstOrNull()?.isDigit() == true)) {
                before + (Names.LOANWORDS["level"] ?: "level") + (if (glued.firstOrNull()?.isDigit() == true) " $glued" else "")
            } else {
                before + name + Names.closing(after, name)
            }
        }
    }

    /** Thay tại chỗ, trong [out], token (chưa bị đổi so với [toks]) là viết tắt TOÀN HOA bằng tên chữ cái, giữ dấu câu quanh; số chữ không đổi. */
    fun spellAbbreviations(toks: List<String>, out: MutableList<String>) {
        val parts = toks.map { Names.splitToken(it) }
        val shouting = parts.map { shouty(it.second) }
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = parts[index]
            if (pronounAi(toks, index)) continue
            if (before.lastOrNull()?.isDigit() == true || after.firstOrNull()?.isDigit() == true) continue
            standardReading(core, toks, index, before, after)?.let {
                out[index] = before + it + Names.closing(after, it)
            }
            if (out[index] != token) continue
            if ('(' in token) {
                out[index] = PAREN_ABBREVIATION.replace(token) { m -> "(" + (spelled(m.groupValues[1]) ?: m.groupValues[1]) + ")" }
                if (out[index] != token) continue
            }
            if (core.isEmpty() || before.lastOrNull()?.isDigit() == true || after.firstOrNull()?.isDigit() == true) continue
            val reading = spelled(core) ?: continue
            var first = index // đang gào: trong dãy chữ hoa cả có chữ có dấu / nối gạch (không phải một dãy viết tắt như "HP MP SP")
            var last = index
            while (first > 0 && caps(parts[first - 1].second)) first--
            while (last + 1 < toks.size && caps(parts[last + 1].second)) last++
            if (last > first && (first..last).any { shouting[it] }) continue
            out[index] = before + reading + Names.closing(after, reading)
        }
    }

    /**
     * Gọi viết hoa cả ("ONII-CHAN", "NEE-SAN", "OPPA") đọc như dạng thường của nó ([Names.honorificReading]: "o-ni-i-chan", "ne-e-xan") - luật hậu tố của Names chỉ nhận chữ thường / viết hoa đầu,
     * còn chữ hoa cả sẽ bị [spellAbbreviations] bỏ qua ở câu đang gào và sea-g2p đọc nguyên "onii chan". Thay tại chỗ, giữ dấu câu quanh; số chữ không đổi - `read_shouted_honorifics`.
     */
    fun readShoutedHonorifics(toks: List<String>, out: MutableList<String>, origin: String?) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = Names.splitToken(token)
            val letters = core.replace("-", "")
            if (letters.length < 3 || !letters.all { it in 'A'..'Z' } || !core.all { it in 'A'..'Z' || it == '-' }) continue
            val reading = Names.honorificReading(core.lowercase(), origin) ?: continue
            out[index] = before + reading + after
        }
    }

    /** Danh xưng viết tắt trước tên: đọc đủ chữ Anh (gold_spec: "mr." là "mister"). */
    private val TITLES = mapOf("mr" to "mister", "mrs" to "missus", "ms" to "miss", "dr" to "doctor", "st" to "saint")
    /** "Dr." / "St." chỉ là danh xưng khi liền trước một tên viết hoa ("Dr. Stone", "St. Louis"); "Mr." / "Ms." / "Mrs." thì luôn. */
    private val TITLE_NEEDS_NAME = setOf("dr", "st")
    /** "mr.lyle": dấu chấm dính liền tên. */
    private val TITLE_GLUED = Regex("""(?i)^(mrs|mr|ms|dr|st)\.(?=\p{L})""")
    private const val TITLE_OPENERS = "\"'“‘([«"

    /**
     * "Mr." / "Mrs." / "Ms." / "Dr." / "St." trước tên đọc đủ chữ Anh ("mister", "missus", "miss", "doctor", "saint"): sea-g2p đọc "mờ rờ" hay để nguyên "mr." làm cả câu bị ngắt ở dấu chấm. Dấu chấm bỏ theo
     * ("mr.lyle" -> "mister lyle"). Thay tại chỗ; số chữ không đổi - `read_titles`.
     */
    fun readTitles(toks: List<String>, out: MutableList<String>) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = Names.splitToken(token)
            if (core.isEmpty() || before.lastOrNull()?.isDigit() == true) continue
            val following = if (index + 1 < toks.size) toks[index + 1].trimStart { it in TITLE_OPENERS } else ""
            val glued = TITLE_GLUED.find(core)
            val key: String
            val tail: String
            if (glued != null) { // "mr.lyle"
                key = glued.groupValues[1].lowercase()
                val rest = core.substring(glued.range.last + 1)
                if (key in TITLE_NEEDS_NAME && !rest[0].isUpperCase()) continue
                tail = " $rest$after"
            } else {
                key = core.lowercase()
                if (key !in TITLES || core.substring(1) != core.substring(1).lowercase()) continue
                val dotted = after.startsWith(".")
                val next = following.firstOrNull()
                if (next == null || !next.isLetter() || (key in TITLE_NEEDS_NAME && !next.isUpperCase()) || (!dotted && (key == "st" || core[0].isLowerCase()))) continue
                tail = if (dotted) after.substring(1) else after
            }
            out[index] = before + TITLES.getValue(key) + tail
        }
    }

    private val VIETNAMESE_TITLES = mapOf(
        "PGS" to "phó giáo sư", "GS" to "giáo sư", "TS" to "tiến sĩ",
        "ThS" to "thạc sĩ", "Th.S" to "thạc sĩ", "BS" to "bác sĩ",
        "KS" to "kỹ sư", "CN" to "cử nhân", "TP" to "thành phố", "Tp" to "thành phố",
        "P" to "phường", "Q" to "quận", "H" to "huyện", "TX" to "thị xã", "ĐH" to "đại học",
    )
    // Explicit whitespace also works on Android ICU (no Java UNICODE_CHARACTER_CLASS).
    private const val VI_SPACE = """[\u0009-\u000D\u001C-\u0020\u0085\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]"""
    private const val VI_TITLE = """(?:PGS|GS|TS|ThS|BS|KS|CN|TP|Tp|TX|ĐH|P|Q|H)\.|Th\.S\.?"""
    private val VI_CHAIN = Regex("""(?<![\p{L}\p{N}_.])(?:(?:$VI_TITLE)$VI_SPACE*)+""")
    private val VI_PART = Regex(VI_TITLE)
    private val VI_HEAD = Regex("""^\p{L}+""")
    private val ADDRESS_HEADS = setOf("Bến", "Bình", "Tân", "Thạnh", "Phú", "Long", "Quảng", "Thủ")
    private val ADDRESS_CONTEXT = Regex("""(?i)(?:tại|ở|thuộc|đến|địa chỉ|địa bàn|khu vực)$VI_SPACE*$""")
    private val ADDRESS_NUMBER = Regex("""[0-9]+(?![\p{L}\p{N}_])""")
    private data class TitleEdit(val start: Int, val end: Int, val word: String)

    /** Vietnamese dotted titles before spelling; preserve source-token ownership. */
    fun readVietnameseTitles(toks: List<String>, out: MutableList<String>) {
        val text = toks.joinToString(" ")
        val edits = mutableListOf<TitleEdit>()
        for (chain in VI_CHAIN.findAll(text)) {
            val tail = text.substring(chain.range.last + 1)
            // An all-capital word after the title is another abbreviation (TP.HCM, PGS.TS), not a name.
            val head = VI_HEAD.find(tail)?.value
            val named = head != null && head[0].isUpperCase() && !(head.length > 1 && head == head.uppercase())
            val number = ADDRESS_NUMBER.find(tail)?.range?.first == 0
            for (part in VI_PART.findAll(chain.value)) {
                val key = part.value.trimEnd('.')
                val locality = tail.split(Regex("$VI_SPACE+")).take(2)
                val addressName = ADDRESS_CONTEXT.containsMatchIn(text.substring(0, chain.range.first)) ||
                    (locality.size == 2 && locality[0] in ADDRESS_HEADS && locality[1].firstOrNull()?.isUpperCase() == true)
                if (!named && !(number && key in setOf("P", "Q", "H", "TP", "Tp", "TX"))) continue
                if (key in setOf("P", "Q", "H") && !number && !addressName) continue
                val start = chain.range.first + part.range.first
                val end = chain.range.first + part.range.last + 1
                val word = VIETNAMESE_TITLES.getValue(key) +
                    (if (end < text.length && !Regex(VI_SPACE).matches(text[end].toString())) " " else "")
                edits.add(TitleEdit(start, end, word))
            }
        }
        var offset = 0
        for ((index, token) in toks.withIndex()) {
            if (out[index] == token) {
                var value = token
                for (edit in edits.asReversed()) {
                    if (offset <= edit.start && edit.end <= offset + token.length)
                        value = value.substring(0, edit.start - offset) + edit.word + value.substring(edit.end - offset)
                }
                out[index] = value
            }
            offset += token.length + 1
        }
    }

}
