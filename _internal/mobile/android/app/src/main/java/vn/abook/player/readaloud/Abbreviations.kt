package vn.abook.player.readaloud

/**
 * Viết tắt TOÀN HOA trong "Nghe ngay": đọc tên chữ cái hệ a-bê-xê ("HP" -> "hát pê", "NPC" -> "en pê xê") - bản Kotlin y hệt `abook/readaloud/abbreviations.py`
 * (cùng đọc tests/fixtures/vieneu/android/text.json: các khúc `units`). Biến đổi để đọc, chữ hiện không đổi. Chỉ đọc khi chắc là viết tắt: 2-5 chữ cái Latin HOA, không dính
 * số, không phải từ tiếng Anh / tiếng Nhật / tiếng cười viết hoa cả (những từ ấy đổi sang chữ thường vì sea-g2p đọc chữ hoa cả thành từng chữ cái), không nằm trong câu
 * viết hoa cả. Ngoại lệ đọc như từ (chủ sách): VIP "víp", ID "ai-đi", OK "ô kê", TV "ti vi".
 */
object Abbreviations {
    private val LETTERS = mapOf(
        'a' to "a", 'b' to "bê", 'c' to "xê", 'd' to "đê", 'e' to "e", 'f' to "ép", 'g' to "giê", 'h' to "hát", 'i' to "i", 'j' to "gi", 'k' to "ca", 'l' to "e-lờ",
        'm' to "em", 'n' to "en", 'o' to "ô", 'p' to "pê", 'q' to "quy", 'r' to "e-rờ", 's' to "ét", 't' to "tê", 'u' to "u", 'v' to "vê", 'w' to "vê-kép", 'x' to "ích",
        'y' to "i-dài", 'z' to "dét",
    )
    private val AS_WORDS = mapOf("vip" to "víp", "id" to "ai-đi", "ok" to "ô kê", "tv" to "ti vi")
    private val SPELLED_ENGLISH = "abc ceo cia dna exp fbi hiv ibm nba usa".split(" ").toSet()
    private val SHOUT_WORDS = "no oh ah eh uh um ha ho yo hi he we me my up so to of or on ya ye go do if in is an by at".split(" ").toSet()
    private val LAUGH = Regex("(?:ha|he|hi|ho)+")
    private val ROMAN_LETTERS = "ivx".toSet()
    /** "đó.”(GM)": viết tắt trong ngoặc dính vào chữ trước. */
    private val PAREN_ABBREVIATION = Regex("""(?<=.)\(([A-Z]{2,5})\)""")
    /** Chủ sách 04-10: Lv không chắc là cấp độ thì đọc tên chữ cái, l = lờ, v = vê. */
    private val LEVEL_NAMES = mapOf("lv" to "lờ vê", "lvl" to "lờ vê lờ")
    private const val MIN_LETTERS = 2
    private const val MAX_LETTERS = 5
    private const val ROMAJI_FROM = 4

    private fun caps(core: String) = core.count { it.isLetter() } >= 2 && core.none { it.isLowerCase() }

    private fun shouty(core: String) = caps(core) && (core.any { it.code >= 128 } || '-' in core)

    private fun word(lower: String): Boolean {
        if (lower.length == 2) return lower in SHOUT_WORDS
        return lower in EnglishWords.ALL && lower !in SPELLED_ENGLISH && lower.any { it in "aeiouy" }
    }

    private fun letterNames(lower: String) = lower.map { LETTERS.getValue(it) }.joinToString(" ")

    /** Cách đọc của [core] (đã bỏ dấu câu quanh) khi nó là chữ HOA cả cần đổi để đọc, null khi để nguyên: viết tắt thì tên chữ cái; từ Anh / Nhật / tiếng cười viết hoa cả thì chữ thường. */
    fun spelled(core: String): String? {
        if (!(core.length >= MIN_LETTERS && core.all { it in 'A'..'Z' })) return null
        val lower = core.lowercase()
        AS_WORDS[lower]?.let { return it }
        if (lower.all { it in ROMAN_LETTERS }) return letterNames(lower)
        if (word(lower) || (lower.length >= 4 && LAUGH.matches(lower))) return lower
        if (lower.length > MAX_LETTERS) return null
        if (lower.length >= ROMAJI_FROM && Romanization.reading(lower, "ja") != null) return lower
        return letterNames(lower)
    }

    /**
     * "Lv" / "Lvl" / "LV" liền trước một số ("Lv 5", "Lv.5", "Lv5", "Lvl.10") là cấp độ: để chữ "level". Không đi với số thì không chắc nghĩa gì: đọc tên chữ cái ("lờ vê").
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
                before + "level" + (if (glued.firstOrNull()?.isDigit() == true) " $glued" else "")
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
}
