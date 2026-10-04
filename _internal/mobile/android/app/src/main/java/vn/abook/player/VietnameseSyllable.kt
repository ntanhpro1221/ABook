package vn.abook.player

import java.text.Normalizer
import java.util.Locale

/**
 * Bộ kiểm một âm tiết tiếng Việt viết đúng chính tả: phụ âm đầu + vần + thanh. Bản Kotlin y hệt `abook/vietnamese_syllable.py`
 * (chặt hơn `analysis._valid_vietnamese_spoken_form`: chính tả g/gh, vần khép p / t / c / ch chỉ đi với thanh sắc hay nặng, vần không
 * có trong tiếng Việt). Dùng cho mọi đường ĐỌC TÊN do máy sinh ra (Romanization, EnglishVi); cách đọc người nghe tự gõ vẫn qua
 * `VietnameseReading.validSpokenForm`, rộng tay hơn như bản Python. Bộ ví dụ dùng chung: tests/fixtures/vietnamese_syllable/cases.json
 * (đổi một bên là phải đổi cả hai).
 */
object VietnameseSyllable {
    // dài trước ngắn
    private val ONSETS = listOf(
        "ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "th", "tr", "qu", "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x", "",
    )

    private fun words(spec: String): Set<String> = spec.split(" ").toSet()

    private val SIMPLE = words("a ă â e ê i y o ô ơ u ư")
    private val DIPHTHONG = words("ia iê yê uyê ua uô ưa ươ oa oă oe uê uâ uy uơ oo")
    private val GLIDE_END = words("ai ao au ay âu ây eo êu iu oi ôi ơi ui ưi ưu iêu yêu uôi ươi ươu oai oay oeo oao uây uyu uya")
    private val NUCLEI = SIMPLE + DIPHTHONG + GLIDE_END

    // Nhân phải có phụ âm cuối mới thành âm tiết.
    private val NEEDS_CODA = words("ă â iê yê uô ươ uâ oă oo uyê")

    // Vần khép: phụ âm cuối -> nhân đi được với nó.
    private val CODA_NUCLEI: Map<String, Set<String>> = mapOf(
        "c" to words("a ă â o ô u ư e iê uô ươ oa oă oe oo"),
        "ch" to words("a ê i oa uê uy"),
        "m" to words("a ă â e ê i o ô ơ u ư iê yê uô ươ oa oă"),
        "n" to words("a ă â e ê i o ô ơ u ư iê yê uô ươ oa oă oe uâ uyê"),
        "ng" to words("a ă â e o ô u ư iê uô ươ oa oă uâ oo"),
        "nh" to words("a ê i oa uê uy y"),
        "p" to words("a ă â e ê i o ô ơ u iê ươ"),
        "t" to words("a ă â e ê i y o ô ơ u ư iê yê uô ươ oa oă oe uâ uyê uy"),
    )
    private val CODAS = listOf("", "c", "ch", "m", "n", "ng", "nh", "p", "t")
    private val CLOSED_TONES = setOf("c", "ch", "p", "t") // chỉ thanh sắc hay nặng
    private val FRONT = setOf('e', 'ê', 'i', 'y')
    private const val VOWELS = "aeiouy"

    private val TONES = mapOf(0x300 to "f", 0x301 to "s", 0x309 to "r", 0x303 to "x", 0x323 to "j")
    private val KEEP = setOf(0x306, 0x302, 0x31B) // ă â ê ô ơ ư
    private val SEPARATORS = Regex("[ -]")

    /** (chữ thường không thanh, thanh) hay null khi có dấu lạ, hai thanh hay thanh đặt trên phụ âm. */
    private fun strip(syllable: String): Pair<String, String>? {
        var tone = ""
        var base = ' '
        val out = StringBuilder()
        for (ch in Normalizer.normalize(syllable.lowercase(Locale.ROOT), Normalizer.Form.NFD)) {
            val code = ch.code
            if (code in 0x300..0x36F) {
                val mark = TONES[code]
                if (mark != null) {
                    if (tone.isNotEmpty() || base !in VOWELS) return null
                    tone = mark
                } else if (code !in KEEP) {
                    return null
                } else {
                    out.append(ch)
                }
            } else {
                out.append(ch)
                base = ch
            }
        }
        return Pair(Normalizer.normalize(out.toString(), Normalizer.Form.NFC), tone)
    }

    private fun rhymeOk(onset: String, rest: String, tone: String, giAbsorbed: Boolean = false): Boolean {
        for (coda in CODAS) {
            val nucleus: String
            if (coda.isNotEmpty()) {
                if (!rest.endsWith(coda)) continue
                nucleus = rest.dropLast(coda.length)
            } else {
                nucleus = rest
            }
            if (nucleus !in NUCLEI) continue
            val first = nucleus[0]
            val front = first in FRONT
            if ((onset == "c" && front) || (onset == "k" && !front)) continue
            if (onset == "g" && front && !giAbsorbed) continue // g + e, ê, i viết gh (gi: i đã nằm trong chữ gi)
            if ((onset == "gh" || onset == "ngh") && !front || onset == "ng" && front) continue
            if (onset == "qu" && (first == 'u' || first == 'o')) continue
            if (onset == "gi" && (first == 'i' || first == 'y')) continue // gi + i viết gi
            if ((nucleus == "yê" || nucleus == "yêu") && onset != "" && onset != "qu") continue // yên, yêu, quyên
            if (coda.isEmpty()) {
                if (nucleus in NEEDS_CODA) continue
            } else {
                if (nucleus in GLIDE_END) continue
                if (nucleus !in CODA_NUCLEI.getValue(coda)) continue
                if (nucleus == "y" && onset != "qu") continue
                if (coda in CLOSED_TONES && tone != "s" && tone != "j") continue
            }
            return true
        }
        return false
    }

    /** Một âm tiết (không dấu cách, không gạch nối), hoa hay thường, có thanh hay không. */
    fun validSyllable(syllable: String): Boolean {
        val composed = Normalizer.normalize(syllable, Normalizer.Form.NFC)
        if (composed.isEmpty() || composed.length > 8) return false
        val (text, tone) = strip(composed) ?: return false
        if (text.isEmpty() || !text.all { it.isLetter() }) return false
        // g + âm đệm u trước y: guy, guyu, guyn (chủ sách 04-10: Will, wind); "guy" vào vần như i, nên chỉ nhận những vần i nhận
        if (text.startsWith("guy") && rhymeOk("g", "i" + text.substring(3), tone, giAbsorbed = true)) return true
        for (onset in ONSETS) {
            if (!text.startsWith(onset)) continue
            val rest = text.substring(onset.length)
            if (rest.isEmpty()) {
                if (onset == "gi") return true // gì, gí
                continue
            }
            if (rhymeOk(onset, rest, tone)) return true
            if (onset == "gi" && rhymeOk("g", "i$rest", tone, giAbsorbed = true)) return true // gin, giêng = g + iê + ng
        }
        return false
    }

    /** Cả cách đọc: mọi âm tiết (tách bằng dấu cách hay gạch nối) phải hợp lệ; rỗng hay có đoạn rỗng là không. */
    fun validSpokenForm(text: String): Boolean {
        val pieces = SEPARATORS.split(VietnameseReading.words(text).joinToString(" "))
        return pieces.isNotEmpty() && pieces.all { validSyllable(it) }
    }
}
