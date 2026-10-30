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

private val unitToken = Regex("""(\d) (chương|giờ|phút|giây|tập|cuốn|vai|KB|MB|GB)(?!\p{L})""")
