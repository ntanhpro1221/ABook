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

/**
 * S3 trên JVM với nguồn giả: cách đọc tên (tìm, lưu qua kiểm rồi giữ 15 giây, bỏ dòng ghi công), duyệt trước khi thu (bước, công tắc chờ), nhạc nền (thân PUT, đường chậm,
 * nhịp hỏi) và kịch bản (lọc, đổi người nói, chữ đem đọc - chữ của sách không bao giờ đổi).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioS3StateTest {
    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val hold = CompletableDeferred<Unit>()
    private val source = FakeStudioSource(listOf(studioBook(running = true)))
    private val session = StudioHub(source, scope).session("")
    private val project = StudioProjectState(session, "b1", pause = never, hold = { hold.await() })
    private val jobs = ArrayList<Job>()

    @After fun cleanUp() {
        jobs.forEach { it.cancel() }
    }

    private fun launchRun(block: suspend () -> Unit) {
        jobs += scope.launch { block() }
    }

    private fun reading(surface: String, spoken: String = "", byListener: Boolean = false, requested: String? = null) =
        NameReading(surface, spoken, byListener, 3, requested, false, null)

    // ---- Cách đọc tên ----

    @Test fun searchIgnoresCaseMarksHyphensAndSpaces() {
        val items = listOf(reading("Hencho", "Hên-cơ"), reading("Dalat", "Đác-lát"), reading("Noah", "Nô-a"))
        assertEquals(listOf("Hencho"), ReadingsLogic.find(items, "hen").map { it.surface })
        assertEquals(listOf("Dalat"), ReadingsLogic.find(items, "dac lat").map { it.surface })
        assertEquals(3, ReadingsLogic.find(items, "  ").size)
    }

    @Test fun aSingleUnknownWordCanBeAddedButASentenceCannot() {
        assertTrue(ReadingsLogic.addable("TP.HCM", emptyList()))
        assertFalse(ReadingsLogic.addable("hai chữ", emptyList()))
        assertFalse(ReadingsLogic.addable("Noah", listOf(reading("Noah"))))
    }

    @Test fun savingTheCurrentReadingIsKeptNotChanged() {
        val data = NameReadings(listOf(reading("Noah", "Nô-a")), 0)
        val kept = ReadingsLogic.withReading(data, data.items[0], "Nô-a").items[0]
        assertNull(kept.requested)
        assertTrue(kept.byListener)
        val changed = ReadingsLogic.withReading(data, data.items[0], "Nố-a").items[0]
        assertEquals("Nố-a", changed.requested)
    }

    @Test fun theSaveBodyCarriesWhatTheScreenSawAndTheEverywhereFlagOnlyWhenOn() {
        val seenNothing = ReadingsLogic.saveStep(reading("Noah"), "Nô-a", false).body
        assertEquals("", seenNothing.getString("seen"))
        assertFalse(seenNothing.has("everywhere"))
        val pending = ReadingsLogic.saveStep(reading("Noah", "Nô-a", requested = "Nố-a"), "No-a", true).body
        assertEquals("Nố-a", pending.getString("seen"))
        assertTrue(pending.getBoolean("everywhere"))
        assertEquals("Nô-a", ReadingsLogic.saveStep(reading("Noah", "Nô-a", byListener = true), "x", false).body.getString("seen"))
    }

    @Test fun savingChecksFirstThenHoldsFifteenSecondsAndSendsOnce() {
        val state = StudioReadingsState(session, "b1", hold = { hold.await() }, pause = never)
        val item = reading("Noah", "Nô-a")
        val checked = runBlocking { state.save(item, "Nố-a", false) }
        assertEquals(ReadingCheck.Ok, checked)
        assertEquals(listOf("pronunciation/check"), source.writes.map { it.first })
        assertNotNull(state.decisions.held)
        hold.complete(Unit)
        assertEquals(listOf("pronunciation/check", "pronunciation"), source.writes.map { it.first })
        assertEquals("Nố-a", source.writes.last().second.getString("spokenForm"))
    }

    @Test fun aRejectedReadingNeverStartsTheHold() {
        source.writeError = { step -> if (step.endpoint == "pronunciation/check") StudioError.Server("Máy không đọc được chữ này", 400) else null }
        val state = StudioReadingsState(session, "b1", hold = { hold.await() }, pause = never)
        val checked = runBlocking { state.save(reading("Noah"), "###", false) }
        assertTrue(checked is ReadingCheck.Rejected)
        assertNull(state.decisions.held)
        assertEquals(listOf("pronunciation/check"), source.writes.map { it.first })
    }

    @Test fun skippingACreditLineIsAPutAndNeverTouchesTheStoryText() {
        val state = StudioReadingsState(session, "b1", hold = { hold.await() }, pause = never)
        source.creditGroups = listOf(CreditGroup("Dịch bởi X", listOf(1, 2), false))
        launchRun { state.run() }
        assertEquals(1, state.credits.size)
        state.skipLine(state.credits[0], true)
        val (endpoint, body, slow) = source.puts.single()
        assertEquals("skip", endpoint)
        assertFalse(slow)
        assertEquals("Dịch bởi X", body.getString("line"))
        assertTrue(body.getBoolean("skip"))
        assertEquals(2, body.getJSONArray("chapters").length())
        assertTrue(state.credits[0].skipped)
        assertTrue(source.writes.isEmpty())
    }

    @Test fun usingTheSharedReadingsIsOnePostAndClearsTheOffer() {
        val state = StudioReadingsState(session, "b1", hold = { hold.await() }, pause = never)
        source.offer = listOf(SharedReading("Noah", "Nô-a", "Sách khác"))
        launchRun { state.run() }
        assertEquals(1, state.offer.size)
        state.applyShared()
        assertEquals(listOf("shared-readings"), source.writes.map { it.first })
        assertTrue(state.offer.isEmpty())
        assertEquals(ReadingsText.sharedDone(1), state.notice)
    }

    // ---- Duyệt trước khi thu ----

    @Test fun theReviewOpensOnlyWhenTheCastIsLockedAndTheBookIsNotDone() {
        assertTrue(PrecastLogic.canReview(studioBook(phase = "synthesis", castLocked = true)))
        assertFalse(PrecastLogic.canReview(studioBook(phase = "done", castLocked = true)))
        assertFalse(PrecastLogic.canReview(studioBook(phase = "analysis")))
    }

    @Test fun theWaitSwitchOnlyMeansSomethingBeforeTheMark() {
        assertTrue(PrecastLogic.showWait(precastView()))
        assertFalse(PrecastLogic.showWait(precastView(announcedAt = 5.0)))
        assertEquals(PrecastText.WAIT_PASSED, PrecastLogic.waitHint(precastView(announcedAt = 5.0)))
    }

    @Test fun theStepsAdvanceAndStopAtTheEnd() {
        assertEquals(PrecastStep.Names, PrecastLogic.next(PrecastStep.Cast))
        assertEquals(PrecastStep.Done, PrecastLogic.next(PrecastStep.Done))
        assertEquals("Chương 1 → Chương 3", PrecastLogic.chapterRange(listOf(PrecastChapter(1, "Chương 1"), PrecastChapter(2, "Chương 2"), PrecastChapter(3, "Chương 3"))))
    }

    @Test fun theWaitSwitchIsAPutAndTheStepsAreLocalOnly() {
        launchRun { project.precast.run() }
        project.precast.next()
        assertEquals(PrecastStep.Names, project.precast.step)
        assertTrue(source.puts.isEmpty())
        project.precast.setWait(true)
        val (endpoint, body, _) = source.puts.single()
        assertEquals("precast", endpoint)
        assertTrue(body.getBoolean("wait"))
        assertEquals("", project.precast.problem)
    }

    @Test fun aRefusedWaitSwitchSaysWhy() {
        source.putError = StudioError.ListenOnly()
        project.precast.setWait(true)
        assertTrue(project.precast.problem.isNotEmpty())
        assertTrue(session.listenOnly)
    }

    // ---- Nhạc nền ----

    @Test fun theMusicBodiesUseTheWebKeys() {
        val scene = musicScene("s1", silenced = true)
        assertEquals("""{"enabled":false}""", MusicLogic.enabled(false).toString())
        assertEquals(-12.0, MusicLogic.level(-12.0).getDouble("levelDb"), 0.0)
        assertTrue(MusicLogic.genre(null).isNull("genre"))
        val pin = MusicLogic.pin(scene, "a/b.mp3")
        assertEquals("a/b.mp3", pin.getJSONObject("pins").getString("s1"))
        assertFalse(pin.getJSONObject("silence").getBoolean("s1"))
        assertTrue(MusicLogic.unpin("s1").getJSONObject("pins").isNull("s1"))
        assertEquals("x", MusicLogic.ban("x").getJSONArray("ban").getString(0))
        assertEquals("x", MusicLogic.unban("x").getJSONArray("unban").getString(0))
    }

    @Test fun onlyAGenreChangeTakesTheSlowPath() {
        assertTrue(MusicLogic.rebuilds(MusicLogic.genre("calm")))
        assertFalse(MusicLogic.rebuilds(MusicLogic.level(-12.0)))
        launchRun { project.music.run() }
        project.music.change(MusicLogic.genre("calm"))
        project.music.change(MusicLogic.level(-12.0))
        assertEquals(listOf(true, false), source.puts.map { it.third })
        assertTrue(source.puts.all { it.first == "music" })
    }

    @Test fun rebuildingPostsOnTheSlowPathAndNeverTwiceAtOnce() {
        val gate = CompletableDeferred<Unit>()
        source.writeGate = gate
        project.music.rebuild()
        project.music.rebuild()
        gate.complete(Unit)
        assertEquals(listOf("music/rebuild"), source.writes.map { it.first })
        assertEquals("", project.music.busy)
    }

    @Test fun theMusicPollOnlyTicksWhileSomethingIsRunning() {
        assertNull(MusicLogic.interval(null))
        assertNull(MusicLogic.interval(musicView()))
        assertEquals(MusicLogic.DOWNLOAD_REFRESH_MS, MusicLogic.interval(musicView(download = MusicDownload(true, 1, 4, 0, 0))))
    }

    @Test fun aSceneNamesItsMoodFromTheStrongestEmotions() {
        val names = mapOf("sadness" to "buồn")
        val sad = musicScene("s1").copy(emotions = mapOf("sadness" to 0.9, "joy" to 0.6, "fear" to 0.1))
        assertEquals("buồn · vui tươi", MusicLogic.moodOf(sad, names))
        assertEquals("êm", MusicLogic.moodOf(musicScene("s2"), names))
        assertEquals("căng thẳng", MusicLogic.moodOf(musicScene("s3").copy(tension = 0.8), names))
    }

    @Test fun aContinuedPieceIsCompactUntilItIsPinned() {
        assertTrue(MusicLogic.isContinuation(musicScene("s1", continued = true)))
        assertFalse(MusicLogic.isContinuation(musicScene("s1", continued = true, pinned = true)))
        assertEquals("Đổi từ đây", MusicLogic.swapText(musicScene("s1", continued = true)))
    }

    @Test fun theMusicJsonIsReadAsTheWebSendsIt() {
        val json = JSONObject(
            """{"plan":{"scenes":[{"key":"s1","chapterId":2,"start":0,"end":30,"link":"a/b.mp3","emotions":{"joy":0.8},"moodSource":"llm"}],"tracks":{"a/b.mp3":{"title":"Bài A","creator":"Ai","license":"cc0"}}},""" +
                """"overrides":{"enabled":false,"levelDb":-12,"genre":"calm","banned":["z"]},"taxonomy":{"genres":{"calm":{"vi":"Êm dịu"}}},"download":{"active":true,"done":1,"total":3}}""",
        )
        val view = StudioMusicJson.view(json)
        assertFalse(view.enabled)
        assertEquals(-12.0, view.levelDb, 0.0)
        assertEquals("calm", view.genre)
        assertEquals(listOf("calm" to "Êm dịu"), view.genres)
        assertEquals("s1", view.scenes.single().key)
        assertEquals("Bài A · Ai", MusicLogic.trackLabel("a/b.mp3", view.tracks["a/b.mp3"]))
        assertTrue(MusicLogic.byAi(view.scenes.single()))
        assertEquals(listOf("z"), view.banned)
        assertEquals(3, view.download?.total)
    }

    // ---- Kịch bản ----

    private fun script(vararg lines: ScriptLine) = chapterScript(lines.toList())

    @Test fun theDoubtFilterKeepsTheSpokenLineBeforeEachDoubtAsContext() {
        val hint = ScriptHint("who", "Chưa chắc ai nói", null)
        val lines = listOf(
            scriptLine("n1", "Trời mưa.", kind = "narration"),
            scriptLine("d1", "Chào anh.", seq = 2),
            scriptLine("d2", "Em đây.", seq = 3, hint = hint),
            scriptLine("d3", "Ừ.", seq = 4),
        )
        val shown = ScriptLogic.visible(lines, ScriptFilter.Doubt)
        assertEquals(listOf("d1" to true, "d2" to false), shown.map { it.line.stableId to it.context })
        assertEquals(listOf("d1", "d2", "d3"), ScriptLogic.visible(lines, ScriptFilter.Speech).map { it.line.stableId })
        assertEquals(4, ScriptLogic.visible(lines, ScriptFilter.All).size)
        assertEquals(1, ScriptLogic.doubts(lines))
    }

    @Test fun changingTheSpeakerIsHeldThenPostedWithWhatTheScreenSaw() {
        val line = scriptLine("d1", "Chào anh.")
        source.scriptContents = ScriptContents(true, listOf(ScriptEntry(1, 1, "Chương 1", 1, 1, 0, 0)))
        source.scriptChapters[1] = script(line)
        val state = StudioScriptState(session, "b1", hold = { hold.await() })
        launchRun { state.load() }
        assertEquals(1, state.chapter)
        assertEquals("d1", state.script?.lines?.single()?.stableId)
        state.assign(line, ScriptPerson("TOM", "Tom", 1))
        assertEquals("TOM", state.shown()?.lines?.single()?.wish?.value)
        assertTrue(source.writes.isEmpty())
        hold.complete(Unit)
        val (endpoint, body) = source.writes.single()
        assertEquals("speaker", endpoint)
        assertEquals("TOM", body.getString("speaker"))
        assertEquals("d1", body.getJSONArray("lines").getJSONObject(0).getString("stableId"))
        assertEquals("", body.getJSONObject("seen").getString("d1"))
    }

    @Test fun theSpokenTextOnlyChangesWhatIsReadAndEmptyMeansTheBooksOwnText() {
        val line = scriptLine("d1", "Ông Bảy đến.")
        assertNull(ScriptLogic.spokenChange(line, "Ông Bảy đến."))
        assertNull(ScriptLogic.spokenChange(line, "  Ông   Bảy  đến.  "))
        assertEquals("Ông Bẩy đến.", ScriptLogic.spokenChange(line, "Ông Bẩy đến."))
        val edited = line.copy(spoken = "Ông Bẩy đến.")
        assertEquals("", ScriptLogic.spokenChange(edited, ""))
        assertEquals("", ScriptLogic.spokenChange(edited, "Ông Bảy đến."))
        assertNull(ScriptLogic.spokenChange(line, ""))
        val step = ScriptLogic.speak(line, "Ông Bẩy đến.").steps.single()
        assertEquals("line", step.endpoint)
        assertEquals("Ông Bẩy đến.", step.body.getString("spoken"))
        assertTrue(step.body.isNull("seen"))
        assertEquals("Ông Bảy đến.", line.text)
    }

    @Test fun openingAnotherChapterSendsTheHeldDecisionFirst() {
        val a = scriptLine("d1", "Chào anh.")
        source.scriptContents = ScriptContents(true, listOf(ScriptEntry(1, 1, "Chương 1", 1, 1, 0, 0), ScriptEntry(2, 2, "Chương 2", 1, 1, 0, 0)))
        source.scriptChapters[1] = chapterScript(listOf(a), id = 1, next = 2)
        source.scriptChapters[2] = chapterScript(listOf(scriptLine("e1", "Ừ.")), id = 2, previous = 1)
        val state = StudioScriptState(session, "b1", hold = { hold.await() })
        launchRun { state.load() }
        state.assign(a, ScriptPerson("TOM", "Tom", 1))
        state.open(2)
        assertEquals(listOf("speaker"), source.writes.map { it.first })
        assertEquals(2, state.chapter)
        assertEquals("e1", state.script?.lines?.single()?.stableId)
    }

    @Test fun theMoreMenuListsTheSubPagesThatApply() {
        // Từ S4 bìa và nhật ký luôn có; xuất khi sách có chương.
        val always = listOf(StudioSubKind.Export, StudioSubKind.Cover, StudioSubKind.Activity)
        assertEquals(always, StudioLogic.subPages(studioBook()))
        assertEquals(listOf(StudioSubKind.Script, StudioSubKind.Readings) + always, StudioLogic.subPages(studioBook(segmentsAnalyzed = 40)))
        assertEquals(
            listOf(StudioSubKind.Precast, StudioSubKind.Script, StudioSubKind.Readings) + always,
            StudioLogic.subPages(studioBook(segmentsAnalyzed = 40, castLocked = true)),
        )
    }
}
