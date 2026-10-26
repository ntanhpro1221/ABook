package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import java.util.Locale

/**
 * Bìa tự sinh cho sách không có ảnh (viết lại từ ui/src/shared/cover.ts): mỗi cuốn nhận một cặp màu cố định băm từ tên - cùng tên, cùng bìa,
 * mọi lần mở. Các tông đá quý đậm, đủ tương phản với chữ trắng ở mọi cặp. Màu là ARGB để hàm thuần (Compose đổi sang Color ở nơi vẽ).
 */
@Immutable
class CoverStyle(val from: Int, val to: Int, val ink: Int, val seed: Long) {
    /** Các vòng cung mờ vẽ từ góc dưới phải (seed lẻ) hay trái (seed chẵn). */
    val arcsFromRight: Boolean get() = seed % 2L == 1L
}

object CoverArt {
    private val palettes = arrayOf(
        intArrayOf(0xFF1F3B57.toInt(), 0xFF0F1F30.toInt(), 0xFFF2A93F.toInt()),
        intArrayOf(0xFF4A2345.toInt(), 0xFF241124.toInt(), 0xFFF7B9C4.toInt()),
        intArrayOf(0xFF1D4A43.toInt(), 0xFF0D2622.toInt(), 0xFF8FE0C6.toInt()),
        intArrayOf(0xFF50301C.toInt(), 0xFF28170C.toInt(), 0xFFF2C078.toInt()),
        intArrayOf(0xFF2D2F5C.toInt(), 0xFF15162E.toInt(), 0xFFB7B9FF.toInt()),
        intArrayOf(0xFF5A2626.toInt(), 0xFF2D1111.toInt(), 0xFFFFB199.toInt()),
        intArrayOf(0xFF1F4D2C.toInt(), 0xFF0E2615.toInt(), 0xFFB8E986.toInt()),
        intArrayOf(0xFF3D3D46.toInt(), 0xFF1B1B20.toInt(), 0xFFE8D5A3.toInt()),
        intArrayOf(0xFF123F5C.toInt(), 0xFF081F2E.toInt(), 0xFF7FD1FF.toInt()),
        intArrayOf(0xFF4B3A14.toInt(), 0xFF241B07.toInt(), 0xFFFFD76A.toInt()),
    )

    /** FNV-1a 32 bit trên các đơn vị UTF-16 của tên (đúng `hash` của cover.ts: `charCodeAt`, `Math.imul`, `>>> 0`). */
    internal fun hash(text: String): Long {
        var value = 0x811C9DC5.toInt()
        for (c in text) {
            value = value xor c.code
            value *= 16777619
        }
        return value.toLong() and 0xFFFFFFFFL
    }

    fun style(title: String): CoverStyle {
        val seed = hash(title.trim().lowercase(Locale.ROOT))
        val p = palettes[(seed % palettes.size).toInt()]
        return CoverStyle(p[0], p[1], p[2], seed)
    }

    private val splitPattern = Regex("""^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(.+)$""", RegexOption.IGNORE_CASE)

    /** Tên sách tách phần chính và phần phụ ("Throne of Magical Arcana · Tập 16" -> "Throne of Magical Arcana", "Tập 16"). `part` > 1: "Phần N". */
    fun splitTitle(title: String, part: Int? = null): Pair<String, String> {
        splitPattern.find(title)?.let { return it.groupValues[1].trim() to "${it.groupValues[2]} ${it.groupValues[3]}".trim() }
        if (part != null && part > 1) return title.trim() to "Phần $part"
        return title.trim() to ""
    }

    private val stopWords = setOf("the", "and", "của", "và", "những", "các", "một")

    /** Chữ trên bìa nhỏ: số tập nếu là sách trong một bộ ("16"), không thì hai chữ cái đầu. */
    fun label(title: String, part: Int? = null): String {
        val (main, sub) = splitTitle(title, part)
        Regex("""(\d+)""").find(sub)?.let { return it.groupValues[1] }
        return main.split(Regex("""\s+""")).filter { it.length > 2 && it.lowercase(Locale.ROOT) !in stopWords }
            .take(2).joinToString("") { it.take(1).uppercase(Locale.ROOT) }
    }
}
