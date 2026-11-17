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
    private val structural = pattern("structural")
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

    /** chapter_titles.opening_line: (first non-empty line, an empty line follows it); a volume wrapper is skipped. */
    fun openingLine(text: String): Pair<String, Boolean> {
        val lines = text.replace("\r\n", "\n").replace('\r', '\n').split('\n')
        var at = lines.indexOfFirst { clean(it).isNotEmpty() }
        if (at < 0) return "" to false
        if (volume.matcher(clean(lines[at])).matches()) {
            at = (at + 1 until lines.size).firstOrNull { clean(lines[it]).isNotEmpty() } ?: return "" to false
        }
        return clean(lines[at]) to (at + 1 < lines.size && lines[at + 1].isBlank())
    }

    private fun endsLikeProse(line: String) = line.last() in ".,;:" || !line[0].isLetter() || !line[0].isUpperCase()

    /** chapter_titles.structural_parts: "Lần gặp thứ 92 - Lời hứa" -> ("lần gặp", "Lần gặp thứ 92", "Lời hứa"). */
    fun structuralParts(line: String): Triple<String, String, String>? {
        val text = clean(line)
        if (text.isEmpty() || text.codePointCount(0, text.length) > rules.getInt("maxHeading") || endsLikeProse(text)) return null
        val match = structural.matcher(text).takeIf { it.matches() } ?: return null
        val lead = match.group(2)!!
        if (!lead.split(' ').all { word -> word.any { it.isLetter() } }) return null
        return Triple(lead.lowercase(), match.group(1)!!, (match.group(3) ?: "").trim())
    }

    private fun looseHeading(line: String) = line.isNotEmpty() && line.codePointCount(0, line.length) <= rules.getInt("maxHeading") &&
        !endsLikeProse(line) && parts(line) == null && line[0] !in "-–—('\"“‘«"

    /** chapter_titles.book_headings: headings decided for the whole book. A repeated structure that opens most untitled
     *  chapters counts for all of them; a book never mixes real names with numbered fallbacks. */
    fun bookHeadings(texts: List<String>, stored: List<String>): List<String> {
        val base = texts.map(::firstHeading)
        val lines = texts.map(::openingLine)
        val open = texts.indices.filter { base[it].isEmpty() || parts(base[it]) == null }
        val keys = LinkedHashMap<String, Int>()
        for (at in open) {
            val (line, blank) = lines[at]
            val found = if (blank) structuralParts(line) else null
            if (found != null) keys[found.first] = (keys[found.first] ?: 0) + 1
        }
        val out = base.toMutableList()
        keys.entries.maxByOrNull { it.value }?.let { (key, count) ->
            if (count >= 2 && count * 2 > open.size) {
                for (at in open) {
                    val (line, blank) = lines[at]
                    if (blank && structuralParts(line)?.first == key) out[at] = line
                }
            }
        }
        val positions = fallbackPositions(stored)
        val titled = open.filter { out[it].isNotEmpty() }
        val untitled = open.filter { out[it].isEmpty() && positions[it] != null }
        if (titled.isNotEmpty() && untitled.isNotEmpty()) {
            if (titled.size > untitled.size) {
                for (at in untitled) {
                    val (line, blank) = lines[at]
                    if (blank && looseHeading(line)) out[at] = line
                }
            }
            if (untitled.any { out[it].isEmpty() }) for (at in titled) out[at] = ""
        }
        return out
    }

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

    /** chapter_titles.is_named_matter: the chapter's own heading names it as front/back matter or an extra ("Mở đầu"). */
    fun isNamedMatter(heading: String): Boolean = heading.isNotEmpty() && named.matcher(clean(heading)).matches()

    /** chapter_titles.fallback_numbers: book order counting only real chapters - "Mở đầu" takes no number. */
    fun fallbackNumbers(positions: List<Int?>, namedMatter: List<Boolean>): List<Int?> {
        var count = 0
        return positions.mapIndexed { index, position ->
            if (!namedMatter[index]) count++
            if (position == null || namedMatter[index]) null else count
        }
    }

    /** chapter_titles.distinct_fallbacks: a numbered fallback never repeats another chapter's name; it shows its file number,
     *  then its file label. Headed names never change. */
    fun distinctFallbacks(names: List<String>, fallback: List<Boolean>, stored: List<String>): List<String> {
        val out = names.toMutableList()
        for (at in out.indices) {
            if (!fallback[at]) continue
            val others = out.filterIndexed { other, _ -> other != at }.map { it.lowercase() }.toSet()
            if (out[at].lowercase() !in others) continue
            listOf(display(stored[at], "", null), clean(stored[at])).firstOrNull { it.isNotEmpty() && it.lowercase() !in others }?.let { out[at] = it }
        }
        return out
    }

    fun display(stored: String, text: String, index: Int?): String = displayHeading(stored, firstHeading(text), index)

    /** importers.display_chapter_name: `heading` as bookHeadings decided it ("" = none), else the file label or book position. */
    fun displayHeading(stored: String, heading: String, index: Int?): String {
        if (heading.isNotEmpty()) return heading
        val title = BookImport.chapterTitle(clean(stored))
        return if (index != null && (title.isEmpty() || numeric.matches(title))) BookImport.chapterTitle(index.toString()) else title
    }
}
