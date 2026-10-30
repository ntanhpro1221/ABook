package vn.abook.player.ui.studio

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.StudioError
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.util.Calendar

/**
 * S4 trên JVM với nguồn giả: xuất (kiểu, thân yêu cầu, theo việc, huỷ), nhật ký, và trình tạo sách ba bước (gửi file, quét, bỏ chương, tạo) - gồm đường gửi file
 * base64 ghi thẳng ra kết nối và giới hạn 17 MB nói trước.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioS4StateTest {
    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val source = FakeStudioSource(listOf(studioBook(running = false)))
    private val session = StudioHub(source, scope).session("")
    private val project = StudioProjectState(session, "b1", pause = never)
    private val jobs = ArrayList<Job>()

    @After fun cleanUp() {
        jobs.forEach { it.cancel() }
    }

    private fun launchRun(block: suspend () -> Unit) {
        jobs += scope.launch { block() }
    }

    // ---- Gửi file: thân JSON base64 ----

    private fun uploadBody(bytes: ByteArray): JSONObject {
        val out = ByteArrayOutputStream()
        StudioUpload.writer("Tải lên", "a \"b\".txt", ByteArrayInputStream(bytes))(out)
        return JSONObject(out.toString(Charsets.UTF_8))
    }

    @Test fun theUploadBodyIsValidJsonAndDecodesBackToTheSameBytesAtEveryChunkEdge() {
        for (size in listOf(0, 1, 2, 3, 4, 49_151, 49_152, 49_153, 100_000)) {
            val bytes = ByteArray(size) { (it * 31 + 7).toByte() }
            val json = uploadBody(bytes)
            assertEquals("Tải lên", json.getString("folder"))
            assertEquals("a \"b\".txt", json.getString("name"))
            assertTrue("size $size", bytes.contentEquals(Base64.getDecoder().decode(json.getString("data"))))
        }
    }

    // ---- Logic gửi file ----

    @Test fun theUploadLimitIsTheRealOneAndTheWrongKindOfFileIsNeverSent() {
        assertEquals(17L * 1024 * 1024, StudioNewLogic.UPLOAD_LIMIT)
        assertEquals(UploadStatus.Waiting, StudioNewLogic.initial("Truyện.TXT", 1000))
        assertEquals(UploadStatus.Waiting, StudioNewLogic.initial("a.epub", StudioNewLogic.UPLOAD_LIMIT))
        assertEquals(UploadStatus.TooBig, StudioNewLogic.initial("a.pdf", StudioNewLogic.UPLOAD_LIMIT + 1))
        assertEquals(UploadStatus.NotStory, StudioNewLogic.initial("anh.jpg", 10))
        assertTrue(StudioNewText.LIMIT_NOTE.contains("17 MB"))
    }

    @Test fun twoFilesWithTheSameNameDoNotOverwriteEachOther() {
        assertEquals("a.txt", StudioNewLogic.uniqueName("a.txt", emptyList()))
        assertEquals("a (2).txt", StudioNewLogic.uniqueName("a.txt", listOf("a.txt")))
        assertEquals("a (3).txt", StudioNewLogic.uniqueName("a.txt", listOf("a.txt", "a (2).txt")))
    }

    @Test fun theBatchFolderNamesTheDayAndMinute() {
        val now = Calendar.getInstance().apply { set(2026, Calendar.OCTOBER, 5, 18, 22, 0) }
        assertEquals("Tải lên 05-10-2026 18h22 ab12", StudioNewLogic.batchName(now, "ab12"))
    }

    @Test fun theCreateBodyCarriesOnlyWhatWasChosen() {
        val plain = StudioNewLogic.body(listOf("p1", "p2"), " Tắt đèn ", NewProfile.High, " ", "", false, true)
        assertEquals("Tắt đèn", plain.getString("title"))
        assertEquals("high_quality", plain.getString("profile"))
        assertEquals("", plain.getString("narrator"))
        assertEquals(2, plain.getJSONArray("paths").length())
        assertTrue(plain.getBoolean("start"))
        assertFalse(plain.has("analysisModel"))
        assertFalse(plain.has("precastWait"))
        val full = StudioNewLogic.body(listOf("p"), "T", NewProfile.Fast, "Kati", "qwen", true, false)
        assertEquals("qwen", full.getString("analysisModel"))
        assertTrue(full.getBoolean("precastWait"))
        assertFalse(full.getBoolean("start"))
        assertEquals("Kati", full.getString("firstPerson"))
    }

    @Test fun matterPagesStayOutUntilTheListenerKeepsThem() {
        val files = listOf(scannedChapter("a"), scannedChapter("cover", matter = "bìa"), scannedChapter("b"))
        assertEquals(listOf("a", "b"), StudioNewLogic.kept(files, emptySet(), emptySet()).map { it.path })
        assertEquals(listOf("a", "cover", "b"), StudioNewLogic.kept(files, emptySet(), setOf("cover")).map { it.path })
        assertEquals(listOf("b"), StudioNewLogic.kept(files, setOf("a"), emptySet()).map { it.path })
    }

    // ---- Trình tạo sách ----

    private fun newState() = StudioNewState(session, "Tải lên")

    private fun pickText(name: String, text: String) = PickedFile(name, text.length.toLong()) { ByteArrayInputStream(text.toByteArray()) }

    @Test fun pickedFilesAreSentOneByOneIntoOneFolderAndTheSourceReferenceIsKept() {
        val state = newState()
        state.add(listOf(pickText("a.txt", "xin chào"), pickText("b.txt", "tạm biệt")))
        assertEquals(listOf("a.txt", "b.txt"), source.uploads.map { it.second })
        assertTrue(source.uploads.all { it.first == "Tải lên" })
        assertEquals("xin chào", String(source.uploads[0].third))
        assertEquals(listOf(UploadStatus.Sent, UploadStatus.Sent), state.rows.map { it.status })
        assertTrue(state.canScan)
        assertEquals(listOf("Tải lên/a.txt", "Tải lên/b.txt"), StudioNewLogic.paths(state.rows))
    }

    @Test fun aTooBigOrNonStoryFileIsNeverSentAndSaysWhy() {
        val state = newState()
        state.add(listOf(PickedFile("lon.txt", StudioNewLogic.UPLOAD_LIMIT + 1) { ByteArrayInputStream(ByteArray(0)) }, pickText("anh.jpg", "x")))
        assertTrue(source.uploads.isEmpty())
        assertEquals(listOf(UploadStatus.TooBig, UploadStatus.NotStory), state.rows.map { it.status })
        assertTrue(state.rows[0].problem.contains("17 MB"))
        assertFalse(state.canScan)
    }

    @Test fun theGatewaysTooBigAnswerBecomesTheSameWordsAndOtherFailuresCanBeRetried() {
        val state = newState()
        source.uploadError = StudioError.TooBig()
        state.add(listOf(pickText("a.txt", "x")))
        assertEquals(UploadStatus.TooBig, state.rows.single().status)
        val failing = newState()
        source.uploadError = StudioError.Offline()
        failing.add(listOf(pickText("b.txt", "x")))
        assertEquals(UploadStatus.Failed, failing.rows.single().status)
        source.uploadError = null
        failing.retry(failing.rows.single().id)
        assertEquals(UploadStatus.Sent, failing.rows.single().status)
    }

    @Test fun cancellingAFileThatIsBeingSentDropsItWhenTheSendReturns() {
        val state = newState()
        source.uploadGate = CompletableDeferred()
        state.add(listOf(pickText("a.txt", "x")))
        val row = state.rows.single()
        assertEquals(UploadStatus.Sending, row.status)
        state.remove(row.id)
        source.uploadGate!!.complete(Unit)
        assertTrue(state.rows.isEmpty())
        assertFalse(state.canScan)
    }

    @Test fun pastedTextBecomesATxtFileLikeAnyOther() {
        val state = newState()
        state.addText("  Chương 1\nXin chào  ")
        assertEquals("Chữ dán.txt", source.uploads.single().second)
        assertEquals("Chương 1\nXin chào", String(source.uploads.single().third))
        state.addText("   ")
        assertEquals(1, state.rows.size)
    }

    @Test fun theThreeStepsGoSourceChaptersStartAndCreateOpensTheNewBook() {
        source.scanView = ScanView(
            listOf(scannedChapter("c1"), scannedChapter("c2"), scannedChapter("bia", matter = "bìa")), emptyList(), emptyList(), emptyList(), "Tắt đèn", emptyList(),
        )
        source.firstPersonView = FirstPersonView(true, 0.8, listOf("Kati"))
        source.modelsView = AnalysisModels("m1", listOf(AnalysisModel("m1", 1, ""), AnalysisModel("m2", 2, "")), true)
        val state = newState()
        state.add(listOf(pickText("a.txt", "x")))
        state.next()
        assertEquals(NewStep.Chapters, state.step)
        assertEquals(listOf(listOf("Tải lên/a.txt")), source.scanCalls)
        assertEquals("Tắt đèn", state.title)
        assertEquals(listOf("c1", "c2"), state.kept.map { it.path })
        state.toggle("c1")
        state.toggle("bia")
        assertEquals(listOf("c2", "bia"), state.kept.map { it.path })
        state.next()
        assertEquals(NewStep.Start, state.step)
        assertEquals("Kati", state.hint?.suggestions?.single())
        assertEquals(listOf("m2"), state.models?.others?.map { it.name })
        state.editTitle("Tắt đèn (bản mới)")
        state.pickProfile(NewProfile.Balanced)
        state.chooseWait(true)
        state.create()
        val body = source.creates.single()
        assertEquals("Tắt đèn (bản mới)", body.getString("title"))
        assertEquals("balanced", body.getString("profile"))
        assertEquals(listOf("c2", "bia"), (0 until body.getJSONArray("paths").length()).map { body.getJSONArray("paths").getString(it) })
        assertTrue(body.getBoolean("precastWait"))
        assertEquals("new1", state.created?.id)
    }

    @Test fun anEmptyScanStaysOnTheSourceStepWithAReason() {
        source.scanView = ScanView(emptyList(), listOf("File rỗng"), emptyList(), emptyList(), "", emptyList())
        val state = newState()
        state.add(listOf(pickText("a.txt", "x")))
        state.next()
        assertEquals(NewStep.Source, state.step)
        assertEquals("File rỗng", state.problem)
    }

    @Test fun aFailedCreateKeepsTheWizardAndShowsTheMachinesWords() {
        source.scanView = ScanView(listOf(scannedChapter("c1")), emptyList(), emptyList(), emptyList(), "T", emptyList())
        source.createError = StudioError.Server("Tên sách đã có", 409)
        val state = newState()
        state.add(listOf(pickText("a.txt", "x")))
        state.next()
        state.next()
        state.create()
        assertNull(state.created)
        assertEquals("Tên sách đã có", state.problem)
        assertFalse(state.creating)
    }

    @Test fun splittingReplacesTheFileWithTheChapterFolderAndScansAgain() {
        source.scanView = ScanView(listOf(scannedChapter("Tải lên/a.txt", split = 12)), emptyList(), emptyList(), emptyList(), "T", emptyList())
        val state = newState()
        state.add(listOf(pickText("a.txt", "x")))
        state.next()
        state.split(state.scan!!.files.single())
        assertEquals(listOf("Tải lên/a.txt"), source.splits)
        assertEquals(listOf("Tải lên/a.txt.chuong"), source.scanCalls.last())
    }

    // ---- Xuất ----

    @Test fun theExportBodyIsPerKindAndTheDefaultTargetIsTheDesktopsExportedFolder() {
        val book = StudioExportLogic.body(StudioExportKind.BookFile, true, "data:x")
        assertEquals("", book.getString("target"))
        assertFalse(book.getBoolean("series"))
        assertFalse(book.has("cover"))
        assertFalse(book.has("music"))
        val m4b = StudioExportLogic.body(StudioExportKind.M4b, true, "data:image/png;base64,AA==")
        assertEquals("data:image/png;base64,AA==", m4b.getString("cover"))
        assertTrue(m4b.getBoolean("music"))
        val mp3 = StudioExportLogic.body(StudioExportKind.Mp3, false, "")
        assertFalse(mp3.has("cover"))
        assertFalse(mp3.has("music"))
    }

    @Test fun anAudioExportNeedsARecordedChapterAndABookFileNeedsAnyChapter() {
        val empty = studioBook(chaptersTotal = 0, chaptersCompleted = 0)
        val text = studioBook(chaptersTotal = 5, chaptersCompleted = 0)
        assertFalse(StudioExportLogic.canExport(StudioExportKind.BookFile, empty))
        assertTrue(StudioExportLogic.canExport(StudioExportKind.BookFile, text))
        assertFalse(StudioExportLogic.canExport(StudioExportKind.M4b, text))
        assertEquals(StudioExportText.NO_AUDIO, StudioExportLogic.blocker(StudioExportKind.Mp3, text))
        assertEquals("", StudioExportLogic.blocker(StudioExportKind.M4b, studioBook()))
    }

    @Test fun ffmpegOnlyMattersWhereTheMachineNeedsIt() {
        val missing = StudioExportOptions(ffmpegReady = false)
        assertTrue(StudioExportLogic.needsFfmpeg(StudioExportKind.M4b, false, missing))
        assertFalse(StudioExportLogic.needsFfmpeg(StudioExportKind.Mp3, false, missing))
        assertTrue(StudioExportLogic.needsFfmpeg(StudioExportKind.Mp3, true, missing))
        assertFalse(StudioExportLogic.needsFfmpeg(StudioExportKind.BookFile, true, missing))
        assertFalse(StudioExportLogic.needsFfmpeg(StudioExportKind.M4b, false, StudioExportOptions(ffmpegReady = null)))
    }

    @Test fun aFinishedJobShowsOnlyWhileItIsRecent() {
        assertFalse(StudioExportLogic.shown(null))
        assertFalse(StudioExportLogic.shown(studioExportJob("idle")))
        assertTrue(StudioExportLogic.shown(studioExportJob("running")))
        assertTrue(StudioExportLogic.shown(studioExportJob("done", finishedAgo = 60.0)))
        assertFalse(StudioExportLogic.shown(studioExportJob("done", finishedAgo = StudioExportLogic.RECENT_SECONDS + 1.0)))
    }

    @Test fun theDoneLineNamesTheMachineTheFileAndWhatIsMissing() {
        val result = StudioExportResult("Tắt đèn.abook", "", 2_000_000, 0, null, 3, 10, 1, "", true, 2, emptyList())
        val outcome = StudioExportLogic.outcome(StudioExportKind.BookFile, result, "Máy bàn")
        assertEquals("Đã xuất vào máy tính Máy bàn", outcome.title)
        assertTrue(outcome.lines.single().startsWith("Tắt đèn.abook"))
        assertEquals(4, outcome.notes.size)
        assertEquals("Đã xuất vào máy tính", StudioExportText.doneTitle(""))
    }

    @Test fun aWindowsPathFromTheMachineShowsOnlyItsName() {
        assertEquals("Tắt đèn", StudioExportLogic.pastName(StudioPast("mp3", "D:\\Sach\\Đã xuất\\Tắt đèn\\", 0)))
        assertEquals("File sách · b.abook", StudioExportLogic.pastTitle(StudioPast("abook", "/x/b.abook", 0)))
        assertEquals("Còn mới", StudioExportLogic.pastLine(StudioPast("abook", "b", 0)))
    }

    @Test fun theExportJsonReadsTheMachinesJobAndKeepsOnlyNames() {
        val job = StudioExportJson.job(
            JSONObject("""{"state":"done","id":"r","elapsed":3.5,"finishedAgo":12,"result":{"file":"a.abook","size":99,"parts":[1,2],"skipped":[{"part":2}],"coverBroken":true}}"""),
        )
        assertEquals("done", job.state)
        assertEquals(12.0, job.finishedAgo!!, 0.0)
        assertEquals(99L, job.result!!.size)
        assertEquals(2, job.result!!.parts)
        assertEquals(listOf(2), job.result!!.skipped)
        assertTrue(job.result!!.coverBroken)
        assertNull(StudioExportJson.job(JSONObject("""{"state":"running"}""")).finishedAgo)
    }

    private fun exportState(): StudioExportState = StudioExportState(project, never)

    @Test fun startingAnExportPostsTheBodyOnceAndFollowsTheJob() {
        launchRun { project.run() }
        val export = exportState()
        launchRun { export.run() }
        assertTrue(export.loaded)
        export.drawCover = { "data:image/png;base64,AA==" }
        export.choose(StudioExportKind.M4b)
        export.start()
        val (kind, body) = source.exportStarts.single()
        assertEquals(StudioExportKind.M4b, kind)
        assertEquals("", body.getString("target"))
        assertEquals("data:image/png;base64,AA==", body.getString("cover"))
        assertTrue(export.job?.running == true)
        export.start()
        assertEquals(1, source.exportStarts.size)
    }

    @Test fun aBookFileExportSendsNoCover() {
        launchRun { project.run() }
        val export = exportState()
        launchRun { export.run() }
        export.drawCover = { "data:image/png;base64,AA==" }
        export.start()
        assertFalse(source.exportStarts.single().second.has("cover"))
    }

    @Test fun theMachinesRefusalToStartIsShownInItsWordsAndNothingIsRunning() {
        launchRun { project.run() }
        val export = exportState()
        launchRun { export.run() }
        source.exportStartError = StudioError.Busy("Máy đang xuất cuốn khác")
        export.start()
        assertEquals("Máy đang xuất cuốn khác", export.problem)
        assertFalse(export.starting)
        assertTrue(export.job?.running != true)
    }

    @Test fun whenTheRunningJobEndsTheStopWaitClearsAndTheHistoryReloads() {
        launchRun { project.run() }
        val export = exportState()
        source.exportJobs[StudioExportKind.BookFile] = studioExportJob("running")
        launchRun { export.run() }
        val before = source.exportOptionsCalls
        export.cancel()
        assertTrue(export.stopping)
        assertEquals(listOf(StudioExportKind.BookFile), source.exportCancels)
        source.exportJobs[StudioExportKind.BookFile] = studioExportJob("cancelled", finishedAgo = 1.0)
        runBlocking { export.refresh() }
        assertFalse(export.stopping)
        assertEquals("cancelled", export.job?.state)
        assertEquals(before + 1, source.exportOptionsCalls)
    }

    @Test fun eachKindHasItsOwnJobAndALateAnswerForTheOldKindIsNotShownForTheNew() {
        launchRun { project.run() }
        val export = exportState()
        source.exportJobs[StudioExportKind.BookFile] = studioExportJob("done", finishedAgo = 5.0, result = exportResult())
        launchRun { export.run() }
        assertEquals("done", export.job?.state)
        export.choose(StudioExportKind.Mp3)
        assertEquals("idle", export.job?.state)
        assertTrue(StudioExportKind.Mp3 in source.exportCalls)
    }

    @Test fun theMusicSwitchFollowsTheBooksSettingUntilTheListenerChoosesAndOnlyForAudio() {
        val options = StudioExportOptions(music = vn.abook.player.ui.export.ExportMusic(available = true, enabled = true))
        assertTrue(StudioExportLogic.musicOn(StudioExportKind.M4b, options, null))
        assertFalse(StudioExportLogic.musicOn(StudioExportKind.M4b, options, false))
        assertFalse(StudioExportLogic.musicOn(StudioExportKind.BookFile, options, true))
        assertFalse(StudioExportLogic.musicOn(StudioExportKind.Mp3, StudioExportOptions(), true))
    }

    // ---- Nhật ký ----

    @Test fun theLogIsNewestFirstAndTheTechnicalSwitchAsksAgainAtOnce() {
        source.activityItems = listOf(StudioLogItem("1", 100.0, "info", "", "Bắt đầu"), StudioLogItem("2", 200.0, "error", "E1", "Hỏng"))
        launchRun { project.run() }
        val activity = StudioLogState(project, never)
        launchRun { activity.run() }
        assertEquals(listOf("2", "1"), StudioLogLogic.ordered(activity.poll.value.data!!).map { it.id })
        assertEquals(listOf(false), source.activityCalls)
        activity.showTechnical(true)
        assertEquals(listOf(false, true), source.activityCalls)
        activity.showTechnical(true)
        assertEquals(2, source.activityCalls.size)
    }

    @Test fun theInfoFactsAreStatusChaptersAndLength() {
        val page = StudioPage(studioBook(chaptersTotal = 10, chaptersCompleted = 4), listOf(studioChapter(1, seconds = 3600.0)))
        val facts = StudioLogLogic.facts(page)
        assertEquals(listOf("Trạng thái", "Chương", "Dài"), facts.map { it.first })
        assertEquals("4/10 xong", facts[1].second)
    }

    // ---- Màn con ----

    @Test fun moreAlwaysOffersCoverAndLogAndExportOnlyWhenThereAreChapters() {
        val fresh = StudioLogic.subPages(studioBook(chaptersTotal = 0, chaptersCompleted = 0))
        assertEquals(listOf(StudioSubKind.Cover, StudioSubKind.Activity), fresh)
        assertTrue(StudioSubKind.Export in StudioLogic.subPages(studioBook()))
        assertNotNull(StudioSubKind.of("export"))
        assertEquals(StudioExportText.TITLE, StudioText.subLabel(StudioSubKind.Export))
    }
}
