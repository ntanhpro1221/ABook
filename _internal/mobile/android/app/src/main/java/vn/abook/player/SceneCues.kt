package vn.abook.player

/** Một câu của chương cho đường nhạc theo cảnh (music_scenes: `id`, `text`, `kind`, `sceneBreak`; không cảm xúc, không giờ). */
class SceneSegment(
    val id: Int,
    val text: String,
    /** "heading" cho dòng tiêu đề chương, còn lại "narration". */
    val kind: String = "narration",
    /** Dòng ngăn cảnh ("***", "◆") đứng ngay SAU câu này (text_processing.segment_chapter_text) - hay dấu hiệu đổi cảnh ([SceneCues.withSceneBreaks]). */
    val sceneBreak: Boolean = false,
    /** Nguồn của cờ `sceneBreak` thêm sau ("cue", "lite"); null = cờ có sẵn từ dòng ngăn cảnh của sách. */
    val sceneSource: String? = null,
    val sceneCue: String? = null,
)

/**
 * Dấu hiệu đổi cảnh trong chữ - bản Kotlin NGUYÊN VĂN của abook/webui/music_scenes.py (`cue_kind`, `cue_bounds`, `with_scene_breaks`,
 * `hard_break`, `bracket_is_subhead`, `subhead_words` và các regex của chúng), main a41b70bc. Đường N0 của nhạc theo cảnh
 * (Corpus/research/music/N0_CALLGRAPH.md mục 2.1-2.2). Mỗi regex chép nguyên chuỗi Python qua [Py.rx]; bộ ca thử
 * tests/fixtures/music/n0/regex_cases.json (SceneMusicTest) chạy từng regex với chữ Việt có dấu.
 */
object SceneCues {
    /** Ngăn cảnh "gắn chặt": dòng chỉ gồm ký hiệu (`hard_break`, mọi câu). */
    internal val SEPARATOR = Py.rx("""^\s*(?:[*~#=_\-·•oO0]\s*){3,}\s*$""")
    internal val TIME_JUMP = Py.rx(
        """^\W*(?:(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm\s+)?sau|hôm\s+sau|ngày\s+(?:hôm\s+)?sau|sáng\s+sớm\s+hôm\s+sau|""" +
            """(?:mấy|vài|ba|bốn|năm|sáu|bảy|mười|một|hai|\d+)\s+(?:ngày|tuần|tháng|năm|canh\s+giờ)\s+sau|""" +
            """(?:the\s+)?next\s+(?:morning|day)|(?:a\s+few|several|\d+)\s+(?:days|weeks|months|years)\s+later)""",
        ignoreCase = true,
    )
    internal val CUE_SYMBOLS = Py.rx("""^\s*(?:(?:[*~#=_\-·•◇◆○●♦※✦＊]\s*){1,}|o\s*O\s*o)\s*$""")
    internal val CUE_SUBHEAD = Py.rx("""^\s*(?:góc nhìn|pov\b|phần\b|interlude|side\b|phía\b)""", ignoreCase = true)
    internal val CUE_BRACKETED = Py.rx("""^\s*(?:【[^】]*】|\[[^\]]*\]|「[^」]*」|[—–-]{1,2}\s*[^—–-]{1,40}\s*[—–-]{1,2})\s*$""")
    // "side" không có \b: y regex đã đóng băng (cue_bracket.keep_bracket).
    internal val CUE_BRACKET_POV = Py.rx("""\bPOV\b|góc nhìn|side""", ignoreCase = true)
    internal const val CUE_SUBHEAD_WORDS = 10
    // [oO0\W\d_] của Python: \W không viết được trong ngoặc vuông của Java/ICU -> chọn một trong hai.
    internal val CUE_DECOR = Py.rx("""^(?:[oO0\d_]|\W)*$""")
    internal val CUE_HEAD_WORD = Py.rx(
        """^(?:phần|chương|hồi|quyển|tập|ngoại\s+truyện|phiên\s+ngoại|chapter|part|interlude|prologue|""" +
            """epilogue|mở\s+đầu|vĩ\s+thanh|kết)\b""",
        ignoreCase = true,
    )
    internal val CUE_NUMERAL = Py.rx("""^(?:\d+|[ivxlcdm]+)\.?$""", ignoreCase = true)
    internal val CUE_NAME_PUNCT = Py.rx("""[.!?…,;:*\"“”]""")
    internal val CUE_VIET_LETTERS = Py.rx(
        "[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", ignoreCase = true,
    )
    internal val CUE_END_WORDS = setOf("end", "fin")
    internal val CUE_PLAIN_END = Py.rx("""[.!?…,;:\"”'’)]\s*$""")
    internal val CUE_PART_NUMBERS = setOf("một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười", "cuối", "kết", "đầu")
    internal val CUE_TIME_PLACE = Py.rx(
        """^\W*(?:trong\s+khi\s+đó|cùng\s+lúc\s+(?:đó|ấy)|lúc\s+(?:ấy|đó)\s+ở|(?:vài|mấy|một|hai|ba)\s+(?:giờ|tiếng|phút)\s+sau|""" +
            """(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm|ngày)\s+(?:ấy|đó)|ngày\s+hôm\s+đó|quay\s+lại|trở\s+lại\s+với|(?:ở|tại)\s+một\s+nơi\s+khác)""",
        ignoreCase = true,
    )
    private val BRACKET_EDGES = Py.rx("""^\s*[\[【「(—–-]+\s*|\s*[\]】」)—–-]+\s*$""")

    /** `bracket_is_subhead`: câu dạng ngoặc chỉ là tiêu đề phụ khi nói góc nhìn mới, hay bao bằng gạch mà bên trong là hoa văn / từ tiêu đề / số / tên. */
    fun bracketIsSubhead(raw: String): Boolean {
        val text = Py.strip(raw)
        val inner = BRACKET_EDGES.matcher(text).replaceAll("")
        if (Py.search(CUE_BRACKET_POV, inner)) return true
        val words = Py.split(inner)
        var name = words.size in 1..3 && !Py.search(CUE_NAME_PUNCT, inner) && words.all { Py.firstIsUpper(it) }
        if (name && words.size == 1 && (Py.search(CUE_VIET_LETTERS, inner) || inner.lowercase() in CUE_END_WORDS)) name = false
        val dashLed = text.isEmpty() || text[0] == '-' || text[0] == '–' || text[0] == '—'
        return dashLed && (Py.match(CUE_DECOR, inner) || Py.match(CUE_HEAD_WORD, inner) || Py.match(CUE_NUMERAL, inner) || name)
    }

    /** `subhead_words`: câu mở bằng từ tiêu đề phụ có thật là tiêu đề ("Phần hai", "Phần 3"), không phải câu thường ("Phần thưởng:", "Phía sau lưng hắn..."). */
    fun subheadWords(text: String): Boolean {
        if (Py.search(CUE_PLAIN_END, text) && !(text.endsWith(":") && Py.split(text).size <= 4)) return false
        val words = Py.split(text.trimEnd(':'))
        if (words.isNotEmpty() && words[0].lowercase() == "phần") {
            val at = if (words.size > 2 && words[1].lowercase() == "thứ") 2 else 1
            val number = if (words.size > at) words[at].trimEnd(':', '.').lowercase() else ""
            if (Py.match(CUE_NUMERAL, number)) return true
            return words.size <= at + 3 && number in CUE_PART_NUMBERS
        }
        return true
    }

    /** `cue_kind`: loại dấu hiệu đổi cảnh của một câu ("heading", "separator", "subhead", "time_place") hay null. */
    fun cueKind(segment: SceneSegment): String? {
        val text = Py.strip(segment.text)
        if (segment.kind == "heading") return "heading"
        if (Py.match(CUE_SYMBOLS, text)) return "separator"
        if (Py.split(text).size <= CUE_SUBHEAD_WORDS &&
            ((Py.match(CUE_SUBHEAD, text) && subheadWords(text)) || (Py.match(CUE_BRACKETED, text) && bracketIsSubhead(text)))
        ) return "subhead"
        if (Py.match(TIME_JUMP, text) || Py.match(CUE_TIME_PLACE, text)) return "time_place"
        return null
    }

    /**
     * `cue_bounds`: {id câu BẮT ĐẦU cảnh mới: loại}. Dòng ký hiệu thì cảnh mới ở câu SAU nó, tiêu đề / tiêu đề phụ ở chính câu ấy; câu đầu chương
     * không tính. ("time_place" không thành ranh giới; câu cuối chương không mở cảnh nào - `index + 1 < len`.)
     */
    fun cueBounds(segments: List<SceneSegment>): Map<Int, String> {
        val out = LinkedHashMap<Int, String>()
        for (index in 1 until segments.size) {
            val kind = cueKind(segments[index])
            if (kind == "separator" || kind == "heading" || kind == "subhead") {
                if (index + 1 < segments.size) out.putIfAbsent(if (kind == "separator") segments[index + 1].id else segments[index].id, kind)
            }
        }
        return out
    }

    /**
     * `with_scene_breaks`: câu đứng ngay trước ranh giới mang cờ `sceneBreak` kèm `sceneSource` (nguồn) và `sceneCue` = loại. Nguồn: "cue" ([cueBounds]) rồi `boundaries`
     * ({nguồn: {id câu bắt đầu cảnh: loại}}, theo thứ tự của map - hiện chỉ "lite" của LB, [NnLite.sceneBounds]); hai nguồn cùng chỗ thì nguồn trước thắng.
     * Câu đã có cờ từ dòng ngăn cảnh của sách giữ nguyên (không thêm nguồn). Câu gốc không bị sửa.
     */
    fun withSceneBreaks(segments: List<SceneSegment>, boundaries: Map<String, Map<Int, String>> = emptyMap()): List<SceneSegment> {
        val sources = ArrayList<Pair<String, Map<Int, String>>>()
        sources.add("cue" to cueBounds(segments))
        for ((name, starts) in boundaries) sources.add(name to starts)
        val out = ArrayList(segments)
        for (index in 0 until segments.size - 1) {
            val following = segments[index + 1].id
            val found = sources.firstOrNull { following in it.second } ?: continue
            val segment = segments[index]
            if (!segment.sceneBreak) {
                out[index] = SceneSegment(segment.id, segment.text, segment.kind, true, found.first, found.second.getValue(following).ifEmpty { found.first })
            }
        }
        return out
    }

    /**
     * `hard_break`: lý do đoạn nhạc mới phải bắt đầu ở `segment` ("heading", "separator", "time_jump", hay loại `sceneCue` của dấu hiệu), hay null.
     * `previous`: câu ngay trước nó (dòng ngăn cảnh không có chữ nên không thành câu, mà đánh dấu câu đứng trước).
     */
    fun hardBreak(segment: SceneSegment, previous: SceneSegment?): String? {
        val flagged = previous != null && previous.sceneBreak
        if (segment.kind == "heading") return "heading"
        if ((flagged && previous.sceneSource == null) || Py.match(SEPARATOR, segment.text)) return "separator"
        if (Py.match(TIME_JUMP, segment.text)) return "time_jump"
        if (flagged) return previous.sceneCue ?: ""
        return null
    }
}
