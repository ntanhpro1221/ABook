package vn.abook.player.ui.studio

import kotlinx.coroutines.CompletableDeferred
import vn.abook.player.StudioError

/** Dự án mẫu: mọi trường có giá trị "sách nghỉ giữa chừng", test chỉ ghi đè điều nó cần. */
fun studioBook(
    id: String = "b1",
    title: String = "Tắt đèn",
    phase: String = "synthesis",
    statusLabel: String = "Đang thu âm",
    running: Boolean = false,
    starting: Boolean = false,
    stopping: Boolean = false,
    paused: StudioPause? = null,
    canPause: Boolean = false,
    queuePosition: Int? = null,
    queueWaitsOn: StudioQueueWait? = null,
    analysisInterrupted: Boolean = false,
    precastHeld: Boolean = false,
    pendingChanges: Int = 0,
    chaptersTotal: Int = 10,
    chaptersCompleted: Int = 4,
    chaptersRedo: Int = 0,
    overall: Float = 0.4f,
    eta: StudioEta? = null,
    broken: String = "",
) = StudioBook(
    id = id, title = title, phase = phase, statusLabel = statusLabel, running = running, starting = starting, stopping = stopping, paused = paused,
    canPause = canPause, queuePosition = queuePosition, queueWaitsOn = queueWaitsOn, analysisInterrupted = analysisInterrupted, precastHeld = precastHeld,
    pendingChanges = pendingChanges, seedPending = false, chaptersTotal = chaptersTotal, chaptersCompleted = chaptersCompleted, chaptersRedo = chaptersRedo,
    segmentsTotal = 0, segmentsAnalyzed = 0, segmentsPending = null, overall = overall, analysis = overall, synthesis = overall, eta = eta, speaker = null,
    startError = "", lastError = "", broken = broken,
)

fun studioChapter(id: Int, title: String = "Chương $id", status: String = "completed", statusLabel: String = "Đã xong", redo: Boolean = false, seconds: Double = 600.0) =
    StudioChapter(id, id, title, status, statusLabel, redo, seconds, playable = status == "completed")

/** Nguồn giả: sách và chương cho từng mã, lệnh ghi lại, và lỗi để bắt máy "nói" một lỗi nào đó. */
class FakeStudioSource(
    var books: List<StudioBook> = emptyList(),
    var chapters: Map<String, List<StudioChapter>> = emptyMap(),
) : StudioSource {
    var error: StudioError? = null
    var commandError: StudioError? = null
    var commandGate: CompletableDeferred<Unit>? = null
    val libraryCalls = ArrayList<String>()
    val bookCalls = ArrayList<String>()
    val commands = ArrayList<Pair<String, StudioCommand>>()

    override fun name(computer: String) = "Máy bàn"

    override suspend fun library(computer: String): List<StudioBook> {
        libraryCalls += computer
        error?.let { throw it }
        return books
    }

    override suspend fun book(computer: String, id: String): StudioPage {
        bookCalls += id
        error?.let { throw it }
        val book = books.firstOrNull { it.id == id } ?: throw StudioError.Gone()
        return StudioPage(book, chapters[id].orEmpty())
    }

    override suspend fun command(computer: String, id: String, command: StudioCommand): StudioBook {
        commands += id to command
        commandGate?.await()
        commandError?.let { throw it }
        return books.first { it.id == id }
    }

    override suspend fun mismatched(computer: String) = false
}
