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
import vn.abook.player.StudioClips
import vn.abook.player.StudioError
import vn.abook.player.StudioPaths
import vn.abook.player.ui.voice.SamplePlayer
import java.io.File
import java.nio.file.Files

/** Trạng thái ba tab nội dung với nguồn giả: bộ bài và hoàn tác, nghe lại (phán quyết, phân trang, nghe liền), nhân vật và bảng giọng. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioTabsStateTest {
    private class Player : SamplePlayer {
        var ended: (() -> Unit)? = null
        val played = ArrayList<String>()

        override fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit) {
            played += File(path).name
            ended = onEnded
        }

        override fun stop() = Unit
    }

    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val hold = CompletableDeferred<Unit>()
    private val source = FakeStudioSource(listOf(studioBook(running = true)))
    private val dir: File = Files.createTempDirectory("studio_tabs").toFile()
    private val player = Player()
    private val fetched = ArrayList<String>()
    private val clips = StudioClips(dir, { _, path, partial -> fetched += path; partial.writeBytes(ByteArray(4)) }, player, scope)
    private val project = StudioProjectState(StudioHub(source, scope, clips).session(""), "b1", pause = never, hold = { hold.await() })
    private val jobs = ArrayList<Job>()

    @After fun cleanUp() {
        jobs.forEach { it.cancel() }
        dir.deleteRecursively()
    }

    private fun launchRun(block: suspend () -> Unit) {
        jobs += scope.launch { block() }
    }

    private fun until(what: String, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + 5_000
        while (!condition()) {
            if (System.currentTimeMillis() > end) throw AssertionError("Hết giờ chờ: $what")
            Thread.sleep(5)
        }
    }

    // ---- Việc cần duyệt ----

    private fun deckKeys() = project.work.deck(project.work.poll.value.data).map { it.key }

    @Test fun theHeldCardLeavesTheDeckAndUndoBringsItBack() {
        source.workView = WorkView(listOf(speakerCard("a"), speakerCard("b")), emptyMap())
        launchRun { project.work.run() }
        assertEquals(listOf("a", "b"), deckKeys())
        project.work.decide(WorkDecisions.speaker(speakerCard("a"), "noah", WorkScope.Alternate, null))
        assertEquals(listOf("b"), deckKeys())
        project.decisions.undo()
        assertEquals(listOf("a", "b"), deckKeys())
        assertTrue(source.writes.isEmpty())
    }

    @Test fun afterTheSendTheDeckReloadsAndTheSentCardStopsBeingHidden() {
        source.workView = WorkView(listOf(speakerCard("a"), speakerCard("b")), emptyMap())
        launchRun { project.work.run() }
        project.work.decide(WorkDecisions.speaker(speakerCard("a"), "noah", WorkScope.Alternate, null))
        source.workView = WorkView(listOf(speakerCard("b")), emptyMap())
        hold.complete(Unit)
        assertEquals(1, source.writes.size)
        assertEquals(listOf("b"), deckKeys())
        assertTrue(project.decisions.away.isEmpty())
    }

    @Test fun aFailedSendReturnsTheCardWithoutResending() {
        source.workView = WorkView(listOf(speakerCard("a")), emptyMap())
        source.writeError = { StudioError.Busy("bận") }
        launchRun { project.work.run() }
        project.work.decide(WorkDecisions.speaker(speakerCard("a"), "noah", WorkScope.Alternate, null))
        hold.complete(Unit)
        assertEquals(listOf("a"), deckKeys())
        assertEquals(WorkText.STALE, project.decisions.notice)
        assertEquals(1, source.writes.size)
    }

    @Test fun skippingMovesACardToTheBottomAndDecidingItClearsTheSkip() {
        source.workView = WorkView(listOf(speakerCard("a"), speakerCard("b")), emptyMap())
        launchRun { project.work.run() }
        project.work.skip("a")
        assertEquals(listOf("b", "a"), deckKeys())
        assertTrue(source.writes.isEmpty())
        project.work.decide(WorkDecisions.speaker(speakerCard("a"), "noah", WorkScope.Alternate, null))
        assertTrue(project.work.skipped.isEmpty())
    }

    @Test fun leavingTheProjectSendsTheHeldDecisionAtOnce() {
        source.workView = WorkView(listOf(speakerCard("a")), emptyMap())
        launchRun { project.work.run() }
        project.work.decide(WorkDecisions.speaker(speakerCard("a"), "noah", WorkScope.Alternate, null))
        assertTrue(source.writes.isEmpty())
        project.leave()
        assertEquals(1, source.writes.size)
    }

    @Test fun morePickExamplesAskForTheNextHundredFromWhatIsLoaded() = runBlocking {
        source.examplesPage = WorkExamplesPage(listOf(workExample(4)), 9)
        val page = project.work.moreExamples(speakerCard(), 3)
        assertEquals(listOf(3 to 100), source.exampleCalls)
        assertEquals(9, page.total)
    }

    @Test fun aReadingIsCheckedBeforeItIsHeld() = runBlocking {
        val card = workItem(kind = WorkKind.Pronunciation, key = "p", surface = "Hên-kơ", current = "hen co")
        assertEquals(ReadingCheck.Ok, project.work.checkReading(card, "hen cơ"))
        source.writeError = { StudioError.Server("Chưa đọc được chữ này", 400, """{"suggestion":"hen cơ"}""") }
        assertEquals(ReadingCheck.Rejected("Chưa đọc được chữ này", "hen cơ"), project.work.checkReading(card, "hen!"))
        source.writeError = { StudioError.Offline() }
        assertTrue(project.work.checkReading(card, "hen cơ") is ReadingCheck.Failed)
        assertTrue(source.writes.all { it.first == "pronunciation/check" })
    }

    // ---- Cần nghe lại ----

    @Test fun aVerdictShowsAtOnceThenTheServersListTakesOver() {
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1), reviewItem(2)))
        launchRun { project.review.run() }
        assertEquals(listOf("r1", "r2"), project.review.items().map { it.stableId })
        source.writeGate = CompletableDeferred()
        project.review.judge(reviewItem(1), "ok")
        // Máy chưa trả lời: câu 1 đã hết khỏi "chưa xem".
        assertEquals(listOf("r2"), project.review.items().map { it.stableId })
        val body = source.writes.single().second
        assertEquals("ok", body.getString("verdict"))
        assertEquals("", body.getJSONObject("seen").getString("r1"))
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1, verdict = "ok"), reviewItem(2)))
        source.writeGate!!.complete(Unit)
        assertTrue(project.review.verdicts.isEmpty())
        assertEquals(listOf("r2"), project.review.items().map { it.stableId })
        project.review.pick(ReviewFilter.Done)
        assertEquals(listOf("r1"), project.review.items().map { it.stableId })
    }

    @Test fun aFailedVerdictSaysSoAndTheItemComesBack() {
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1)))
        launchRun { project.review.run() }
        source.writeError = { StudioError.Offline() }
        project.review.judge(reviewItem(1), "redo")
        assertEquals("Mất kết nối tới ABook.", project.review.problem)
        assertEquals(listOf("r1"), project.review.items().map { it.stableId })
    }

    @Test fun anEditMadeElsewhereOffersTheirVerdict() {
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1)))
        launchRun { project.review.run() }
        source.writeAnswers["review"] = JSONObject("""{"elsewhere":{"r1":"redo"}}""")
        project.review.judge(reviewItem(1), "ok")
        assertEquals("redo", project.review.elsewhere?.theirs)
        project.review.takeTheirs()
        assertEquals("redo", source.writes.last().second.getString("verdict"))
        assertNull(project.review.elsewhere)
    }

    @Test fun moreItemsFollowTheCursorAndKeepWhatIsAlreadyShown() {
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1)), next = "c1")
        source.reviewPages["c1"] = emptyReview(listOf(reviewItem(2)))
        launchRun { project.review.run() }
        assertEquals(1, project.review.items().size)
        project.review.loadMore()
        assertEquals(listOf("r1", "r2"), project.review.items().map { it.stableId })
        assertTrue(source.reviewCalls.any { it.third == "c1" })
    }

    @Test fun showingMinorItemsAsksForAllOfThem() {
        launchRun { project.review.run() }
        project.review.toggleMinor()
        assertTrue(source.reviewCalls.last().second)
        assertEquals("todo", source.reviewCalls.last().first)
    }

    @Test fun listenInARowMovesToTheNextPlayableSentenceAndThenStops() {
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1), reviewItem(2), reviewItem(3, playable = false)))
        launchRun { project.review.run() }
        project.review.startContinuous()
        until("câu 1") { clips.state.value.playing == "review-1" }
        player.ended!!.invoke()
        until("câu 2") { clips.state.value.playing == "review-2" }
        assertTrue(project.review.continuous)
        player.ended!!.invoke()
        until("hết") { project.review.finished }
        assertFalse(project.review.continuous)
        assertEquals(listOf(StudioPaths.sample("b1", 1), StudioPaths.sample("b1", 2)), fetched)
    }

    @Test fun aNotRecordedBookSaysNothingToReviewYet() {
        assertTrue(ReviewLogic.notRecordedYet(studioBook().copy(segmentsRecorded = 0)))
        assertFalse(ReviewLogic.notRecordedYet(studioBook().copy(segmentsRecorded = 3)))
        assertFalse(ReviewLogic.notRecordedYet(studioBook()))
    }

    @Test fun aSentenceWithoutItsOwnRecordingPlaysItsWindowInTheChapterFile() {
        val item = reviewItem(5, playable = false, chapterClip = ChapterWindow(1.5, 3.25))
        val spec = ReviewLogic.clip("", "b1", item)!!
        assertEquals(StudioPaths.chapterAudio("b1", 1), spec.path)
        assertEquals(1500, spec.startMs)
        assertEquals(3250, spec.endMs)
        assertNull(ReviewLogic.clip("", "b1", reviewItem(6, playable = false)))
    }

    // ---- Nhân vật và bảng giọng ----

    @Test fun theCastLoadsAndPlayingASampleFetchesItsRecording() {
        source.cast = Cast(CastNarrator("", 0, 0.0, null, null, 0), listOf(castMember("kati", sampleId = 7)), emptyList(), emptyList())
        launchRun { project.cast.run() }
        val member = project.cast.poll.value.data!!.characters.single()
        project.cast.playSample(member)
        until("phát mẫu") { clips.state.value.playing == StudioCastState.sampleId(member) }
        assertEquals(listOf(StudioPaths.sample("b1", 7)), fetched)
    }

    private fun sheet(character: String = "kati", gender: String = "female", voices: List<VoiceEntry>, pending: PendingChoice? = null): VoiceSheetState {
        source.voiceChoicesFor[character] = voiceChoices(character, gender, voices, pending)
        return project.cast.voiceSheet(character, "Kati").also { runBlocking { it.load() } }
    }

    @Test fun pickingAVoiceOfTheSameGenderIsHeldForUndoThenSentWithoutAGender() {
        val sheet = sheet(voices = listOf(voiceEntry("v1", gender = "female")))
        assertTrue(sheet.choose(sheet.choices!!.voices[0]))
        assertEquals("voice:kati", project.decisions.held?.decision?.key)
        assertTrue(source.writes.isEmpty())
        project.decisions.flush()
        val body = source.writes.single().second
        assertEquals("v1", body.getString("preset"))
        assertFalse(body.has("gender"))
    }

    @Test fun aVoiceOfTheOtherGenderAsksFirstAndSendsTheGenderOnlyWhenAgreed() {
        val sheet = sheet(voices = listOf(voiceEntry("m1", gender = "male")))
        val voice = sheet.choices!!.voices[0]
        assertFalse(sheet.choose(voice))
        assertEquals(voice, sheet.crossing)
        assertNull(project.decisions.held)
        assertFalse(sheet.answerCrossing(false))
        assertNull(project.decisions.held)
        sheet.choose(voice)
        assertTrue(sheet.answerCrossing(true))
        project.decisions.flush()
        assertEquals("male", source.writes.single().second.getString("gender"))
    }

    @Test fun theNarratorHasNoGenderToCross() {
        val sheet = sheet("NARRATOR", "female", listOf(voiceEntry("m1", gender = "male")))
        assertTrue(sheet.choose(sheet.choices!!.voices[0]))
        assertNull(sheet.crossing)
    }

    @Test fun keepingTheCurrentVoiceWithdrawsThePendingChoiceAtOnce() {
        val sheet = sheet(voices = listOf(voiceEntry("v1", gender = "female")), pending = PendingChoice("Giọng C", 5.5))
        sheet.keepCurrent()
        val body = source.writes.single().second
        assertTrue(body.getBoolean("withdraw"))
        assertEquals(5.5, body.getDouble("requestedAt"), 0.0)
        assertNull(project.decisions.held)
    }

    @Test fun tryingAVoiceOnTheBooksOwnSentenceAsksOnceThenReplaysFromMemory() {
        val sheet = sheet(voices = listOf(voiceEntry("v1", gender = "female")))
        val voice = sheet.choices!!.voices[0]
        source.writeAnswers["voice/preview"] = JSONObject("""{"url":"/media/books/b1/tries/1","segmentId":1,"text":"Chào","speaker":"Kati"}""")
        sheet.tryVoice(voice)
        assertEquals(listOf("voice/preview"), source.writes.map { it.first })
        assertEquals("kati", source.writes[0].second.getString("character"))
        assertTrue(sheet.said, sheet.said.contains("Chào"))
        until("phát") { clips.state.value.playing == sheet.heardClip(voice) }
        sheet.tryVoice(voice)
        assertEquals(1, source.writes.size)
    }

    @Test fun aCharacterWithNoLineFallsBackToTheSharedSample() {
        val sheet = sheet(voices = listOf(voiceEntry("v1", gender = "female")))
        source.writeError = { StudioError.Server("Chưa có câu", 400, """{"reason":"no-line"}""") }
        sheet.tryVoice(sheet.choices!!.voices[0])
        assertTrue(sheet.said, sheet.said.startsWith("Người này chưa có câu nào"))
        until("phát mẫu chung") { clips.state.value.playing == sheet.sampleClip(sheet.choices!!.voices[0]) }
        assertNotNull(fetched.firstOrNull())
    }

    @Test fun aRefusedPreviewSaysWhyInWords() {
        val sheet = sheet(voices = listOf(voiceEntry("v1", gender = "female", preview = false)))
        source.writeError = { StudioError.Server("busy", 409, """{"reason":"gpu"}""") }
        sheet.tryVoice(sheet.choices!!.voices[0])
        assertEquals("Card đồ hoạ đang bận - thử lại sau ít phút", sheet.said)
    }
}
