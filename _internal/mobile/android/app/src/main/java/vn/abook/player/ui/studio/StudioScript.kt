package vn.abook.player.ui.studio

import vn.abook.player.ui.data.dotJoined
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.ClipSpec
import vn.abook.player.ClipState
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPaths

// "Kịch bản" (NATIVE_REMOTE_STUDIO.md §6.8): đọc cả chương như kịch bản - câu nào của ai - và đổi người nói / chữ đem đọc của từng câu. Port từ ScriptTab.tsx
// (webui/casting_review.py). Chữ của truyện KHÔNG bao giờ bị sửa: "chữ đem đọc" chỉ đổi điều máy đọc, sách giữ nguyên chữ của nó.
// Bỏ so với web (việc của máy tính): tìm-thay thế cả cuốn, chọn nhiều câu, kéo, người mới, cảm xúc / mức, loại đoạn.

/** Một chương trong mục lục `GET /casting`. */
@Immutable
data class ScriptEntry(val chapterId: Int, val index: Int, val title: String, val lines: Int, val speech: Int, val hints: Int, val decided: Int)

@Immutable
data class ScriptContents(val castReady: Boolean, val chapters: List<ScriptEntry>)

@Immutable
data class ScriptPerson(val value: String, val label: String, val lines: Int)

/** Chỗ máy nghi ai nói câu này (web `Hint`). */
@Immutable
data class ScriptHint(val kind: String, val note: String, val suggest: String?)

/** Điều người nghe đã ghi cho người nói của câu (web `Wish`): `state` là pending | applied | refused. */
@Immutable
data class ScriptWish(val value: String, val label: String, val state: String, val reason: String?)

/** Cách đọc câu người nghe đã ghi (web `LineWish`): cái ta cần là `spoken` ("" = trả về chữ sách, null = không đổi chữ). */
@Immutable
data class ScriptLineWish(val kind: String, val emotion: String, val intensity: Int?, val spoken: String?, val state: String)

@Immutable
data class ScriptLine(
    val segmentId: Int,
    val stableId: String,
    val textSha256: String,
    val seq: Int,
    val text: String,
    /** narration | dialogue | thought. */
    val kind: String,
    val current: String,
    val label: String,
    val editable: Boolean,
    val hasAudio: Boolean,
    val hint: ScriptHint?,
    val wish: ScriptWish?,
    /** Chữ người nghe sửa đang được đọc thay câu gốc (đã áp); null = đọc đúng chữ sách. */
    val spoken: String?,
    val lineWish: ScriptLineWish?,
)

/** Một chương như `GET /casting/<chapterId>` mô tả (web `ChapterScript`). */
@Immutable
data class ChapterScript(
    val chapterId: Int,
    val index: Int,
    val title: String,
    val previous: Int?,
    val next: Int?,
    val castReady: Boolean,
    val cast: List<ScriptPerson>,
    val others: List<ScriptPerson>,
    val lines: List<ScriptLine>,
)

internal object StudioScriptJson {
    private fun optInt(json: JSONObject, key: String): Int? = if (!json.has(key) || json.isNull(key)) null else json.optInt(key)

    private fun person(json: JSONObject) = ScriptPerson(json.text("value"), json.text("label"), json.optInt("lines"))

    private fun line(json: JSONObject) = ScriptLine(
        segmentId = json.optInt("segmentId"),
        stableId = json.text("stableId"),
        textSha256 = json.text("textSha256"),
        seq = json.optInt("seq"),
        text = json.text("text"),
        kind = json.text("kind"),
        current = json.text("current"),
        label = json.text("label"),
        editable = json.optBoolean("editable"),
        hasAudio = json.optBoolean("hasAudio"),
        hint = json.optJSONObject("hint")?.let { ScriptHint(it.text("kind"), it.text("note"), it.textOrNull("suggest")?.takeIf { s -> s.isNotEmpty() }) },
        wish = json.optJSONObject("wish")?.let { ScriptWish(it.text("value"), it.text("label"), it.text("state"), it.textOrNull("reason")) },
        spoken = json.textOrNull("spoken"),
        lineWish = json.optJSONObject("lineWish")?.let { ScriptLineWish(it.text("kind"), it.text("emotion"), optInt(it, "intensity"), it.textOrNull("spoken"), it.text("state")) },
    )

    fun contents(json: JSONObject) = ScriptContents(
        json.optBoolean("castReady"),
        json.optJSONArray("chapters").objects().map { ScriptEntry(it.optInt("chapterId"), it.optInt("index"), it.text("title"), it.optInt("lines"), it.optInt("speech"), it.optInt("hints"), it.optInt("decided")) },
    )

    fun chapter(json: JSONObject) = ChapterScript(
        chapterId = json.optInt("chapterId"),
        index = json.optInt("index"),
        title = json.text("title"),
        previous = optInt(json, "previous"),
        next = optInt(json, "next"),
        castReady = json.optBoolean("castReady"),
        cast = json.optJSONArray("cast").objects().map(::person),
        others = json.optJSONArray("others").objects().map(::person),
        lines = json.optJSONArray("lines").objects().map(::line).filter { it.stableId.isNotEmpty() },
    )
}

/** Bộ lọc của danh sách câu (web `Filter`). */
enum class ScriptFilter(val label: String) { All("Cả chương"), Speech("Chỉ lời nói"), Doubt("Máy nghi") }

/** Một câu hiện ra, kèm cờ "chỉ làm ngữ cảnh" (câu trước chỗ nghi, hiện mờ). */
@Immutable
data class ShownLine(val line: ScriptLine, val context: Boolean)

object ScriptLogic {
    /** Người nói cố định luôn chọn được (web `FIXED`). */
    const val NARRATOR = "NARRATOR"
    const val UNNAMED = "UNNAMED"
    val FIXED = listOf(ScriptPerson(NARRATOR, "Người kể", 0), ScriptPerson(UNNAMED, "Vai phụ không tên", 0))

    fun isSpeech(line: ScriptLine) = line.kind == "dialogue" || line.kind == "thought"

    /** Người đang tính cho câu: đang chờ đổi thì theo người mới. */
    fun speaker(line: ScriptLine): String = if (line.wish?.state == "pending") line.wish.value else line.current

    fun speakerLabel(line: ScriptLine): String = if (line.wish?.state == "pending") line.wish.label else line.label

    /** Câu hiện ra theo bộ lọc; "Máy nghi" giữ câu nói liền trước mỗi chỗ nghi làm ngữ cảnh (mờ) (web `visibleLines`). */
    fun visible(lines: List<ScriptLine>, filter: ScriptFilter): List<ShownLine> = when (filter) {
        ScriptFilter.All -> lines.map { ShownLine(it, false) }
        ScriptFilter.Speech -> lines.filter(::isSpeech).map { ShownLine(it, false) }
        ScriptFilter.Doubt -> buildList {
            var previous: ScriptLine? = null
            for (line in lines) {
                if (!isSpeech(line)) continue
                if (line.hint != null) {
                    val before = previous
                    if (before != null && none { it.line.stableId == before.stableId }) add(ShownLine(before, true))
                    add(ShownLine(line, false))
                }
                previous = line
            }
        }
    }

    fun doubts(lines: List<ScriptLine>): Int = lines.count { isSpeech(it) && it.hint != null }

    /** Tên hiện của một người nói theo mã (để nói "trước đó đang là ..."). */
    fun nameOf(script: ChapterScript, value: String): String =
        (script.cast + script.others + FIXED).firstOrNull { it.value == value }?.label ?: value

    /** Mọi người chọn được cho một câu: người của chương, người khác, rồi hai vai cố định (không trùng mã). */
    fun people(script: ChapterScript): List<ScriptPerson> {
        val seen = HashSet<String>()
        return (script.cast + script.others + FIXED).filter { seen.add(it.value) }
    }

    /** Chỉ ghi điều KHÁC giữa các chương: chương không có câu nói nào mới ghi "chỉ lời kể", rồi tới chỗ nghi và việc đã quyết. */
    fun extras(entry: ScriptEntry): String = listOfNotNull(
        "chỉ lời kể".takeIf { entry.speech == 0 }, "${entry.hints} chỗ nghi".takeIf { entry.hints > 0 }, "${entry.decided} đã quyết".takeIf { entry.decided > 0 },
    ).dotJoined()

    fun chapterLabel(entry: ScriptEntry) = entry.title.ifEmpty { "Chương ${entry.index}" }

    /** `seen` của lần sửa người nói (`seenFor`): điều màn này đang thấy cho câu - người đang chờ đổi, "" nếu chưa ai quyết. */
    fun seenSpeaker(line: ScriptLine): JSONObject =
        WorkLogic.seenFor(listOf(LineRef(line.stableId, line.textSha256)), mapOf(line.stableId to (line.wish?.value ?: "")))

    /** `POST /speaker`: đổi người nói của một câu. */
    fun assign(line: ScriptLine, person: ScriptPerson): WorkDecision {
        val ref = LineRef(line.stableId, line.textSha256)
        val body = JSONObject()
            .put("lines", org.json.JSONArray().put(JSONObject().put("stableId", ref.stableId).put("textSha256", ref.textSha256)))
            .put("speaker", person.value).put("newGender", "").put("seen", seenSpeaker(line))
        val summary = if (person.value == line.current) "Giữ nguyên: câu này của ${line.label}" else "Đã ghi: câu này của ${person.label}"
        return WorkDecision("line:${line.stableId}", summary, listOf(WorkStep("speaker", body)))
    }

    /** Chữ đem đọc của câu: ô trống hay đúng chữ sách = trả về chữ sách (""). Null = không đổi gì. */
    fun spokenChange(line: ScriptLine, typed: String): String? {
        val cleaned = typed.replace(Regex("\\s+"), " ").trim()
        val reading = (line.spoken ?: line.text).replace(Regex("\\s+"), " ").trim()
        if (cleaned == reading) return null
        if (cleaned.isEmpty()) return if (line.spoken != null && line.spoken.isNotEmpty()) "" else null
        return if (cleaned == line.text.trim()) "" else cleaned
    }

    /** `seen` của lần sửa cách đọc một câu: cách đọc màn này đang thấy (bỏ trạng thái chờ / đã áp), null = chưa ai sửa câu này (web `seenDelivery`). */
    fun seenDelivery(wish: ScriptLineWish?): Any {
        if (wish == null) return JSONObject.NULL
        val seen = JSONObject().put("kind", wish.kind).put("emotion", wish.emotion).put("intensity", wish.intensity ?: JSONObject.NULL)
        if (wish.spoken != null) seen.put("spoken", wish.spoken)
        return seen
    }

    /** `POST /line`: chữ đem đọc của một câu. */
    fun speak(line: ScriptLine, spoken: String): WorkDecision {
        val body = JSONObject().put("stableId", line.stableId).put("textSha256", line.textSha256).put("spoken", spoken).put("seen", seenDelivery(line.lineWish))
        val summary = if (spoken.isEmpty()) "Câu này trở về chữ của sách" else "Đã ghi: câu này đọc là “$spoken”"
        return WorkDecision("spoken:${line.stableId}", summary, listOf(WorkStep("line", body)))
    }

    /** Câu như đã lưu: điều đang giữ cho "Hoàn tác" hiện như đã ghi. */
    fun withHeld(script: ChapterScript, held: WorkDecision?): ChapterScript {
        if (held == null) return script
        val step = held.steps.firstOrNull() ?: return script
        return when {
            held.key.startsWith("line:") -> {
                val id = held.key.removePrefix("line:")
                val value = step.body.optString("speaker")
                val label = nameOf(script, value)
                script.copy(lines = script.lines.map { if (it.stableId == id) it.copy(wish = ScriptWish(value, label, if (value == it.current) "applied" else "pending", null)) else it })
            }
            held.key.startsWith("spoken:") -> {
                val id = held.key.removePrefix("spoken:")
                val spoken = step.body.optString("spoken")
                script.copy(lines = script.lines.map { if (it.stableId == id) it.copy(lineWish = (it.lineWish ?: ScriptLineWish("", "", null, null, "pending")).copy(spoken = spoken, state = "pending")) else it })
            }
            else -> script
        }
    }
}

object ScriptText {
    const val TITLE = "Kịch bản"
    const val LOADING = "Đang tải kịch bản"
    const val EMPTY = "Chương này chưa có câu nào."
    const val NOT_READY = "Phân vai chưa xong - kịch bản hiện ra sau bước ấy."
    const val CHAPTERS = "Đổi chương"
    const val PREVIOUS = "Chương trước"
    const val NEXT = "Chương sau"
    const val WHO = "Ai nói câu này"
    const val SPOKEN = "Chữ đem đọc"
    const val SPOKEN_HINT = "Chỉ sửa chữ đem đọc; sách giữ nguyên chữ của nó. Ô trống là đọc đúng chữ của sách."
    const val SAVE = "Lưu cho câu này"
    const val ORIGINAL = "Dùng chữ gốc"
    const val CANCEL = "Huỷ"
    const val NARRATION = "Lời kể"
    const val CONTEXT = "câu trước chỗ nghi"
    const val READ_AS = "Đọc là"
    const val PENDING = "chờ áp dụng"

    fun doubt(count: Int) = "Máy nghi · $count"
    fun suggest(note: String, suggest: String?) = if (suggest.isNullOrEmpty()) note else "$note · gợi ý: $suggest"
    fun line(seq: Int) = "Câu $seq"
}

/**
 * "Kịch bản" của một dự án: một chương một màn. Hỏi mục lục `GET /casting` rồi chương đang xem `GET /casting/<id>`; chỉ nạp lại sau khi chính điện thoại này gửi xong
 * một quyết định. Đổi người nói / chữ đem đọc đi đường của thẻ "Ai nói câu này": giữ 15 giây cho "Hoàn tác" rồi gửi một lần ([StudioDecisions]).
 */
@Stable
class StudioScriptState(
    val session: StudioSession,
    val bookId: String,
    first: Int? = null,
    hold: suspend (Long) -> Unit = { delay(it) },
) {
    val decisions = StudioDecisions(session, bookId, hold) { reload() }

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    var contents by mutableStateOf<ScriptContents?>(null)
        private set

    var script by mutableStateOf<ChapterScript?>(null)
        private set

    /** Chương đang xem (mã chương); null = chưa chọn, sẽ lấy chương đầu. */
    var chapter by mutableStateOf(first)
        private set

    var error by mutableStateOf<StudioError?>(null)
        private set

    var filter by mutableStateOf(ScriptFilter.All)

    /** Lời nói điều vừa xảy ra (lỗi gửi...) - rỗng khi không có. */
    val notice: String get() = decisions.notice

    suspend fun run() {
        load()
    }

    /** Mục lục rồi chương đang chọn (chương đầu nếu chưa chọn). */
    suspend fun load() {
        try {
            val loaded = session.source.castingContents(session.computer, bookId)
            contents = loaded
            if (chapter == null) chapter = loaded.chapters.firstOrNull()?.chapterId
            error = null
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Throwable) {
            fail(failure)
            return
        }
        reload()
    }

    /** Nạp lại chương đang xem (sau một lần gửi). */
    suspend fun reload() {
        val id = chapter ?: return
        try {
            script = session.source.castingChapter(session.computer, bookId, id)
            error = null
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Throwable) {
            fail(failure)
        }
    }

    private fun fail(failure: Throwable) {
        val mapped = StudioErrors.of(failure)
        session.note(mapped)
        error = mapped as? StudioError ?: StudioError.Server(StudioErrors.UNEXPECTED, 0)
    }

    fun retry() {
        session.scope.launch { load() }
    }

    /** Sang chương khác: dừng tiếng, gửi nốt quyết định đang giữ rồi nạp chương mới. */
    fun open(chapterId: Int) {
        if (chapterId == chapter) return
        decisions.flush()
        session.clips?.stop()
        chapter = chapterId
        script = null
        session.scope.launch { reload() }
    }

    /** Chương đang xem, như đã lưu (kể cả điều đang giữ). */
    fun shown(): ChapterScript? = script?.let { ScriptLogic.withHeld(it, decisions.held?.decision) }

    fun assign(line: ScriptLine, person: ScriptPerson) = decisions.hold(ScriptLogic.assign(line, person))

    /** Lưu chữ đem đọc của một câu; không đổi gì thì không gửi. */
    fun speak(line: ScriptLine, typed: String): Boolean {
        val spoken = ScriptLogic.spokenChange(line, typed) ?: return false
        decisions.hold(ScriptLogic.speak(line, spoken))
        return true
    }

    fun play(line: ScriptLine) {
        session.clips?.toggle(clipId(line), ClipSpec(session.computer, StudioPaths.sample(bookId, line.segmentId)))
    }

    /** Rời màn: gửi nốt điều đang giữ và dừng tiếng. */
    fun leave() {
        decisions.flush()
        session.clips?.stop()
    }

    companion object {
        fun clipId(line: ScriptLine) = "script-${line.segmentId}"
    }
}
