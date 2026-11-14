package vn.abook.player

import java.text.Normalizer
import java.util.regex.Pattern
import org.json.JSONObject

/** Display metadata only. The rules come from the same JSON as Python. */
internal object ChapterTitles {
    private val rules = JSONObject(BuildConfig.CHAPTER_TITLE_RULES)
    private fun pattern(key: String) = Pattern.compile(rules.getString(key), Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE)
    private val numbered = pattern("numbered")
    private val named = pattern("named")
    private val prose = pattern("prose")
    private val unsafe = pattern("unsafe")
    private val volume = pattern("volume")
    private val numeric = Regex("(?:\\p{Nd}+|chương\\s+\\p{Nd}+)", RegexOption.IGNORE_CASE)
    private fun clean(line: String) = Normalizer.normalize(line.trimStart('\uFEFF').trim().replace(Regex("[\\s\\p{Z}]+"), " "), Normalizer.Form.NFC)

    fun parts(line: String): Pair<String, String>? {
        val text = clean(line)
        if (text.isEmpty() || text.codePointCount(0, text.length) > rules.getInt("maxHeading")) return null
        val match = numbered.matcher(text).takeIf { it.matches() } ?: named.matcher(text).takeIf { it.matches() } ?: return null
        var name = match.group(1)!!
        if (match.groupCount() > 2 && match.group(3) != null) name += " " + match.group(3)
        return name.replaceFirstChar { it.uppercaseChar() } to (match.group(2) ?: "").trim()
    }

    fun firstHeading(text: String): String {
        val lines = text.replace("\r\n", "\n").replace('\r', '\n').split('\n')
        val at = lines.indexOfFirst { clean(it).isNotEmpty() }
        if (at < 0) return ""
        val first = clean(lines[at])
        if (volume.matcher(first).matches()) {
            val following = lines.drop(at + 1).firstOrNull { clean(it).isNotEmpty() }?.let(::clean).orEmpty()
            return if (parts(following) != null) following else ""
        }
        if (parts(first) != null) return first
        if (at + 1 >= lines.size || lines[at + 1].isNotBlank()) return ""
        if (first.codePointCount(0, first.length) > rules.getInt("maxStandalone") || first.split(' ').size !in rules.getInt("minWords")..rules.getInt("maxWords")) return ""
        if (!first[0].isUpperCase() || first[0] in "-–—('" || first.none { it.isLetter() }) return ""
        if (unsafe.matcher(first).find() || prose.matcher(first).find()) return ""
        return first
    }

    fun explicitHeading(text: String): String = firstHeading(text).takeIf { parts(it) != null }.orEmpty()

    private val order = Regex("^0\\p{Nd}*(?:\\s*[-_.:]+\\s*|\\s+)(\\S.*)$")
    private val numberOnly = Regex("(?:chương\\s+)?(\\p{Nd}+)", RegexOption.IGNORE_CASE)

    /** chapter_titles.file_number: "013", "Chương 13", "0013 - 13" -> 13; a real name -> null. */
    fun fileNumber(stored: String): Int? {
        val text = clean(stored).let { order.matchEntire(it)?.groupValues?.get(1) ?: it }
        return numberOnly.matchEntire(text)?.groupValues?.get(1)?.toIntOrNull()
    }

    /** Numeric file labels use book order. An actual source heading still wins. */
    fun fallbackPositions(stored: List<String>): List<Int?> {
        return stored.mapIndexed { index, title ->
            val text = clean(title).let { order.matchEntire(it)?.groupValues?.get(1) ?: it }
            if (text.isEmpty() || numberOnly.matches(text)) index + 1 else null
        }
    }

    fun display(stored: String, text: String, index: Int?): String {
        val heading = firstHeading(text)
        if (heading.isNotEmpty()) return heading
        val title = BookImport.chapterTitle(clean(stored))
        return if (index != null && (title.isEmpty() || numeric.matches(title))) BookImport.chapterTitle(index.toString()) else title
    }
}
