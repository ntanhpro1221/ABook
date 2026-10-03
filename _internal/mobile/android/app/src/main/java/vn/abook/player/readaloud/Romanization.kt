package vn.abook.player.readaloud

import java.text.Normalizer
import java.util.Locale
import vn.abook.player.BookEdits
import vn.abook.player.VietnameseReading

/**
 * Đọc romaji Nhật (Hepburn) và phiên âm Latinh Hàn (RR) thành âm tiết tiếng Việt, theo docs/READING_FOREIGN_NAMES.md mục 1-3 - bản Kotlin
 * y hệt `abook/romanization.py` (cùng đọc tests/fixtures/romanization/cases.json, sinh bằng scripts/build_romanization_fixture.py: đổi một
 * bên là phải đổi cả hai). Mỗi âm tiết đầu ra phải qua phép kiểm âm tiết của `VietnameseReading` (bản `_valid_vietnamese_spoken_form`).
 * CHƯA nối vào đường đọc.
 *
 * Ba loại cờ: `open:` quy ước ghi "mở", đây là mặc định chờ kiểm bằng âm thanh (OPEN_CHOICES); `analogy:` quy ước không nói, suy theo hàng
 * gần nhất; `fit:` quy ước chọn dạng mà bộ kiểm âm tiết không nhận, nên dùng dạng khác cũng có nguồn.
 */
object Romanization {
    /** Cách đọc và các cờ (không trùng, theo thứ tự gặp). */
    data class Reading(val text: String, val flags: List<String>)

    val OPEN_CHOICES = mapOf(
        "y_after_vowel_pair" to "hai nguyên âm rồi ya / yu / yo cuối từ mà luật y cuối từ không áp (Kouya, Raiya: âu / ai + y không thành vần): hiện y -> gi (Câu-gia)",
        "ko_rare_vowels" to "oe / wi / ui / we / wae của tiếng Hàn: mặc định uê / uy / ưi / uê / oe theo âm (chưa có ví dụ chính thức)",
    )

    private val LONG_VOWELS = mapOf(
        'ā' to 'a', 'ī' to 'i', 'ū' to 'u', 'ē' to 'e', 'ō' to 'o', 'â' to 'a', 'î' to 'i', 'û' to 'u', 'ê' to 'e', 'ô' to 'o',
        'Ā' to 'A', 'Ī' to 'I', 'Ū' to 'U', 'Ē' to 'E', 'Ō' to 'O', 'Â' to 'A', 'Î' to 'I', 'Û' to 'U', 'Ê' to 'E', 'Ô' to 'O',
    )
    // Tiếng Nhật giữ ō / ô thành "ô" (dài viết bằng dấu -> ô), để phân biệt với "ou" viết ra hai chữ (-> âu: chủ sách 04-10)
    private val JA_LONG_O = mapOf('ō' to 'ô', 'Ō' to 'Ô', 'ô' to 'ô', 'Ô' to 'Ô')
    private const val ACUTE = "́"
    private const val DIACRITIC_VOWELS = "ăâêôơư"
    private val FRONT = setOf("i", "e", "ê", "y")

    /** Một âm tiết đầu ra: phụ âm đầu (ký hiệu K, G hay chữ Việt), vần, phụ âm cuối đã đổi sang chữ Việt (c, t, p, n, m, ng). */
    private class Syl(var onset: String, var nucleus: String, var coda: String = "")

    /** Khép âm tiết cuối bằng một phụ âm. Vần kết bằng i / u (ai, iu, ưi) không đứng trước phụ âm cuối: tách chữ cuối ra. */
    private fun close(syllables: MutableList<Syl>, coda: String): Boolean {
        if (syllables.isEmpty() || syllables.last().coda.isNotEmpty()) return false
        val last = syllables.last()
        if (last.nucleus == "uy" || (last.nucleus.length > 1 && last.nucleus.endsWith("y"))) return false
        if (last.nucleus.length > 1 && last.nucleus.last() in "iu") {
            syllables.removeAt(syllables.size - 1)
            syllables.add(Syl(last.onset, last.nucleus.dropLast(1)))
            syllables.add(Syl("", last.nucleus.last().toString(), coda))
        } else {
            last.coda = coda
        }
        return true
    }

    /** Thanh sắc cho vần của âm tiết khép p / t / c: lên chữ có dấu mũ / móc / trăng, không thì chữ cuối (oát, uýt). */
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
        if (coda.isNotEmpty() && nucleus == "ê") nucleus = "e" // ê chỉ đứng cuối âm tiết mở (chỉ Hàn: ye -> ê)
        if (onset == "K") {
            val glide = listOf("oai", "oa", "oe", "uy", "uê", "uơ", "uô").firstOrNull { nucleus.startsWith(it) }
            if (glide != null) {
                onset = "qu"
                nucleus = nucleus.substring(1)
            } else {
                onset = if (nucleus.take(1) in FRONT) "k" else "c"
            }
        } else if (onset == "G") {
            // g + i đọc "ghi" (chủ sách 04-10: Hiiragi -> Hi-ra-ghi; ji vẫn -> gi); trước e, ê cũng "gh"
            onset = if (nucleus.take(1) in FRONT) "gh" else "g"
        } else if (onset == "gi" && nucleus.take(1) == "i") {
            nucleus = nucleus.substring(1)
        }
        val before = if (nucleus.length >= 2) nucleus.substring(nucleus.length - 2, nucleus.length - 1) else ""
        if ((coda == "ng" || coda == "c") && (nucleus.endsWith("i") || nucleus.endsWith("ê")) && before != "i" && before != "y") {
            coda = if (coda == "ng") "nh" else "ch" // kinh, ích: -nh / -ch sau i, ê đơn
        }
        if (coda == "c" || coda == "t" || coda == "p" || coda == "ch") nucleus = toneAcute(nucleus)
        return onset + nucleus + coda
    }

    private fun validated(syllables: List<Syl>, capital: Boolean): String? {
        val pieces = syllables.map { render(it) }
        if (pieces.isEmpty() || pieces.any { !VietnameseReading.validSpokenForm("", it) }) return null
        val word = pieces.joinToString("-")
        return if (capital) word.substring(0, 1).uppercase(Locale.ROOT) + word.substring(1) else word
    }

    private fun sub(text: String, from: Int, to: Int): String = text.substring(minOf(from, text.length), minOf(to, text.length))

    // ---- tiếng Nhật (mục 2) ------------------------------------------------------------------------------------------

    private const val JA_VOWELS = "aiueo"
    private const val JA_VOWELS_LONG = "aiueoô" // ô: o viết bằng dấu (ō), đọc ô
    private val JA_VOWEL = mapOf('a' to "a", 'i' to "i", 'u' to "u", 'e' to "e", 'o' to "ô") // chủ sách 04-10: u -> u và e -> e ở mọi chỗ
    private val JA_SIMPLE = mapOf(
        "k" to "K", "g" to "G", "s" to "x", "z" to "d", "t" to "t", "d" to "đ", "n" to "n", "h" to "h", "b" to "b", "p" to "p", "m" to "m", "r" to "r",
    )
    private val JA_ALLOWED = mapOf(
        "k" to "aiueo", "g" to "aiueo", "n" to "aiueo", "b" to "aiueo", "p" to "aiueo", "m" to "aiueo", "r" to "aiueo",
        "s" to "aueo", "z" to "aueo", "t" to "aeo", "d" to "aeo", "h" to "aieo",
        "sh" to "aiueo", "ch" to "aiueo", "j" to "aiueo", "ts" to "u", "f" to "u", "w" to "a", "y" to "auo",
        "ky" to "auo", "gy" to "auo", "ny" to "auo", "hy" to "auo", "by" to "auo", "py" to "auo", "my" to "auo", "ry" to "auo",
    )
    private val JA_ONSETS = listOf("sh", "ch", "ts", "ky", "gy", "ny", "hy", "by", "py", "my", "ry")
    private val JA_GEMINATE_CODA = mapOf("k" to "c", "p" to "p", "t" to "t", "s" to "t")

    private fun jaEmit(onset: String, vowel: Char, syllables: MutableList<Syl>, flags: MutableList<String>) {
        val plain = JA_VOWEL.getValue(vowel)
        when {
            onset == "" -> { // chỉ là nguyên âm: o đầu từ hay sau a / e -> o (Osaka -> O-xa-ca, Aoi -> A-o-i), sau i / u -> ô (Fumio -> Phu-mi-ô, Fukuoka -> Phu-cu-ô-ca)
                val afterIu = syllables.isNotEmpty() && syllables.last().coda.isEmpty() && syllables.last().nucleus.takeLast(1) in listOf("i", "u")
                syllables.add(Syl("", if (vowel == 'o' && !afterIu) "o" else plain))
            }
            onset in JA_SIMPLE -> syllables.add(Syl(JA_SIMPLE.getValue(onset), plain))
            onset == "sh" -> syllables.add(Syl("s", plain)) // shi shu sha sho -> si su sa sô (chủ sách 04-10: shu giữ s + u)
            onset == "ch" -> syllables.add(Syl("ch", if (vowel == 'u') "u" else plain))
            onset == "j" -> syllables.add(Syl("gi", if (vowel == 'u') "u" else plain))
            onset == "ts" -> syllables.add(Syl("x", "u")) // tsu -> xu ở mọi chỗ (chủ sách 04-10)
            onset == "f" -> syllables.add(Syl("ph", "u"))
            onset == "w" -> syllables.add(Syl("", "oa"))
            onset == "y" -> { // y + nguyên âm -> gi + nguyên âm, đầu từ và giữa từ (chủ sách 04-10); yu, yo theo ya
                if (vowel != 'a') flags.add("analogy:y_gi")
                syllables.add(Syl("gi", plain))
            }
            else -> {
                val head = JA_SIMPLE.getValue(onset.substring(0, 1))
                if (vowel == 'a') flags.add("analogy:cya") // kyu -> ki-u, kyo -> ki-ô (chủ sách 04-10: Ryuu -> Ri-u)
                syllables.add(Syl(head, "i"))
                syllables.add(Syl("", plain))
            }
        }
    }

    /** Từ đã quen ở Việt Nam, chủ sách ghi đè cố định (04-10): onigiri (cơm nắm) -> o-ni-gi-ri, trong khi g + i -> ghi (Hiiragi) vẫn đứng. */
    private val JA_FIXED = mapOf(
        "onigiri" to listOf("" to "o", "n" to "i", "gi" to "i", "r" to "i"),
    )

    private fun jaWord(word: String, flags: MutableList<String>): List<Syl>? {
        JA_FIXED[word]?.let { fixed -> return fixed.map { (onset, nucleus) -> Syl(onset, nucleus) } }
        val syllables = ArrayList<Syl>()
        var i = 0
        while (i < word.length) {
            val c = word.substring(i, i + 1)
            val after = sub(word, i + 1, i + 2)
            if (c in JA_GEMINATE_CODA && (after == c || (c == "t" && sub(word, i + 1, i + 3) == "ch"))) {
                if (c == "s") flags.add("analogy:ss_t")
                if (!close(syllables, JA_GEMINATE_CODA.getValue(c))) return null
                i += 1
                continue
            }
            if (c == "n" && after == "'") {
                if (!close(syllables, "n")) return null
                i += 2
                continue
            }
            val moraic = (c == "n" && (after.isEmpty() || after[0] !in JA_VOWELS_LONG) &&
                !(after == "y" && sub(word, i + 2, i + 3) in listOf("a", "u", "o"))) ||
                (c == "m" && after in listOf("b", "m", "p"))
            if (moraic) {
                if (!close(syllables, "n")) return null
                i += 1
                continue
            }
            val onset: String
            var j: Int
            if (c[0] in JA_VOWELS_LONG) {
                onset = ""
                j = i
            } else {
                onset = JA_ONSETS.firstOrNull { word.startsWith(it, i) } ?: c
                j = i + onset.length
                if (onset !in JA_ALLOWED) return null
            }
            val vowelText = sub(word, j, j + 1)
            val longO = vowelText == "ô"
            if (vowelText.isEmpty() || vowelText[0] !in JA_VOWELS_LONG) return null
            val vowel = if (longO) 'o' else vowelText[0]
            if (onset.isNotEmpty() && vowel !in JA_ALLOWED.getValue(onset)) return null
            j += 1
            if (onset == "y" && j == word.length && syllables.isNotEmpty() && syllables.last().coda.isEmpty() && syllables.last().nucleus in listOf("a", "ây")) {
                // ya CUỐI từ sau nguyên âm: y thành bán âm cuối của âm tiết trước (ay, ây) + nguyên âm riêng (chủ sách 04-10: Maya -> May-a, Kaya -> Cay-a, Seiya -> Xây-a);
                // yu / yo cuối từ theo cùng cách là analogy (Mayu -> May-u, Sayo -> Say-ô); ya giữa / đầu từ vẫn gia (Ayaka -> A-gia-ca)
                if (syllables.last().nucleus == "a") syllables.last().nucleus = "ay"
                if (vowel != 'a') flags.add("analogy:y_final")
                syllables.add(Syl("", JA_VOWEL.getValue(vowel)))
                i = j
                continue
            }
            if (onset == "y" && i >= 2 && word[i - 2] in JA_VOWELS_LONG && word[i - 1] in JA_VOWELS_LONG) {
                flags.add("open:y_after_vowel_pair") // Kouya, Raiya: hai nguyên âm rồi ya mà luật ya cuối từ không áp (âu / ai + y không thành vần): hiện y -> gi
            }
            jaEmit(onset, vowel, syllables, flags)
            val follow = if (longO) "" else sub(word, j, j + 1)
            if (vowel == 'e' && follow == "i") {
                syllables.last().nucleus = "ây" // ei -> ây (chủ sách 04-10: Rei -> Rây, sensei -> xen-xây)
                j += 1
            } else if (vowel == 'o' && follow == "u") { // ou viết ra -> âu (chủ sách 04-10: Kyouko -> Ki-âu-cô); ō / oo vẫn -> ô
                if (onset == "sh" || onset == "ch" || onset == "j") flags.add("analogy:ou_vom")
                syllables.last().nucleus = "âu"
                j += 1
            } else if (follow.length == 1 && vowel == follow[0] && vowel in "oueia") {
                j += 1 // nguyên âm kép viết lặp gộp một: oo, uu, ee, ii, aa (chủ sách 04-10)
            } else if (vowel == 'a' && follow == "o") {
                if (j + 1 == word.length) {
                    syllables.last().nucleus = "ao" // ao CUỐI từ gộp một âm tiết (Nao -> Nao)
                    j += 1
                } else {
                    flags.add("analogy:ao_split") // ao giữa từ tách a-o (Aoi, Kaori; Naoki theo analogy)
                }
            } else if (vowel == 'a' && follow == "i") {
                syllables.last().nucleus += "i"
                j += 1
            }
            i = j
        }
        return syllables
    }

    // ---- tiếng Hàn (mục 3) -------------------------------------------------------------------------------------------

    private val KO_ONSETS = listOf("kk", "tt", "pp", "ss", "jj", "ch", "g", "k", "n", "d", "t", "r", "m", "b", "p", "s", "j", "h")
    private val KO_VOWELS = listOf(
        "yeo", "yae", "wae", "eo", "eu", "ae", "ya", "yo", "yu", "ye", "wa", "wo", "we", "wi", "oe", "oi", "ui", "a", "e", "i", "o", "u",
    )
    private val KO_CODAS = listOf("", "ng", "n", "m", "l", "k", "t", "p")
    private val KO_CODA_VIET = mapOf("" to "", "ng" to "ng", "n" to "n", "m" to "m", "l" to "n", "k" to "c", "t" to "t", "p" to "p")
    private val KO_VOWEL = mapOf(
        "a" to "a", "eo" to "eo", "o" to "ô", "u" to "u", "eu" to "ư", "i" to "i", "ae" to "e", "e" to "ê",
        "oe" to "uê", "oi" to "oi", "wi" to "uy", "ui" to "ưi", "wa" to "oa", "wo" to "uô", "we" to "uê", "wae" to "oe",
    )
    private val KO_RARE = setOf("oe", "wi", "ui", "we", "wae")
    private val KO_SPELLINGS = mapOf(
        "kim" to "gim", "park" to "pak", "lee" to "ri", "young" to "yeong", "myung" to "mung", "hyong" to "hyeong", "hee" to "hui",
        "soo" to "su", "yoo" to "yu", "yoon" to "yun", "shin" to "sin", "moon" to "mun", "kwon" to "gwon", "cho" to "jo",
    )

    private fun koParses(
        word: String, start: Int, previousCoda: String?, out: MutableList<List<Triple<String, String, String>>>,
        current: MutableList<Triple<String, String, String>>,
    ) {
        if (start == word.length) {
            out.add(ArrayList(current))
            return
        }
        val onsets = KO_ONSETS.filter { word.startsWith(it, start) }.sortedByDescending { it.length }.toMutableList()
        onsets.add("")
        if (previousCoda == "l" && word.startsWith("l", start)) onsets.add(0, "l")
        for (onset in onsets) {
            val at = start + onset.length
            for (vowel in KO_VOWELS) {
                if (!word.startsWith(vowel, at)) continue
                val after = at + vowel.length
                for (coda in KO_CODAS) {
                    if (coda.isNotEmpty() && !word.startsWith(coda, after)) continue
                    current.add(Triple(onset, vowel, coda))
                    koParses(word, after + coda.length, coda, out, current)
                    current.removeAt(current.size - 1)
                }
            }
        }
    }

    private fun koBest(raw: String): List<Triple<String, String, String>>? {
        val word = KO_SPELLINGS[raw] ?: raw
        if (word.isEmpty() || word.length > 24 || listOf("aa", "ee", "ii", "oo", "uu").any { it in word }) return null
        val parses = ArrayList<List<Triple<String, String, String>>>()
        koParses(word, 0, null, parses, ArrayList())
        if (parses.isEmpty()) return null
        fun rank(parse: List<Triple<String, String, String>>): Pair<Int, Int> = Pair(parse.size, parse.drop(1).count { it.first.isEmpty() })
        val ranks = parses.map { rank(it) }
        val top = ranks.minWithOrNull(compareBy<Pair<Int, Int>>({ it.first }, { it.second }))!!
        val best = parses.filterIndexed { index, _ -> ranks[index] == top }
        if (best.any { it != best[0] }) return null
        val chosen = best[0]
        for (parse in parses) {
            if (parse != chosen && parse.size == chosen.size) {
                for (k in 0 until chosen.size - 1) {
                    if (chosen[k].third == "n" && chosen[k + 1].first == "g" && parse[k].third == "ng") return null
                }
            }
        }
        return chosen
    }

    private fun koOnset(onset: String, previous: String?, flags: MutableList<String>): String {
        if (onset == "g" || onset == "d" || onset == "b") {
            val voiced = previous != null && previous in listOf("", "n", "m", "ng")
            return when (onset) {
                "g" -> if (voiced) "G" else "K"
                "d" -> if (voiced) "đ" else "t"
                else -> "b" // b đầu từ -> b (chủ sách 04-10: Busan -> Bu-xan; Park vẫn Pắc vì chữ P)
            }
        }
        if (onset == "k" || onset == "t" || onset == "p") { // bật hơi đọc như âm thường (chủ sách 04-10: Kang -> Cang)
            return when (onset) { "k" -> "K"; "t" -> "t"; else -> "p" }
        }
        if (onset == "kk" || onset == "tt" || onset == "pp" || onset == "jj" || onset == "ss") {
            flags.add("analogy:ko_tense")
            return when (onset) { "kk" -> "K"; "tt" -> "t"; "pp" -> "p"; "jj" -> "gi"; else -> "x" }
        }
        return when (onset) {
            "s" -> "x" // chủ sách 04-10: Seojun -> Xeo-giun
            "j" -> "gi"
            "ch" -> "ch"
            "r" -> if (previous == null) "l" else "r"
            "l" -> "l"
            "h" -> "h"
            "m" -> "m"
            "n" -> "n"
            else -> ""
        }
    }

    /** ㅓ: "eo" khi âm tiết mở (Seo -> Xeo); có phụ âm cuối thì tách e-o + coda (Jeong -> Gie-ong): chủ sách 04-10. */
    private fun koEo(onset: String, closing: String): MutableList<Syl> =
        if (closing.isEmpty()) mutableListOf(Syl(onset, "eo")) else mutableListOf(Syl(onset, "e"), Syl("", "o", closing))

    private fun koNucleus(onset: String, vowel: String, closing: String, flags: MutableList<String>, initial: Boolean, beforeU: Boolean): List<Syl>? {
        if (vowel in KO_RARE) flags.add("open:ko_rare_vowels")
        if (vowel == "yae") return null
        var pieces: MutableList<Syl>
        var closing = closing
        when {
            vowel == "ya" || vowel == "yo" || vowel == "yu" -> { // y + nguyên âm -> gi (chủ sách 04-10: Yoon -> Giun); sau phụ âm tách i- (Hyung -> Hi-ung)
                val letter = when (vowel) { "ya" -> "a"; "yo" -> "ô"; else -> "u" }
                pieces = if (onset.isEmpty()) mutableListOf(Syl("gi", letter)) else mutableListOf(Syl(onset, "i"), Syl("", letter))
            }
            vowel == "yeo" -> {
                flags.add("analogy:ko_yeo")
                // đầu từ gi + eo (Yeon -> Gie-on); sau phụ âm y MẤT, eo như thường (chủ sách 04-10: Gyeong -> Ghe-ong, Pyeong -> Pe-ong); g + y đọc g (ghe)
                pieces = if (onset.isEmpty()) koEo("gi", closing) else koEo(if (onset == "K") "G" else onset, closing)
                closing = ""
            }
            vowel == "eo" && closing.isEmpty() && beforeU -> { // eo mở trước âm tiết u gộp thành e (chủ sách 04-10: Seoul -> Xe-un)
                flags.add("analogy:ko_eo_u")
                pieces = mutableListOf(Syl(onset, "e"))
            }
            vowel == "eo" -> {
                pieces = koEo(onset, closing)
                closing = ""
            }
            vowel == "ye" -> {
                flags.add("analogy:ko_ye")
                pieces = mutableListOf(
                    when {
                        onset == "K" || onset == "G" -> Syl("G", "i") // gye -> ghi (chủ sách 04-10: Cheonggyecheon -> Che-ong-ghi-che-on)
                        onset.isNotEmpty() -> Syl(onset, "ê")
                        else -> Syl("gi", "ê")
                    },
                )
            }
            vowel == "wo" && onset.isEmpty() -> { // w đầu từ -> gu (Won -> Guôn); giữa từ (Suwon) theo analogy
                if (!initial) flags.add("analogy:ko_w_gu")
                pieces = mutableListOf(Syl("gu", "ô"))
            }
            else -> {
                var nucleus = KO_VOWEL.getValue(vowel)
                if (nucleus == "a" && (closing == "c" || closing == "t" || closing == "p")) nucleus = "ă"
                pieces = mutableListOf(Syl(onset, nucleus))
            }
        }
        if (closing.isNotEmpty()) {
            if (pieces.size == 2) {
                pieces[1].coda = closing
            } else {
                val tail = pieces.map { Syl(it.onset, it.nucleus) }.toMutableList()
                if (!close(tail, closing)) return null
                pieces = tail
            }
        }
        return pieces
    }

    private fun koWords(segments: List<String>, flags: MutableList<String>): List<List<Syl>>? {
        val out = ArrayList<List<Syl>>()
        var previous: String? = null
        for (segment in segments) {
            val parse = koBest(segment) ?: return null
            val syllables = ArrayList<Syl>()
            for ((position, entry) in parse.withIndex()) {
                val (onset, vowel, coda) = entry
                val next = parse.getOrNull(position + 1)
                val vietOnset = koOnset(onset, previous, flags)
                val part = koNucleus(vietOnset, vowel, KO_CODA_VIET.getValue(coda), flags, previous == null, next != null && next.first.isEmpty() && next.second == "u") ?: return null
                syllables.addAll(part)
                previous = coda
            }
            out.add(syllables)
        }
        return out
    }

    // ---- cửa vào -----------------------------------------------------------------------------------------------------

    internal val JA_SUFFIXES = setOf("san", "kun", "chan", "sama", "senpai", "sensei", "dono", "tan", "nee", "nii")

    private fun isAsciiLetter(ch: Char): Boolean = ch in 'a'..'z' || ch in 'A'..'Z' || ch == 'ô' || ch == 'Ô' // ô, Ô: ō của tiếng Nhật sau khi đổi

    /** true nếu viết hoa chữ đầu, false nếu toàn chữ thường, null nếu không phải chữ hay viết hoa lạ. */
    private fun partCase(part: String): Boolean? {
        val letters = part.replace("'", "")
        if (letters.isEmpty() || !letters.all { isAsciiLetter(it) } || part.startsWith("'") || part.endsWith("'")) return null
        if (part == part.lowercase(Locale.ROOT)) return false
        if ((part[0] in 'A'..'Z' || part[0] == 'Ô') && part.substring(1) == part.substring(1).lowercase(Locale.ROOT)) return true
        return null
    }

    private fun read(token: String, origin: String): Reading? {
        var value = Normalizer.normalize(BookEdits.pyStrip(token), Normalizer.Form.NFC).replace('’', '\'')
        val longMap = if (origin == "ja") LONG_VOWELS + JA_LONG_O else LONG_VOWELS
        value = value.map { longMap[it] ?: it }.joinToString("")
        if (value.isEmpty() || !value.all { isAsciiLetter(it) || it == '\'' || it == '-' || it == ' ' }) return null
        val flags = ArrayList<String>()
        val words = ArrayList<String>()
        for (word in value.split(' ').filter { it.isNotEmpty() }) {
            val segments = word.split('-')
            val cases = segments.map { partCase(it) }
            if (cases.any { it == null }) return null
            val lowered = segments.map { it.lowercase(Locale.ROOT) }
            val readings: List<List<Syl>>
            if (origin == "ja") {
                val list = ArrayList<List<Syl>>()
                for (segment in lowered) {
                    val syllables = jaWord(segment, flags)
                    if (syllables.isNullOrEmpty()) return null
                    list.add(syllables)
                }
                readings = list
            } else {
                if (lowered.any { "'" in it }) return null
                readings = koWords(lowered, flags) ?: return null
            }
            readings.forEachIndexed { index, syllables ->
                // hậu tố gọi (-kun) giữ chữ thường và nối gạch vào tên thành một chuỗi (chủ sách 04-10: Haruto-kun -> Ha-ru-tô-cun)
                // tên Hàn nối gạch cũng thành một chuỗi (chủ sách 04-10: Kim Jong-un -> Kim Giông-un)
                val suffix = index > 0 && (origin == "ko" || (origin == "ja" && lowered[index] in JA_SUFFIXES))
                val reading = validated(syllables, !suffix && cases[0] == true) ?: return null
                if (suffix) words[words.size - 1] = words.last() + "-" + reading else words.add(reading)
            }
        }
        if (words.isEmpty()) return null
        return Reading(words.joinToString(" "), flags.distinct())
    }

    /** Cách đọc và cờ, hay null khi không chắc. `origin` "ja" / "ko" do cuốn sách cho biết; không biết gốc thì không đoán. */
    fun readingWithFlags(token: String, origin: String?): Reading? = if (origin == "ja" || origin == "ko") read(token, origin) else null

    /** Cách đọc nối gạch của một tên romaji Nhật / phiên âm Latinh Hàn (các bộ phận cách nhau dấu cách, hậu tố nối gạch), hay null khi không chắc. */
    fun reading(token: String, origin: String?): String? = readingWithFlags(token, origin)?.text
}
