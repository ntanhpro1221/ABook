package vn.abook.player

import vn.abook.player.readaloud.Paragraphs

/** Một câu do bộ tách của chương trả ra (`text_processing.segment_chapter_text`): thứ tự, đoạn nguồn và cờ dòng ngăn cảnh đứng sau câu. */
class SegmentRow(val seq: Int, val paragraphIndex: Int, val text: String, var sceneBreak: Boolean = false)

/**
 * Bản Kotlin của bộ tách câu `text_processing.segment_chapter_text` (khoá, chỉ đọc) cho đường nhạc theo cảnh: điện thoại không có bộ tách nào khác, mà
 * ranh giới đoạn nhạc và thời lượng ước của đoạn tính trên ĐÚNG các câu ấy (độ dài từng câu, `max(0.3, ...)`, cờ ngăn cảnh), nên làm đúng từng chữ.
 * Chỉ giữ phần quyết định chữ của câu và cờ ngăn cảnh: nhãn lời kể / thoại / nội tâm chỉ dùng để gộp mảnh liền nhau (nên vẫn tính), quãng nghỉ
 * (`break_ms`), id ổn định và phép kiểm "không mất chữ" thì bỏ (chương nào Python từ chối thì ở đây cũng văng [IllegalStateException]).
 * Khoảng trắng / chữ / `\b` / `$` theo Python: mọi regex đi qua [Py.rx] (lớp ký tự viết rõ, không `(?U)` - xem ScenePy.kt).
 */
object SceneSegmenter {
    private const val MAX_CHARS = 340
    private val PARAGRAPH_SPLIT = Py.rx("""\n\s*\n""")
    private val NOTE_MARKER = Py.rx("""\[\s*note\d+\s*\]""", ignoreCase = true)
    private val SPACE_RUN = Regex("[ \t]+")
    private val LINE_INDENT = Regex("\n[ \t]+")
    private val NEWLINE_RUN = Regex("\n{3,}")

    private val QUOTE = Py.rx("""([“"][^”"]{1,1600}[”"])""", dotAll = true)
    private const val THOUGHT_CLOSING_SOURCE = """’|(?<=\S)'(?!\w)"""
    private val THOUGHT_CLOSING = Py.rx(THOUGHT_CLOSING_SOURCE)
    private val THOUGHT_QUOTE = Py.rx("(‘[^’]{1,1600}?(?:$THOUGHT_CLOSING_SOURCE))", dotAll = true)
    private val WHITE_CORNER_LINE = Py.rx("""『[^』]{1,1600}』""")
    private val LETTERED_VOICE_LINES = listOf(Py.rx("""\[[^\]]{1,1600}\]"""), Py.rx("""【[^】]{1,1600}】"""))
    private val TRANSLATOR_NOTE_LABEL = Py.rx(
        """^[\s*_~]*(?:lời\s+)?(?:t/n|n/t|n/a|tl[\s-]*note|tl|translator(?:'s)?[\s-]*note|trans(?:lator)?|editor|edit|note|nd|n\.d|""" +
            """người dịch|dịch giả|(?:ghi chú|chú thích)(?=\s+của\s+(?:dịch giả|người dịch|nhóm dịch))|nhóm dịch|raw|eng|""" +
            """bản\s+(?:jap|eng))""" +
            """(?:\s+của\s+(?:dịch giả|người dịch|nhóm dịch|editor))?(?:\s*\d+)?\s*(?:[:：]|[-–—](?=\s)|$)""",
        ignoreCase = true,
    )
    private val TRANSLATOR_SELF_REFERENCE = Py.rx(
        """\b(?:bọn mình|tụi mình|nhóm mình|mình)\b[^.!?]{0,80}?(?<!đại )(?<!ôn )\bd[ịi]ch\b(?!\s+(?:chuyển|vụ|bệnh|hạch|tễ))""",
        ignoreCase = true,
    )
    private val SENTENCE_BOUNDARY = Py.rx("""(?<=[.!?…;:])\s+""")
    private val SPEECH_VERB = Py.rx("""\b(?:nói|hỏi|đáp|trả lời|quát|hét|gào|thì thầm|lẩm bẩm|kêu|bảo|ra lệnh|cười)\b""", ignoreCase = true)
    private val DASH_LINE = Py.rx("""^[—–-]+\s*(?=\S)""")
    private val QUOTE_LED_LINE = Py.rx("""^[“"‘「『]""")
    private const val THIRD_PERSON_SOURCE = """(?:hắn|họ|gã|lão|(?:anh|cô|ông|bà|cậu|nàng|chàng)\s+(?:ta|ấy))"""
    private val THIRD_PERSON = Py.rx("""(?<!\w)$THIRD_PERSON_SOURCE(?!\w)""", ignoreCase = true)
    private val NARRATIVE_SUBJECT = Py.rx(
        """(?<!\w)(?:$THIRD_PERSON_SOURCE""" +
            """|(?!(?:Tôi|Mình|Ta|Chúng|Bọn|Cô|Nó|Anh|Em|Cậu|Ngài|Bạn|Người|Hãy|Đừng)(?!\w))[A-ZĐ]\w*(?:[\s-][A-ZĐ]\w*)*)""" +
            """\s+(?:đã|đang|vừa|liền|bèn)\s+\w""",
    )
    private val SPEECH_PRONOUN = Py.rx(
        """(?<!\w)(?:ta|ngươi|tớ|mày|tao|ngài|tui|mi|cậu|nàng|anh|em|con|tôi|mình|bạn|ông|bà|cháu|chị|chúng|bọn)(?!\w)""", ignoreCase = true,
    )
    private val SPEECH_ONLY_PRONOUN = Py.rx("""(?<!\w)(?:ta|ngươi|tớ|mày|tao|ngài|tui|mi)(?!\w)""", ignoreCase = true)
    private val SPEECH_MARK = Py.rx("""[?!~…*“”"‘’「」『』\[\]〔〕()]|\.\.""")
    private val SPEECH_FINAL_PARTICLE = Py.rx(
        """(?<!\w)(?:chăng|à|ư|nhỉ|hả|nhé|nha|chứ|vậy|đấy|đâu|nào|ạ|mà|rồi|sao|thôi)\W*$""", ignoreCase = true,
    )
    private val TERM_INTRODUCER = Py.rx("""\b(?:là|gọi|tên|chữ|từ|cụm|câu|hiệu|danh|như|kiểu|thành|mệnh danh|xưng)$""")
    private val DASH_LED_LINE_START = Py.rx("""^[—–-]\s*\S""")
    private val HEADING = Py.rx(
        """^\s*((?:chương|chapter|hồi|quyển|phần|tiết)\s*[\dIVXLC]+)\s*(?:[-:–—.·|]+\s*([^\n]*?))?\s*$""", ignoreCase = true,
    )

    private const val QUOTED_CHAPTER_MIN_QUOTE_LINES = 10
    private const val QUOTED_CHAPTER_MAX_DASH_LINES = 3
    private const val FRAMED_NAME_MAX_WORDS = 4
    private const val FRAMED_NAME_PUNCTUATION = ".!?…~,;"
    private val FRAMED_INTERJECTIONS: Set<String> = (
        "hmm hm hừm khụ ừ ừm ờ à á ồ ơ ê hả hử hừ hứ hì hehe haha hihi ối ui úi ây chậc chẹp xì phù hự oa wow " +
            "vâng dạ hế haiz haizz hây nhưng phải không được thôi"
        ).split(" ").toSet()

    private class State(val hint: String, val closing: String)
    private class Piece(val text: String, val hint: String)
    private class Span(val start: Int, val end: Int)
    private class Walk(val rows: List<SegmentRow>, val state: State?, val openedAt: Int?)

    /** `humanize.is_heading`: dòng tiêu đề "Chương 12 - ..." (tối đa 160 ký tự). */
    fun isHeading(text: String): Boolean = Py.len(text) <= 160 && Py.match(HEADING, text)

    /** `text_processing.normalize_text`. */
    fun normalizeText(raw: String): String {
        var text = raw.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
        for (zeroWidth in listOf("​", "‌", "‍", "⁠", "﻿")) text = text.replace(zeroWidth, "")
        text = text.replace('「', '“').replace('」', '”')
        text = NOTE_MARKER.matcher(text).replaceAll("")
        text = SPACE_RUN.replace(text, " ")
        text = LINE_INDENT.replace(text, "\n")
        text = NEWLINE_RUN.replace(text, "\n\n")
        return Py.strip(text)
    }

    /** `text_processing.split_long_text`: cắt theo câu rồi theo chữ để mỗi mảnh không quá `maxChars` ký tự (code point). */
    fun splitLongText(raw: String, maxChars: Int): List<String> {
        val text = Py.strip(raw)
        if (text.isEmpty()) return emptyList()
        if (Py.len(text) <= maxChars) return listOf(text)
        val result = ArrayList<String>()
        var current = ""
        for (part in SENTENCE_BOUNDARY.split(text, -1)) {
            var sentence = Py.strip(part)
            if (sentence.isEmpty()) continue
            val candidate = Py.strip("$current $sentence")
            if (Py.len(candidate) <= maxChars) {
                current = candidate
                continue
            }
            if (current.isNotEmpty()) {
                result.add(current)
                current = ""
            }
            while (Py.len(sentence) > maxChars) {
                val limit = sentence.offsetByCodePoints(0, maxChars)
                val space = if (limit > 0) sentence.lastIndexOf(' ', limit - 1) else -1 // rfind(" ", 0, max_chars)
                var cut = if (space < 0) -1 else sentence.codePointCount(0, space)
                if (cut < maxChars / 2) cut = maxChars
                val at = sentence.offsetByCodePoints(0, cut)
                result.add(Py.strip(sentence.substring(0, at)))
                sentence = Py.strip(sentence.substring(at))
            }
            current = sentence
        }
        if (current.isNotEmpty()) result.add(current)
        return result
    }

    // ---- bộ tách ---------------------------------------------------------------------------------------------------------------------
    /**
     * `segment_chapter_text(chapter_index, text)` (không bỏ dòng ghi công - người nghe bỏ dòng nào thì chữ đã được [Paragraphs.withoutLines] bỏ trước).
     * Ngoặc kép mở mà không đóng thì đóng ở cuối đoạn mở rồi tách lại, đúng vòng hồi phục của Python.
     */
    fun segment(text: String, maxChars: Int = MAX_CHARS): List<SegmentRow> {
        val clean = normalizeText(text)
        val paragraphs = PARAGRAPH_SPLIT.split(clean, -1).map { Py.strip(it) }.filter { it.isNotEmpty() }
        var closeAt: Set<Int> = emptySet()
        val dialogueInQuotes = chapterWritesDialogueInQuotes(paragraphs)
        var walk = walkParagraphs(paragraphs, maxChars, closeAt, dialogueInQuotes)
        while (walk.state != null) {
            val opened = walk.openedAt
            closeAt = if (opened == null || opened in closeAt) paragraphs.indices.toSet() else closeAt + opened
            walk = walkParagraphs(paragraphs, maxChars, closeAt, dialogueInQuotes)
            if (walk.state != null && closeAt.size >= paragraphs.size) {
                throw IllegalStateException("Unclosed ${walk.state?.hint} quote at the end of the chapter survived closing every paragraph")
            }
        }
        val rows = walk.rows
        // Hết chương: không có cảnh nào sau đó để ngăn, nên không đánh dấu.
        if (rows.isNotEmpty()) rows.last().sceneBreak = false
        return rows
    }

    /** Kịch bản trần của chương cho đường nhạc theo cảnh (`music_nnscene.chapter_script`): `kind` "heading" cho câu đầu nếu là dòng tiêu đề. */
    fun script(text: String): List<SceneSegment> =
        segment(text).mapIndexed { index, row ->
            SceneSegment(row.seq, row.text, if (index == 0 && isHeading(row.text)) "heading" else "narration", row.sceneBreak)
        }

    /**
     * `music_nnscene.paragraph_ids`: mã đoạn của màn đọc (chỉ số trong [Paragraphs.split] của `body`) chứa chỗ mỗi câu bắt đầu. Hai bên đọc cùng một
     * chữ nên số chữ cái / chữ số tới một chỗ bằng nhau; lệch nhẹ thì co theo tỉ lệ.
     */
    fun paragraphIds(sentences: List<String>, body: String): List<Int> {
        val pieces = Paragraphs.split(body)
        if (pieces.isEmpty()) return sentences.map { 0 }
        val starts = ArrayList<Int>(pieces.size)
        var total = 0
        for (piece in pieces) {
            starts.add(total)
            total += letters(piece.text)
        }
        var spoken = 0
        for (sentence in sentences) spoken += letters(sentence)
        val scale = if (spoken != 0 && total != 0) total.toDouble() / spoken else 1.0
        var seen = 0
        val out = ArrayList<Int>(sentences.size)
        for (sentence in sentences) {
            val target = Math.rint(seen * scale).toLong() // round() của Python: chẵn gần nhất
            var at = 0 // bisect_right
            while (at < starts.size && starts[at] <= target) at++
            out.add(maxOf(0, at - 1))
            seen += letters(sentence)
        }
        return out
    }

    /** Số ký tự loại L* / N* (`unicodedata.category(char)[0] in "LN"`). */
    private fun letters(text: String): Int {
        var count = 0
        var at = 0
        while (at < text.length) {
            val cp = text.codePointAt(at)
            at += Character.charCount(cp)
            when (Character.getType(cp).toByte()) {
                Character.UPPERCASE_LETTER, Character.LOWERCASE_LETTER, Character.TITLECASE_LETTER, Character.MODIFIER_LETTER,
                Character.OTHER_LETTER, Character.DECIMAL_DIGIT_NUMBER, Character.LETTER_NUMBER, Character.OTHER_NUMBER -> count++
                else -> {}
            }
        }
        return count
    }

    // ---- đi qua các đoạn ---------------------------------------------------------------------------------------------------------------
    private fun walkParagraphs(paragraphs: List<String>, maxChars: Int, closeAt: Set<Int>, dialogueInQuotes: Boolean): Walk {
        val rows = ArrayList<SegmentRow>()

        fun append(piece: String, paragraphIndex: Int) {
            if (!Py.hasAlnum(piece)) return
            for (chunk in splitLongText(Py.strip(piece), maxChars)) rows.add(SegmentRow(rows.size, paragraphIndex, chunk))
        }

        var state: State? = null
        var openedAt: Int? = null
        var ranOnUnmarked = false // có đoạn nào từ chỗ mở tới đây KHÔNG mở lại bằng dấu ngoặc
        for ((paragraphIndex, paragraph) in paragraphs.withIndex()) {
            val lines = Py.splitLines(paragraph).map { Py.strip(it) }.filter { it.isNotEmpty() }
            for (line in lines) {
                if (state == null && rows.isNotEmpty() && Paragraphs.isSceneBreakLine(line, lines.size == 1)) {
                    rows.last().sceneBreak = true
                    continue
                }
                val wasOpen = state != null
                if (state != null && paragraphIndex != openedAt) {
                    val fresh = freshQuoteOpening(line, state)
                    if (fresh > 0 || (fresh == 0 && ranOnUnmarked)) return Walk(rows, state, openedAt)
                    if (fresh < 0) ranOnUnmarked = true
                }
                val pieces: List<Piece>
                if (state == null && dialogueInQuotes && dashLineIsNarration(line)) {
                    pieces = listOf(Piece(line, "narration"))
                } else {
                    val result = linePiecesWithQuoteState(line, state)
                    pieces = result.first
                    state = result.second
                }
                if (state == null) {
                    openedAt = null
                } else if (!wasOpen) {
                    openedAt = paragraphIndex
                    ranOnUnmarked = false
                }
                for (piece in pieces) append(piece.text, paragraphIndex)
            }
            if (state != null && paragraphIndex in closeAt) {
                state = null
                openedAt = null
            }
        }
        return Walk(rows, state, openedAt)
    }

    private fun chapterWritesDialogueInQuotes(paragraphs: List<String>): Boolean {
        var quoteLed = 0
        var dashLed = 0
        for (paragraph in paragraphs) {
            for (raw in Py.splitLines(paragraph)) {
                val line = Py.strip(raw)
                if (line.isEmpty()) continue
                if (Py.match(QUOTE_LED_LINE, line)) quoteLed++
                if (Py.match(DASH_LINE, line)) dashLed++
            }
        }
        return quoteLed >= QUOTED_CHAPTER_MIN_QUOTE_LINES && dashLed <= QUOTED_CHAPTER_MAX_DASH_LINES
    }

    /** `_dash_line_is_narration`: dòng gạch đọc như lời kể (chỉ dùng ở chương viết thoại trong ngoặc kép). */
    private fun dashLineIsNarration(line: String): Boolean {
        val dash = DASH_LINE.matcher(line)
        if (!dash.lookingAt()) return false
        val body = line.substring(dash.end())
        if (!Py.hasAlnum(body) || Py.search(SPEECH_MARK, body) || Py.search(SPEECH_FINAL_PARTICLE, body)) return false
        val withoutThirdPerson = THIRD_PERSON.matcher(body).replaceAll(" ")
        if (Py.search(SPEECH_ONLY_PRONOUN, withoutThirdPerson)) return false
        if (body.isNotEmpty() && Character.isLowerCase(body.codePointAt(0))) return true
        if (Py.search(SPEECH_PRONOUN, withoutThirdPerson)) return false
        return Py.search(NARRATIVE_SUBJECT, body)
    }

    // ---- giọng nguyên dòng ------------------------------------------------------------------------------------------------------------
    /** `[^\W\d_]`: chữ (kể cả số La Mã / số khác chữ số thập phân), không phải chữ số thập phân hay gạch dưới. */
    private fun hasLetter(text: String): Boolean {
        var at = 0
        while (at < text.length) {
            val cp = text.codePointAt(at)
            at += Character.charCount(cp)
            if (Py.isAlnum(cp) && Character.getType(cp) != Character.DECIMAL_DIGIT_NUMBER.toInt()) return true
        }
        return false
    }

    /** `([^\W\d_])\1{2,}` không phân biệt hoa thường: có một chữ cái lặp từ 3 lần liền không. */
    private fun hasRepeatedLetter(text: String): Boolean {
        var run = 0
        var previous = -1
        var at = 0
        while (at < text.length) {
            val original = text.codePointAt(at)
            at += Character.charCount(original)
            val cp = Character.toLowerCase(Character.toUpperCase(original))
            val letter = Py.isAlnum(cp) && Character.getType(cp) != Character.DECIMAL_DIGIT_NUMBER.toInt()
            if (letter && cp == previous) run++ else run = if (letter) 1 else 0
            previous = if (letter) cp else -1
            if (run >= 3) return true
        }
        return false
    }

    private fun isFramedNameOrTitle(inner: String): Boolean {
        if (FRAMED_NAME_PUNCTUATION.any { it in inner }) return false
        val words = Py.split(inner).filter { Py.hasAlnum(it) }
        if (words.isEmpty() || words.size > FRAMED_NAME_MAX_WORDS) return false
        if (words.size == 1) {
            val sound = StringBuilder()
            var at = 0
            val word = words[0]
            while (at < word.length) {
                val cp = word.codePointAt(at)
                at += Character.charCount(cp)
                if (Py.isAlnum(cp)) sound.appendCodePoint(cp)
            }
            val folded = sound.toString().lowercase()
            if (folded in FRAMED_INTERJECTIONS || hasRepeatedLetter(folded)) return false
        }
        for (word in words) {
            var at = 0
            var first = -1
            while (at < word.length) {
                val cp = word.codePointAt(at)
                at += Character.charCount(cp)
                if (Py.isAlnum(cp)) { first = cp; break }
            }
            if (!(Character.isDigit(first) || Character.isUpperCase(first))) return false
        }
        return true
    }

    /** `is_whole_line_voice`: dòng nguyên vẹn trong 『…』, [ … ] hay 【…】 là MỘT giọng, không phải lời kể (và không phải ghi chú / tên khung). */
    fun isWholeLineVoice(line: String): Boolean {
        val stripped = Py.strip(line)
        if (Py.fullMatch(WHITE_CORNER_LINE, stripped)) return Py.hasAlnum(stripped)
        if (LETTERED_VOICE_LINES.none { Py.fullMatch(it, stripped) } || !hasLetter(stripped)) return false
        val inner = stripped.substring(1, stripped.length - 1)
        return !(Py.match(TRANSLATOR_NOTE_LABEL, inner) || Py.search(TRANSLATOR_SELF_REFERENCE, inner) || isFramedNameOrTitle(inner))
    }

    /** `^'(?=\S)(?:(?!\S'\s).)*\S'$` bằng vòng lặp (lặp nhóm của regex đệ quy trên JVM: dòng dài tràn ngăn xếp). */
    private fun isStraightThoughtLine(line: String): Boolean {
        val n = line.length
        if (n < 3 || line[0] != '\'' || Py.isSpace(line.codePointAt(1))) return false
        if (line[n - 1] != '\'' || Py.isSpace(line.codePointBefore(n - 1))) return false
        for (at in 1 until n - 2) {
            if (!Py.isSpace(line.codePointAt(at)) && line[at + 1] == '\'' && Py.isSpace(line.codePointAt(at + 2))) return false
        }
        return true
    }

    // ---- ngoặc kép --------------------------------------------------------------------------------------------------------------------
    private fun findAll(pattern: java.util.regex.Pattern, line: String): List<Span> {
        val found = ArrayList<Span>()
        val matcher = pattern.matcher(line)
        while (matcher.find()) found.add(Span(matcher.start(), matcher.end()))
        return found
    }

    private fun lastCodePoints(text: String, count: Int): String {
        val total = text.codePointCount(0, text.length)
        return if (total <= count) text else text.substring(text.offsetByCodePoints(0, total - count))
    }

    private fun firstCodePoints(text: String, count: Int): String {
        val total = text.codePointCount(0, text.length)
        return if (total <= count) text else text.substring(0, text.offsetByCodePoints(0, count))
    }

    private fun quotedSpanIsDialogue(line: String, span: Span): Boolean {
        val quoted = Py.strip(line.substring(span.start, span.end))
        val inner = Py.strip(quoted.substring(1, quoted.length - 1))
        if (!Py.hasAlnum(inner)) return false
        if (Py.strip(line.substring(0, span.start)).isEmpty()) {
            val after = Py.strip(line.substring(span.end))
            if (after == "" || after == ".") return true
        }
        if (inner.contains("?") || inner.contains("!") || inner.contains("…") || inner.endsWith(".")) return true
        val before = Py.rstrip(line.substring(0, span.start))
        val after = Py.lstrip(line.substring(span.end))
        if (before.endsWith(":")) return true
        if (inner.endsWith(",") && !Py.search(TERM_INTRODUCER, before.lowercase())) return true
        val context = "${lastCodePoints(before, 100)} ${firstCodePoints(after, 100)}"
        return Py.search(SPEECH_VERB, context)
    }

    private fun joinFragments(left: String, right: String): String {
        if (left.isEmpty()) return right
        if (right.isEmpty()) return left
        if (right[0] in ",.;:!?…)]}”") return left + right
        return "$left $right"
    }

    /** `_nested_dialogue_quote_spans`: cặp “…” có “…” lồng bên trong, khi cả dòng cân dấu. */
    private fun nestedDialogueQuoteSpans(line: String): List<Span> {
        val spans = ArrayList<Span>()
        var depth = 0
        var start = 0
        var nested = false
        for ((index, char) in line.withIndex()) {
            if (char == '“') {
                if (depth == 0) { start = index; nested = false } else nested = true
                depth++
            } else if (char == '”') {
                depth--
                if (depth < 0) return emptyList()
                if (depth == 0 && nested) spans.add(Span(start, index + 1))
            }
        }
        return if (depth == 0) spans else emptyList()
    }

    private fun dialogueQuoteMatches(line: String): List<Span> {
        val matches = findAll(QUOTE, line)
        val nested = nestedDialogueQuoteSpans(line)
        if (nested.isEmpty()) return matches
        val kept = ArrayList(matches.filter { match -> nested.none { match.start >= it.start && match.start < it.end } })
        kept.addAll(nested) // `(.+)` DOTALL khớp trọn [start, end)
        return kept.sortedBy { it.start }
    }

    private fun linePieces(line: String): List<Piece> {
        if (Py.match(DASH_LED_LINE_START, line)) return listOf(Piece(line, "dialogue"))
        if (isWholeLineVoice(line)) return listOf(Piece(line, "dialogue"))
        if (isStraightThoughtLine(line)) return listOf(Piece(line, "thought"))
        val matches = ArrayList<Pair<Span, String>>()
        for (span in dialogueQuoteMatches(line)) matches.add(span to (if (quotedSpanIsDialogue(line, span)) "dialogue" else "narration"))
        for (span in findAll(THOUGHT_QUOTE, line)) matches.add(span to "thought")
        val ordered = matches.sortedWith(compareBy({ it.first.start }, { -it.first.end })) // sắp ổn định
        val kept = ArrayList<Pair<Span, String>>()
        var occupiedUntil = -1
        for (item in ordered) {
            if (item.first.start < occupiedUntil) continue
            kept.add(item)
            occupiedUntil = item.first.end
        }
        if (kept.isEmpty()) {
            val hint = if (line.startsWith("(") && line.endsWith(")")) "thought" else "narration"
            return listOf(Piece(line, hint))
        }

        class Raw(val text: String, val hint: String, val quoted: Boolean)
        val raw = ArrayList<Raw>()
        var cursor = 0
        for ((span, hint) in kept) {
            if (span.start > cursor) raw.add(Raw(line.substring(cursor, span.start), "narration", false))
            raw.add(Raw(line.substring(span.start, span.end), hint, true))
            cursor = span.end
        }
        if (cursor < line.length) raw.add(Raw(line.substring(cursor), "narration", false))

        val merged = ArrayList<Piece>()
        // Mảnh cuối của `merged` là trọn một câu thoại trong ngoặc: câu thoại trong ngoặc liền sau nó là một lượt riêng.
        var lastIsQuotedDialogue = false
        var pendingPrefix = ""
        for (item in raw) {
            var text = Py.strip(item.text)
            if (text.isEmpty()) continue
            if (!Py.hasAlnum(text)) {
                if (merged.isNotEmpty()) {
                    val previous = merged.last()
                    merged[merged.size - 1] = Piece(joinFragments(previous.text, text), previous.hint)
                    lastIsQuotedDialogue = lastIsQuotedDialogue && text == "."
                } else {
                    pendingPrefix = joinFragments(pendingPrefix, text)
                }
                continue
            }
            if (pendingPrefix.isNotEmpty()) {
                text = joinFragments(pendingPrefix, text)
                pendingPrefix = ""
            }
            val quotedDialogue = item.quoted && item.hint == "dialogue"
            if (merged.isNotEmpty() && merged.last().hint == item.hint && !(quotedDialogue && lastIsQuotedDialogue)) {
                merged[merged.size - 1] = Piece(joinFragments(merged.last().text, text), item.hint)
                lastIsQuotedDialogue = false
            } else {
                merged.add(Piece(text, item.hint))
                lastIsQuotedDialogue = quotedDialogue
            }
        }
        return merged
    }

    private fun findQuoteClosing(line: String, closing: String, start: Int = 0): Int {
        if (closing != "’") return line.indexOf(closing, start)
        if (start > line.length) return -1
        val matcher = THOUGHT_CLOSING.matcher(line)
        return if (matcher.find(start)) matcher.start() else -1
    }

    private val CURLY_QUOTES = listOf(Triple("“", "”", "dialogue"), Triple("‘", "’", "thought"))

    private fun balancedQuoteSpans(line: String): List<Span> {
        val spans = ArrayList<Span>()
        for ((opening, closing, _) in CURLY_QUOTES) {
            var cursor = 0
            while (cursor < line.length) {
                val openingIndex = line.indexOf(opening, cursor)
                if (openingIndex < 0) break
                val closingIndex = findQuoteClosing(line, closing, openingIndex + 1)
                if (closingIndex < 0) {
                    cursor = openingIndex + 1
                    continue
                }
                spans.add(Span(openingIndex, closingIndex + 1))
                cursor = closingIndex + 1
            }
        }
        val ascii = line.indices.filter { line[it] == '"' }
        for (pair in 0 until ascii.size / 2) spans.add(Span(ascii[pair * 2], ascii[pair * 2 + 1] + 1))
        return spans
    }

    private class Opening(val index: Int, val closing: String, val hint: String)

    private fun unmatchedCurlyQuoteOpenings(line: String): MutableList<Opening> {
        val balanced = balancedQuoteSpans(line)
        val unmatched = ArrayList<Opening>()
        for ((opening, closing, hint) in CURLY_QUOTES) {
            var cursor = 0
            while (cursor < line.length) {
                val openingIndex = line.indexOf(opening, cursor)
                if (openingIndex < 0) break
                val closingIndex = findQuoteClosing(line, closing, openingIndex + 1)
                if (closingIndex >= 0) {
                    cursor = closingIndex + 1
                    continue
                }
                if (balanced.none { it.start < openingIndex && openingIndex < it.end }) unmatched.add(Opening(openingIndex, closing, hint))
                cursor = openingIndex + 1
            }
        }
        return unmatched
    }

    private fun terminalAlternativeQuoteClosing(line: String, expectedClosing: String): Int {
        val stripped = Py.rstrip(line)
        if (stripped.isEmpty()) return -1
        val terminal = stripped.last()
        if (terminal.toString() == expectedClosing || terminal !in "”’\"") return -1
        if (balancedQuoteSpans(stripped).any { it.end == stripped.length && stripped[it.start] in "“‘" }) return -1
        return stripped.length - 1
    }

    private fun linePiecesWithQuoteState(line: String, state: State?): Pair<List<Piece>, State?> {
        if (state != null) {
            val closingIndex = findQuoteClosing(line, state.closing)
            if (closingIndex < 0) {
                val alternative = terminalAlternativeQuoteClosing(line, state.closing)
                if (alternative >= 0) return listOf(Piece(line.substring(0, alternative + 1), state.hint)) to null
                return listOf(Piece(line, state.hint)) to state
            }
            val pieces = ArrayList<Piece>()
            pieces.add(Piece(line.substring(0, closingIndex + 1), state.hint))
            val remainder = Py.strip(line.substring(closingIndex + 1))
            if (remainder.isEmpty()) return pieces to null
            val (tail, next) = linePiecesWithQuoteState(remainder, null)
            return (pieces + tail) to next
        }

        // Một giọng nguyên dòng tự đóng: dấu “ lẻ bên trong không được mở một lời thoại treo qua đoạn sau.
        if (isWholeLineVoice(line)) return listOf(Piece(line, "dialogue")) to null
        val unmatched = unmatchedCurlyQuoteOpenings(line)
        val ascii = line.indices.filter { line[it] == '"' }
        if (ascii.size % 2 == 1) {
            val openingIndex = ascii.last()
            if (balancedQuoteSpans(line).none { it.start < openingIndex && openingIndex < it.end }) {
                unmatched.add(Opening(openingIndex, "\"", "dialogue"))
            }
        }
        if (unmatched.isEmpty()) return linePieces(line) to null

        val first = unmatched.minByOrNull { it.index }!! // `min` lấy mục đầu khi hoà
        val pieces = ArrayList<Piece>()
        if (first.index > 0) pieces.addAll(linePieces(Py.strip(line.substring(0, first.index))))
        val alternative = terminalAlternativeQuoteClosing(line, first.closing)
        if (alternative > first.index) {
            val quoted = Py.strip(line.substring(first.index, alternative + 1))
            if (quoted.isNotEmpty()) pieces.add(Piece(quoted, first.hint))
            val remainder = Py.strip(line.substring(alternative + 1))
            if (remainder.isNotEmpty()) {
                val (tail, next) = linePiecesWithQuoteState(remainder, null)
                return (pieces + tail) to next
            }
            return pieces to null
        }
        val quoted = Py.strip(line.substring(first.index))
        if (quoted.isNotEmpty()) pieces.add(Piece(quoted, first.hint))
        return pieces to State(first.hint, first.closing)
    }

    /** `_fresh_quote_opening`: chỗ một đoạn sau mở dấu ngoặc MỚI dù ngoặc cũ chưa đóng (-1: không). Chỉ dấu của kết quả (<0, 0, >0) được dùng. */
    private fun freshQuoteOpening(line: String, state: State): Int {
        val closing = state.closing
        if (line.startsWith("“") || (closing == "’" && line.startsWith("‘"))) return 0
        if (line.startsWith("\"") && Py.len(line) > 1 && !Py.isSpace(line.codePointAt(1))) return 0
        if (closing == "\"") return -1
        val openers = if (closing == "’") "“‘" else "“"
        val closingIndex = findQuoteClosing(line, closing)
        val before = if (closingIndex < 0) line else line.substring(0, closingIndex)
        return before.indexOfFirst { it in openers }
    }
}
