package vn.abook.player.readaloud

import java.text.Normalizer
import java.util.Locale
import vn.abook.player.BookEdits
import vn.abook.player.VietnameseSyllable

/**
 * Đọc romaji Nhật (Hepburn) và phiên âm Latinh Hàn (RR) thành âm tiết tiếng Việt, theo docs/READING_FOREIGN_NAMES.md mục 1-3 - bản Kotlin
 * y hệt `abook/romanization.py` (cùng đọc tests/fixtures/romanization/cases.json, sinh bằng scripts/build_romanization_fixture.py: đổi một
 * bên là phải đổi cả hai). Mỗi âm tiết đầu ra phải qua phép kiểm âm tiết `VietnameseSyllable` (bản `vietnamese_syllable.py`).
 * CHƯA nối vào đường đọc.
 *
 * Ba loại cờ: `open:` quy ước ghi "mở", đây là mặc định chờ kiểm bằng âm thanh (OPEN_CHOICES); `analogy:` quy ước không nói, suy theo hàng
 * gần nhất; `fit:` quy ước chọn dạng mà bộ kiểm âm tiết không nhận, nên dùng dạng khác cũng có nguồn. Thêm `keep:` cho đoạn giữ nguyên chữ (viet / abbr / english) trong token nối
 * gạch (Gấu-san, PD-nim, Ikemen-style); tiền xử lý (TOÀN HOA, CamelCase, gạch nối, cách viết quen của tên Hàn) mô tả ở đầu `abook/romanization.py`.
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
        if (pieces.isEmpty() || pieces.any { !VietnameseSyllable.validSpokenForm(it) }) return null
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
        "onigiri" to listOf(Triple("", "o", ""), Triple("n", "i", ""), Triple("gi", "i", ""), Triple("r", "i", "")),
        // chwan: cách viết nũng của -chan (Tenshi-chwan); w giữa ch và a là bán âm oa (analogy theo wa -> oa), khép n
        "chwan" to listOf(Triple("ch", "oa", "n")),
    )

    private fun jaWord(word: String, flags: MutableList<String>): List<Syl>? {
        JA_FIXED[word]?.let { fixed -> return fixed.map { (onset, nucleus, coda) -> Syl(onset, nucleus, coda) } }
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

    private val KO_SILENT_H = Regex("ah(?![aeiouy])")

    /**
     * Đổi cách viết Latinh quen dùng của tên Hàn về RR trước khi tách: nguyên cả đoạn (KO_SPELLINGS), rồi từng chỗ (sh -> s, oo -> u, woo -> u, yoo -> yu: Shin, Joo, Hoon, Ji-woo;
     * weo -> wo: Weol; ah -> a khi h không đứng trước nguyên âm: Ahn, Ahri, Seol-Ah). sh và oo là quyết định của lead (04-10, bộ đo luật); weo và ah là analogy.
     */
    private fun koSpelling(raw: String, flags: MutableList<String>): String {
        KO_SPELLINGS[raw]?.let { return it }
        var word = raw.replace("sh", "s").replace("woo", "u").replace("yoo", "yu").replace("oo", "u")
        if ("weo" in word) {
            flags.add("analogy:ko_weo")
            word = word.replace("weo", "wo")
        }
        if (KO_SILENT_H.containsMatchIn(word)) {
            flags.add("analogy:ko_ah")
            word = KO_SILENT_H.replace(word, "a")
        }
        return word
    }

    private fun koBest(raw: String, flags: MutableList<String>): List<Triple<String, String, String>>? {
        val word = koSpelling(raw, flags)
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
                    // n + y: Jin-yun / Ji-nyun cũng viết giống nhau (Jinyoon), RR chỉ phân bằng dấu gạch
                    if (chosen[k].third == "" && chosen[k + 1].first == "n" && chosen[k + 1].second.startsWith("y") && parse[k].third == "n") return null
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

    /**
     * Các đoạn nối gạch của một tên Hàn (Geun-hye): cùng một từ về âm (g, d, b hữu thanh sau n, m, ng ngay cả qua dấu gạch), nhưng mỗi đoạn một bộ phận.
     * Đoạn null là chữ giữ nguyên (PD, Hoẵng): cho bộ phận rỗng và cắt mạch âm (đoạn sau lại là đầu từ).
     */
    private fun koWords(segments: List<String?>, flags: MutableList<String>): List<List<Syl>>? {
        val out = ArrayList<List<Syl>>()
        var previous: String? = null
        for (segment in segments) {
            if (segment == null) {
                out.add(emptyList())
                previous = null
                continue
            }
            val parse = koBest(segment, flags) ?: return null
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

    internal val JA_SUFFIXES = setOf("san", "kun", "chan", "chwan", "sama", "senpai", "sensei", "dono", "tan", "nee", "nii")
    private const val ABBREVIATION_MAX = 4 // chữ TOÀN HOA dài nhất mà còn coi là viết tắt (PD, NPC) khi giữ nguyên
    private const val ENGLISH_MIN = 4 // chữ Anh ngắn hơn thế (Si, Man, ram) dễ là âm tiết của tên Nhật / Hàn: không giữ

    private fun isAsciiLetter(ch: Char): Boolean = ch in 'a'..'z' || ch in 'A'..'Z' || ch == 'ô' || ch == 'Ô' // ô, Ô: ō của tiếng Nhật sau khi đổi

    /** Một đoạn của token (giữa hai dấu gạch, hay một nửa của CamelCase): đọc theo luật (kind "read") hay giữ nguyên chữ ("keep:..."). */
    private class Piece(val text: String, val norm: String, val case: Boolean, val kind: String) {
        var join = "new" // "new" tách bằng dấu cách; "hyphen" sau dấu gạch; "camel" sau chỗ tách CamelCase
        var syllables: List<Syl> = emptyList()
    }

    /** lower (không chữ hoa), title (chỉ chữ đầu hoa), upper (toàn hoa, từ hai chữ), mixed (CamelCase hay hoa lạ). */
    private fun shape(letters: String): String {
        if (letters == letters.lowercase(Locale.ROOT)) return "lower"
        if (letters[0].isUpperCase() && letters.substring(1) == letters.substring(1).lowercase(Locale.ROOT)) return "title"
        if (letters.length >= 2 && letters == letters.uppercase(Locale.ROOT)) return "upper"
        return "mixed"
    }

    /** Tách ở chữ hoa đứng sau chữ thường (OkabeRintarou -> Okabe, Rintarou) hay chữ hoa cuối chuỗi hoa mà liền sau là chữ thường (HImeno -> H, Imeno). */
    private fun splitCamel(segment: String): List<String> {
        val parts = ArrayList<String>()
        var start = 0
        for (i in 1 until segment.length) {
            val after = if (i + 1 < segment.length) segment[i + 1] else null
            if (segment[i].isUpperCase() && (segment[i - 1].isLowerCase() || (segment[i - 1].isUpperCase() && after != null && after.isLowerCase()))) {
                parts.add(segment.substring(start, i))
                start = i
            }
        }
        parts.add(segment.substring(start))
        return parts
    }

    private fun isLatinLetter(ch: Char): Boolean = ch.isLetter() && Character.UnicodeScript.of(ch.code) == Character.UnicodeScript.LATIN

    /**
     * Chữ Việt giữ nguyên chữ (Vương-sama, Gấu-san): có chữ Latin mang dấu mà KHÔNG là dấu nguyên âm dài của romaji (â ê ô û...: "Công", "Tây" cũng là chữ Việt, nhưng đường quét tên cho
     * qua chúng như tên có dấu dài). Âm tiết Việt viết không dấu (Khoan, Seo) cũng KHÔNG tính: nhiều tên romaji / RR (Si-eun, Seo-ram) là âm tiết Việt hợp lệ.
     */
    private fun isVietnamese(text: String): Boolean =
        text.all { it == '\'' || isLatinLetter(it) } && text.any { it.code > 127 && it !in LONG_VOWELS && it !in JA_LONG_O }

    /** Đoạn (đã thường hoá, đã đổi nguyên âm dài) tách hết được thành âm tiết của hệ `origin` không; chỉ để thử, bỏ cờ. */
    private fun reads(norm: String, origin: String): Boolean =
        if (origin == "ja") !jaWord(norm, ArrayList()).isNullOrEmpty() else "'" !in norm && koWords(listOf(norm), ArrayList()) != null

    private fun makePiece(text: String, case: Boolean, origin: String, allowEnglish: Boolean): Piece? {
        val longMap = if (origin == "ja") LONG_VOWELS + JA_LONG_O else LONG_VOWELS
        val mapped = text.map { longMap[it] ?: it }.joinToString("")
        if (mapped.all { isAsciiLetter(it) || it == '\'' } && reads(mapped.lowercase(Locale.ROOT), origin)) return Piece(text, mapped.lowercase(Locale.ROOT), case, "read")
        if (isVietnamese(text)) return Piece(text, "", case, "keep:viet")
        if (allowEnglish && text.all { it in 'a'..'z' || it in 'A'..'Z' }) {
            if (text.all { it.isUpperCase() } && text.length in 2..ABBREVIATION_MAX) return Piece(text, "", case, "keep:abbr") // PD: viết tắt, việc của luật chữ viết tắt
            // style, Stable: việc của đường đọc từ Anh. Chữ ngắn (Si, ram) và chữ mà hệ kia đọc được (Young, Soon) không tính là chữ Anh: giữ nguyên chúng sẽ làm tên Hàn / Nhật
            // nối gạch thành "tên đọc được" của hệ sai khi quét gốc cuốn
            val lowered = text.lowercase(Locale.ROOT)
            if (text.length >= ENGLISH_MIN && lowered in EnglishWords.ALL && !reads(lowered, if (origin == "ja") "ko" else "ja")) return Piece(text, "", case, "keep:english")
        }
        return null
    }

    /** Một đoạn giữa hai dấu gạch -> các đoạn nhỏ: một (thường, Hoa đầu, TOÀN HOA casefold), hay nhiều khi là CamelCase. */
    private fun segmentPieces(segment: String, origin: String, allowEnglish: Boolean, flags: MutableList<String>): List<Piece>? {
        val letters = segment.replace("'", "")
        if (letters.isEmpty() || !letters.all { it.isLetter() } || segment.startsWith("'") || segment.endsWith("'")) return null
        if (shape(letters) != "mixed") return makePiece(segment, segment[0].isUpperCase(), origin, allowEnglish)?.let { listOf(it) }
        val parts = splitCamel(segment)
        if (parts.size >= 2 && parts.all { it.replace("'", "").length >= 2 }) {
            val pieces = parts.map { makePiece(it, it[0].isUpperCase(), origin, false) }
            if (pieces.all { it != null }) {
                flags.add("analogy:camel_split")
                return pieces.filterNotNull()
            }
        }
        // hoa lạ không tách được (HImeno): đọc như viết hoa chữ đầu
        val piece = makePiece(segment.lowercase(Locale.ROOT), segment[0].isUpperCase(), origin, false)
        if (piece == null || piece.kind != "read") return null
        flags.add("analogy:case_fold")
        return listOf(piece)
    }

    private fun wordPieces(word: String, origin: String, flags: MutableList<String>): List<Piece>? {
        val segments = word.split('-')
        val pieces = ArrayList<Piece>()
        for ((index, segment) in segments.withIndex()) {
            val found = segmentPieces(segment, origin, segments.size > 1, flags) ?: return null
            for ((sub, piece) in found.withIndex()) piece.join = if (sub > 0) "camel" else if (index == 0) "new" else "hyphen"
            pieces.addAll(found)
        }
        if (pieces.any { it.kind == "keep:english" }) {
            // chữ Anh đứng cạnh một đoạn mà chính nó cũng là chữ Anh (Spider-Man) là tên Tây, không phải tên romaji kèm chữ Anh (Ikemen-style)
            for (piece in pieces) if (piece.kind == "read" && piece.norm !in JA_SUFFIXES && piece.norm in EnglishWords.ALL) return null
        }
        return pieces
    }

    private fun read(token: String, origin: String): Reading? {
        val value = Normalizer.normalize(BookEdits.pyStrip(token), Normalizer.Form.NFC).replace('’', '\'')
        val flags = ArrayList<String>()
        val words = ArrayList<String>()
        var readAny = false // có ít nhất một đoạn đọc theo luật (toàn đoạn giữ nguyên thì không phải việc của luật này)
        for (word in value.split(' ').filter { it.isNotEmpty() }) {
            val pieces = wordPieces(word, origin, flags) ?: return null
            if (origin == "ja") {
                for (piece in pieces) if (piece.kind == "read") piece.syllables = jaWord(piece.norm, flags) ?: emptyList()
            } else {
                val readings = koWords(pieces.map { if (it.kind == "read") it.norm else null }, flags) ?: return null
                pieces.forEachIndexed { index, piece -> piece.syllables = readings[index] }
            }
            for ((index, piece) in pieces.withIndex()) {
                if (piece.kind != "read") flags.add(piece.kind)
                // nối vào từ trước bằng gạch (chain) hay mở từ mới. Hậu tố gọi (-san) nối gạch vào tên thành một chuỗi, chữ thường (chủ sách 04-10: Haruto-kun -> Ha-ru-tô-cun); tên Hàn
                // nối gạch cũng thành một chuỗi (Kim Jong-un -> Kim Giông-un); đoạn thường sau gạch (Kanata-cả, Ikemen-style) cũng nối; đoạn viết hoa sau gạch (Waseda-Keio) là từ mới.
                // CamelCase: hai nửa đều MỘT âm tiết (JoJo, ChuChu) là một tên lặp, nối gạch; còn lại cách nhau dấu cách
                val chain = when {
                    index == 0 || piece.join == "new" -> false
                    piece.join == "hyphen" -> origin == "ko" || !piece.case || (piece.kind == "read" && piece.norm in JA_SUFFIXES)
                    else -> piece.kind == "read" && piece.syllables.size == 1 && pieces[index - 1].kind == "read" && pieces[index - 1].syllables.size == 1
                }
                val reading = if (piece.kind == "read") {
                    (validated(piece.syllables, piece.case && !chain) ?: return null).also { readAny = true }
                } else {
                    piece.text
                }
                if (chain) words[words.size - 1] = words.last() + "-" + reading else words.add(reading)
            }
        }
        if (words.isEmpty() || !readAny) return null
        return Reading(words.joinToString(" "), flags.distinct())
    }

    /** Cách đọc và cờ, hay null khi không chắc. `origin` "ja" / "ko" do cuốn sách cho biết; không biết gốc thì không đoán. */
    fun readingWithFlags(token: String, origin: String?): Reading? = if (origin == "ja" || origin == "ko") read(token, origin) else null

    /** Cách đọc nối gạch của một tên romaji Nhật / phiên âm Latinh Hàn (các bộ phận cách nhau dấu cách, hậu tố nối gạch), hay null khi không chắc. */
    fun reading(token: String, origin: String?): String? = readingWithFlags(token, origin)?.text
}
