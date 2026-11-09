package vn.abook.player.ui.studio

import vn.abook.player.S

import androidx.compose.runtime.Immutable
import org.json.JSONObject

/** 16 kiểu thẻ "Việc cần duyệt" (web `WorkKind`); `label` là nhãn nhỏ trên thẻ (`KIND_LABEL` của WorkInbox.tsx). */
enum class WorkKind(val key: String, val label: String) {
    Speaker("speaker", S.s_ai_noi_cau_nay_0e00a5c7),
    Caller("caller", S.s_nguoi_goi_ngoai_khung_03677986),
    Turn("turn", S.s_luot_doi_dap_a2c055e0),
    Pronunciation("pronunciation", S.s_cach_doc_ten_1c46e75d),
    Gender("gender", S.s_nam_hay_nu_0167dbc6),
    Vocative("vocative", S.s_goi_hay_noi_305521d7),
    Alias("alias", S.s_mot_nguoi_hai_ten_9293d8ab),
    Bracket("bracket", S.s_loi_trong_c682376b),
    SharedVoice("shared-voice", S.s_chung_giong_a58df5cc),
    Unnamed("unnamed", S.s_vai_phu_khong_ten_6395f0d2),
    Audio("audio", S.s_ban_thu_loi_753aaed5),
    Narrator("narrator", S.s_nguoi_ke_cua_doan_b218398e),
    VoiceWish("voice-wish", S.s_giong_chua_doi_duoc_2617419d),
    Snap("snap", S.s_ten_viet_khac_f05542f3),
    TellerVoice("teller-voice", S.s_giong_loi_dan_f8f4ea1e),
    TellerThought("teller-thought", S.s_noi_tam_nguoi_ke_0c360f80),
    Refused("refused", S.s_yeu_cau_chua_duoc_3c62dd70);

    companion object {
        fun of(key: String): WorkKind? = entries.firstOrNull { it.key == key }
    }
}

/** Mẫu thẻ (NATIVE_REMOTE_STUDIO.md §6.4): 16 kiểu gom về năm mẫu, thêm [Plain] cho thẻ máy gửi thiếu phần để trả lời (chỉ đọc). */
enum class CardTemplate { Choose, Reading, Voice, Listen, Refused, Plain }

/** Một câu (mã ổn định + băm chữ): máy từ chối câu đã đổi chữ, nên mọi quyết định gửi kèm cặp này. */
@Immutable
data class LineRef(val stableId: String, val textSha256: String)

/** Câu ví dụ trên thẻ (web `WorkExample`). */
@Immutable
data class WorkExample(
    val segmentId: Int,
    val chapterId: Int,
    val chapterTitle: String,
    val seq: Int,
    val text: String,
    val speaker: String,
    /** Câu đã có bản thu (nghe được). */
    val hasAudio: Boolean,
    /** Câu mà lựa chọn trên thẻ sẽ đổi người nói. */
    val changes: Boolean,
    val stableId: String,
    val before: String,
    val after: String,
    /** Câu lời kể quanh câu được hỏi: không ai "nói" nó. */
    val narration: Boolean,
    /** Tên ứng viên để tô trong câu (đã hạ chữ). */
    val names: List<String>,
)

/** Nút trả lời của thẻ chọn người nói; `name` là tên người khi nhãn không phải tên ("Gộp vào Kati"); `sampleId`: một câu đã
 *  thu của người ấy - nghe giọng ngay cạnh nút (như tab Nhân vật). */
@Immutable
data class WorkChoice(val label: String, val value: String, val name: String?, val sampleId: Int? = null, val samplePreset: String? = null)

/** Nút trả lời của thẻ giọng / giới (web `VoiceChoice`); các trường `null` thì không gửi. */
@Immutable
data class VoiceOption(
    val label: String,
    val character: String,
    val gender: String?,
    val preset: String?,
    val avoid: String?,
    /** Cái giá của lựa chọn ("giữ giọng đang đọc", "đổi giọng, thu lại 12 câu"). */
    val note: String?,
    /** Câu báo khi đã ghi ("Noah là nữ"). */
    val done: String?,
    val recommended: Boolean,
)

/** Một yêu cầu "giữ nguyên" của thẻ nhóm: mỗi vai giữ người của nó. */
@Immutable
data class SpeakerRequest(val lines: List<LineRef>, val speaker: String)

@Immutable
data class NarratorHeading(val line: String, val narrator: String, val label: String)

/** Thẻ người kể của một đoạn (webui/narrator_cards.py). */
@Immutable
data class NarratorSection(
    val chapterIndex: Int,
    val fromSeq: Int,
    val toSeq: Int,
    val narrator: String,
    val appliesNote: String,
    val choices: List<WorkChoice>,
    val heading: NarratorHeading?,
)

/** Yêu cầu đã bị máy từ chối: phần, khoá và mốc để bỏ đúng yêu cầu ấy. */
@Immutable
data class RefusedRef(val section: String, val key: String, val requestedAt: Double)

/** Người có giọng đã chọn mà không áp được: nút "Chọn giọng khác" mở bảng giọng của họ. */
@Immutable
data class PickVoice(val name: String, val displayName: String)

/** Một thẻ việc cần duyệt (web `WorkItem`): chỉ phần màn native dùng. */
@Immutable
data class WorkItem(
    val kind: WorkKind,
    val key: String,
    val title: String,
    val problem: String,
    val affected: Int,
    val doubt: Int,
    val options: List<String>,
    val current: String,
    val examples: List<WorkExample>,
    val surface: String?,
    /** Điều người nghe đã ghi mà dây chuyền chưa áp; null = chưa quyết. */
    val requested: String?,
    val redoOnly: Boolean,
    val lines: List<LineRef>?,
    val allLines: List<LineRef>?,
    val scopeLabels: Pair<String, String>?,
    val choices: List<WorkChoice>?,
    val currentValue: String?,
    /** Người đang được ghi cho từng câu khi thẻ được dựng ("" = chưa ai quyết): gửi lại làm `seen`. */
    val seen: Map<String, String>,
    val keepLabel: String?,
    /** false: máy không đề xuất ai - nút đầu không tô như gợi ý. */
    val suggested: Boolean,
    val subject: String?,
    val voiceChoices: List<VoiceOption>?,
    val keepCharacters: List<String>,
    val refused: RefusedRef?,
    val pickVoice: PickVoice?,
    val chapters: List<Int>,
    val pick: Boolean,
    val examplesTotal: Int?,
    val keepGroups: List<SpeakerRequest>,
    val newPerson: String?,
    val newPersonLabel: String?,
    val suggestedName: String = "",
    val narratorSection: NarratorSection?,
)

/** Lời đáp của `GET /api/books/<id>/work`. */
@Immutable
data class WorkView(val items: List<WorkItem>, val counts: Map<WorkKind, Int>)

/** Một trang câu ví dụ của thẻ nhóm lớn (`GET /work/examples`). */
@Immutable
data class WorkExamplesPage(val examples: List<WorkExample>, val total: Int)

/** Đọc lời đáp `/work` thành mô hình (hình JSON của webui/work_items.py). Kiểu thẻ lạ (máy mới hơn điện thoại) bị bỏ, không làm hỏng cả danh sách. */
internal object StudioWorkJson {
    private fun lines(array: org.json.JSONArray?): List<LineRef> =
        array.objects().map { LineRef(it.text("stableId"), it.text("textSha256")) }

    fun example(json: JSONObject) = WorkExample(
        segmentId = json.optInt("segmentId"),
        chapterId = json.optInt("chapterId"),
        chapterTitle = json.text("chapterTitle"),
        seq = json.optInt("seq"),
        text = json.text("text"),
        speaker = json.text("speaker"),
        hasAudio = json.optBoolean("hasAudio"),
        changes = json.optBoolean("changes"),
        stableId = json.text("stableId"),
        before = json.text("before"),
        after = json.text("after"),
        narration = json.optBoolean("narration"),
        names = json.optJSONArray("names").strings(),
    )

    private fun choice(json: JSONObject) = WorkChoice(
        json.text("label"), json.text("value"), json.textOrNull("name")?.takeIf { it.isNotEmpty() },
        if (json.has("sampleId") && !json.isNull("sampleId")) json.optInt("sampleId") else null,
        json.textOrNull("samplePreset")?.takeIf { it.isNotEmpty() },
    )

    private fun voiceOption(json: JSONObject) = VoiceOption(
        label = json.text("label"),
        character = json.text("character"),
        gender = json.textOrNull("gender"),
        preset = json.textOrNull("preset"),
        avoid = json.textOrNull("avoid"),
        note = json.textOrNull("note")?.takeIf { it.isNotEmpty() },
        done = json.textOrNull("done")?.takeIf { it.isNotEmpty() },
        recommended = json.optBoolean("recommended"),
    )

    private fun narrator(json: JSONObject) = NarratorSection(
        chapterIndex = json.optInt("chapterIndex"),
        fromSeq = json.optInt("fromSeq"),
        toSeq = json.optInt("toSeq"),
        narrator = json.text("narrator"),
        appliesNote = json.text("appliesNote"),
        choices = json.optJSONArray("choices").objects().map(::choice),
        heading = json.optJSONObject("heading")?.let { NarratorHeading(it.text("line"), it.text("narrator"), it.text("label")) },
    )

    fun examples(json: JSONObject) = WorkExamplesPage(json.optJSONArray("examples").objects().map(::example), json.optInt("total"))

    /** Một thẻ, hay null khi kiểu thẻ lạ hoặc thiếu khoá. */
    fun item(json: JSONObject): WorkItem? {
        val kind = WorkKind.of(json.text("kind")) ?: return null
        val key = json.text("key").ifEmpty { return null }
        val seen = json.optJSONObject("seen")
        val scope = json.optJSONArray("scopeLabels")?.strings()?.takeIf { it.size == 2 }
        return WorkItem(
            kind = kind,
            key = key,
            title = json.text("title"),
            problem = json.text("problem"),
            affected = json.optInt("affected"),
            doubt = json.optInt("doubt"),
            options = json.optJSONArray("options").strings(),
            current = json.text("current"),
            examples = json.optJSONArray("examples").objects().map(::example),
            surface = json.textOrNull("surface")?.takeIf { it.isNotEmpty() },
            requested = json.textOrNull("requested"),
            redoOnly = json.optBoolean("redoOnly"),
            lines = json.optJSONArray("lines")?.let(::lines),
            allLines = json.optJSONArray("allLines")?.let(::lines),
            scopeLabels = scope?.let { it[0] to it[1] },
            choices = json.optJSONArray("choices")?.objects()?.map(::choice),
            currentValue = json.textOrNull("currentValue"),
            seen = seen?.keys()?.asSequence()?.associateWith { seen.text(it) }.orEmpty(),
            keepLabel = json.textOrNull("keepLabel")?.takeIf { it.isNotEmpty() },
            suggested = if (json.has("suggested") && !json.isNull("suggested")) json.optBoolean("suggested") else true,
            subject = json.textOrNull("subject")?.takeIf { it.isNotEmpty() },
            voiceChoices = json.optJSONArray("voiceChoices")?.objects()?.map(::voiceOption),
            keepCharacters = json.optJSONArray("keepCharacters").strings(),
            refused = json.optJSONObject("refused")?.let { RefusedRef(it.text("section"), it.text("key"), it.optDouble("requestedAt")) },
            pickVoice = json.optJSONObject("pickVoice")?.let { PickVoice(it.text("name"), it.text("displayName")) },
            chapters = json.optJSONArray("chapters")?.let { array -> (0 until array.length()).map { array.optInt(it) } }.orEmpty(),
            pick = json.optBoolean("pick"),
            examplesTotal = if (json.has("examplesTotal") && !json.isNull("examplesTotal")) json.optInt("examplesTotal") else null,
            keepGroups = json.optJSONArray("keepGroups").objects().map { SpeakerRequest(lines(it.optJSONArray("lines")), it.text("speaker")) },
            newPerson = json.textOrNull("newPerson")?.takeIf { it.isNotEmpty() },
            newPersonLabel = json.textOrNull("newPersonLabel")?.takeIf { it.isNotEmpty() },
            suggestedName = json.optString("suggestedName"),
            narratorSection = json.optJSONObject("narratorSection")?.let(::narrator),
        )
    }

    fun view(json: JSONObject): WorkView {
        val items = json.optJSONArray("items").objects().mapNotNull(::item)
        val counts = json.optJSONObject("counts")?.let { counts ->
            counts.keys().asSequence().mapNotNull { key -> WorkKind.of(key)?.let { it to counts.optInt(key) } }.toMap()
        }.orEmpty()
        return WorkView(items, counts)
    }
}
