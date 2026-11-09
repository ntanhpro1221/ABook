package vn.abook.player.ui.studio

import vn.abook.player.S

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
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling

// "Duyệt trước khi thu" (NATIVE_REMOTE_STUDIO.md §6.9). Port từ precast.ts / PrecastReview.tsx (webui/precast.py): ngay khi phân tích xong và trước khi thu những chương
// đầu, dẫn qua đúng thứ tự người duyệt cần. Không bước nào chặn dây chuyền; chỉ khi bật "Chờ tôi duyệt" thì sách đứng lại (tạm dừng) và chờ nút "Thu âm".

@Immutable
data class PrecastChapter(val id: Int, val title: String)

/** Lời đáp của `GET /api/books/<id>/precast`. */
@Immutable
data class PrecastView(
    val ready: Boolean,
    val wait: Boolean,
    /** Lúc Studio báo mốc phân tích xong (một lần mỗi cuốn); null = chưa. */
    val announcedAt: Double?,
    val held: Boolean,
    val chapters: Int,
    val recordedChapters: Int,
    /** Chương xa nhất đã thu xong: sửa ở chương sau nó không phải thu lại. */
    val recordedThrough: PrecastChapter?,
    /** Vài chương sắp thu, theo thứ tự đọc. */
    val upcoming: List<PrecastChapter>,
)

/** Bốn bước của màn duyệt (web `PRECAST_STEPS`). */
enum class PrecastStep(val label: String) {
    Cast(S.s_nhan_vat_va_giong_52dfc919),
    Names(S.s_cach_doc_ten_1c46e75d),
    Lines(S.s_ai_noi_cau_nay_0e00a5c7),
    Done(S.s_xong_a6f4543a),
}

internal object StudioPrecastJson {
    private fun chapter(json: JSONObject?) = json?.let { PrecastChapter(it.optInt("id"), it.text("title")) }

    fun view(json: JSONObject) = PrecastView(
        ready = json.optBoolean("ready"),
        wait = json.optBoolean("wait"),
        announcedAt = if (json.isNull("announcedAt") || !json.has("announcedAt")) null else json.optDouble("announcedAt"),
        held = json.optBoolean("held"),
        chapters = json.optInt("chapters"),
        recordedChapters = json.optInt("recordedChapters"),
        recordedThrough = chapter(json.optJSONObject("recordedThrough")),
        upcoming = json.optJSONArray("upcoming").objects().mapNotNull(::chapter),
    )
}

object PrecastLogic {
    /** Những người nói nhiều nhất: giọng của họ nghe suốt cuốn. */
    const val TOP_PEOPLE = 6

    /** Nhịp hỏi lại (web `usePrecast`: 15 giây). */
    const val REFRESH_MS = 15_000L

    private val CAST_KINDS = setOf(WorkKind.Gender, WorkKind.Alias, WorkKind.SharedVoice)
    private val LINE_KINDS = setOf(WorkKind.Speaker, WorkKind.Caller, WorkKind.Turn, WorkKind.Vocative, WorkKind.Bracket, WorkKind.Unnamed)

    private fun open(items: List<WorkItem>) = items.filter(WorkLogic::isOpen)

    /** (a) Việc về người và giọng: nam hay nữ, một người hai tên, hai người chung giọng. Giữ thứ tự lợi / lần bấm của hộp việc. */
    fun castItems(items: List<WorkItem>): List<WorkItem> = open(items).filter { it.kind in CAST_KINDS }

    /** (b) Cách đọc tên máy tự đoán - tên máy kém chắc nhất trước, cùng mức thì tên gặp nhiều câu hơn trước. */
    fun nameItems(items: List<WorkItem>): List<WorkItem> =
        open(items).filter { it.kind == WorkKind.Pronunciation }.sortedWith(compareByDescending<WorkItem> { it.doubt }.thenByDescending { it.affected })

    /** (c) "Ai nói câu này" kém chắc ở các chương sắp thu - thu xong chương ấy thì sửa phải thu lại. */
    fun lineItems(items: List<WorkItem>, upcoming: List<Int>): List<WorkItem> {
        val ahead = upcoming.toSet()
        return open(items).filter { it.kind in LINE_KINDS && it.chapters.any { id -> id in ahead } }
    }

    /** Mã các thẻ nằm trong màn duyệt: tab "Việc cần duyệt" không hiện lại chúng. */
    fun keys(items: List<WorkItem>, upcoming: List<Int>): Set<String> =
        (castItems(items) + nameItems(items) + lineItems(items, upcoming)).map { it.key }.toSet()

    fun lineCount(items: List<WorkItem>): Int = items.sumOf { it.affected }

    /** "Chương 1" / "Chương 1 → Chương 3" cho các chương sắp thu (đã theo thứ tự đọc). */
    fun chapterRange(chapters: List<PrecastChapter>): String = when {
        chapters.isEmpty() -> ""
        chapters.size == 1 -> chapters.first().title
        else -> "${chapters.first().title} → ${chapters.last().title}"
    }

    /** Sửa tới đâu thì miễn phí: chưa thu gì là mọi sửa; đã thu tới chương X thì sửa ở chương sau X không phải thu lại. */
    fun freeNote(view: PrecastView): String = view.recordedThrough?.let {
        S.s_da_thu_toi_0_sua_o_chuong_sau_do_khong_pha_fa584b22(it.title)
    } ?: S.s_chua_thu_chuong_nao_sua_bay_gio_khong_phai_e0dc8283

    /** Có nên mở màn duyệt: phân tích xong và phân vai đã khoá (web `precast.ready`), sách chưa xong. */
    fun canReview(book: StudioBook): Boolean = book.phase != "done" && book.castLocked

    /** Công tắc "Chờ tôi duyệt" chỉ có nghĩa trước mốc (Studio mở màn này cả khi chưa kịp báo, vd app đóng lúc phân tích xong). */
    fun showWait(view: PrecastView): Boolean = view.announcedAt == null && view.recordedChapters == 0

    /** Dòng phụ dưới công tắc. */
    fun waitHint(view: PrecastView): String = when {
        view.announcedAt != null -> PrecastText.WAIT_PASSED
        view.wait -> PrecastText.WAIT_ON
        else -> PrecastText.WAIT_OFF
    }

    /** Số việc mỗi bước, ngắn (dòng phụ của bước). */
    fun count(step: PrecastStep, cast: List<WorkItem>, names: List<WorkItem>, lines: List<WorkItem>, people: Int): String = when (step) {
        PrecastStep.Cast -> if (cast.isNotEmpty()) S.s_0_viec_d6b72911(cast.size) else S.s_0_nguoi_272b4f6d(people)
        PrecastStep.Names -> if (names.isNotEmpty()) S.s_0_ten_f2f08473(names.size) else PrecastText.NAMES_FINE
        PrecastStep.Lines -> if (lines.isNotEmpty()) S.s_0_cau_2a1e6590(lineCount(lines)) else PrecastText.LINES_FINE
        PrecastStep.Done -> ""
    }

    fun next(step: PrecastStep): PrecastStep = PrecastStep.entries[minOf(step.ordinal + 1, PrecastStep.entries.lastIndex)]
}

object PrecastText {
    const val TITLE = S.s_duyet_truoc_khi_thu_74c121d0
    const val LEAD = S.s_duyet_nhanh_truoc_khi_thu_co_the_bo_qua_tu_d3a2f0a0
    const val HELD = S.s_sach_dang_cho_ban_duyet_duyet_xong_bam_thu_5583a564
    const val WAIT = S.s_duyet_truoc_khi_thu_74c121d0
    const val WAIT_PASSED = S.s_phan_tich_da_xong_muon_dung_thi_bam_tam_du_73416c6b
    const val WAIT_ON = S.s_dung_sau_phan_tich_de_ban_duyet_roi_bam_th_0ca451d3
    const val WAIT_OFF = S.s_phan_tich_xong_thi_thu_luon_duyet_luc_nao_1f91e9f9
    const val WHEN = S.s_khi_ap_dung_017de1f0
    const val LOADING = S.s_dang_tai_luot_duyet_c2e5bf3f
    const val CAST_LEAD = S.s_nghe_va_chinh_giong_cho_nhung_nhan_vat_noi_cc91379e
    const val CAST_UNSURE = S.s_may_chua_chac_5781f0c4
    const val NAMES_ALL = S.s_xem_va_sua_cach_doc_tung_ten_o_danh_sach_r_fee07309
    const val NAMES_OPEN = S.s_cach_doc_ten_1c46e75d
    /** Dòng phụ của bước khi không có gì cần xem (cùng chữ với PrecastReview.tsx): một câu đủ nghĩa, không phải chữ "ổn" lẻ loi. */
    const val NAMES_FINE = S.s_ten_nao_cung_on_095d4866
    const val LINES_FINE = S.s_khong_cau_nao_nghi_25d773f7
    const val SKIP = S.s_bo_qua_buoc_nay_128392ff
    const val NEXT = S.s_tiep_tuc_87a7ae88
    const val DONE_TITLE = S.s_xong_luot_duyet_aaf11626
    const val FINISH = S.s_duyet_xong_78e42d1f
    const val RECORD = S.s_thu_am_db588c2e
    const val BACK = S.s_ve_danh_sach_chuong_b5fd5434
    const val DONE_HELD = S.s_da_ghi_lai_bam_thu_am_de_lam_tiep_0f63f737
    const val DONE_RUNNING = S.s_sua_nao_cung_da_ghi_lai_may_ap_o_chuong_ke_7b639271
    const val DONE_IDLE = S.s_sua_nao_cung_da_ghi_lai_may_ap_khi_sach_ch_eb78b798
    const val SAME_NAME = S.s_cung_ten_voi_nguoi_khac_trong_sach_mot_ngu_e99f281d

    fun step(index: Int, total: Int) = S.s_buoc_0_1_b5e91411(index, total)
    fun castUnsure(count: Int) = S.s_0_viec_ve_nguoi_va_giong_538472a9(count)
    fun namesLead(count: Int) = if (count > 0) S.s_nghe_va_sua_0_cach_doc_ten_ten_kem_chac_o_bc275c71(count) else NAMES_ALL
    fun linesLead(count: Int, range: String, anyUpcoming: Boolean) = when {
        count > 0 -> S.s_0_cau_may_chua_chac_ai_noi_o_1_cac_chuong_560614c7(count, range.ifEmpty { S.s_nhung_chuong_sap_thu_969d3947 })
        anyUpcoming -> S.s_khong_co_cau_nghi_ngo_o_0_cac_chuong_sau_x_7c9bb017(range)
        else -> S.s_da_thu_moi_chuong_cac_chuong_sau_xem_o_vie_e8860c7b
    }

    fun done(book: StudioBook) = when {
        book.precastHeld -> DONE_HELD
        book.running -> DONE_RUNNING
        else -> DONE_IDLE
    }
}

/**
 * Màn duyệt của một dự án: số liệu `GET /precast` (15 giây một lần), bước đang mở, và công tắc "Chờ tôi duyệt" (`PUT /precast`). Thẻ việc, người nói, giọng lấy từ
 * chính [StudioWorkState] / [StudioCastState] của dự án - cùng quyết định, cùng hàng chờ "Hoàn tác".
 */
@Stable
class StudioPrecastState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private val poller = StudioPoller<PrecastView>({ session.source.precast(session.computer, project.bookId) }, { PrecastLogic.REFRESH_MS }, pause)
    val poll: StateFlow<StudioPolling.Poll<PrecastView>> get() = poller.state

    var step by mutableStateOf(PrecastStep.Cast)
        private set

    var saving by mutableStateOf(false)
        private set

    var problem by mutableStateOf("")
        private set

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    fun open(next: PrecastStep) {
        step = next
    }

    fun next() {
        step = PrecastLogic.next(step)
    }

    /** `PUT /precast {wait}`: bật = dây chuyền dừng ở cổng này sau phân tích. */
    fun setWait(value: Boolean) {
        if (saving) return
        saving = true
        problem = ""
        session.scope.launch {
            try {
                session.source.put(session.computer, project.bookId, "precast", JSONObject().put("wait", value))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                saving = false
            }
            poller.refresh()
            project.refresh()
        }
    }
}
