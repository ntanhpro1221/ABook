package vn.abook.player.ui.studio

import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.After
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.StudioError

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioEditStateTest {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
    private val source = FakeStudioSource(listOf(studioBook(running = true)))
    private val session = StudioHub(source, scope).session("")
    private val gate = CompletableDeferred<Unit>()
    private val state = StudioScriptState(session, "b1", hold = { gate.await() })
    private val narrator = scriptLine("n", "Đèn sân đã sáng.", kind = "narration", current = "NARRATOR", editable = false).copy(emotion = "neutral", intensity = 0)
    private val newPerson = ScriptPerson("Bác Trực", "Bác Trực", 0, "male")

    @After fun close() { scope.cancel() }

    @Test fun aFailedSecondRequestWithdrawsOnlyItsOwnLineReceipt() {
        source.writeAnswers["line"] = JSONObject("""{"requestedAt":41.5}""")
        source.writeError = { if (it.endpoint == "speaker") StudioError.Offline() else null }
        state.delivery(narrator, "thought", "sad", 2, newPerson)
        assertTrue(source.writes.isEmpty())
        gate.complete(Unit)
        assertEquals(listOf("line", "speaker", "line"), source.writes.map { it.first })
        val undo = source.writes.last().second
        assertEquals("n", undo.getString("stableId"))
        assertEquals(41.5, undo.getDouble("requestedAt"), 0.0)
        assertTrue(undo.getBoolean("withdraw"))
        assertFalse(state.notice.startsWith("Mới ghi được"))
    }

    @Test fun aFailedWithdrawalOrMissingReceiptReportsThePartialWrite() {
        source.writeError = { if (it.endpoint == "speaker") StudioError.Offline() else null }
        state.delivery(narrator, "dialogue", "neutral", 0, newPerson)
        gate.complete(Unit)
        assertEquals(listOf("line", "speaker"), source.writes.map { it.first })
        assertTrue(state.notice.startsWith("Mới ghi được 1/2 việc."))
    }

    @Test fun aFailedRollbackStillReportsThePartialWriteWithoutRetry() {
        source.writeAnswers["line"] = JSONObject("""{"requestedAt":41.5}""")
        source.writeError = { if (it.endpoint == "speaker" || it.body.optBoolean("withdraw")) StudioError.Offline() else null }
        state.delivery(narrator, "dialogue", "neutral", 0, newPerson)
        gate.complete(Unit)
        assertEquals(listOf("line", "speaker", "line"), source.writes.map { it.first })
        assertTrue(state.notice.startsWith("Mới ghi được 1/2 việc."))
        state.leave()
        assertEquals(3, source.writes.size)
    }

    @Test fun theHoldRequestsExactlyFifteenSeconds() {
        var duration = 0L
        val timed = StudioScriptState(session, "b1", hold = { duration = it; gate.await() })
        timed.assign(scriptLine("a", "Xin đặt ghế ở đây."), newPerson)
        assertEquals(15_000L, duration)
        assertTrue(source.writes.isEmpty())
        gate.complete(Unit)
        assertEquals(1, source.writes.size)
    }

    @Test fun undoDuringTheFifteenSecondHoldSendsNoRequest() {
        state.delivery(narrator, "thought", "neutral", 0, newPerson)
        assertNotNull(state.decisions.held)
        state.decisions.undo()
        gate.complete(Unit)
        assertTrue(source.writes.isEmpty())
    }

    @Test fun leavingFlushesAndReopeningReadsThePersistedWish() = runBlocking {
        val line = scriptLine("a", "Xin đặt ghế ở đây.")
        source.scriptChapters[1] = chapterScript(listOf(line))
        state.assign(line, ScriptPerson("TOM", "Tom", 1))
        state.leave()
        assertEquals(1, source.writes.size)
        source.scriptChapters[1] = chapterScript(listOf(line.copy(wish = ScriptWish("TOM", "Tom", "pending", null))))
        val reopened = StudioScriptState(session, "b1", first = 1)
        reopened.reload()
        assertEquals("TOM", ScriptLogic.speaker(reopened.shown()!!.lines.single()))
        assertEquals(line.text, reopened.shown()!!.lines.single().text)
    }

    @Test fun noVoiceAndOfflineSurfaceTheServerReasonWithoutRetry() {
        source.writeError = { StudioError.Server("Người này chưa có giọng trong sách (chưa nói câu nào) - chưa gán được.", 400) }
        state.assign(scriptLine("a", "Xin đặt ghế ở đây."), ScriptPerson("NOBODY", "Nobody", 0))
        gate.complete(Unit)
        assertEquals(1, source.writes.size)
        assertTrue(state.notice.contains("chưa có giọng"))
    }

    @Test fun listenOnlyBlocksSingleBatchAndDeliveryWrites() = runBlocking {
        source.scriptChapters[1] = chapterScript(listOf(scriptLine("a", "Xin đặt ghế ở đây.")))
        val blocked = StudioScriptState(session, "b1", first = 1)
        blocked.reload()
        session.note(StudioError.ListenOnly())
        val line = blocked.shown()!!.lines.single()
        blocked.assign(line, newPerson)
        blocked.toggle(line)
        blocked.assignSelected(newPerson)
        assertFalse(blocked.delivery(narrator, "thought", "neutral", 0, newPerson))
        blocked.leave()
        assertNull(blocked.decisions.held)
        assertTrue(source.writes.isEmpty())
    }

    @Test fun batchDeselectAndFiltersNeverExpandTheIds() = runBlocking {
        val lines = listOf("a", "b", "c").map { scriptLine(it, "Xin đặt ghế ở đây.") }
        source.scriptChapters[1] = chapterScript(lines)
        val batch = StudioScriptState(session, "b1", first = 1, hold = { gate.await() })
        batch.reload()
        lines.forEach(batch::toggle)
        batch.toggle(lines[1])
        batch.query = "ghế"
        batch.assignSelected(ScriptPerson("TOM", "Tom", 1))
        gate.complete(Unit)
        val sent = source.writes.single().second.getJSONArray("lines")
        assertEquals(listOf("a", "c"), (0 until sent.length()).map { sent.getJSONObject(it).getString("stableId") })
    }
}
