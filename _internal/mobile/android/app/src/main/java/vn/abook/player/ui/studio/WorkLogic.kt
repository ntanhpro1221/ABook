package vn.abook.player.ui.studio

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
        ApplyWhen.Start -> "dùng khi bắt đầu làm sách"
        ApplyWhen.Cast -> "chờ phân vai xong"
        ApplyWhen.Running -> "áp từ chương sau"
        ApplyWhen.Done -> "bấm “Áp dụng thay đổi” ở đầu trang để áp"
        ApplyWhen.Paused -> "chờ áp dụng khi sách chạy tiếp"
    }

    /** Chữ đầu viết hoa - "câu này" đứng đầu câu báo. */
    fun sentence(text: String): String = text.replaceFirstChar { it.uppercase() }

    /** Nhãn nút ("Vai phụ không tên", "Người kể") đứng GIỮA câu thì viết thường chữ đầu. Tên người giữ nguyên. */
    fun midSentence(label: String?): String {
        val text = label.orEmpty()
        return if (text == "Vai phụ không tên" || text == "Người kể") text.replaceFirstChar { it.lowercase() } else text
    }

    /** Tiêu đề thẻ người kể sau khi đã quyết: nói KẾT QUẢ, không lặp tiền tố của nhãn. */
    fun narratorDecidedTitle(current: String, answer: String): String {
        if (answer == "Giữ nguyên") return if (current.isNotEmpty()) "Đoạn này vẫn do $current kể" else "Đoạn này vẫn kể ở ngôi thứ ba"
        if (answer == "Đổi người kể") return "Đoạn này không phải $current kể"
        val name = answer.replace(Regex("^Người kể:\\s*"), "").trim()
        return "Đoạn này do ${name.ifEmpty { answer }} kể"
    }

    /** Hai nút đầu của thẻ người kể và lựa chọn đã ghi (`requested`) ứng với nút nhận. */
    fun narratorButtons(current: String, heading: NarratorHeading?): NarratorButtons {
        val keep = if (current.isNotEmpty()) "Giữ $current" else "Giữ ngôi thứ ba"
        if (heading == null) return NarratorButtons("Kể ngôi thứ ba", keep, "Đổi người kể")
        return if (heading.label.isNotEmpty()) NarratorButtons("${heading.label} kể", keep, "Người kể: ${heading.label}")
        else NarratorButtons("Kể ngôi thứ ba", keep, "Đổi người kể")
    }

    /** Thẻ đã quyết nói KẾT QUẢ thay vì lặp câu hỏi; null = giữ tiêu đề. */
    fun decidedTitle(item: WorkItem): String? {
        val answer = item.requested ?: return null
        if (item.kind == WorkKind.Pronunciation && item.surface != null) {
            return if (answer == item.current) "Giữ: “${item.surface}” đọc là “$answer”" else "“${item.surface}” sẽ đọc là “$answer”"
        }
        val voices = item.voiceChoices.orEmpty()
        if (voices.isNotEmpty()) return voices.firstOrNull { it.label == answer || it.done == answer }?.done
        if (item.kind == WorkKind.Alias) return "“${item.subject ?: item.current}” là ${midSentence(answer)}"
        if (item.kind == WorkKind.Narrator) return narratorDecidedTitle(item.current, answer)
        val count = item.lines?.size ?: 0
        if (count > 0) return "${if (count > 1) "$count câu này" else "Câu này"} của ${midSentence(answer)}"
        return null
    }

    /** Lời mở đầu của hộp việc theo trạng thái sách. */
    fun inboxLead(book: StudioBook): String {
        val first = when {
            book.running && book.paused != null -> "Sách đang tạm dừng; sửa áp khi làm tiếp."
            book.running -> "Máy đang chạy tiếp; sửa áp ở chương sau."
            book.phase == "done" -> "Sửa xong, bấm “Áp dụng thay đổi”."
            else -> "Sách đang dừng; sửa áp khi làm tiếp."
        }
        return "Ưu tiên việc trên. $first"
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
        total -> "Đang chọn cả $total câu"
        0 -> "Chưa chọn câu nào trong $total câu"
        else -> "Đang chọn $picked/$total câu"
    }

    /** Chữ nút "Xem thêm" của thẻ nhóm lớn. */
    fun moreText(shown: Int, total: Int): String = "Xem thêm (đang hiện $shown/$total câu)"

    /** Còn trang ví dụ kế không: số câu đã có / tổng. */
    fun hasMoreExamples(loaded: Int, total: Int?): Boolean = loaded < maxOf(total ?: 0, loaded)

    // ---- bản đã ghi ở máy khác (elsewhere.ts) ----

    /** Câu báo `count` chỗ vừa được sửa ở nơi khác; `was` là điều nơi ấy đã đặt ("" = chưa ai quyết). Trả (tiêu đề, mô tả). */
    fun elsewhereNote(count: Int, was: String): Pair<String, String> = Pair(
        if (count > 1) "$count câu vừa được sửa ở máy hay cửa sổ khác" else "Chỗ này vừa được sửa ở máy hay cửa sổ khác",
        "${if (was.isNotEmpty()) "Trước đó đang là $was" else "Trước đó chưa ai quyết khác"} - lần ghi của bạn đã thay nó.",
    )

    /** `seen` gửi kèm lần ghi: điều thẻ này đang thấy cho từng câu (câu không có thì ""). */
    fun seenFor(lines: List<LineRef>, known: Map<String, String>): JSONObject =
        JSONObject().also { seen -> lines.forEach { seen.put(it.stableId, known[it.stableId].orEmpty()) } }

    /** Phán quyết "Nghe lại" nói bằng lời ("" = chưa ai quyết). */
    fun verdictWord(verdict: String?): String = when (verdict) {
        "ok" -> "“Ổn”"
        "redo" -> "“Cần thu lại”"
        else -> ""
    }

    /** Lựa chọn giọng máy kia đã đặt cho nhân vật, nói bằng lời ("" = không có gì chờ). */
    fun voiceWas(voice: String, gender: String): String = when {
        voice.isNotEmpty() -> "giọng $voice"
        gender == "female" -> "nhân vật nữ"
        gender == "male" -> "nhân vật nam"
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
        val which = if (lines.size > 1) "${lines.size} câu này" else "câu này"
        val summary = if (speaker == item.currentValue) {
            item.keepLabel?.let { "Đã ghi: $it" } ?: "Giữ nguyên: $which của ${WorkLogic.midSentence(item.current)}"
        } else {
            val choice = item.choices.orEmpty().firstOrNull { it.value == speaker }
            "Đã ghi: $which của ${WorkLogic.midSentence(choice?.name ?: choice?.label ?: speaker)}"
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
        return WorkDecision(item.key, "Đã ghi: ${item.keepLabel ?: "Giữ nguyên"}", steps)
    }

    /** `POST /pronunciation` (`PronunciationFix.save`): `seen` là cách đọc thẻ này đang thấy đã ghi. */
    fun pronunciation(item: WorkItem, spoken: String): WorkDecision {
        val surface = item.surface.orEmpty()
        val body = JSONObject().put("surface", surface).put("spokenForm", spoken).put("seen", item.requested.orEmpty())
        val summary = if (spoken == item.current) "Giữ cách đọc “$spoken”" else "Đã ghi: “$surface” đọc là “$spoken”"
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
            action == "keep" -> if (item.current.isNotEmpty()) "Giữ nguyên: đoạn này vẫn do ${item.current} kể" else "Giữ nguyên: đoạn này vẫn kể ở ngôi thứ ba"
            chosen.isNotEmpty() -> "Đã ghi: đoạn này do ${if (section.heading?.narrator == chosen) section.heading.label else chosen} kể"
            else -> "Đã ghi: đoạn này không phải ${item.current} kể"
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
        WorkDecision(item.key, "Đã ghi: ${choice.done ?: choice.label}", listOf(WorkStep("voice", voiceBody(choice.character, choice.gender, choice.preset, choice.avoid))))

    /** "Giữ nguyên" của thẻ giọng: ghi yêu cầu rỗng cho từng người trong `keepCharacters` (thẻ thôi hỏi). */
    fun voiceKeep(item: WorkItem): WorkDecision? =
        item.keepCharacters.takeIf { it.isNotEmpty() }?.let { people ->
            WorkDecision(item.key, "Đã ghi: ${item.keepLabel ?: "Giữ nguyên"}", people.map { WorkStep("voice", voiceBody(it)) })
        }

    /** Đổi giọng một nhân vật từ bảng giọng: `gender` kèm theo khi giọng khác giới đã được hỏi và đồng ý. `seen`: mốc lựa chọn đang chờ bảng này thấy (0 = không). */
    fun voicePick(character: String, name: String, voiceName: String, preset: String, gender: String?, seen: Double): WorkDecision {
        val body = JSONObject().put("character", character).put("preset", preset)
        gender?.let { body.put("gender", it) }
        body.put("seen", seen)
        val tail = if (gender != null) " và là ${if (gender == "female") "nữ" else "nam"}" else ""
        return WorkDecision("voice:$character", "Đã ghi: $name đọc bằng giọng $voiceName$tail", listOf(WorkStep("voice", body)))
    }

    /** Bỏ lựa chọn giọng chưa vào sách (`POST /voice` với `withdraw`) - không giữ 15 giây. */
    fun voiceWithdraw(character: String, requestedAt: Double): WorkDecision =
        WorkDecision("voice:$character", "Đã bỏ lựa chọn giọng", listOf(WorkStep("voice", JSONObject().put("character", character).put("withdraw", true).put("requestedAt", requestedAt))), hold = false)

    /** Bỏ một yêu cầu máy đã từ chối (`RefusedFix`): không hoàn tác được nên không giữ 15 giây. */
    fun dropRefused(item: WorkItem): WorkDecision? {
        val refused = item.refused ?: return null
        val body = JSONObject().put("section", refused.section).put("key", refused.key).put("requestedAt", refused.requestedAt)
        return WorkDecision(item.key, "Đã bỏ yêu cầu này", listOf(WorkStep("pending-changes/withdraw", body)), hold = false)
    }

    /** Phán quyết "Nghe lại" (`POST /review`): `verdict` ok | redo | null (bỏ phán quyết). */
    fun review(stableId: String, chapterId: Int, audioSha256: String, verdict: String?, seen: String?): WorkStep {
        val body = JSONObject().put("stableId", stableId).put("chapterId", chapterId).put("audioSha256", audioSha256)
        body.put("verdict", verdict ?: JSONObject.NULL)
        if (seen != null) body.put("seen", JSONObject().put(stableId, seen))
        return WorkStep("review", body)
    }
}
