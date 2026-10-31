package vn.abook.player.ui.components

/**
 * Địa chỉ web trong câu chữ giữ NGUYÊN MỘT KHỐI khi xuống dòng: chèn U+2060 (nối từ, không rộng, không vẽ) sau mỗi "/" nên địa chỉ không tách đôi giữa đường dẫn
 * ("github.com/" ở dòng này, "ntanhpro1221/ABook" ở dòng sau - soát điện thoại 30-10) mà cả khối xuống dòng sau. Chỉ khi cả địa chỉ rộng hơn dòng thì máy mới buộc phải ngắt
 * (ở chữ, không có dấu "/" nào để ngắt nữa). Dùng cho chữ do mình soạn; mọi nơi có địa chỉ trong chữ giao diện qua đây ([TextWrapRulesTest] quét).
 */
fun keepUrlTogether(text: String): String = urlToken.replace(text) { it.value.replace("/", "/\u2060") }

private val urlToken = Regex("""(?:https?://)?[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+/[^\s]*""")

/**
 * Dòng cuối chỉ có MỘT chữ (không nối được vào dòng trên): "giờ" lẻ ở "Ngô Tất Tố · 12 chương · 2 giờ", "vai." lẻ ở câu trống. Hàm thuần cho máy dò đặt trên bố cục
 * đã đo: `lines` là chữ của từng dòng; chữ nối bằng NBSP (U+00A0) vẫn tính là hai chữ ("2 giờ" đủ cặp).
 */
fun hasOrphanLastLine(lines: List<String>): Boolean {
    if (lines.size < 2) return false
    val words = lines.last().trim().split(Regex("""[\s\u00A0]+""")).filter { it.isNotEmpty() }
    return words.size == 1
}

/**
 * Số và đơn vị đi liền nhau khi xuống dòng ("12 chương", "2 giờ 5 phút"): thay khoảng trắng giữa số và chữ đơn vị bằng NBSP (U+00A0), nên dòng không bao giờ kết thúc bằng "12"
 * rồi "chương" xuống dòng sau. Chỉ để vẽ - chữ so với web vẫn là chữ gốc.
 */
fun keepUnitsTogether(text: String): String = unitToken.replace(text) { "${it.groupValues[1]}\u00A0${it.groupValues[2]}" }

private const val UNITS = "chương|giờ|phút|giây|tập|cuốn|vai|KB|MB|GB"

private val unitToken = Regex("""(\d) ($UNITS)(?!\p{L})""")

/**
 * Dấu ngăn ("·", "-", "–", "|", "/") đứng giữa hai khoảng trắng: không bao giờ ở ĐẦU dòng (soát 31-10: "· 0 chương", "- bản dịch" mở dòng sau; "Tác giả 1 ·" cuối dòng
 * trước). Khoảng trắng TRƯỚC dấu thành NBSP nên dấu dính vào chữ đứng trước; nếu chỗ ngắt đẹp nhất vẫn rơi sau dấu thì dấu ở CUỐI dòng và [separatorsAtLineEnd] báo để vẽ
 * trong suốt (chỉ để vẽ - chữ vẫn nguyên, bố cục không đổi).
 */
fun tieSeparators(text: String): String = if (text.indexOf(' ') < 0) text else separatorToken.replace(text, "\u00A0")

private val separatorToken = Regex("""(?<=\S) (?=[·\-–|/](?: |$))""")

/** Các ký tự dấu ngăn đứng riêng (bị khoảng trắng hai bên, hoặc đầu/cuối chuỗi, kẹp lại). */
private const val SEPARATORS = "·-–|/"

/** Có dấu ngăn đứng riêng nào trong chữ không (để chỉ những chữ đó mới phải theo dõi bố cục dòng). */
fun hasSeparator(text: String): Boolean {
    for (i in text.indices) if (text[i] in SEPARATORS && isStandalone(text, i)) return true
    return false
}

private fun isBlank(c: Char) = c == ' ' || c == '\u00A0'

private fun isStandalone(text: String, i: Int): Boolean {
    val before = i == 0 || isBlank(text[i - 1])
    val after = i == text.lastIndex || isBlank(text[i + 1])
    return before && after
}

/**
 * Vị trí các dấu ngăn nằm ở cuối dòng (trừ dòng cuối): `lineEnds` là offset kết thúc của từng dòng trong `text`. Dấu ở đó phải được vẽ trong suốt.
 */
fun separatorsAtLineEnd(text: String, lineEnds: List<Int>): List<Int> {
    val hidden = ArrayList<Int>()
    for (k in 0 until lineEnds.size - 1) {
        var end = minOf(lineEnds[k], text.length)
        while (end > 0 && isBlank(text[end - 1])) end--
        val i = end - 1
        if (i >= 0 && text[i] in SEPARATORS && isStandalone(text, i)) hidden += i
    }
    return hidden
}

/**
 * Chữ + số ngắn đi liền nhau khi xuống dòng ("số 1", "Tập 2", "Chương 12"): khoảng trắng giữa chữ và số 1-3 chữ số thành NBSP, nên dòng không kết thúc bằng "số" rồi "1" xuống dòng
 * sau. Không đụng giờ ("1:40"), số thập phân ("2,0") hay số lớn. Chỉ để vẽ - chữ trong cây trợ năng vẫn là chữ gốc ([BasicText]).
 */
fun keepNumbersTogether(text: String): String = if (text.none { it.isDigit() }) text else numberToken.replace(text) { "${it.groupValues[1]}\u00A0${it.groupValues[2]}" }

// Số đứng trước đơn vị ("chiếm 12 MB") thì để số đi với đơn vị của nó ([keepUnitsTogether]) chứ không kéo thêm chữ phía trước: ngắt trước "12 MB" tốt hơn ngắt giữa "12" và "MB".
private val numberToken = Regex("""(\p{L}) (\d{1,3})(?!\d|[:.,]\d|[ \u00A0](?:$UNITS)(?!\p{L}))""")

/** Các luật xuống dòng (số đi liền đơn vị, số ngắn đi liền chữ, dấu ngăn không đầu dòng) trong một bước: chữ mọi nơi trong app qua đây ([BasicText]). */
fun shapeForWrap(text: String): String = tieSeparators(keepNumbersTogether(keepUnitsTogether(text)))
