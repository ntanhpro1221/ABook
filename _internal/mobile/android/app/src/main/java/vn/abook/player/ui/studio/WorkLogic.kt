package vn.abook.player.ui.studio

import vn.abook.player.S

import androidx.compose.runtime.Immutable
import org.json.JSONArray
import org.json.JSONObject

/** Thay đổi của người nghe vào sách lúc nào (web `decisions.ts ApplyWhen`). */
enum class ApplyWhen { Start, Cast, Running, Done, Paused }

/** Một mảnh câu lời kể: thường, hay tô (tên ứng viên). */
@Immutable
data class NamePart(val text: String, val mark: Boolean)

/** Ba nút đầu của thẻ người kể của đoạn (web `narratorButtons`). */
@Immutable
data class NarratorButtons(val accept: String, val keep: String, val accepted: String)

/** Phạm vi của thẻ chuỗi lượt đối đáp / thẻ 『』: các câu xen kẽ (chương này) hay cả chuỗi (cả cuốn). */
enum class WorkScope { Alternate, All }

/**
 * Logic thuần của "Việc cần duyệt", port từ `ui/src/studio` (decisions.ts, workText.ts, minorGroups.ts, elsewhere.ts, precast.ts `isOpenWork`): cùng điều kiện
 * và cùng chữ với web. Chữ riêng của điện thoại (nút, nhãn) nằm ở [WorkText].
 */
object WorkLogic {
    /** Việc còn chờ người duyệt: chưa quyết, và quyết thì có tác dụng ngay (không tính việc đã quyết hay việc chỉ áp khi phân tích lại). */
    fun isOpen(item: WorkItem): Boolean = item.requested == null && !item.redoOnly

    /** `decisions.ts applyWhen`: lời hứa sau khi ghi một thay đổi, theo trạng thái sách. */
    fun applyWhen(book: StudioBook?): ApplyWhen = when {
        book == null -> ApplyWhen.Paused
        book.phase == "idle" && !book.running && !book.starting -> ApplyWhen.Start
        book.phase == "analysis" || (book.phase == "casting" && !book.castLocked) -> ApplyWhen.Cast
        book.paused != null -> ApplyWhen.Paused
        book.running || book.starting -> ApplyWhen.Running
        else -> if (book.phase == "done") ApplyWhen.Done else ApplyWhen.Paused
    }

    /** Vế sau gạch nối, cho dòng "Đã ghi ... - {vế}". */
    fun pendingNote(when_: ApplyWhen): String = when (when_) {
        ApplyWhen.Start -> S.s_dung_khi_bat_dau_lam_sach_a665a71d
        ApplyWhen.Cast -> S.s_cho_phan_vai_xong_51f41859
        ApplyWhen.Running -> S.s_ap_tu_chuong_sau_8f2706c5
        ApplyWhen.Done -> S.s_bam_ap_dung_thay_doi_o_dau_trang_de_ap_fd47948b
        ApplyWhen.Paused -> S.s_cho_ap_dung_khi_sach_chay_tiep_6f0a3bc6
    }

    /** Chữ đầu viết hoa - "câu này" đứng đầu câu báo. */
    fun sentence(text: String): String = text.replaceFirstChar { it.uppercase() }

    /** Nhãn nút ("Vai phụ không tên", "Người kể") đứng GIỮA câu thì viết thường chữ đầu. Tên người giữ nguyên. */
    fun midSentence(label: String?): String {
        val text = label.orEmpty()
        return if (text == S.s_vai_phu_khong_ten_6395f0d2 || text == S.s_nguoi_ke_fd36cd15) text.replaceFirstChar { it.lowercase() } else text
    }

    /** Tiêu đề thẻ người kể sau khi đã quyết: nói KẾT QUẢ, không lặp tiền tố của nhãn. */
    fun narratorDecidedTitle(current: String, answer: String): String {
        if (answer == S.s_giu_nguyen_1b550a12) return if (current.isNotEmpty()) S.s_doan_nay_van_do_0_ke_1aa31bd2(current) else S.s_doan_nay_van_ke_o_ngoi_thu_ba_ad31af6d
        if (answer == S.s_doi_nguoi_ke_ddc42796) return S.s_doan_nay_khong_phai_0_ke_691681b8(current)
        val name = answer.replace(Regex("^Người kể:\\s*"), "").trim()
        return S.s_doan_nay_do_0_ke_9870e5f7(name.ifEmpty { answer })
    }

    /** Hai nút đầu của thẻ người kể và lựa chọn đã ghi (`requested`) ứng với nút nhận. */
    fun narratorButtons(current: String, heading: NarratorHeading?): NarratorButtons {
        val keep = if (current.isNotEmpty()) S.s_giu_0_b8c06ffa(current) else S.s_giu_ngoi_thu_ba_271d46cb
        if (heading == null) return NarratorButtons(S.s_ke_ngoi_thu_ba_3ba8b1e4, keep, S.s_doi_nguoi_ke_ddc42796)
        return if (heading.label.isNotEmpty()) NarratorButtons(S.s_0_ke_d684eff0(heading.label), keep, S.s_nguoi_ke_0_78e70db0(heading.label))
        else NarratorButtons(S.s_ke_ngoi_thu_ba_3ba8b1e4, keep, S.s_doi_nguoi_ke_ddc42796)
    }

    /** Thẻ đã quyết nói KẾT QUẢ thay vì lặp câu hỏi; null = giữ tiêu đề. */
    fun decidedTitle(item: WorkItem): String? {
        val answer = item.requested ?: return null
        if (item.kind == WorkKind.Pronunciation && item.surface != null) {
            return if (answer == item.current) S.s_giu_0_doc_la_1_f568ced8(item.surface, answer) else S.s_0_se_doc_la_1_e0b21c39(item.surface, answer)
        }
        val voices = item.voiceChoices.orEmpty()
        if (voices.isNotEmpty()) return voices.firstOrNull { it.label == answer || it.done == answer }?.done
        if (item.kind == WorkKind.Alias) return S.s_0_la_1_9ee6c344(item.subject ?: item.current, midSentence(answer))
        if (item.kind == WorkKind.Narrator) return narratorDecidedTitle(item.current, answer)
        val count = item.lines?.size ?: 0
        if (count > 0) return S.s_0_cua_1_c0e3e388(if (count > 1) S.s_0_cau_nay_eeb40df6(count) else S.s_cau_nay_ee66e104, midSentence(answer))
        return null
    }

    /** Lời mở đầu của hộp việc theo trạng thái sách. */
    fun inboxLead(book: StudioBook): String {
        val first = when {
            book.running && book.paused != null -> S.s_sach_dang_tam_dung_sua_ap_khi_lam_tiep_12a374a4
            book.running -> S.s_may_dang_chay_tiep_sua_ap_o_chuong_sau_5482c856
            book.phase == "done" -> S.s_sua_xong_bam_ap_dung_thay_doi_43042cc6
            else -> S.s_sach_dang_dung_sua_ap_khi_lam_tiep_9778f9fd
        }
        return S.s_uu_tien_viec_tren_0_c06ed70f(first)
    }

    /**
     * Câu lời kể chia thành mảnh thường / mảnh tô ở mỗi chỗ có một trong `names` (dạng đã hạ chữ): nguyên chữ, không phân biệt hoa thường, tên dài trước,
     * và chỉ khi hai bên không dính chữ / số. Quét tay, không regex (ICU của Android khác JVM ở lớp ký tự).
     */
    fun markNames(text: String, names: List<String>): List<NamePart> {
        val forms = names.map { it.trim().lowercase() }.filter { it.isNotEmpty() }.distinct().sortedByDescending { it.length }
        val lower = text.lowercase()
        if (forms.isEmpty() || lower.length != text.length) return listOf(NamePart(text, false))
        val parts = ArrayList<NamePart>()
        var last = 0
        var index = 0
        while (index < lower.length) {
            val form = if (index > 0 && lower[index - 1].isLetterOrDigit()) null else forms.firstOrNull { lower.startsWith(it, index) && !(index + it.length < lower.length && lower[index + it.length].isLetterOrDigit()) }
            if (form == null) {
                index++
                continue
            }
            if (index > last) parts += NamePart(text.substring(last, index), false)
            parts += NamePart(text.substring(index, index + form.length), true)
            index += form.length
            last = index
        }
        if (last < text.length || parts.isEmpty()) parts += NamePart(text.substring(last), false)
        return parts
    }

    /** Số thay đổi đang chờ áp dụng trong các thẻ đã quyết: hai thẻ cùng quyết một câu là MỘT thay đổi; "giữ" cách đang đọc không tính. */
    fun waitingChanges(decided: List<WorkItem>): Int {
        val changes = HashSet<String>()
        for (item in decided) {
            if (item.requested == item.current) continue
            val ids = item.lines?.map { it.stableId }?.sorted().orEmpty()
            changes += if (ids.isNotEmpty()) "lines:${ids.joinToString(",")}" else "key:${item.key}"
        }
        return changes.size
    }

    /** Mẫu thẻ của một việc: cùng thứ tự rẽ nhánh với `Card` của WorkInbox.tsx. */
    fun template(item: WorkItem): CardTemplate = when {
        item.kind == WorkKind.Audio -> CardTemplate.Listen
        item.kind == WorkKind.Pronunciation && item.surface != null -> CardTemplate.Reading
        item.kind == WorkKind.Narrator && item.narratorSection != null -> CardTemplate.Choose
        item.kind == WorkKind.Refused && item.refused != null -> CardTemplate.Refused
        item.kind == WorkKind.VoiceWish -> CardTemplate.Voice
        !item.voiceChoices.isNullOrEmpty() -> CardTemplate.Voice
        item.lines != null && item.choices != null -> CardTemplate.Choose
        else -> CardTemplate.Plain
    }

    /**
     * Bộ bài: việc còn chờ, theo thứ tự máy gửi (lợi nhất trước), bỏ thẻ đang chờ gửi (`held`); thẻ "Bỏ qua" (`skipped`, theo thứ tự bấm) xuống cuối.
     * Sách đang chạy thì thẻ mới tự rơi vào cuối nhóm chưa bỏ qua, không xáo thứ tự.
     */
    fun deck(items: List<WorkItem>, held: Set<String>, skipped: List<String>): List<WorkItem> {
        val open = items.filter { isOpen(it) && it.key !in held }
        val later = skipped.mapNotNull { key -> open.firstOrNull { it.key == key } }
        return open.filter { it.key !in skipped } + later
    }

    // ---- thẻ nhóm (minorGroups.ts) ----

    /** "Giữ nguyên" một thẻ là những yêu cầu nào: thẻ nhóm giữ người của từng vai; thẻ thường giữ người đang nói cho mọi câu; không giữ được thì rỗng. */
    fun keepRequests(item: WorkItem): List<SpeakerRequest> {
        if (item.keepGroups.isNotEmpty()) return item.keepGroups.filter { it.lines.isNotEmpty() }
        val lines = item.lines
        val current = item.currentValue
        if (!lines.isNullOrEmpty() && current != null && current.isNotEmpty()) return listOf(SpeakerRequest(lines, current))
        return emptyList()
    }

    /** Câu còn được chọn (giữ thứ tự của thẻ). */
    fun pickedLines(lines: List<LineRef>, left: Set<String>): List<LineRef> = lines.filter { it.stableId !in left }

    /** Bật / tắt một câu: trả tập mới. */
    fun toggleLine(left: Set<String>, stableId: String): Set<String> = if (stableId in left) left - stableId else left + stableId

    /** Dòng nói đang chọn bao nhiêu câu, cho thẻ nhóm. */
    fun pickNote(picked: Int, total: Int): String = when (picked) {
        total -> S.s_dang_chon_ca_0_cau_504a9b88(total)
        0 -> S.s_chua_chon_cau_nao_trong_0_cau_0e18fa35(total)
        else -> S.s_dang_chon_0_1_cau_3dce2fb6(picked, total)
    }

    /** Chữ nút "Xem thêm" của thẻ nhóm lớn. */
    fun moreText(shown: Int, total: Int): String = S.s_xem_them_dang_hien_0_1_cau_ebb4ffe0(shown, total)

    /** Còn trang ví dụ kế không: số câu đã có / tổng. */
    fun hasMoreExamples(loaded: Int, total: Int?): Boolean = loaded < maxOf(total ?: 0, loaded)

    // ---- bản đã ghi ở máy khác (elsewhere.ts) ----

    /** Câu báo `count` chỗ vừa được sửa ở nơi khác; `was` là điều nơi ấy đã đặt ("" = chưa ai quyết). Trả (tiêu đề, mô tả). */
    fun elsewhereNote(count: Int, was: String): Pair<String, String> = Pair(
        if (count > 1) S.s_0_cau_vua_duoc_sua_o_may_hay_cua_so_khac_1f803269(count) else S.s_cho_nay_vua_duoc_sua_o_may_hay_cua_so_khac_66af9a6c,
        S.s_0_lan_ghi_cua_ban_da_thay_no_420a088b(if (was.isNotEmpty()) S.s_truoc_do_dang_la_0_4ed72a4f(was) else S.s_truoc_do_chua_ai_quyet_khac_1f656a59),
    )

    /** `seen` gửi kèm lần ghi: điều thẻ này đang thấy cho từng câu (câu không có thì ""). */
    fun seenFor(lines: List<LineRef>, known: Map<String, String>): JSONObject =
        JSONObject().also { seen -> lines.forEach { seen.put(it.stableId, known[it.stableId].orEmpty()) } }

    /** Phán quyết "Nghe lại" nói bằng lời ("" = chưa ai quyết). */
    fun verdictWord(verdict: String?): String = when (verdict) {
        "ok" -> S.s_on_742e24ad
        "redo" -> S.s_can_thu_lai_9d482626
        else -> ""
    }

    /** Lựa chọn giọng máy kia đã đặt cho nhân vật, nói bằng lời ("" = không có gì chờ). */
    fun voiceWas(voice: String, gender: String): String = when {
        voice.isNotEmpty() -> S.s_giong_0_e048b478(voice)
        gender == "female" -> S.s_nhan_vat_nu_36236b63
        gender == "male" -> S.s_nhan_vat_nam_8de64942
        else -> ""
    }
}

/** Một POST của một quyết định: `endpoint` là khoá trong [vn.abook.player.StudioPaths.WRITES]. */
@Immutable
data class WorkStep(val endpoint: String, val body: JSONObject)

/**
 * Một quyết định của người duyệt, chưa gửi. `key` là khoá thẻ (cùng khoá thì quyết định sau thay quyết định trước); `summary` là câu báo "Đã ghi: ..." trên
 * dải hoàn tác. `hold`: giữ 15 giây trước khi gửi, cho "Hoàn tác" - false cho việc không hoàn tác được (bỏ một yêu cầu đã bị từ chối).
 */
@Immutable
data class WorkDecision(val key: String, val summary: String, val steps: List<WorkStep>, val hold: Boolean = true, val names: Map<String, String> = emptyMap())

/** Dựng thân yêu cầu cho từng kiểu quyết định - port nguyên từ `SpeakerFix` / `PronunciationFix` / `NarratorFix` / `VoiceFix` / `RefusedFix` của WorkInbox.tsx. */
object WorkDecisions {
    /** Thời gian giữ trước khi gửi, để "Hoàn tác" (`decisions.ts UNDO_MS`). */
    const val UNDO_MS = 15_000L

    private fun array(lines: List<LineRef>) = JSONArray().also { array -> lines.forEach { array.put(JSONObject().put("stableId", it.stableId).put("textSha256", it.textSha256)) } }

    /** Các câu một lần bấm gán người nói: câu còn chọn của thẻ nhóm, hay cả chuỗi khi phạm vi "Cả chuỗi", không thì các câu của thẻ. */
    fun linesOf(item: WorkItem, scope: WorkScope, picked: List<LineRef>?): List<LineRef> =
        picked ?: if (scope == WorkScope.All && item.allLines != null) item.allLines else item.lines.orEmpty()

    /** `POST /speaker` cho một lựa chọn người nói (`SpeakerFix.save`). `newGender`: người mới ("male", "female", "unknown"), null = người đã có. */
    fun speaker(item: WorkItem, speaker: String, scope: WorkScope, picked: List<LineRef>?, newGender: String? = null): WorkDecision {
        val lines = linesOf(item, scope, picked)
        val body = JSONObject().put("lines", array(lines)).put("speaker", speaker).put("newGender", newGender.orEmpty()).put("seen", WorkLogic.seenFor(lines, item.seen))
        // "Một người hai tên": gộp là quyết cả ở cấp tên.
        if (item.kind == WorkKind.Alias && speaker != item.currentValue) body.put("alias", item.currentValue.orEmpty())
        // Thẻ 『』 phạm vi "Cả cuốn": quy ước của cả cuốn, các phần sau tự áp.
        if (item.kind == WorkKind.Bracket && scope == WorkScope.All) body.put("bracketRule", true)
        val which = if (lines.size > 1) S.s_0_cau_nay_eeb40df6(lines.size) else S.s_cau_nay_c70feb8f
        val summary = if (speaker == item.currentValue) {
            item.keepLabel?.let { S.s_da_ghi_0_5450366f(it) } ?: S.s_giu_nguyen_0_cua_1_f0574c99(which, WorkLogic.midSentence(item.current))
        } else {
            val choice = item.choices.orEmpty().firstOrNull { it.value == speaker }
            S.s_da_ghi_0_cua_1_36d6075b(which, WorkLogic.midSentence(choice?.name ?: choice?.label ?: speaker))
        }
        // Tên hiện của từng người nói (mã -> tên) để câu "vừa được sửa ở máy khác" nói tên người, không nói mã.
        val names = item.choices.orEmpty().associate { it.value to (it.name ?: it.label) } + (item.currentValue?.let { mapOf(it to item.current) } ?: emptyMap())
        return WorkDecision(item.key, summary, listOf(WorkStep("speaker", body)), names = names)
    }

    /** "Giữ nguyên" của thẻ nhóm: mỗi vai giữ người của nó, một yêu cầu cho mỗi vai (`keepAll`). Rỗng nếu thẻ không giữ được. */
    fun keepAll(item: WorkItem): WorkDecision? {
        val requests = WorkLogic.keepRequests(item)
        if (requests.isEmpty()) return null
        val steps = requests.map { request ->
            WorkStep("speaker", JSONObject().put("lines", array(request.lines)).put("speaker", request.speaker).put("seen", WorkLogic.seenFor(request.lines, item.seen)))
        }
        return WorkDecision(item.key, S.s_da_ghi_0_5450366f(item.keepLabel ?: S.s_giu_nguyen_1b550a12), steps)
    }

    /** `POST /pronunciation` (`PronunciationFix.save`): `seen` là cách đọc thẻ này đang thấy đã ghi. */
    fun pronunciation(item: WorkItem, spoken: String): WorkDecision {
        val surface = item.surface.orEmpty()
        val body = JSONObject().put("surface", surface).put("spokenForm", spoken).put("seen", item.requested.orEmpty())
        val summary = if (spoken == item.current) S.s_giu_cach_doc_0_ad3b6d08(spoken) else S.s_da_ghi_0_doc_la_1_2c14f196(surface, spoken)
        return WorkDecision(item.key, summary, listOf(WorkStep("pronunciation", body)))
    }

    /** Phép kiểm cách đọc trước khi giữ 15 giây (nghe được là lưu được): `POST /pronunciation/check`. */
    fun pronunciationCheck(item: WorkItem, spoken: String): WorkStep =
        WorkStep("pronunciation/check", JSONObject().put("surface", item.surface.orEmpty()).put("spokenForm", spoken))

    /** "Nghe thử" một cách đọc: `POST /pronunciation/preview`. */
    fun pronunciationPreview(item: WorkItem, spoken: String): WorkStep =
        WorkStep("pronunciation/preview", JSONObject().put("surface", item.surface.orEmpty()).put("spokenForm", spoken))

    /** `POST /narrator-section` (`NarratorFix.save`): `action` accept | keep | choose. */
    fun narrator(item: WorkItem, action: String, narrator: String? = null): WorkDecision? {
        val section = item.narratorSection ?: return null
        val body = JSONObject().put("chapterIndex", section.chapterIndex).put("fromSeq", section.fromSeq).put("toSeq", section.toSeq).put("action", action)
        if (narrator != null) body.put("narrator", narrator)
        val chosen = when (action) {
            "accept" -> section.heading?.narrator.orEmpty()
            "choose" -> narrator.orEmpty()
            else -> ""
        }
        val summary = when {
            action == "keep" -> if (item.current.isNotEmpty()) S.s_giu_nguyen_doan_nay_van_do_0_ke_dffb3797(item.current) else S.s_giu_nguyen_doan_nay_van_ke_o_ngoi_thu_ba_f0be91ed
            chosen.isNotEmpty() -> S.s_da_ghi_doan_nay_do_0_ke_99b4e3f7(if (section.heading?.narrator == chosen) section.heading.label else chosen)
            else -> S.s_da_ghi_doan_nay_khong_phai_0_ke_71722738(item.current)
        }
        return WorkDecision(item.key, summary, listOf(WorkStep("narrator-section", body)))
    }

    private fun voiceBody(character: String, gender: String? = null, preset: String? = null, avoid: String? = null) =
        JSONObject().put("character", character).also { body ->
            gender?.let { body.put("gender", it) }
            preset?.let { body.put("preset", it) }
            avoid?.let { body.put("avoid", it) }
        }

    /** `POST /voice` cho một nút của thẻ giọng / giới (`VoiceFix`). */
    fun voice(item: WorkItem, choice: VoiceOption): WorkDecision =
        WorkDecision(item.key, S.s_da_ghi_0_5450366f(choice.done ?: choice.label), listOf(WorkStep("voice", voiceBody(choice.character, choice.gender, choice.preset, choice.avoid))))

    /** "Giữ nguyên" của thẻ giọng: ghi yêu cầu rỗng cho từng người trong `keepCharacters` (thẻ thôi hỏi). */
    fun voiceKeep(item: WorkItem): WorkDecision? =
        item.keepCharacters.takeIf { it.isNotEmpty() }?.let { people ->
            WorkDecision(item.key, S.s_da_ghi_0_5450366f(item.keepLabel ?: S.s_giu_nguyen_1b550a12), people.map { WorkStep("voice", voiceBody(it)) })
        }

    /** Đổi giọng một nhân vật từ bảng giọng: `gender` kèm theo khi giọng khác giới đã được hỏi và đồng ý. `seen`: mốc lựa chọn đang chờ bảng này thấy (0 = không). */
    fun voicePick(character: String, name: String, voiceName: String, preset: String, gender: String?, seen: Double): WorkDecision {
        val body = JSONObject().put("character", character).put("preset", preset)
        gender?.let { body.put("gender", it) }
        body.put("seen", seen)
        val tail = if (gender != null) S.s_va_la_0_3ac4fdbc(if (gender == "female") S.s_nu_316c30fd else "nam") else ""
        return WorkDecision("voice:$character", S.s_da_ghi_0_doc_bang_giong_1_2_27a9c30c(name, voiceName, tail), listOf(WorkStep("voice", body)))
    }

    /** Bỏ lựa chọn giọng chưa vào sách (`POST /voice` với `withdraw`) - không giữ 15 giây. */
    fun voiceWithdraw(character: String, requestedAt: Double): WorkDecision =
        WorkDecision("voice:$character", S.s_da_bo_lua_chon_giong_1aff3c76, listOf(WorkStep("voice", JSONObject().put("character", character).put("withdraw", true).put("requestedAt", requestedAt))), hold = false)

    /** Bỏ một yêu cầu máy đã từ chối (`RefusedFix`): không hoàn tác được nên không giữ 15 giây. */
    fun dropRefused(item: WorkItem): WorkDecision? {
        val refused = item.refused ?: return null
        val body = JSONObject().put("section", refused.section).put("key", refused.key).put("requestedAt", refused.requestedAt)
        return WorkDecision(item.key, S.s_da_bo_yeu_cau_nay_5eec8a27, listOf(WorkStep("pending-changes/withdraw", body)), hold = false)
    }

    /** Phán quyết "Nghe lại" (`POST /review`): `verdict` ok | redo | null (bỏ phán quyết). */
    fun review(stableId: String, chapterId: Int, audioSha256: String, verdict: String?, seen: String?): WorkStep {
        val body = JSONObject().put("stableId", stableId).put("chapterId", chapterId).put("audioSha256", audioSha256)
        body.put("verdict", verdict ?: JSONObject.NULL)
        if (seen != null) body.put("seen", JSONObject().put(stableId, seen))
        return WorkStep("review", body)
    }
}
