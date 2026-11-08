package vn.abook.player.ui.studio

import vn.abook.player.S

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
        S.s_may_doc_ky_hieu_trong_0_thanh_mot_cho_ngun_41720519(surface)

    private fun where(reach: Reach): String {
        val named = reach.chapters.take(3).map { it.title.ifEmpty { S.s_chuong_0_55d256d1(it.chapterId) } }
        val more = reach.chapters.size - named.size
        return if (named.isEmpty()) "" else S.s_o_0_1_dd43afcc(named.joinToString(", "), if (more > 0) S.s_va_0_chuong_nua_128abbd4(more) else "")
    }

    /** Dòng dưới ô khi đang sửa: có bao nhiêu câu, bao nhiêu câu đã thu sẽ phải thu lại (web `reachSummary`). */
    fun reachSummary(reach: Reach): String {
        if (reach.never) return S.s_0_ay_khong_dung_duoc_cach_doc_cho_chu_co_k_0fe94280(if (reach.lines > 0) S.s_co_0_cau_co_chu_nay_nhung_m_d75dd8c1(reach.lines) else "M")
        if (reach.lines == 0) return S.s_chua_co_cau_nao_co_chu_nay_cach_doc_se_duo_2d730bc4
        val cost = if (reach.recorded > 0) S.s_0_cau_da_thu_se_duoc_thu_lai_4520a0f5(reach.recorded) else S.s_chua_thu_cau_nao_nen_khong_phai_thu_lai_79ed2712
        val blocked = if (reach.blocked > 0) S.s_0_cau_khac_khong_dung_duoc_vi_ky_hieu_d0715176(reach.blocked) else ""
        return S.s_0_cau_co_chu_nay_1_2_3_8abc27d8(reach.reached, cost, where(reach), blocked)
    }

    /** Dòng phụ dưới một tên: bao nhiêu câu và ai chọn cách đọc. `analyzed`: sách đã phân tích xong chưa. */
    fun rowNote(item: NameReading, analyzed: Boolean, shared: Boolean): String {
        val base = when {
            !analyzed && item.lines == 0 -> S.s_chua_phan_tich_toi_34530fdc
            else -> S.s_0_cau_4e05e46f(item.lines) + when {
                item.never -> S.s_may_khong_dung_duoc_cach_doc_nay_ky_hieu_2038583b
                item.byListener -> S.s_da_chon_a0788df6
                item.spoken.isNotEmpty() -> S.s_may_doan_7217169e
                else -> S.s_chua_co_trong_sach_5fecd5a8
            }
        }
        return base + (if (shared) S.s_dung_chung_9b5fc850 else "") + (item.requested?.let { S.s_cho_ap_dung_0_7f062955(it) } ?: "")
    }

    /** Mục cách đọc chung của một chữ (không phân biệt hoa thường). */
    fun sharedEntry(shared: List<SharedReading>, surface: String, reading: String? = null): SharedReading? =
        shared.firstOrNull { it.surface.lowercase() == surface.lowercase() && (reading == null || it.spokenForm == reading) }

    /** Số chương một dòng gợi ý nằm ở, nói gọn. */
    fun where(group: CreditGroup): String = if (group.chapters.size == 1) S.s_chuong_0_55d256d1(group.chapters[0]) else S.s_0_chuong_04093412(group.chapters.size)

    /** Thân `POST /pronunciation` (`EditReading.save`): `seen` là cách đọc dòng này thấy (chờ áp, hay người nghe đã giữ). */
    fun saveStep(item: NameReading, spoken: String, everywhere: Boolean): WorkStep {
        val body = JSONObject().put("surface", item.surface).put("spokenForm", spoken)
            .put("seen", item.requested ?: if (item.byListener) item.spoken else "")
        if (everywhere) body.put("everywhere", true)
        return WorkStep("pronunciation", body)
    }

    fun decision(item: NameReading, spoken: String, everywhere: Boolean): WorkDecision {
        val keep = spoken == item.spoken
        val summary = if (keep) S.s_giu_cach_doc_0_ad3b6d08(shown(spoken)) else S.s_da_ghi_0_doc_la_1_2c14f196(item.surface, spoken)
        return WorkDecision("reading:${item.surface}", summary, listOf(saveStep(item, spoken, everywhere)))
    }

    fun checkStep(surface: String, spoken: String) = WorkStep("pronunciation/check", JSONObject().put("surface", surface).put("spokenForm", spoken))

    fun previewStep(surface: String, spoken: String) = WorkStep("pronunciation/preview", JSONObject().put("surface", surface).put("spokenForm", spoken))

    /** `PUT /skip`: bỏ (hay đọc lại) dòng `line` trong phần đọc của các chương ấy. Chữ của truyện KHÔNG đổi. */
    fun skipBody(group: CreditGroup, skip: Boolean): JSONObject =
        JSONObject().put("line", group.line).put("chapters", org.json.JSONArray(group.chapters)).put("skip", skip)
}

object ReadingsText {
    const val TITLE = S.s_cach_doc_ten_1c46e75d
    const val LEAD = S.s_nghe_va_sua_cach_doc_ten_cau_da_thu_co_ten_957bce51
    /** Gợi ý trong ô tìm (cùng chữ với NameReadings.tsx): ngắn, vừa một dòng; gõ chữ chưa có thì ô vẫn thêm được. */
    const val SEARCH = S.s_tim_hoac_them_ten_27507006
    const val SEARCH_NAME = S.s_tim_ten_260c6baf
    const val LOADING = S.s_dang_tai_cach_doc_ten_8856dead
    const val EMPTY = S.s_cuon_nay_chua_co_ten_nao_can_chot_cach_doc_c132f8db
    const val EDIT = S.s_sua_d4e07603
    const val SAVE = S.s_luu_e91f26c0
    const val CANCEL = S.s_huy_96732485
    const val TRY = S.s_nghe_thu_fa024065
    const val TRYING = S.s_may_tinh_dang_doc_thu_ebc9983a
    const val TRY_STOP = S.s_dung_nghe_f20939be
    const val FIELD = S.s_cach_doc_moi_39ce794c
    const val EVERYWHERE = S.s_dung_cho_moi_sach_fd10b5e6
    const val MORE = S.s_xem_them_e0ac1b1e
    const val NO_MATCH = S.s_khong_khop_go_mot_chu_lien_de_them_cach_do_62b9e5c9
    const val SHARED_NONE = S.s_khong_co_trong_danh_sach_may_doc_theo_chu_935ca799
    fun lineCount(n: Int) = S.s_0_dong_4a3b8570(n)
    const val SUGGEST_TITLE = S.s_dong_nen_bo_khoi_phan_doc_16f0e5d7
    const val SUGGEST_LEAD = S.s_may_thay_vai_dong_ghi_cong_hay_xin_ung_ho_9597cd96
    const val SUGGEST_SKIP = S.s_bo_doc_dong_3e82a7fd

    fun count(counted: Int, analyzed: Boolean) = if (analyzed) S.s_0_ten_trong_phan_nay_e81c3ccb(counted) else S.s_chua_phan_tich_ten_hien_ra_sau_buoc_ay_32656b4c
    fun unseen(count: Int) = S.s_0_ten_khac_cua_cuon_khong_co_cau_nao_trong_acf7b517(count)
    fun more(count: Int) = S.s_xem_them_0_ten_bce27e05(count)
    fun add(surface: String) = S.s_doc_0_5067e74c(surface)
    fun sharedOffer(count: Int) = S.s_dung_0_cach_doc_chung_0622f2a8(count)
    fun sharedDone(count: Int) = S.s_da_dung_0_cach_doc_chung_f3c4cdb8(count)
    fun playTitle(item: NameReading) = dotJoin(item.example?.chapterTitle, S.s_cau_0_7b7d4092(item.example?.seq ?: 0))
}
