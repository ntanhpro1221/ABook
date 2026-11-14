package vn.abook.player.ui.studio

import vn.abook.player.S

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors

/** Một quyết định đang chờ gửi: `id` phân biệt hai lần giữ cùng khoá để hẹn giờ cũ không gửi nhầm. */
class HeldDecision(val id: Int, val decision: WorkDecision)

/**
 * Hàng chờ gửi quyết định của người duyệt, dùng chung cho "Việc cần duyệt" và bảng giọng (NATIVE_REMOTE_STUDIO.md §2.7, §4.4, §13.1-6):
 * - Quyết xong thì thân yêu cầu CHƯA gửi: giữ [WorkDecisions.UNDO_MS] cho "Hoàn tác"; bấm thì bỏ hẳn tại máy, hết giờ thì gửi MỘT lần.
 * - Một lúc chỉ giữ một quyết định: quyết định thẻ khác thì cái trước gửi ngay; cùng khoá thì cái sau thay cái trước (không gửi cái cũ đè cái mới).
 * - Rời màn thì [flush]: gửi ngay, không mất việc người dùng đã quyết. Giữ trong phạm vi của phiên nên Back không huỷ; tiến trình bị giết trong 15 giây thì mất
 *   (đã chấp nhận, §13.1-6).
 * - Gửi hỏng KHÔNG bao giờ tự gửi lại: thẻ trở về bộ bài, một dòng nói vì sao. Câu đã đổi (409, hay 400 máy từ chối câu) thì nạp lại bộ bài.
 *
 * `after(sent)`: gọi sau mỗi lần gửi xong (true) hay hỏng (false) để các màn nạp lại; `wait` đổi được để thử không cần đợi thật.
 */
@Stable
class StudioDecisions(
    private val session: StudioSession,
    private val bookId: String,
    private val wait: suspend (Long) -> Unit = { delay(it) },
    private val after: suspend (sent: Boolean) -> Unit = {},
) {
    /** The player persists first, then offers the same strip with receipt-bound undo. Studio keeps its existing hold. */
    var persistImmediately: Boolean = false
    var busy by mutableStateOf(false)
        private set
    private var saved = false
    private var undoSteps = emptyList<WorkStep>()
    /** Quyết định đang được giữ cho "Hoàn tác" (null = không có). */
    var held by mutableStateOf<HeldDecision?>(null)
        private set

    /** Khoá thẻ đang gửi hay vừa gửi mà danh sách chưa nạp lại: không hiện lại trong bộ bài. */
    var away by mutableStateOf<Set<String>>(emptySet())
        private set

    /** Một câu nói điều vừa xảy ra khi gửi ("" = không có): lỗi, hay "vừa được sửa ở máy khác". */
    var notice by mutableStateOf("")
        private set

    private var counter = 0
    private var timer: Job? = null

    /** Khoá thẻ cần giấu khỏi bộ bài: đang giữ + đang gửi + vừa gửi. */
    fun hiding(): Set<String> = held?.let { away + it.decision.key } ?: away

    fun hold(decision: WorkDecision) {
        if (session.listenOnly) return
        if (persistImmediately) {
            if (busy) return
            flush()
            notice = ""
            send(decision, rememberUndo = true)
            return
        }
        notice = ""
        val current = held
        if (current != null) {
            if (current.decision.key == decision.key) cancelTimer() else flush()
        }
        if (!decision.hold) {
            held = null
            send(decision)
            return
        }
        val mine = HeldDecision(++counter, decision)
        held = mine
        timer = session.scope.launch {
            wait(WorkDecisions.UNDO_MS)
            if (held?.id == mine.id) flush()
        }
    }

    /** "Hoàn tác": bỏ quyết định đang giữ, chưa gửi gì. */
    fun undo() {
        cancelTimer()
        if (saved) {
            val previous = held
            val steps = undoSteps.asReversed()
            held = null; saved = false; undoSteps = emptyList()
            notice = ""
            if (previous != null && steps.isNotEmpty()) send(WorkDecision("undo:${previous.id}", S.s_da_hoan_tac_2ef55fca, steps, hold = false))
            return
        }
        held = null
    }

    /** Gửi ngay quyết định đang giữ (hết giờ, quyết định khác, rời màn). */
    fun flush() {
        val current = held ?: return
        cancelTimer()
        held = null
        if (saved) { saved = false; undoSteps = emptyList(); return }
        send(current.decision)
    }

    fun dismissNotice() {
        notice = ""
    }

    /** Danh sách đã nạp lại sau lần gửi: bỏ những khoá đã gửi xong khỏi `away` (máy đã đánh dấu thẻ là đã quyết). */
    fun forgetSent(keys: Set<String>) {
        away = away - keys
    }

    private fun cancelTimer() {
        timer?.cancel()
        timer = null
    }

    private fun send(decision: WorkDecision, rememberUndo: Boolean = false) {
        if (session.listenOnly) return
        away = away + decision.key
        if (persistImmediately) busy = true
        session.scope.launch {
            var done = 0
            var ok = false
            var lineReceipt: Pair<String, Double>? = null
            val receipts = ArrayList<WorkStep>()
            var retractSent = false
            try {
                if (decision.scopeChapter != null) {
                    val fresh = session.source.castingChapter(session.computer, bookId, decision.scopeChapter)
                    if (decision.scopeRevision.isEmpty() || fresh.scopeRevision != decision.scopeRevision) {
                        notice = S.s_scope_changed
                        after(false)
                        return@launch
                    }
                }
                var elsewhere: Pair<Int, String>? = null
                for (step in decision.steps) {
                    val answer = session.source.write(session.computer, bookId, step)
                    retractSent = retractSent || answer.optBoolean("sent")
                    if (rememberUndo) receipt(step, answer)?.let(receipts::add)
                    elsewhere = elsewhere ?: WorkLogic.elsewhere(step.endpoint, answer, decision.names)
                    if (decision.rollbackLine && step.endpoint == "line" && answer.optDouble("requestedAt", 0.0) > 0.0)
                        lineReceipt = step.body.getString("stableId") to answer.getDouble("requestedAt")
                    done++
                }
                ok = true
                if (rememberUndo && receipts.size == decision.steps.size) {
                    saved = true
                    undoSteps = receipts
                    val mine = HeldDecision(++counter, decision)
                    held = mine
                    timer = session.scope.launch {
                        wait(WorkDecisions.UNDO_MS)
                        if (held?.id == mine.id) flush()
                    }
                }
                if (persistImmediately && decision.key.startsWith("undo:")) notice =
                    if (retractSent) S.s_da_nho_may_giu_sach_rut_lai_e7afaa0b else decision.summary
                elsewhere?.let { (count, was) -> WorkLogic.elsewhereNote(count, was).let { (title, detail) -> notice = "$title. $detail" } }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                var rolledBack = false
                if (decision.rollbackLine && done == 1) {
                    lineReceipt?.let { (id, stamp) ->
                        try {
                            session.source.write(session.computer, bookId, WorkStep("line", JSONObject().put("stableId", id).put("withdraw", true).put("requestedAt", stamp)))
                            rolledBack = true
                        } catch (cancelled: CancellationException) { throw cancelled }
                        catch (_: Throwable) { /* The partial-write notice below remains visible. */ }
                    }
                }
                notice = failureNotice(failure, if (rolledBack) 0 else done, decision.steps.size)
            } finally {
                if (persistImmediately) busy = false
                // Thẻ chưa gửi được (hay chỉ gửi được một phần) trở lại bộ bài; thẻ đã gửi chờ lần nạp lại kế tiếp mới rời `away`.
                if (!ok) away = away - decision.key
            }
            after(ok)
        }
    }

    private fun receipt(step: WorkStep, answer: JSONObject): WorkStep? {
        val at = answer.optDouble("requestedAt", 0.0)
        if (at <= 0.0) return null
        val body = step.body
        return when (step.endpoint) {
            "speaker" -> WorkStep("speaker", JSONObject().put("lines", body.getJSONArray("lines")).put("requestedAt", at).put("withdraw", true))
            "line" -> WorkStep("line", JSONObject().put("stableId", body.getString("stableId")).put("requestedAt", at).put("withdraw", true))
            "review" -> {
                val ids = body.optJSONArray("lines")?.let { refs -> (0 until refs.length()).map { refs.getJSONObject(it).getString("stableId") } }
                    ?: listOf(body.getString("stableId"))
                WorkStep("pending-changes/withdraw", JSONObject().put("section", "retakes").put("key", ids.first()).put("keys", org.json.JSONArray(ids)).put("requestedAt", at))
            }
            else -> null
        }
    }

    private fun failureNotice(error: StudioError, done: Int, total: Int): String {
        val why = when {
            error is StudioError.Busy -> WorkText.STALE
            else -> StudioText.failure(error)
        }
        return if (done > 0 && total > 1) S.s_moi_ghi_duoc_0_1_viec_2_d1370bff(done, total, why) else why
    }
}

/** Đọc `elsewhere` của lời đáp một bước ghi (máy khác hay cửa sổ khác vừa sửa chính chỗ này): (số chỗ, điều nơi ấy đã đặt) hay null khi không lệch. */
internal fun WorkLogic.elsewhere(endpoint: String, answer: JSONObject, names: Map<String, String>): Pair<Int, String>? {
    val theirs = answer.opt("elsewhere") as? JSONObject ?: return null
    return when (endpoint) {
        "speaker" -> if (theirs.length() == 0) null else {
            val first = theirs.keys().asSequence().map { theirs.optString(it) }.firstOrNull().orEmpty()
            theirs.length() to (if (first.isEmpty()) "" else names[first] ?: first)
        }
        "pronunciation" -> if (theirs.has("spokenForm")) 1 to theirs.optString("spokenForm").let { if (it.isEmpty()) "" else "“$it”" } else null
        "voice" -> if (theirs.length() == 0) null else 1 to voiceWas(theirs.optString("voice"), theirs.optString("gender"))
        "line" -> if (!theirs.has("delivery")) null else 1 to (theirs.optJSONObject("delivery")?.let { delivery ->
            listOfNotNull(
                ScriptEdits.kinds.firstOrNull { it.first == delivery.optString("kind") }?.second,
                ScriptEdits.emotions.firstOrNull { it.first == delivery.optString("emotion") }?.second,
                delivery.optString("spoken").takeIf { it.isNotEmpty() },
            ).joinToString(" · ")
        }.orEmpty())
        "review" -> if (theirs.length() == 0) null else theirs.length() to
            (if (theirs.keys().asSequence().any { theirs.optString(it) == "redo" }) S.s_thu_lai_cau_nay_034c2834 else "")
        else -> null
    }
}
