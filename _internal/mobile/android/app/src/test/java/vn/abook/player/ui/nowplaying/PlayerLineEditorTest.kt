package vn.abook.player.ui.nowplaying

import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.After
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.*
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.studio.WorkStep

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PlayerLineEditorTest {
    private val cases get() = JSONArray(File("../../../tests/fixtures/player_line/cases.json").readText())
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
    private val id = "f-0123456789abcdef01234567"
    @After fun resetClock() { LocalStudio.now = { System.currentTimeMillis() / 1000.0 }; scope.cancel() } // wallclock-ok: restore the production clock after the fake-clock fixture

    private class Source(val case: JSONObject, val persist: Boolean = false) : PlayerLineSource {
        val writes = ArrayList<Pair<String, JSONObject>>()
        var blocked = case.optBoolean("listenOnly")
        var failSpeaker = false
        var failSample = false
        override suspend fun sample(bookId: String, chapter: Int, paragraph: ReadParagraph) { if (failSample) error("sample unavailable") }
        override val decisionsSource: StudioSource = object : StudioSource by FakeStudioSource() {
            override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject {
                check(!blocked)
                writes += step.endpoint to JSONObject(step.body.toString())
                if (failSpeaker && step.endpoint == "speaker") throw StudioError.Server("test write failed", 500)
                if (!persist) return JSONObject().put("requestedAt", 10)
                val (status, data) = LocalStudio.handle("POST", "/api/books/$id/${step.endpoint}", step.body)
                check(status == 200) { "$status $data" }
                return data as JSONObject
            }
        }
        override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph): PlayerLineSnapshot {
            val wishes = if (persist) LocalStudio.handle("GET", "/api/books/$bookId/wishes", null).second as JSONObject else case.getJSONObject("wishes")
            return PlayerLineLogic.snapshot(chapter, paragraph, case.getJSONObject("cast"), wishes, if (blocked) S.s_may_tinh_chua_cho_ban_sua_6a5d6567 else "")
        }
    }

    private fun paragraph(case: JSONObject) = ReadAlongLookup.parse(JSONObject().put("timed", true).put("segments", JSONArray().put(case.getJSONObject("source")))).single()
    private fun person(json: JSONObject?) = json?.let { ScriptPerson(it.getString("value"), it.getString("label"), it.optInt("lines"), it.optString("newGender")) }
    private fun canonical(value: Any?): Any? = when (value) {
        is JSONObject -> value.keys().asSequence().toList().sorted().associateWith { canonical(value.opt(it)) }
        is JSONArray -> (0 until value.length()).map { canonical(value.opt(it)) }
        else -> value
    }
    private fun book(case: JSONObject): File {
        BookEditsFixtures.useStoreRoot(Files.createTempDirectory("player-line").toFile())
        var tick = 0
        LocalStudio.now = { 100.0 + tick++ }
        val dir = Store.bookDir(id).apply { mkdirs() }
        val scripts = File(dir, "scripts").apply { mkdirs() }
        File(scripts, "1.json").writeText(JSONObject().put("chapterId", 1).put("timed", true).put("segments", JSONArray().put(case.getJSONObject("source"))).toString())
        File(dir, "cast.json").writeText(case.getJSONObject("cast").toString())
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Hộp kiểm thử")
            .put("cast", "cast.json").put("chapters", JSONArray().put(JSONObject().put("id", 1).put("script", "scripts/1.json").put("available", true))).toString())
        return dir
    }

    private fun choose(editor: PlayerLineEditor, case: JSONObject) {
        when (case.getString("action")) {
            "speaker" -> editor.assign(person(case.getJSONObject("person"))!!)
            "delivery" -> case.getJSONObject("delivery").let { editor.delivery(it.getString("kind"), it.getString("emotion"), it.getInt("intensity"), person(case.optJSONObject("person")), editor.line!!.text) }
            "spoken" -> editor.delivery(editor.line!!.kind, "neutral", 0, null, case.getString("spoken"))
            "review" -> editor.retake()
            else -> { assertFalse(editor.enabled); editor.assign(ScriptPerson("AN", "An", 1)); editor.retake() }
        }
    }

    @Test fun twelveSharedRequestsPersistThroughCloseAndReopenWithoutChangingTheBook() {
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val dir = book(case)
            val original = dir.walkTopDown().filter { it.isFile }.associate { it.relativeTo(dir).path to it.readBytes().toList() }
            if (case.getString("name") == "pending-new-person") {
                val s = case.getJSONObject("source")
                BookWishes.requestSpeakers(dir, listOf(s.getString("stableId") to s.getString("textSha256")), "Bình", 1.0, "unknown")
            }
            val source = Source(case, persist = true)
            val editor = PlayerLineEditor(source, scope)
            editor.open(id, 1, paragraph(case))
            choose(editor, case)
            if (case.getJSONArray("expectedSteps").length() > 0) assertTrue("saved before closing", File(dir, "edits.json").isFile)
            editor.close() // Closing only dismisses the receipt-bound Undo; the wish is already durable.
            val actual = JSONArray(source.writes.map { (endpoint, body) -> JSONObject().put("endpoint", endpoint).put("body", body) })
            assertEquals(case.getString("name"), canonical(case.getJSONArray("expectedSteps")), canonical(actual))
            for ((name, bytes) in original) assertEquals(name, bytes, File(dir, name).readBytes().toList())
            if (source.writes.isNotEmpty()) {
                val reopened = BookEdits.parse(File(dir, "edits.json").readBytes())
                assertTrue(reopened.optJSONObject("wishes")!!.length() > 0)
                editor.open(id, 1, paragraph(case))
                assertNotNull(editor.snapshot)
                if (case.getString("action") == "speaker") assertEquals(case.getJSONObject("person").getString("value"), editor.line!!.wish!!.value)
                editor.close()
            }
        }
    }

    @Test fun undoUsesTheStudioDecisionOwnerAndOnlyRetractsItsReceipt() {
        val case = cases.getJSONObject(0)
        val source = Source(case)
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); choose(editor, case)
        assertNotNull(editor.decisions!!.held)
        editor.decisions!!.undo(); editor.close()
        assertEquals(2, source.writes.size)
        assertTrue(source.writes.last().second.getBoolean("withdraw"))
        assertEquals(10.0, source.writes.last().second.getDouble("requestedAt"), 0.0)
    }

    @Test fun narrationToThoughtCannotSaveWithoutAPerson() {
        val case = cases.getJSONObject(4)
        val source = Source(case)
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case))
        assertFalse(editor.delivery("thought", "neutral", 0, null, editor.line!!.text))
        editor.close(); assertTrue(source.writes.isEmpty())
    }

    @Test fun selectionKeepsOriginalIdentityWhenAnotherChapterArrives() {
        val case = cases.getJSONObject(0)
        val source = Source(case)
        val editor = PlayerLineEditor(source, scope)
        val picked = paragraph(case)
        editor.open(id, 1, picked)
        val other = ReadAlongLookup.parse(JSONObject().put("segments", JSONArray().put(JSONObject(case.getJSONObject("source").toString()).put("stableId", "other"))))
        assertNotEquals(other.single().line!!.stableId, editor.line!!.stableId)
        choose(editor, case); editor.close()
        assertEquals(picked.line!!.stableId, source.writes.single().second.getJSONArray("lines").getJSONObject(0).getString("stableId"))
    }

    @Test fun backFromAChildReturnsToTheMenuWithoutWriting() {
        val source = Source(cases.getJSONObject(0)); val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(source.case)); editor.step = "speaker"; editor.back()
        assertEquals("menu", editor.step); assertNotNull(editor.selected); assertTrue(source.writes.isEmpty())
        editor.back(); assertNull(editor.selected); assertTrue(source.writes.isEmpty())
    }

    @Test fun staleUndoCannotEraseAnotherDevicesDecision() {
        val case = cases.getJSONObject(0); val dir = book(case)
        val source = Source(case, persist = true); val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); choose(editor, case)
        val line = case.getJSONObject("source")
        val changed = JSONObject().put("lines", JSONArray().put(JSONObject().put("stableId", line.getString("stableId")).put("textSha256", line.getString("textSha256"))))
            .put("speaker", "MINH").put("seen", JSONObject().put(line.getString("stableId"), "AN"))
        assertEquals(200, LocalStudio.handle("POST", "/api/books/$id/speaker", changed).first)
        editor.decisions!!.undo()
        assertEquals("MINH", BookEdits.load(dir).getJSONObject("wishes").getJSONObject("speakers").getJSONObject(line.getString("stableId")).getString("speaker"))
        assertTrue(editor.notice.isNotEmpty()); editor.close()
    }

    @Test fun failedNewPersonRollsBackTheAcknowledgedDeliveryInImmediateMode() {
        val case = cases.getJSONObject(5); val dir = book(case)
        val source = Source(case, persist = true).also { it.failSpeaker = true }
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); choose(editor, case)
        assertFalse(BookEdits.load(dir).optJSONObject("wishes")?.optJSONObject("lines")?.has(case.getJSONObject("source").getString("stableId")) == true)
        assertTrue(editor.notice.isNotEmpty()); editor.close()
    }

    @Test fun changedSourceHashIsRefusedWithoutChoosingANearbyLine() {
        val case = cases.getJSONObject(0); val selected = paragraph(case); val dir = book(case)
        val script = JSONObject(File(dir, "scripts/1.json").readText())
        script.getJSONArray("segments").getJSONObject(0).put("textSha256", "b".repeat(64))
        File(dir, "scripts/1.json").writeText(script.toString())
        val source = Source(case, persist = true); val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, selected); choose(editor, case)
        assertTrue(editor.notice.isNotEmpty())
        assertFalse(BookEdits.load(dir).optJSONObject("wishes")?.optJSONObject("speakers")?.has(selected.line!!.stableId) == true)
        assertEquals(selected.line!!.textSha256, source.writes.single().second.getJSONArray("lines").getJSONObject(0).getString("textSha256"))
        editor.close()
    }

    @Test fun anUnavailableSampleDoesNotDisableSentenceEditing() {
        val case = cases.getJSONObject(0); val source = Source(case).also { it.failSample = true }
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); editor.sample()
        assertTrue(editor.notice.isNotEmpty()); assertTrue(editor.enabled)
        choose(editor, case); assertEquals(1, source.writes.size); editor.close()
    }

    @Test fun aHeldRemoteSpeakerIsNotReportedAsALocalDecision() {
        val case = cases.getJSONObject(0)
        val original = case.getJSONObject("source")
        case.getJSONObject("wishes").getJSONObject("lines").put(original.getString("stableId"),
            JSONObject().put("speaker", JSONObject().put("name", "MINH").put("shown", "Minh").put("held", true)))
        val source = Source(case); val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); choose(editor, case)
        assertEquals("", source.writes.single().second.getJSONObject("seen").getString(original.getString("stableId")))
        editor.close()
    }

    @Test fun remoteProjectUsesTheSharedRequestsAndThePinnedComputerAndProject() {
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val local = Source(case)
            val writes = ArrayList<Pair<String, JSONObject>>()
            val remote = object : StudioSource by FakeStudioSource() {
                override suspend fun castingChapter(computer: String, id: String, chapter: Int): ChapterScript {
                    assertEquals("desk-pinned", computer); assertEquals("project-selected", id); assertEquals(1, chapter)
                    if (case.optBoolean("listenOnly")) throw StudioError.ListenOnly()
                    val script = PlayerLineLogic.snapshot(chapter, paragraph(case), case.getJSONObject("cast"), case.getJSONObject("wishes")).script
                    // Match the endpoint: narration is not speaker-editable, and a chapter MP3 can outlive per-line WAVs.
                    return script.copy(lines = script.lines.map { it.copy(editable = ScriptLogic.isSpeech(it), hasAudio = false) })
                }
                override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject {
                    assertEquals("desk-pinned", computer); assertEquals("project-selected", id)
                    writes += step.endpoint to JSONObject(step.body.toString())
                    return JSONObject().put("requestedAt", 123)
                }
            }
            val source = object : PlayerLineSource by local {
                override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph) =
                    PlayerLineRemote.load(remote, "desk-pinned", "project-selected", chapter, paragraph)
            }
            val editor = PlayerLineEditor(source, scope)
            editor.open(id, 1, paragraph(case)); choose(editor, case); editor.close()
            val actual = JSONArray(writes.map { (endpoint, body) -> JSONObject().put("endpoint", endpoint).put("body", body) })
            assertEquals(case.getString("name"), canonical(case.getJSONArray("expectedSteps")), canonical(actual))
            assertTrue(local.writes.isEmpty())
        }
    }

    @Test fun remoteUndoKeepsItsWriterWhenRefreshIsOfflineAndAnotherSelectionOpens() {
        val case = cases.getJSONObject(0); val local = Source(case)
        val writes = ArrayList<JSONObject>(); var offline = false
        val remote = object : StudioSource by FakeStudioSource() {
            override suspend fun castingChapter(computer: String, id: String, chapter: Int): ChapterScript {
                if (offline) throw StudioError.Offline()
                return PlayerLineLogic.snapshot(chapter, paragraph(case), case.getJSONObject("cast"), case.getJSONObject("wishes")).script
            }
            override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject {
                assertEquals("original-desk", computer); assertEquals("original-project", id)
                writes += JSONObject(step.body.toString()); offline = true
                return JSONObject().put("requestedAt", 321)
            }
        }
        val source = object : PlayerLineSource by local {
            override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph) =
                if (bookId == "other-book") local.load(bookId, chapter, paragraph)
                else PlayerLineRemote.load(remote, "original-desk", "original-project", chapter, paragraph)
        }
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); choose(editor, case)
        assertTrue(editor.problem.isNotEmpty()); assertFalse(editor.enabled)
        editor.decisions!!.undo()
        assertEquals(321.0, writes.last().getDouble("requestedAt"), 0.0)
        assertTrue(writes.last().getBoolean("withdraw")); assertTrue(local.writes.isEmpty())
        editor.open("other-book", 1, paragraph(case)); assertTrue(editor.enabled)
        assertEquals(2, writes.size); editor.close()
    }

    @Test fun remoteHashMismatchCannotFallBackToLocalWishesOrANearbyLine() {
        val case = cases.getJSONObject(0); val local = Source(case)
        val remote = object : StudioSource by FakeStudioSource() {
            override suspend fun castingChapter(computer: String, id: String, chapter: Int): ChapterScript {
                val script = local.load(id, chapter, paragraph(case)).script
                return script.copy(lines = script.lines.map { it.copy(textSha256 = "b".repeat(64)) })
            }
        }
        val source = object : PlayerLineSource by local {
            override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph) = PlayerLineRemote.load(remote, "desk", "project", chapter, paragraph)
        }
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); editor.assign(ScriptPerson("AN", "An", 1)); editor.retake()
        assertFalse(editor.enabled); assertEquals(WorkText.STALE, editor.snapshot!!.blocked)
        assertTrue(local.writes.isEmpty()); editor.close()
    }

    @Test fun remoteRetakeAndHeldSpeakerAreParsedFromTheExistingEndpoint() {
        val json = JSONObject().put("stableId", "line").put("retake", "pending")
            .put("wish", JSONObject().put("value", "AN").put("label", "An").put("state", "pending").put("held", true))
        val line = StudioScriptJson.chapter(JSONObject().put("lines", JSONArray().put(json))).lines.single()
        assertEquals("pending", line.retake); assertTrue(line.wish!!.held)
    }

    @Test fun aLateReceiptCannotReloadAnotherSelectionInTheSameBook() {
        val case = cases.getJSONObject(0); val local = Source(case)
        val reply = CompletableDeferred<JSONObject>(); var loads = 0
        val writer = object : StudioSource by FakeStudioSource() {
            override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject = reply.await()
        }
        val source = object : PlayerLineSource by local {
            override val decisionsSource = writer
            override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph): PlayerLineSnapshot {
                loads++
                return local.load(bookId, chapter, paragraph)
            }
        }
        val editor = PlayerLineEditor(source, scope)
        val first = paragraph(case)
        editor.open(id, 1, first); choose(editor, case)
        assertTrue(editor.decisions!!.busy)
        editor.open(id, 2, first.copy(line = first.line!!.copy(stableId = "other-line")))
        reply.complete(JSONObject().put("requestedAt", 100))
        assertEquals(2, loads); assertEquals(2, editor.snapshot!!.script.chapterId)
        assertEquals("other-line", editor.line!!.stableId); assertTrue(editor.notice.isEmpty())
        editor.close()
    }

    @Test fun offlinePlayerWishCanBeReopenedAndSentFromDiskByTheExistingSyncPath() {
        val case = cases.getJSONObject(0); val dir = book(case)
        val manifest = File(dir, "book.json")
        manifest.writeText(JSONObject(manifest.readText()).put("source", "test-desk").put("sourceKind", "computer").put("remoteId", "test-project").toString())
        val source = Source(case, persist = true)
        val editor = PlayerLineEditor(source, scope)
        editor.open(id, 1, paragraph(case)); choose(editor, case); editor.close()
        val reopened = PlayerLineEditor(Source(case, persist = true), scope)
        reopened.open(id, 1, paragraph(case))
        assertEquals("AN", reopened.line!!.wish!!.value); reopened.close()
        var sent: JSONObject? = null
        val view = EditsSync.push(id) { file ->
            java.util.zip.ZipFile(file).use { zip -> sent = JSONObject(zip.getInputStream(zip.getEntry("edits.json")).bufferedReader().readText()) }
            JSONObject().put("applied", 0).put("waiting", 1).put("conflicts", JSONArray()).toString()
        }
        val wish = sent!!.getJSONObject("wishes").getJSONObject("speakers").getJSONObject(paragraph(case).line!!.stableId)
        assertEquals("AN", wish.getString("speaker")); assertEquals(paragraph(case).line!!.textSha256, wish.getString("text_sha256"))
        assertTrue(wish.getDouble("requested_at") > 0)
        assertEquals(0, view.getInt("pending")); assertEquals(1, view.getJSONObject("last").getInt("waiting"))
    }
}
