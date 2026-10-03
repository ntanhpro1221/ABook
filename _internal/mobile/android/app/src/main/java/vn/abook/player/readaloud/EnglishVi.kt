package vn.abook.player.readaloud

import java.io.File
import java.text.Normalizer
import java.util.Locale
import java.util.zip.GZIPInputStream
import vn.abook.player.BookEdits
import vn.abook.player.VietnameseReading

/**
 * Việt hoá một từ / tên tiếng Anh thành âm tiết tiếng Việt cho máy đọc CHỈ nói được âm tiết Việt, theo docs/READING_FOREIGN_NAMES.md
 * mục 1 và 4 - bản Kotlin y hệt `abook/english_vi.py` (cùng đọc tests/fixtures/english_vi/cases.json, sinh bằng
 * scripts/build_english_vi_fixture.py: đổi một bên là phải đổi cả hai). Mỗi âm tiết đầu ra phải qua `VietnameseReading.validSpokenForm`.
 * CHƯA nối vào đường đọc.
 *
 * Ba tầng: bảng ghi đè (chủ sách + từ mượn đã vào từ điển); đường âm vị khi có từ điển phát âm (english_phones.txt.gz - điện thoại tải
 * theo yêu cầu, `loadPhones`; chưa có UI tải); đường chính tả khi không có. Cờ: `via:` đường đã đi, `open:` điểm quy ước còn mở,
 * `analogy:` suy theo phán quyết gần nhất, `fit:` đường âm vị bị bộ kiểm âm tiết từ chối nên đọc theo chữ.
 */
object EnglishVi {
    /** Cách đọc và các cờ (không trùng, theo thứ tự gặp). */
    data class Reading(val text: String, val flags: List<String>)

    // Phán quyết chủ sách 04-10 (mục 4): cố định. Kate, Pete, guild, time, Thomas, great, Gate là ca riêng, không suy rộng (t đầu từ vẫn là t).
    // Kyle: chủ sách viết kai-ồ; chính tả luật 1.5 viết c trước a, cùng một âm.
    val OWNER = mapOf(
        "game" to "ghêm", "level" to "le-vồ", "maple" to "máp-pồ", "michael" to "mai-cồ", "kate" to "ca-tê",
        "mike" to "mi-ke", "jake" to "gia-ke", "luke" to "lu-ke", "pete" to "pi-tờ", "skill" to "xờ-kiu", "boss" to "bót", "slime" to "xờ-lam",
        "quest" to "quét",
        "guild" to "gui", "thomas" to "tho-mát", "boston" to "bót-tơn", "rocky" to "róc-ki", "time" to "tham", "night" to "nai",
        "blake" to "bờ-lếch", "master" to "mát-tơ", "zeke" to "de-ke", "gold" to "gôn",
        "tom" to "tom", "tony" to "to-ni", "team" to "tim", "tank" to "tanh", "tina" to "ti-na", "lyle" to "lai-ồ", "kyle" to "cai-ồ",
        "doyle" to "đoi-ồ",
        "fireball" to "phai-bôn", "rose" to "ro-xe", "great" to "gờ-rít", "late" to "lết", "grace" to "gờ-rây", "gate" to "ghết",
        "nate" to "na-te",
    )
    // Chữ viết tắt đã đọc thành từ (chủ sách 04-10): khoá là đúng chữ hoa như viết.
    val ACRONYMS = mapOf("VIP" to "víp", "ID" to "ai-đi")
    // Từ mượn đã vào từ điển tiếng Việt (mục 6).
    val LOANWORDS = mapOf(
        "radio" to "ra-đi-ô", "radar" to "ra-đa", "tennis" to "ten-nít", "acid" to "a-xít", "piano" to "pi-a-nô", "chocolate" to "sô-cô-la",
        "vitamin" to "vi-ta-min", "cowboy" to "cao-bồi", "meeting" to "mít-tinh", "dollar" to "đô-la", "cafe" to "cà-phê", "golf" to "gôn",
        "card" to "cạc",
    )
    val OVERRIDES = LOANWORDS + OWNER

    // Chỗ quy ước ghi "mở": chủ sách 04-10 (lần 3, 4) đã chốt mọi điểm trước đây.
    val OPEN_CHOICES = emptyMap<String, String>()

    // Giá trị đã quét (scripts/sweep_english_vi_variants.py); ý nghĩa từng điểm ở CHOICES của bản Python.
    private const val SCHWA = "letter"
    private const val EPENTHESIS = "ờ"
    private const val EPENTHESIS_MEDIAL = "ơ"
    private const val L_CODA = "n"
    private const val IL_FINAL = "u"
    private const val S_CODA = "t"
    private const val FRIC_FINAL = "stop"
    private const val VOICED_FINAL = "devoice"
    private const val FINAL_CLUSTER = "drop"
    private const val GLIDE_CODA = "drop"
    private const val TH = "th"
    private const val DH = "đ"
    private const val AE = "a"
    private const val AA_O = "o"
    private const val EH = "e"
    private const val IH = "i"
    private const val EY_P = "a"
    private const val EY_K = "ê"
    private const val EY_T = "ê"
    private const val AY_M = "am"
    private const val EY_NASAL = "ê"
    private const val GEMINATE = "primary"
    private const val TR = "tr"
    private const val SHORT_SILENT_E = "face"

    private val GLIDE_VOWELS = setOf("AY", "AW", "OY")
    private val SHORT_VOWELS = setOf("AE", "EH", "IH", "AA", "AH", "UH")
    private val STOPS = setOf("P", "T", "K")
    private val ONSET = mapOf(
        "B" to "b", "CH" to "ch", "D" to "đ", "F" to "ph", "G" to "G", "HH" to "h", "JH" to "gi", "K" to "K", "L" to "l", "M" to "m", "N" to "n",
        "NG" to "NG", "P" to "p", "R" to "r", "S" to "x", "SH" to "s", "T" to "t", "V" to "v", "Z" to "d", "ZH" to "gi", "W" to "u", "Y" to "i",
    )
    private val PLAIN_CODA = mapOf("P" to "p", "T" to "t", "K" to "c", "M" to "m", "N" to "n", "NG" to "ng")
    private val VOICED_STOP_CODA = mapOf("B" to "p", "D" to "t", "G" to "c")
    private val FRICATIVE_CODA = mapOf(
        "S" to "t", "Z" to "t", "SH" to "t", "ZH" to "t", "TH" to "t", "DH" to "t", "CH" to "t", "JH" to "t", "F" to "p", "V" to "p",
    )
    private val FRONT = setOf("i", "e", "ê", "y")
    private const val GRAVE = "̀"
    private const val ACUTE = "́"
    private const val DIACRITIC_VOWELS = "ăâêôơư"
    private val SCHWA_LETTER = mapOf('a' to "a", 'e' to "e", 'i' to "i", 'y' to "i", 'o' to "ơ", 'u' to "ơ")
    private val HIATUS = setOf("ia", "io", "iu", "ie", "ea", "eo", "ua", "uo", "oa", "oe", "ue", "ui", "eu")

    /** (ARPAbet không số, nhấn: -1 phụ âm / 0 / 1 / 2, chữ nguyên âm viết ra tương ứng hay ""). */
    private data class Phone(val base: String, val stress: Int, val letters: String)

    private class Syl(var onset: String, var nucleus: String, var coda: String = "", var grave: Boolean = false)

    private fun sub(text: String, from: Int, to: Int): String {
        val start = from.coerceIn(0, text.length)
        return text.substring(start, to.coerceIn(start, text.length))
    }

    // ---- từ điển phát âm -----------------------------------------------------------------------------------------------

    /** Đọc từ điển gọn (gzip, mỗi dòng "từ PHONES"); điện thoại tải file này theo yêu cầu, không đóng vào APK. */
    fun loadPhones(file: File): Map<String, String> {
        val entries = HashMap<String, String>(160_000)
        GZIPInputStream(file.inputStream()).bufferedReader(Charsets.UTF_8).useLines { lines ->
            for (line in lines) {
                val space = line.indexOf(' ')
                if (space > 0 && space < line.length - 1) entries[line.substring(0, space)] = line.substring(space + 1)
            }
        }
        return entries
    }

    private fun parsePhones(text: String, word: String): List<Phone> {
        val phones = text.split(' ').filter { it.isNotEmpty() }.map { raw ->
            if (raw.last().isDigit()) Phone(raw.dropLast(1), raw.last() - '0', "") else Phone(raw, -1, "")
        }
        return alignLetters(phones, word)
    }

    private fun vowelGroups(word: String, dropFinalE: Boolean): List<String> {
        val letters = if (dropFinalE) word.dropLast(1) else word
        val groups = ArrayList<String>()
        val current = StringBuilder()
        letters.forEachIndexed { index, ch ->
            val vowel = ch in "aeiou" || (ch == 'y' && !(index == 0 && sub(letters, 1, 2).let { it.isNotEmpty() && it[0] in "aeiou" }))
            if (vowel) {
                current.append(ch)
            } else if (current.isNotEmpty()) {
                groups.add(current.toString())
                current.setLength(0)
            }
        }
        if (current.isNotEmpty()) groups.add(current.toString())
        return groups
    }

    private fun splitHiatus(groups: List<String>, count: Int): List<String>? {
        val need = count - groups.size
        if (need == 0) return groups
        if (need < 0) return null
        val candidates = groups.indices.filter { groups[it] in HIATUS }
        if (candidates.size < need) return null
        val chosen = candidates.takeLast(need).toSet()
        val out = ArrayList<String>()
        groups.forEachIndexed { index, group ->
            if (index in chosen) {
                out.add(group.substring(0, 1))
                out.add(group.substring(1, 2))
            } else {
                out.add(group)
            }
        }
        return out
    }

    private fun alignLetters(phones: List<Phone>, word: String): List<Phone> {
        val count = phones.count { it.stress >= 0 }
        for (drop in listOf(false, true)) {
            if (drop && !(word.length > 2 && word.endsWith("e") && word[word.length - 2] !in "aeiouy")) continue
            val groups = splitHiatus(vowelGroups(word, drop), count) ?: continue
            var at = 0
            return phones.map { phone -> if (phone.stress >= 0) phone.copy(letters = groups[at++]) else phone.copy(letters = "") }
        }
        return phones
    }

    // ---- đường chính tả: chữ -> ARPAbet ----------------------------------------------------------------------------------

    private const val LETTER_VOWELS = "aeiouy"
    private val LONG = mapOf('a' to "EY", 'e' to "IY", 'i' to "AY", 'o' to "OW", 'u' to "UW", 'y' to "AY")
    private val FACE = mapOf('a' to "AA", 'e' to "EH", 'i' to "IH", 'o' to "AA", 'u' to "UH", 'y' to "IH") // o -> o (tom, ro-xe)
    private val FINAL_OPEN = mapOf('a' to "AA", 'e' to "IY", 'i' to "IY", 'o' to "OW", 'u' to "UW", 'y' to "IY")
    private val DIGRAPHS = listOf(
        "eau" to "OW", "igh" to "AY", "ee" to "IY", "ea" to "IY", "ai" to "EY", "ay" to "EY", "ei" to "EY", "ie" to "IY", "oa" to "OW",
        "oo" to "UW", "ou" to "AW", "oi" to "OY", "oy" to "OY", "au" to "AO", "aw" to "AO", "ew" to "UW",
    )
    private val SIMPLE_CONSONANT = mapOf(
        'b' to "B", 'd' to "D", 'f' to "F", 'k' to "K", 'l' to "L", 'm' to "M", 'n' to "N", 'p' to "P", 'r' to "R", 's' to "S", 't' to "T",
        'v' to "V", 'z' to "Z",
    )
    private val CONSONANT_DIGRAPHS = mapOf(
        "ch" to "CH", "sh" to "SH", "th" to "TH", "ph" to "F", "ck" to "K", "ng" to "NG", "wh" to "W", "dg" to "JH",
    )

    private fun isVowelLetter(word: String, index: Int): Boolean {
        if (index < 0 || index >= word.length) return false
        val ch = word[index]
        if (ch == 'y') {
            val next = sub(word, index + 1, index + 2)
            return !(next.isNotEmpty() && next[0] in "aeiou" && (index == 0 || word[index - 1] !in LETTER_VOWELS))
        }
        return ch in "aeiou"
    }

    private fun spellPhones(word: String): List<Phone>? {
        val w = word
        val size = w.length
        if (size == 0 || !w.all { it in 'a'..'z' || it in 'A'..'Z' }) return null
        var silentE = size >= 3 && w[size - 1] == 'e' && !isVowelLetter(w, size - 2) && (0 until size - 2).any { isVowelLetter(w, it) }
        val syllabicLe = silentE && w[size - 2] == 'l' && size >= 4 && !isVowelLetter(w, size - 3)
        if (syllabicLe) silentE = false
        var end = if (silentE) size - 1 else size
        if (syllabicLe) end = size - 2
        val magic = if (silentE && isVowelLetter(w, size - 3) && !isVowelLetter(w, size - 4)) size - 3 else -1
        val out = ArrayList<Phone>()
        var i = 0
        while (i < end) {
            val rest = w.substring(i, end)
            val ch = w[i]
            if (isVowelLetter(w, i)) {
                if (i == magic) {
                    out.add(Phone(LONG.getValue(ch), 0, ch.toString()))
                    i += 1
                    continue
                }
                var digraph = DIGRAPHS.firstOrNull { rest.startsWith(it.first) }
                if (rest == "ey" || rest == "ay" || (rest == "ie" && size <= 4)) digraph = rest to (if (rest != "ay") "IY" else "EY")
                if (rest.startsWith("ow")) digraph = "ow" to (if (rest == "ow") "OW" else "AW")
                if (rest == "ue") digraph = "ue" to "UW"
                if (digraph != null) {
                    out.add(Phone(digraph.second, 0, digraph.first))
                    i += digraph.first.length
                    continue
                }
                val after = sub(w, i + 1, i + 2)
                if (after == "r" && !isVowelLetter(w, i + 2) && i + 1 < end) {
                    // ar, or, er / ir / ur / yr trước phụ âm hay cuối từ
                    when (ch) {
                        'a' -> { out.add(Phone("AA", 0, "a")); out.add(Phone("R", -1, "")) }
                        'o' -> { out.add(Phone("AO", 0, "o")); out.add(Phone("R", -1, "")) }
                        else -> out.add(Phone("ER", 0, ch.toString()))
                    }
                    i += 2
                    continue
                }
                val vowel = when {
                    ch == 'a' && sub(w, i + 1, i + 3) == "nk" -> "AE" // ank -> anh như đường âm vị (tank -> tanh)
                    i == end - 1 -> FINAL_OPEN.getValue(ch)
                    else -> FACE.getValue(ch)
                }
                out.add(Phone(vowel, 0, ch.toString()))
                i += 1
                continue
            }
            // phụ âm
            if (rest.startsWith("tion") || rest.startsWith("sion")) {
                out.add(Phone(if (ch == 't') "SH" else "ZH", -1, ""))
                out.add(Phone("AH", 0, "io"))
                out.add(Phone("N", -1, ""))
                i += 4
                continue
            }
            if (rest.startsWith("tch")) {
                out.add(Phone("CH", -1, ""))
                i += 3
                continue
            }
            val two = sub(rest, 0, 2)
            val digraph = CONSONANT_DIGRAPHS[two]
            if (digraph != null) {
                out.add(Phone(digraph, -1, ""))
                i += 2
                continue
            }
            if (two == "gh") {
                if (i == 0) out.add(Phone("G", -1, ""))
                i += 2 // gh giữa / cuối từ câm (light, Hugh)
                continue
            }
            if (two == "qu") {
                out.add(Phone("K", -1, ""))
                out.add(Phone("W", -1, ""))
                i += 2
                continue
            }
            if (i == 0 && (two == "kn" || two == "gn" || two == "wr")) {
                out.add(Phone(if (two != "wr") "N" else "R", -1, ""))
                i += 2
                continue
            }
            if (two == "gu" && isVowelLetter(w, i + 2)) {
                out.add(Phone("G", -1, ""))
                i += 2
                continue
            }
            val following = sub(w, i + 1, i + 2)
            if (following == ch.toString() && ch != 'c') {
                i += 1 // phụ âm đôi đọc một lần
                continue
            }
            when (ch) {
                'c' -> when {
                    following == "e" || following == "i" || following == "y" -> out.add(Phone("S", -1, ""))
                    following == "c" -> {
                        out.add(Phone("K", -1, ""))
                        i += 1
                        val third = sub(w, i + 1, i + 2)
                        if (third == "e" || third == "i" || third == "y") out.add(Phone("S", -1, ""))
                    }
                    else -> out.add(Phone("K", -1, ""))
                }
                'g' -> out.add(Phone(if (following == "e" || following == "i" || following == "y") "JH" else "G", -1, ""))
                'x' -> if (i == 0) out.add(Phone("Z", -1, "")) else { out.add(Phone("K", -1, "")); out.add(Phone("S", -1, "")) }
                'y' -> out.add(Phone("Y", -1, ""))
                'h' -> if (i == 0 || isVowelLetter(w, i + 1)) out.add(Phone("HH", -1, "")) // h sau nguyên âm, trước phụ âm / cuối từ câm
                'w' -> out.add(Phone("W", -1, ""))
                'j' -> out.add(Phone("JH", -1, ""))
                'n' -> out.add(Phone(if (following == "k") "NG" else "N", -1, "")) // nk đọc /ŋk/
                'q' -> out.add(Phone("K", -1, ""))
                else -> out.add(Phone(SIMPLE_CONSONANT.getValue(ch), -1, ""))
            }
            i += 1
        }
        if (syllabicLe) {
            out.add(Phone("AH", 0, "e"))
            out.add(Phone("L", -1, ""))
        }
        // mọi nguyên âm nhấn 0: chữ không cho biết trọng âm, nên không nhân đôi phụ âm
        return if (out.any { it.stress >= 0 }) out else null
    }

    /** Tên ngắn phụ âm tắc + e câm đọc theo MẶT CHỮ (Mike -> mi-ke): nguyên âm như chữ, e cuối đọc e. */
    private fun faceShort(word: String): List<Phone> {
        val phones = (spellPhones(word.dropLast(1)) ?: emptyList()).toMutableList()
        val soft = word[word.length - 2]
        if ((soft == 'c' || soft == 'g') && phones.isNotEmpty()) phones[phones.size - 1] = Phone(if (soft == 'c') "S" else "JH", -1, "") // la-xe
        val vowel = word[word.length - 3]
        return phones.map { if (it.stress >= 0) Phone(FACE.getValue(vowel), 0, vowel.toString()) else it } + Phone("EH", 0, "e")
    }

    /** MỘT phụ âm đầu (một chữ, hay ch / sh / th / ph / wh) + một nguyên âm + MỘT phụ âm (trừ h w x y) + e câm: Jake, Zeke, Rose (chủ sách). */
    private fun shortSilentE(word: String): Boolean {
        if (!(word.length >= 4 && word.endsWith("e") && word[word.length - 2] in "bcdfgjklmnpqrstvz" && word[word.length - 3] in "aeiou")) return false
        val onset = word.substring(0, word.length - 3)
        return (onset.length == 1 && onset[0] !in "aeiouy") || onset in setOf("ch", "sh", "th", "ph", "wh")
    }

    // ---- ARPAbet -> âm tiết Việt -----------------------------------------------------------------------------------------

    private fun onsetLetter(base: String): String = when (base) {
        "TH" -> TH
        "DH" -> DH
        else -> ONSET.getValue(base)
    }

    private fun epenthetic(base: String, initial: Boolean = false): Syl {
        val vowel = if (initial) EPENTHESIS else EPENTHESIS_MEDIAL
        if (base == "W") return Syl("", "u")
        if (base == "Y") return Syl("", "i")
        return Syl(onsetLetter(base), "ơ", "", vowel == "ờ")
    }

    private fun finalSyllable(base: String, flags: MutableList<String>): Syl {
        if (base == "L") {
            flags.add("analogy:l_syllable")
            return Syl("l", "ô", "", true)
        }
        flags.add("analogy:final_syllable")
        if (base == "W" || base == "Y") return Syl("", if (base == "W") "u" else "i", "", true)
        return Syl(onsetLetter(base), "ơ", "", true)
    }

    /** Chữ Việt khép âm tiết ("" = bỏ), hay null khi phụ âm ấy phải thành âm tiết riêng. */
    private fun codaLetter(base: String, final: Boolean): String? {
        PLAIN_CODA[base]?.let { return it }
        if (base == "L") return if (L_CODA == "n") "n" else ""
        if (base == "R") return ""
        VOICED_STOP_CODA[base]?.let { return if (final && VOICED_FINAL == "syllable") null else it }
        val fricative = FRICATIVE_CODA[base] ?: return null
        if (final) return if (FRIC_FINAL == "stop") fricative else null
        if (base == "S" || base == "Z") return if (S_CODA == "t") "t" else null
        return fricative
    }

    private fun isSchwa(phone: Phone) = phone.base == "AH" && phone.stress == 0

    private fun nucleus(phone: Phone, coda: String, rColored: Boolean): String {
        val letters = phone.letters
        return when (phone.base) {
            "AA" -> if ('o' in letters) AA_O else "a"
            "AO" -> when {
                'a' in letters && 'o' !in letters -> "a"
                rColored && (coda == "c" || coda == "ng") -> "oo" // Niu Oóc, Poóc-len
                else -> "o"
            }
            "AE" -> AE
            "AH" -> if (phone.stress == 0) {
                if (SCHWA == "letter" && letters.isNotEmpty()) SCHWA_LETTER[letters.last()] ?: "ơ" else "ơ"
            } else {
                if (coda.isNotEmpty()) "ă" else "a"
            }
            "EH" -> EH
            "IH" -> IH
            "EY" -> when {
                coda.isEmpty() -> "ây"
                coda == "m" || coda == "n" || coda == "ng" -> EY_NASAL
                coda == "p" -> EY_P
                coda == "c" || coda == "ch" -> EY_K
                else -> EY_T
            }
            "AY" -> if (coda == "m") "a" else "ai" // xờ-lam, tham (chủ sách 04-10)
            else -> mapOf("IY" to "i", "UH" to "u", "UW" to "u", "OW" to "ô", "ER" to "ơ", "AY" to "ai", "AW" to "ao", "OY" to "oi")
                .getValue(phone.base)
        }
    }

    private fun glideW(nucleus: String): String? {
        val first = nucleus.take(1)
        return when {
            nucleus.startsWith("ây") -> "u$nucleus"
            first == "a" || first == "ă" || first == "e" -> "o$nucleus"
            first == "ê" || first == "ơ" || first == "â" -> "u$nucleus"
            nucleus == "i" -> "uy"
            else -> null
        }
    }

    private fun syllabify(input: List<Phone>, flags: MutableList<String>): List<Syl>? {
        // /aɪər/ (fire, higher): ơ sau ai nuốt vào ai, r bỏ (chủ sách 04-10: fireball -> phai-bôn)
        val phones = input.filterIndexed { index, phone -> !(phone.base == "ER" && phone.stress == 0 && index > 0 && input[index - 1].base == "AY") }
        val vowels = phones.indices.filter { phones[it].stress >= 0 }
        if (vowels.isEmpty()) return null
        val out = ArrayList<Syl>()
        var (onset, glide) = onsetRun(phones.subList(0, vowels[0]).map { it.base }, out)
        for ((k, at) in vowels.withIndex()) {
            val vowel = phones[at]
            val last = k == vowels.size - 1
            var run = (if (last) phones.subList(at + 1, phones.size) else phones.subList(at + 1, vowels[k + 1])).map { it.base }
            // -əl cuối từ: schwa + l thành "ồ" (l bỏ), thanh huyền - chủ sách 04-10 (máp-pồ, mai-cồ, le-vồ)
            if (last && isSchwa(vowel) && run.firstOrNull() == "L") {
                emit(out, onset, glide, "ô", "", true)
                for (base in run.drop(1)) if (FINAL_CLUSTER == "syllable") out.add(finalSyllable(base, flags))
                return out
            }
            var rColored = false
            if (run.firstOrNull() == "R" && (last || run.size >= 2)) {
                run = run.drop(1) // r sau nguyên âm bỏ
                rColored = true
            }
            val canClose = vowel.base !in GLIDE_VOWELS || (vowel.base == "AY" && run.firstOrNull() == "M" && AY_M == "am")
            var ilFinal = false
            var coda = ""
            var codaPhone = ""
            val tail = ArrayList<Syl>()
            var nextOnset = ""
            var nextGlide = ""
            if (last) {
                if (run.firstOrNull() == "L" && (vowel.base == "IH" || vowel.base == "IY") && IL_FINAL == "u") {
                    ilFinal = true // skill -> xờ-kiu (chủ sách 04-10): l cuối sau i thành u
                    for (base in run.drop(1)) if (FINAL_CLUSTER == "syllable") tail.add(finalSyllable(base, flags))
                    run = emptyList()
                }
                if (vowel.base == "EY" && run.firstOrNull() == "S") run = emptyList() // /eɪ/ + s cuối: ây, s bỏ (gờ-rây)
                if (run.isNotEmpty()) {
                    val first = run[0]
                    codaPhone = first
                    val letter: String? = if (canClose) codaLetter(first, true) else (if (GLIDE_CODA == "drop") "" else null)
                    when {
                        // l sau ai / ao / oi: âm tiết "ồ" KHÔNG phụ âm đầu, l bỏ (chủ sách 04-10: lai-ồ, kai-ồ, đoi-ồ)
                        first == "L" && !canClose -> tail.add(Syl("", "ô", "", true))
                        letter == null -> tail.add(finalSyllable(first, flags))
                        else -> coda = letter
                    }
                    for (base in run.drop(1)) if (FINAL_CLUSTER == "syllable") tail.add(finalSyllable(base, flags))
                }
            } else {
                val split = splitOnset(run)
                var head = split.first
                nextOnset = split.second
                nextGlide = split.third
                if (nextOnset == "NG") {
                    head = head + "NG" // ng tiếng Anh không mở âm tiết: Hê-minh-uây
                    nextOnset = ""
                }
                if (run.isEmpty() && vowel.base == "ER") nextOnset = "R" // Cô-lô-ra-đô, ca-mê-ra
                if (head.isEmpty() && nextOnset.isNotEmpty() && run.size == 1 && run[0] in STOPS && canClose && vowel.stress >= 1 && (
                        GEMINATE == "stressed" || (GEMINATE == "primary" && vowel.stress == 1) ||
                            (GEMINATE == "short" && vowel.base in SHORT_VOWELS)
                        )
                ) {
                    coda = PLAIN_CODA.getValue(run[0]) // máp-pồ, Rốc-ki
                }
                if (head.isNotEmpty() && canClose) {
                    val letter = codaLetter(head[0], false)
                    if (letter != null) {
                        coda = letter
                        codaPhone = head[0]
                        head = head.drop(1)
                    }
                }
                head.forEach { tail.add(epenthetic(it)) }
            }
            var core = nucleus(vowel, coda, rColored)
            if (vowel.base == "AO" && codaPhone == "L" && coda.isNotEmpty()) core = "ô" // /ɔːl/ -> ôn (phai-bôn, như gôn)
            if (vowel.base == "AE" && coda == "ng" && run.size >= 2 && run[0] == "NG" && run[1] == "K") {
                core = "a" // /æŋk/ -> anh (chủ sách 04-10: tank -> tanh; rank, thank theo đó)
                coda = "nh"
                flags.add("analogy:ank")
            }
            if (ilFinal) core += "u"
            emit(out, onset, glide, core, coda, false) // -er cuối: ơ thanh ngang (chủ sách 04-10: mát-tơ)
            out.addAll(tail)
            onset = nextOnset
            glide = nextGlide
        }
        return out
    }

    private fun onsetRun(run: List<String>, out: MutableList<Syl>): Pair<String, String> {
        val (head, onset, glide) = splitOnset(run)
        head.forEach { out.add(epenthetic(it, true)) }
        return onset to glide
    }

    private fun splitOnset(input: List<String>): Triple<List<String>, String, String> {
        if (input.isEmpty()) return Triple(emptyList(), "", "")
        var run = input
        var glide = ""
        if (run.last() == "W" || run.last() == "Y") {
            glide = run.last()
            run = run.dropLast(1)
            if (run.isEmpty()) return Triple(emptyList(), "", glide)
        }
        if (run.size >= 2 && run[run.size - 2] == "T" && run[run.size - 1] == "R" && TR == "tr") return Triple(run.dropLast(2), "tr", glide)
        return Triple(run.dropLast(1), run.last(), glide)
    }

    private fun emit(out: MutableList<Syl>, onset: String, glide: String, nucleus: String, coda: String, grave: Boolean) {
        var letter = if (onset.isNotEmpty() && onset != "tr") onsetLetter(onset) else onset
        if (glide == "W") {
            val joined = if (nucleus == "ô" && coda.isNotEmpty()) "uô" else glideW(nucleus) // uô chỉ trước phụ âm cuối: Walt -> Uôn
            if (joined != null) {
                out.add(Syl(letter, joined, coda, grave))
                return
            }
            out.add(Syl(letter, "u"))
            letter = ""
        } else if (glide == "Y") {
            if (nucleus.startsWith("i")) {
                out.add(Syl(letter, nucleus, coda, grave)) // y + i: một âm i
                return
            }
            if (nucleus == "u" && coda.isEmpty()) {
                out.add(Syl(letter, "iu", "", grave)) // Mét-thiu, Niu
                return
            }
            out.add(Syl(letter, "i"))
            letter = ""
        }
        out.add(Syl(letter, nucleus, coda, grave))
    }

    /**
     * Thanh sắc cho vần khép p / t / c / ch: lên chữ có dấu mũ / móc / trăng, không thì chữ cuối. Cùng luật với `Romanization.toneAcute`
     * (riêng tư ở đó; bản Python dùng chung một hàm `romanization._tone_acute`).
     */
    private fun toneAcute(nucleus: String): String {
        var index = -1
        nucleus.forEachIndexed { position, letter -> if (letter in DIACRITIC_VOWELS) index = position }
        if (index < 0) index = nucleus.length - 1
        return Normalizer.normalize(nucleus.substring(0, index + 1) + ACUTE + nucleus.substring(index + 1), Normalizer.Form.NFC)
    }

    private fun render(syllable: Syl): String {
        var onset = syllable.onset
        var nucleus = syllable.nucleus
        var coda = syllable.coda
        if (coda.isEmpty() && (nucleus == "ă" || nucleus == "â" || nucleus == "oă")) {
            nucleus = mapOf("ă" to "a", "â" to "ơ", "oă" to "oa").getValue(nucleus)
        }
        if (nucleus == "oo" && coda != "c" && coda != "ng") nucleus = "o"
        when (onset) {
            "K" -> {
                val glide = listOf("oai", "oa", "oă", "oe", "uy", "uê", "uơ", "uâ").firstOrNull { nucleus.startsWith(it) }
                if (glide != null) {
                    onset = "qu"
                    nucleus = nucleus.substring(1)
                } else {
                    onset = if (nucleus.take(1) in FRONT) "k" else "c"
                }
            }
            "G" -> onset = if (nucleus.take(1) in FRONT) "gh" else "g"
            "NG" -> onset = if (nucleus.take(1) in FRONT) "ngh" else "ng"
            "gi" -> if (nucleus.take(1) == "i") onset = "g" // gi + in viết gin
        }
        val before = if (nucleus.length >= 2) nucleus.substring(nucleus.length - 2, nucleus.length - 1) else ""
        if ((coda == "ng" || coda == "c") && (nucleus.endsWith("i") || nucleus.endsWith("ê")) && before != "i" && before != "y" && before != "u") {
            coda = if (coda == "ng") "nh" else "ch" // kinh, ích
        }
        if (coda == "c" || coda == "t" || coda == "p" || coda == "ch") {
            nucleus = toneAcute(nucleus)
        } else if (syllable.grave) {
            nucleus = Normalizer.normalize(nucleus + GRAVE, Normalizer.Form.NFC)
        }
        return onset + nucleus + coda
    }

    private fun validated(syllables: List<Syl>, capital: Boolean): String? {
        val pieces = syllables.map { render(it) }
        if (pieces.isEmpty() || pieces.any { !VietnameseReading.validSpokenForm("", it) }) return null
        val word = pieces.joinToString("-")
        return if (capital) word.substring(0, 1).uppercase(Locale.ROOT) + word.substring(1) else word
    }

    // ---- cửa vào -------------------------------------------------------------------------------------------------------

    /** true nếu viết hoa chữ đầu, false nếu toàn chữ thường, null nếu không phải chữ ASCII hay viết hoa lạ. */
    private fun partCase(part: String): Boolean? {
        if (part.isEmpty() || !part.all { it in 'a'..'z' || it in 'A'..'Z' }) return null
        if (part == part.lowercase(Locale.ROOT)) return false
        if (part[0] in 'A'..'Z' && part.substring(1) == part.substring(1).lowercase(Locale.ROOT)) return true
        return null
    }

    /** Cùng số với `analysis.COMPOUND_NAME_MIN_PART` (cách tách tên ghép của Studio) - bản Python import thẳng hằng ấy. */
    private const val COMPOUND_MIN_PART = 4

    /** Từ ghép không có trong từ điển mà hai nửa có (sandworm = sand + worm): đọc từng phần; nửa đầu dài nhất trước. */
    private fun compoundParts(key: String, dictionary: Map<String, String>): List<String>? {
        for (cut in key.length - COMPOUND_MIN_PART downTo COMPOUND_MIN_PART) {
            if (key.substring(0, cut) in dictionary && key.substring(cut) in dictionary) return listOf(key.substring(0, cut), key.substring(cut))
        }
        return null
    }

    private fun readWord(key: String, capital: Boolean, dictionary: Map<String, String>, overrides: Boolean, flags: MutableList<String>): String? {
        if (overrides) {
            OVERRIDES[key]?.let { reading ->
                flags.add("via:override")
                return if (capital) reading.substring(0, 1).uppercase(Locale.ROOT) + reading.substring(1) else reading
            }
        }
        var phones: List<Phone>? = null
        var route = "via:phonemes"
        if (capital && shortSilentE(key) && SHORT_SILENT_E == "face") {
            phones = faceShort(key)
            route = "via:face"
        }
        if (phones == null) dictionary[key]?.let { phones = parsePhones(it, key) }
        if (phones == null) {
            compoundParts(key, dictionary)?.let { parts ->
                val inner = ArrayList<String>()
                val readings = parts.mapIndexed { index, part -> readWord(part, capital && index == 0, dictionary, overrides, inner) }
                if (readings.all { it != null }) {
                    flags.add("via:compound")
                    flags.addAll(inner)
                    return readings.joinToString("-")
                }
            }
        }
        phones?.let { found ->
            val trial = ArrayList<String>()
            val reading = syllabify(found, trial)?.let { validated(it, capital) }
            if (reading != null) {
                flags.add(route)
                flags.addAll(trial)
                return reading
            }
            flags.add("fit:spelling")
        }
        val spelled = spellPhones(key) ?: return null
        val trial = ArrayList<String>()
        val reading = syllabify(spelled, trial)?.let { validated(it, capital) } ?: return null
        flags.add("via:spelling")
        flags.addAll(trial)
        return reading
    }

    /**
     * Cách đọc + cờ, hay null. `dictionary`: từ điển phát âm đã tải (`loadPhones`), rỗng khi máy chưa có (chỉ đường chính tả).
     * `overrides` false = chỉ luật (bộ thử đo luật). Từ nối gạch đọc từng bộ phận, cách nhau dấu cách.
     */
    fun readingWithFlags(word: String, dictionary: Map<String, String>, overrides: Boolean = true): Reading? {
        val value = Normalizer.normalize(BookEdits.pyStrip(word), Normalizer.Form.NFC)
        if (value.isEmpty()) return null
        val flags = ArrayList<String>()
        val readings = ArrayList<String>()
        for (part in value.split('-')) {
            val acronym = if (overrides) ACRONYMS[part] else null
            if (acronym != null) {
                flags.add("via:override")
                readings.add(acronym)
                continue
            }
            val case = partCase(part) ?: return null
            readings.add(readWord(part.lowercase(Locale.ROOT), case, dictionary, overrides, flags) ?: return null)
        }
        return Reading(readings.joinToString(" "), flags.distinct())
    }

    /** Cách đọc nối gạch của một từ / tên tiếng Anh bằng âm tiết Việt, hay null khi không chắc. */
    fun reading(word: String, dictionary: Map<String, String>, overrides: Boolean = true): String? =
        readingWithFlags(word, dictionary, overrides)?.text
}
