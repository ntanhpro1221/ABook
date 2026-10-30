package vn.abook.player.ui.studio

import kotlinx.coroutines.CompletableDeferred
import org.json.JSONObject
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

fun lineRef(id: String, hash: String = "h-$id") = LineRef(id, hash)

fun workExample(segmentId: Int, text: String = "Câu $segmentId", hasAudio: Boolean = false, narration: Boolean = false, names: List<String> = emptyList()) = WorkExample(
    segmentId = segmentId, chapterId = 1, chapterTitle = "Chương 1", seq = segmentId, text = text, speaker = "", hasAudio = hasAudio, changes = true,
    stableId = "s$segmentId", before = "", after = "", narration = narration, names = names,
)

/** Thẻ việc mẫu: mọi trường rỗng, test chỉ đặt điều nó cần. */
fun workItem(
    kind: WorkKind = WorkKind.Speaker,
    key: String = "k-${kind.key}",
    title: String = "Ai nói câu này?",
    current: String = "",
    examples: List<WorkExample> = emptyList(),
    surface: String? = null,
    requested: String? = null,
    redoOnly: Boolean = false,
    lines: List<LineRef>? = null,
    allLines: List<LineRef>? = null,
    choices: List<WorkChoice>? = null,
    currentValue: String? = null,
    seen: Map<String, String> = emptyMap(),
    keepLabel: String? = null,
    voiceChoices: List<VoiceOption>? = null,
    keepCharacters: List<String> = emptyList(),
    refused: RefusedRef? = null,
    pickVoice: PickVoice? = null,
    pick: Boolean = false,
    examplesTotal: Int? = null,
    keepGroups: List<SpeakerRequest> = emptyList(),
    newPerson: String? = null,
    narratorSection: NarratorSection? = null,
    affected: Int = 0,
    problem: String = "",
    suggested: Boolean = true,
) = WorkItem(
    kind = kind, key = key, title = title, problem = problem, affected = affected, doubt = 0, options = emptyList(), current = current, examples = examples,
    surface = surface, requested = requested, redoOnly = redoOnly, lines = lines, allLines = allLines, scopeLabels = null, choices = choices, currentValue = currentValue,
    seen = seen, keepLabel = keepLabel, suggested = suggested, subject = null, voiceChoices = voiceChoices, keepCharacters = keepCharacters, refused = refused,
    pickVoice = pickVoice, chapters = emptyList(), pick = pick, examplesTotal = examplesTotal, keepGroups = keepGroups, newPerson = newPerson, newPersonLabel = null,
    narratorSection = narratorSection,
)

/** Thẻ chọn người nói một câu: hai người để chọn, "Kati" đang được ghi. */
fun speakerCard(key: String = "k1", lineId: String = "s1") = workItem(
    key = key, current = "Kati", currentValue = "kati", lines = listOf(lineRef(lineId)), seen = mapOf(lineId to "kati"),
    choices = listOf(WorkChoice("Kati", "kati", null), WorkChoice("Noah", "noah", null)),
    examples = listOf(workExample(1)),
)

fun reviewItem(
    segmentId: Int,
    text: String = "Câu $segmentId",
    kind: ReviewKind = ReviewKind.Failed,
    playable: Boolean = true,
    verdict: String? = null,
    heard: String = "",
    chapterClip: ChapterWindow? = null,
) = ReviewItem(
    segmentId = segmentId, stableId = "r$segmentId", audioSha256 = "a$segmentId", chapterId = 1, chapterTitle = "Chương 1", text = text, heard = heard, similarity = null,
    speaker = "", kind = kind, reason = "", playable = playable, chapterClip = chapterClip, verdict = verdict, pendingSpoken = null, spoken = null,
)

fun emptyReview(items: List<ReviewItem> = emptyList(), next: String? = null, pending: Int = items.size) =
    ReviewPage(emptyMap(), pending, emptyList(), items, next, if (next == null) 0 else 5)

fun castMember(name: String, display: String = name, voice: String? = "Giọng A", sampleId: Int? = null, lines: Int = 5) = CastMember(
    name = name, displayName = display, originalName = null, gender = "male", age = "", lines = lines, seconds = 10.0, recorded = lines,
    voice = voice?.let { VoiceProfile("k", "p", it, "") }, sampleId = sampleId, firstChapter = "Chương 1", pendingVoice = null, mergedInto = null,
)

fun voiceEntry(key: String, name: String = key, gender: String = "male", current: Boolean = false, preview: Boolean = true, engine: String = "vieneu") = VoiceEntry(
    key = key, name = name, engine = engine, engineLabel = engine, installed = true, oneStep = true, sharedWith = emptyList(), otherUsers = 0, gender = gender,
    genderLabel = if (gender == "female") "Nữ" else "Nam", region = "", style = "", preview = preview, current = current, pending = false, suggested = false,
    description = "", takenBy = emptyList(), takenNote = null,
)

fun voiceChoices(character: String = "kati", gender: String = "female", voices: List<VoiceEntry> = emptyList(), pending: PendingChoice? = null) = VoiceChoices(
    character = VoiceCharacter(character, "Kati", gender, 5, 1), current = "", pending = pending, voices = voices, tryLine = null, rerecord = null, moduleStates = emptyMap(),
)

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

    // ---- Việc cần duyệt / Cần nghe lại / Nhân vật ----
    var workView = WorkView(emptyList(), emptyMap())
    var examplesPage = WorkExamplesPage(emptyList(), 0)
    var workError: StudioError? = null
    val workCalls = ArrayList<String>()
    val exampleCalls = ArrayList<Pair<Int, Int>>()

    /** Trang `review` theo con trỏ ("" = trang đầu); thiếu thì trang rỗng. */
    val reviewPages = HashMap<String, ReviewPage>()
    val reviewCalls = ArrayList<Triple<String, Boolean, String>>()
    var reviewError: StudioError? = null
    var cast = Cast(CastNarrator("", 0, 0.0, null, null, 0), emptyList(), emptyList(), emptyList())
    var castError: StudioError? = null
    val voiceChoicesFor = HashMap<String, VoiceChoices>()
    val voicesCalls = ArrayList<String>()

    /** Mọi bước ghi, theo thứ tự (kèm thân JSON). */
    val writes = ArrayList<Pair<String, JSONObject>>()

    /** Lỗi cho một bước ghi; null = ghi được. */
    var writeError: (WorkStep) -> StudioError? = { null }

    /** Lời đáp cho một bước ghi (theo tên endpoint); thiếu thì `{}`. */
    val writeAnswers = HashMap<String, JSONObject>()
    var writeGate: CompletableDeferred<Unit>? = null

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

    override suspend fun work(computer: String, id: String): WorkView {
        workCalls += id
        workError?.let { throw it }
        return workView
    }

    override suspend fun workExamples(computer: String, id: String, key: String, offset: Int, limit: Int): WorkExamplesPage {
        exampleCalls += offset to limit
        return examplesPage
    }

    override suspend fun review(computer: String, id: String, filter: String, all: Boolean, cursor: String): ReviewPage {
        reviewCalls += Triple(filter, all, cursor)
        reviewError?.let { throw it }
        return reviewPages[cursor] ?: emptyReview()
    }

    override suspend fun cast(computer: String, id: String): Cast {
        castError?.let { throw it }
        return cast
    }

    override suspend fun voices(computer: String, id: String, character: String): VoiceChoices {
        voicesCalls += character
        return voiceChoicesFor[character] ?: voiceChoices(character)
    }

    override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject {
        writes += step.endpoint to step.body
        writeGate?.await()
        writeError(step)?.let { throw it }
        return writeAnswers[step.endpoint] ?: JSONObject()
    }
}
