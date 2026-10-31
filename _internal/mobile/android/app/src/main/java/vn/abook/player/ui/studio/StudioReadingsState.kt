package vn.abook.player.ui.studio

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import vn.abook.player.ClipSpec
import vn.abook.player.ClipState
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPaths
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling

/**
 * Màn "Cách đọc tên" của một dự án (NATIVE_REMOTE_STUDIO.md §6.10). Hỏi `GET /pronunciations` một lần (hàng nghìn tên, không hỏi theo nhịp) rồi mỗi lần
 * một lệnh xong. Lưu một cách đọc đi đúng đường của thẻ cách đọc: máy KIỂM trước, rồi giữ 15 giây cho "Hoàn tác", rồi gửi một lần ([StudioDecisions]).
 * Danh sách hiện luôn điều đang giữ như đã lưu (web `withReading`), không đợi nạp lại.
 */
@Stable
class StudioReadingsState(
    val session: StudioSession,
    val bookId: String,
    name: String = "",
    pause: suspend (Long) -> Unit = { delay(it) },
    hold: suspend (Long) -> Unit = { delay(it) },
    private val settle: suspend (Long) -> Unit = { delay(it) },
) {
    private val poller = StudioPoller<NameReadings>({ session.source.readings(session.computer, bookId) }, { null }, pause)
    val poll: StateFlow<StudioPolling.Poll<NameReadings>> get() = poller.state

    val decisions = StudioDecisions(session, bookId, hold) { refresh() }

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    /** Ô tìm; điền sẵn tên của thẻ đã mở màn này. */
    var query by mutableStateOf(name)
        private set

    /** Số tên đang hiện. */
    var limit by mutableIntStateOf(ReadingsLogic.PAGE)
        private set

    /** Sách đã phân tích xong chưa (chưa thì "tên hiện ra sau bước ấy"). Không hỏi được = coi như xong. */
    var analyzed by mutableStateOf(true)
        private set

    /** Cách đọc chung cho mọi sách, và những mục có tên trong cuốn này mà cuốn đang đọc khác. */
    var shared by mutableStateOf<List<SharedReading>>(emptyList())
        private set
    var offer by mutableStateOf<List<SharedReading>>(emptyList())
        private set

    /** Dòng máy gợi ý bỏ khỏi phần đọc, mặc định KHÔNG áp. */
    var credits by mutableStateOf<List<CreditGroup>>(emptyList())
        private set

    /** Reach của chữ đang gõ để thêm; null khi chưa có hay đang hỏi. */
    var reach by mutableStateOf<Reach?>(null)
        private set

    /** Lời nói điều vừa xảy ra ("Đã dùng 3 cách đọc chung", lỗi) - rỗng khi không có. */
    var notice by mutableStateOf("")
        private set

    private var reachJob: Job? = null
    private var previewJob: Job? = null

    /** "Nghe thử" đang chạy cho tên này ("" = không), để nút thành "Huỷ". */
    var trying by mutableStateOf("")
        private set

    suspend fun run() {
        loadExtras()
        poller.run()
    }

    suspend fun refresh() = poller.refresh()

    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }

    /** Những thứ phụ (không có thì màn vẫn dùng được): sách đã phân tích chưa, cách đọc chung, dòng ghi công. */
    private suspend fun loadExtras() {
        analyzed = quiet(true) { session.source.book(session.computer, bookId).book.let { it.segmentsTotal > 0 && it.segmentsAnalyzed == it.segmentsTotal } }
        shared = quiet(emptyList()) { session.source.sharedReadings(session.computer) }
        offer = quiet(emptyList()) { session.source.sharedOffer(session.computer, bookId) }
        credits = quiet(emptyList()) { session.source.credits(session.computer, bookId) }
    }

    private suspend fun <T> quiet(fallback: T, block: suspend () -> T): T = try {
        block()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Throwable) {
        val failure = StudioErrors.of(error)
        session.note(failure)
        fallback
    }

    fun search(text: String) {
        query = text
        limit = ReadingsLogic.PAGE
    }

    fun more() {
        limit += ReadingsLogic.PAGE * 3
    }

    /** Danh sách như đã lưu: điều đang giữ cho "Hoàn tác" hiện như đã ghi. */
    fun shown(data: NameReadings): NameReadings {
        val held = decisions.held?.decision ?: return data
        val surface = held.key.removePrefix("reading:")
        val item = data.items.firstOrNull { it.surface == surface } ?: return data
        val body = held.steps.firstOrNull()?.body ?: return data
        return ReadingsLogic.withReading(data, item, body.optString("spokenForm"))
    }

    fun sharedHere(item: NameReading): Boolean = ReadingsLogic.sharedEntry(shared, item.surface, item.requested ?: item.spoken) != null

    /** Lưu: máy kiểm cách đọc trước (nghe được là lưu được), qua thì giữ 15 giây. Trả kết quả kiểm để ô sửa nói lỗi ngay tại chỗ. */
    suspend fun save(item: NameReading, spoken: String, everywhere: Boolean): ReadingCheck {
        val typed = ReadingsLogic.asStored(item, spoken.trim())
        val checked = session.checkReading(bookId, ReadingsLogic.checkStep(item.surface, typed))
        if (checked == ReadingCheck.Ok) decisions.hold(ReadingsLogic.decision(item, typed, everywhere))
        return checked
    }

    /** "Nghe thử" cách đang gõ: máy tính đọc một câu có tên ấy (tới ~2 phút), rồi phát bản thu; `done` nhận kết quả. Huỷ được bằng [cancelTry]. */
    fun tryReading(surface: String, spoken: String, done: (PreviewOutcome) -> Unit) {
        previewJob?.cancel()
        trying = surface
        previewJob = session.scope.launch {
            try {
                val outcome = session.preview(bookId, ReadingsLogic.previewStep(surface, spoken.trim()))
                if (outcome is PreviewOutcome.Ready) session.clips?.toggle("try-${outcome.preview.url}", ClipSpec(session.computer, outcome.preview.url))
                done(outcome)
            } finally {
                trying = ""
            }
        }
    }

    /** Bỏ chờ lần nghe thử đang chạy (máy tính vẫn đọc xong nhưng kết quả bị bỏ). */
    fun cancelTry() {
        previewJob?.cancel()
        previewJob = null
        trying = ""
    }

    /** Gõ xong mới hỏi một chữ chạm tới bao nhiêu câu (không hỏi từng phím). */
    fun askReach(surface: String) {
        reachJob?.cancel()
        reach = null
        val word = surface.trim()
        if (word.isEmpty() || !ReadingsLogic.single(word)) return
        reachJob = session.scope.launch {
            settle(ReadingsLogic.REACH_SETTLE_MS)
            reach = quiet(null) { session.source.reach(session.computer, bookId, word) }
        }
    }

    fun playSample(example: ReadingExample) {
        session.clips?.toggle(sampleId(example), ClipSpec(session.computer, StudioPaths.sample(bookId, example.segmentId)))
    }

    /** Dùng mọi cách đọc chung có tên trong cuốn: một lần bấm (`POST /shared-readings`), đi đường của một lần sửa tay. */
    fun applyShared() {
        val count = offer.size
        session.scope.launch {
            try {
                session.source.write(session.computer, bookId, WorkStep("shared-readings", org.json.JSONObject()))
                notice = ReadingsText.sharedDone(count)
                offer = emptyList()
                poller.refresh()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                notice = StudioText.failure(failure)
            }
        }
    }

    /** Bỏ (hay đọc lại) một dòng gợi ý khỏi phần đọc của các chương ấy. Chữ truyện không đổi; bỏ chọn là đọc lại như cũ. */
    fun skipLine(group: CreditGroup, skip: Boolean) {
        session.scope.launch {
            try {
                session.source.put(session.computer, bookId, "skip", ReadingsLogic.skipBody(group, skip))
                credits = credits.map { if (it.line == group.line) it.copy(skipped = skip) else it }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                notice = StudioText.failure(failure)
            }
        }
    }

    fun dismissNotice() {
        notice = ""
    }

    /** Rời màn: gửi nốt điều đang giữ và dừng tiếng. */
    fun leave() {
        decisions.flush()
        cancelTry()
        session.clips?.stop()
    }

    companion object {
        fun sampleId(example: ReadingExample) = "reading-${example.segmentId}"
    }
}
