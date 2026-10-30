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
    segmentsAnalyzed: Int = 0,
    castLocked: Boolean = false,
) = StudioBook(
    id = id, title = title, phase = phase, statusLabel = statusLabel, running = running, starting = starting, stopping = stopping, paused = paused,
    canPause = canPause, queuePosition = queuePosition, queueWaitsOn = queueWaitsOn, analysisInterrupted = analysisInterrupted, precastHeld = precastHeld,
    pendingChanges = pendingChanges, seedPending = false, chaptersTotal = chaptersTotal, chaptersCompleted = chaptersCompleted, chaptersRedo = chaptersRedo,
    segmentsTotal = segmentsAnalyzed, segmentsAnalyzed = segmentsAnalyzed, segmentsPending = null, overall = overall, analysis = overall, synthesis = overall, eta = eta, speaker = null,
    startError = "", lastError = "", broken = broken, castLocked = castLocked,
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

    // ---- S3: nhạc nền / duyệt trước khi thu / cách đọc tên / kịch bản ----

    /** Mọi lần PUT (đường, thân, đã đi đường chậm chưa). */
    val puts = ArrayList<Triple<String, JSONObject, Boolean>>()
    var putError: StudioError? = null
    var readings = NameReadings(emptyList(), 0)
    var readingsError: StudioError? = null
    val reachFor = HashMap<String, Reach>()
    val reachCalls = ArrayList<String>()
    var shared: List<SharedReading> = emptyList()
    var offer: List<SharedReading> = emptyList()
    var creditGroups: List<CreditGroup> = emptyList()
    var precastView = precastView()
    var precastError: StudioError? = null
    var musicView = musicView()
    var musicError: StudioError? = null
    var moods = MoodsModel(installed = false, downloading = false, percent = null, error = "", downloadable = true)
    var alternativesFor = HashMap<String, List<MusicAlternative>>()
    var scriptContents = ScriptContents(true, emptyList())
    val scriptChapters = HashMap<Int, ChapterScript>()
    val scriptCalls = ArrayList<Int>()

    override suspend fun put(computer: String, id: String, endpoint: String, body: JSONObject, slow: Boolean): JSONObject {
        puts += Triple(endpoint, body, slow)
        putError?.let { throw it }
        return JSONObject()
    }

    override suspend fun readings(computer: String, id: String): NameReadings {
        readingsError?.let { throw it }
        return readings
    }

    override suspend fun reach(computer: String, id: String, surface: String): Reach {
        reachCalls += surface
        return reachFor[surface] ?: Reach(surface, 0, 0, 0, 0, false, emptyList(), null)
    }

    override suspend fun sharedReadings(computer: String): List<SharedReading> = shared

    override suspend fun sharedOffer(computer: String, id: String): List<SharedReading> = offer

    override suspend fun credits(computer: String, id: String): List<CreditGroup> = creditGroups

    override suspend fun precast(computer: String, id: String): PrecastView {
        precastError?.let { throw it }
        return precastView
    }

    override suspend fun music(computer: String, id: String): MusicView {
        musicError?.let { throw it }
        return musicView
    }

    override suspend fun moodsModel(computer: String): MoodsModel = moods

    override suspend fun alternatives(computer: String, id: String, scene: String): List<MusicAlternative> = alternativesFor[scene].orEmpty()

    override suspend fun castingContents(computer: String, id: String): ScriptContents = scriptContents

    override suspend fun castingChapter(computer: String, id: String, chapter: Int): ChapterScript {
        scriptCalls += chapter
        return scriptChapters[chapter] ?: throw StudioError.Gone()
    }

    // ---- S4: xuất / nhật ký / bìa / sách mới ----

    /** Việc xuất theo kiểu; thiếu thì `idle`. `exportStart` đặt việc thành đang chạy. */
    val exportJobs = HashMap<StudioExportKind, StudioExportJob>()
    val exportCalls = ArrayList<StudioExportKind>()
    val exportStarts = ArrayList<Pair<StudioExportKind, JSONObject>>()
    val exportCancels = ArrayList<StudioExportKind>()
    var exportError: StudioError? = null
    var exportStartError: StudioError? = null
    var exportOptionsView = StudioExportOptions()
    var exportOptionsError: StudioError? = null
    var exportOptionsCalls = 0
    var activityItems: List<StudioLogItem> = emptyList()
    var activityError: StudioError? = null
    val activityCalls = ArrayList<Boolean>()
    var coverResults = vn.abook.player.ui.editbook.CoverResults("", emptyList(), emptyList())
    val coverQueries = ArrayList<String>()
    val deletes = ArrayList<String>()

    override suspend fun exportJob(computer: String, id: String, kind: StudioExportKind): StudioExportJob {
        exportCalls += kind
        exportError?.let { throw it }
        return exportJobs[kind] ?: studioExportJob("idle")
    }

    override suspend fun exportStart(computer: String, id: String, kind: StudioExportKind, body: JSONObject): StudioExportJob {
        exportStarts += kind to body
        exportStartError?.let { throw it }
        return studioExportJob("running").also { exportJobs[kind] = it }
    }

    override suspend fun exportCancel(computer: String, id: String, kind: StudioExportKind): StudioExportJob {
        exportCancels += kind
        return exportJobs[kind] ?: studioExportJob("idle")
    }

    override suspend fun exportOptions(computer: String, id: String): StudioExportOptions {
        exportOptionsCalls++
        exportOptionsError?.let { throw it }
        return exportOptionsView
    }

    override suspend fun activity(computer: String, id: String, technical: Boolean): List<StudioLogItem> {
        activityCalls += technical
        activityError?.let { throw it }
        return activityItems
    }

    override suspend fun coverSearch(computer: String, id: String, query: String): vn.abook.player.ui.editbook.CoverResults {
        coverQueries += query
        return coverResults
    }

    override suspend fun delete(computer: String, id: String, endpoint: String): JSONObject {
        deletes += endpoint
        return JSONObject()
    }

    /** Mọi file đã gửi (thư mục, tên, nội dung). */
    val uploads = ArrayList<Triple<String, String, ByteArray>>()
    var uploadError: StudioError? = null
    var uploadGate: CompletableDeferred<Unit>? = null
    val splits = ArrayList<String>()
    var scanView = ScanView(emptyList(), emptyList(), emptyList(), emptyList(), "", emptyList())
    var scanError: StudioError? = null
    val scanCalls = ArrayList<List<String>>()
    var firstPersonView = FirstPersonView(false, 0.0, emptyList())
    var modelsView = AnalysisModels("", emptyList(), false)
    var createdBook = CreatedBook("new1", null)
    var createError: StudioError? = null
    val creates = ArrayList<JSONObject>()

    override suspend fun uploadSource(computer: String, folder: String, name: String, input: () -> java.io.InputStream): UploadedSource {
        val bytes = input().use { it.readBytes() }
        uploadGate?.await()
        uploadError?.let { throw it }
        uploads += Triple(folder, name, bytes)
        return UploadedSource(folder, "$folder/$name")
    }

    override suspend fun splitSource(computer: String, path: String, title: String): String {
        splits += path
        return "$path.chuong"
    }

    override suspend fun scan(computer: String, paths: List<String>): ScanView {
        scanCalls += paths
        scanError?.let { throw it }
        return scanView
    }

    override suspend fun firstPerson(computer: String, paths: List<String>) = firstPersonView

    override suspend fun analysisModels(computer: String) = modelsView

    override suspend fun createBook(computer: String, body: JSONObject): CreatedBook {
        creates += body
        createError?.let { throw it }
        return createdBook
    }
}

fun studioExportJob(
    state: String = "running", phase: String? = null, done: Int? = null, total: Int? = null, finishedAgo: Double? = null, result: StudioExportResult? = null, error: String = "",
) = StudioExportJob(state, "run1", phase, done, total, null, null, null, null, null, null, null, 5.0, finishedAgo, result, error)

fun exportResult(file: String = "Tắt đèn.abook", size: Long = 2_000_000) =
    StudioExportResult(file, "", size, 0, null, null, null, 0, "", false, 0, emptyList())

fun scannedChapter(path: String, title: String = path, matter: String = "", split: Int = 0, words: Int = 1000) =
    ScannedChapter(path, path, title, "", words, 600.0, matter, split, false)

fun precastView(ready: Boolean = true, wait: Boolean = false, announcedAt: Double? = null, held: Boolean = false, upcoming: List<PrecastChapter> = emptyList()) =
    PrecastView(ready, wait, announcedAt, held, upcoming.size, 0, null, upcoming)

fun musicScene(key: String, chapterId: Int = 1, start: Double = 0.0, end: Double = 60.0, link: String? = "t1", pinned: Boolean = false, silenced: Boolean = false, continued: Boolean = false) =
    MusicScene(key, chapterId, start, end, 0.0, 0.0, emptyMap(), link, pinned, silenced, continued, false, "labels")

fun musicView(
    enabled: Boolean = true, scenes: List<MusicScene> = emptyList(), tracks: Map<String, MusicTrack> = emptyMap(), genre: String? = null, levelDb: Double = -18.0,
    download: MusicDownload? = null, banned: List<String> = emptyList(),
) = MusicView(true, enabled, levelDb, genre, scenes, tracks, banned, emptyMap(), "", false, "", download, listOf("calm" to "Êm dịu"), emptyMap())

fun scriptLine(
    id: String, text: String, kind: String = "dialogue", current: String = "KATI", label: String = "Kati", seq: Int = 1, hint: ScriptHint? = null,
    wish: ScriptWish? = null, spoken: String? = null, hasAudio: Boolean = false, editable: Boolean = true,
) = ScriptLine(seq, id, "sha-$id", seq, text, kind, current, label, editable, hasAudio, hint, wish, spoken, null)

fun chapterScript(lines: List<ScriptLine>, id: Int = 1, previous: Int? = null, next: Int? = null) = ChapterScript(
    id, id, "Chương $id", previous, next, true, listOf(ScriptPerson("KATI", "Kati", 3)), listOf(ScriptPerson("TOM", "Tom", 1)), lines,
)
