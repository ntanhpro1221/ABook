package vn.abook.player.ui.studio

import vn.abook.player.ui.data.dotJoin
import androidx.compose.runtime.Immutable
import org.json.JSONObject
import java.text.Normalizer

// "Cách đọc tên" (NATIVE_REMOTE_STUDIO.md §6.10): mọi tên riêng máy đọc thế nào. Port từ NameReadings.tsx / readingReach.ts / sharedReadings.tsx / ReadingSuggestions.tsx.

/** Câu ví dụ có tên ấy (câu ĐÃ THU nếu có). */
@Immutable
data class ReadingExample(val segmentId: Int, val chapterTitle: String, val seq: Int, val text: String, val hasAudio: Boolean)

/** Một tên và cách đọc của nó trong sách (web `NameReading`). */
@Immutable
data class NameReading(
    val surface: String,
    val spoken: String,
    /** Cách đọc đang nằm trong sách là người nghe chọn (không phải máy đoán). */
    val byListener: Boolean,
    val lines: Int,
    /** Cách đọc người nghe đã ghi mà dây chuyền chưa áp. */
    val requested: String?,
    /** Cách đọc này không bao giờ được dùng (ký hiệu xé đôi chữ ấy trước khi tra cách đọc). */
    val never: Boolean,
    val example: ReadingExample?,
)

@Immutable
data class NameReadings(val items: List<NameReading>, val unseen: Int)

@Immutable
data class ReachChapter(val chapterId: Int, val title: String, val lines: Int, val recorded: Int)

/** Một chữ chạm tới những câu nào (`GET /pronunciations/reach`, web `Reach`). */
@Immutable
data class Reach(
    val surface: String,
    val lines: Int,
    val reached: Int,
    val recorded: Int,
    val blocked: Int,
    val never: Boolean,
    val chapters: List<ReachChapter>,
    val example: ReadingExample?,
)

/** Cách đọc chung cho mọi sách (`GET /api/readings`). */
@Immutable
data class SharedReading(val surface: String, val spokenForm: String, val from: String)

/** Một dòng máy gợi ý bỏ khỏi phần đọc, gộp theo chữ: mọi chương mang dòng ấy (web `SuggestionGroup`). */
@Immutable
data class CreditGroup(val line: String, val chapters: List<Int>, val skipped: Boolean)

internal object StudioReadingsJson {
    private fun example(json: JSONObject?): ReadingExample? = json?.let {
        ReadingExample(it.optInt("segmentId"), it.text("chapterTitle"), it.optInt("seq"), it.text("text"), it.optBoolean("hasAudio"))
    }

    fun readings(json: JSONObject) = NameReadings(
        json.optJSONArray("items").objects().map {
            NameReading(
                surface = it.text("surface"),
                spoken = it.text("spoken"),
                byListener = it.optBoolean("byListener"),
                lines = it.optInt("lines"),
                requested = it.textOrNull("requested")?.takeIf { text -> text.isNotEmpty() },
                never = it.optBoolean("never"),
                example = example(it.optJSONObject("example")),
            )
        }.filter { it.surface.isNotEmpty() },
        json.optInt("unseen"),
    )

    fun reach(json: JSONObject) = Reach(
        surface = json.text("surface"),
        lines = json.optInt("lines"),
        reached = json.optInt("reached"),
        recorded = json.optInt("recorded"),
        blocked = json.optInt("blocked"),
        never = json.optBoolean("never"),
        chapters = json.optJSONArray("chapters").objects().map { ReachChapter(it.optInt("chapterId"), it.text("title"), it.optInt("lines"), it.optInt("recorded")) },
        example = example(json.optJSONObject("example")),
    )

    fun shared(json: JSONObject): List<SharedReading> =
        json.optJSONArray("entries").objects().map { SharedReading(it.text("surface"), it.text("spokenForm"), it.text("from")) }.filter { it.surface.isNotEmpty() }

    /** Mọi dòng gợi ý của cuốn, gộp theo chữ (`groupSuggestions`): một dòng lặp ở đầu cả trăm chương chỉ là một lựa chọn. */
    fun credits(json: JSONObject): List<CreditGroup> {
        val groups = LinkedHashMap<String, Pair<MutableList<Int>, Boolean>>()
        for (row in json.optJSONArray("suggestions").objects()) {
            val line = row.text("line")
            if (line.isEmpty()) continue
            val current = groups[line] ?: (mutableListOf<Int>() to true)
            current.first.add(row.optInt("chapter"))
            groups[line] = current.first to (current.second && row.optBoolean("skipped"))
        }
        return groups.map { (line, group) -> CreditGroup(line, group.first, group.second) }
    }
}

object ReadingsLogic {
    /** Số tên hiện mỗi lần; "Xem thêm" thêm ba trang (web `PAGE`). */
    const val PAGE = 30

    /** Gõ xong mới hỏi "chạm tới bao nhiêu câu" (web `useSettled`). */
    const val REACH_SETTLE_MS = 350L

    /** So tên không phân biệt hoa thường, dấu, gạch nối hay khoảng trắng: gõ "hen" thấy "Hên-cơ", "dac lat" thấy "Đác-lát" (web `fold`). */
    fun fold(text: String): String =
        Normalizer.normalize(text, Normalizer.Form.NFD).replace(Regex("\\p{M}"), "").lowercase().replace('đ', 'd').replace(Regex("[\\s\\-‐-―]"), "")

    /** Các tên khớp ô tìm (tên, hay cách đọc đang ghi / đang chờ); ô trống = tất cả. */
    fun find(items: List<NameReading>, query: String): List<NameReading> {
        val needle = fold(query.trim())
        if (needle.isEmpty()) return items
        return items.filter { fold(it.surface).contains(needle) || fold(it.requested ?: it.spoken).contains(needle) }
    }

    /** Gõ đúng một chữ liền mà không khớp tên nào thì mời thêm cách đọc cho nó ("TP.HCM", "km/h" cũng được, không chỉ tên). */
    fun addable(query: String, found: List<NameReading>): Boolean = found.isEmpty() && single(query.trim())

    fun single(text: String): Boolean = text.length in 1..80 && text.none { it.isWhitespace() }

    /** Danh sách sau khi lưu `spoken` cho `item` - đúng điều máy chủ sẽ trả: cách mới là "chờ áp dụng", trùng cách đang đọc là "giữ" (web `withReading`). */
    fun withReading(data: NameReadings, item: NameReading, spoken: String): NameReadings {
        if (data.items.none { it.surface == item.surface }) return data
        val keep = spoken == item.spoken
        val updated = item.copy(requested = if (keep) null else spoken, byListener = item.byListener || keep)
        return data.copy(items = data.items.map { if (it.surface == item.surface) updated else it })
    }

    /** Chữ hiện của một cách đọc: chữ đầu mỗi từ viết hoa ("rên-ta-rô" thành "Rên-ta-rô"), như web `shownReading`. */
    fun shown(reading: String): String = Regex("(^|\\s)(\\p{Ll})").replace(reading) { match -> match.groupValues[1] + match.groupValues[2].uppercase() }

    /** Lưu mà chỉ khác hoa thường thì gửi đúng cách đang lưu, không thành một thay đổi bắt thu lại các câu. */
    fun asStored(item: NameReading, typed: String): String =
        listOfNotNull(item.requested, item.spoken.takeIf { it.isNotEmpty() }).firstOrNull { it.lowercase() == typed.lowercase() } ?: typed

    /** Vì sao không lưu được cách đọc cho chữ có ký hiệu bị xé đôi ("Mở/đóng"), và làm gì thay vào đó. */
    fun neverText(surface: String): String =
        "Máy đọc ký hiệu trong “$surface” thành một chỗ ngừng trước khi tra cách đọc, nên cách đọc cho chữ này không bao giờ được dùng. Muốn đọc khác, sửa “Chữ đem đọc” của từng câu có chữ ấy."

    private fun where(reach: Reach): String {
        val named = reach.chapters.take(3).map { it.title.ifEmpty { "chương ${it.chapterId}" } }
        val more = reach.chapters.size - named.size
        return if (named.isEmpty()) "" else " · ở ${named.joinToString(", ")}${if (more > 0) " và $more chương nữa" else ""}"
    }

    /** Dòng dưới ô khi đang sửa: có bao nhiêu câu, bao nhiêu câu đã thu sẽ phải thu lại (web `reachSummary`). */
    fun reachSummary(reach: Reach): String {
        if (reach.never) return "${if (reach.lines > 0) "Có ${reach.lines} câu có chữ này, nhưng m" else "M"}áy không dùng được cách đọc cho chữ có ký hiệu này."
        if (reach.lines == 0) return "Chưa có câu nào có chữ này - cách đọc sẽ được dùng khi chữ xuất hiện."
        val cost = if (reach.recorded > 0) "${reach.recorded} câu đã thu sẽ được thu lại" else "chưa thu câu nào nên không phải thu lại"
        val blocked = if (reach.blocked > 0) " (${reach.blocked} câu khác không dùng được vì ký hiệu)" else ""
        return "${reach.reached} câu có chữ này · $cost${where(reach)}$blocked"
    }

    /** Dòng phụ dưới một tên: bao nhiêu câu và ai chọn cách đọc. `analyzed`: sách đã phân tích xong chưa. */
    fun rowNote(item: NameReading, analyzed: Boolean, shared: Boolean): String {
        val base = when {
            !analyzed && item.lines == 0 -> "chưa phân tích tới"
            else -> "${item.lines} câu · " + when {
                item.never -> "máy không dùng được cách đọc này (ký hiệu)"
                item.byListener -> "đã chọn"
                item.spoken.isNotEmpty() -> "máy đoán"
                else -> "chưa có trong sách"
            }
        }
        return base + (if (shared) " · dùng chung" else "") + (item.requested?.let { " · chờ áp dụng: “$it”" } ?: "")
    }

    /** Mục cách đọc chung của một chữ (không phân biệt hoa thường). */
    fun sharedEntry(shared: List<SharedReading>, surface: String, reading: String? = null): SharedReading? =
        shared.firstOrNull { it.surface.lowercase() == surface.lowercase() && (reading == null || it.spokenForm == reading) }

    /** Số chương một dòng gợi ý nằm ở, nói gọn. */
    fun where(group: CreditGroup): String = if (group.chapters.size == 1) "chương ${group.chapters[0]}" else "${group.chapters.size} chương"

    /** Thân `POST /pronunciation` (`EditReading.save`): `seen` là cách đọc dòng này thấy (chờ áp, hay người nghe đã giữ). */
    fun saveStep(item: NameReading, spoken: String, everywhere: Boolean): WorkStep {
        val body = JSONObject().put("surface", item.surface).put("spokenForm", spoken)
            .put("seen", item.requested ?: if (item.byListener) item.spoken else "")
        if (everywhere) body.put("everywhere", true)
        return WorkStep("pronunciation", body)
    }

    fun decision(item: NameReading, spoken: String, everywhere: Boolean): WorkDecision {
        val keep = spoken == item.spoken
        val summary = if (keep) "Giữ cách đọc “${shown(spoken)}”" else "Đã ghi: “${item.surface}” đọc là “$spoken”"
        return WorkDecision("reading:${item.surface}", summary, listOf(saveStep(item, spoken, everywhere)))
    }

    fun checkStep(surface: String, spoken: String) = WorkStep("pronunciation/check", JSONObject().put("surface", surface).put("spokenForm", spoken))

    fun previewStep(surface: String, spoken: String) = WorkStep("pronunciation/preview", JSONObject().put("surface", surface).put("spokenForm", spoken))

    /** `PUT /skip`: bỏ (hay đọc lại) dòng `line` trong phần đọc của các chương ấy. Chữ của truyện KHÔNG đổi. */
    fun skipBody(group: CreditGroup, skip: Boolean): JSONObject =
        JSONObject().put("line", group.line).put("chapters", org.json.JSONArray(group.chapters)).put("skip", skip)
}

object ReadingsText {
    const val TITLE = "Cách đọc tên"
    const val LEAD = "Nghe và sửa cách đọc tên; câu đã thu có tên ấy sẽ thu lại."
    const val SEARCH = "Tìm tên, hoặc gõ một chữ để thêm cách đọc"
    const val LOADING = "Đang tải cách đọc tên"
    const val EMPTY = "Cuốn này chưa có tên nào cần chốt cách đọc."
    const val EDIT = "Sửa"
    const val SAVE = "Lưu"
    const val CANCEL = "Huỷ"
    const val TRY = "Nghe thử"
    const val TRYING = "Máy tính đang đọc thử"
    const val TRY_STOP = "Dừng nghe"
    const val FIELD = "Cách đọc mới"
    const val EVERYWHERE = "Dùng cho mọi sách"
    const val MORE = "Xem thêm"
    const val NO_MATCH = "Không khớp; gõ một chữ liền để thêm cách đọc."
    const val SHARED_NONE = "Không có trong danh sách - máy đọc theo chữ"
    const val SUGGEST_TITLE = "Dòng nên bỏ khỏi phần đọc"
    const val SUGGEST_LEAD = "Máy thấy vài dòng ghi công hay xin ủng hộ. Chữ của truyện giữ nguyên; chọn dòng nào thì phần đọc bỏ qua dòng ấy."
    const val SUGGEST_SKIP = "Bỏ đọc dòng"

    fun count(counted: Int, analyzed: Boolean) = if (analyzed) "$counted tên trong phần này" else "chưa phân tích - tên hiện ra sau bước ấy"
    fun unseen(count: Int) = "$count tên khác của cuốn không có câu nào trong phần này."
    fun more(count: Int) = "Xem thêm $count tên"
    fun add(surface: String) = "Đọc “$surface”"
    fun sharedOffer(count: Int) = "Dùng $count cách đọc chung"
    fun sharedDone(count: Int) = "Đã dùng $count cách đọc chung"
    fun playTitle(item: NameReading) = dotJoin(item.example?.chapterTitle, "câu ${item.example?.seq ?: 0}")
}
