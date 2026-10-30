package vn.abook.player.ui.studio

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject
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
 * Hàng chờ gửi quyết định (NATIVE_REMOTE_STUDIO.md §2.7, §13.1-6): giữ 15 giây, "Hoàn tác" bỏ hẳn, hết giờ gửi MỘT lần, rời màn gửi ngay, gửi hỏng không bao giờ
 * tự gửi lại. `wait` là một cổng để test không đợi 15 giây thật.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioDecisionsTest {
    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val source = FakeStudioSource()
    private val session = StudioHub(source, scope).session("")
    private val gate = CompletableDeferred<Unit>()
    private val after = ArrayList<Boolean>()
    private val decisions = StudioDecisions(session, "b1", { gate.await() }) { after += it }

    private fun speak(key: String = "k1", speaker: String = "noah") = WorkDecisions.speaker(speakerCard(key), speaker, WorkScope.Alternate, null)

    @Test fun undoWithinTheHoldSendsNothingAtAll() {
        decisions.hold(speak())
        assertNotNull(decisions.held)
        assertEquals(setOf("k1"), decisions.hiding())
        decisions.undo()
        gate.complete(Unit)
        assertNull(decisions.held)
        assertTrue(source.writes.isEmpty())
        assertTrue(decisions.hiding().isEmpty())
        assertTrue(after.isEmpty())
    }

    @Test fun expiryPostsOnceAndKeepsTheCardAwayUntilTheListReloads() {
        decisions.hold(speak())
        assertTrue(source.writes.isEmpty())
        gate.complete(Unit)
        assertEquals(listOf("speaker"), source.writes.map { it.first })
        assertNull(decisions.held)
        assertEquals(setOf("k1"), decisions.away)
        assertEquals(listOf(true), after)
        decisions.forgetSent(setOf("k1"))
        assertTrue(decisions.away.isEmpty())
    }

    @Test fun leavingTheScreenSendsTheHeldDecisionNowAndOnlyOnce() {
        decisions.hold(speak())
        decisions.flush()
        assertEquals(1, source.writes.size)
        gate.complete(Unit)
        assertEquals(1, source.writes.size)
        decisions.flush()
        assertEquals(1, source.writes.size)
    }

    @Test fun aDecisionOnAnotherCardSendsThePreviousOneFirst() {
        decisions.hold(speak("k1", "noah"))
        decisions.hold(speak("k2", "kati"))
        assertEquals(1, source.writes.size)
        assertEquals("noah", source.writes[0].second.getString("speaker"))
        assertEquals("k2", decisions.held?.decision?.key)
    }

    @Test fun theSameCardReplacesTheHeldDecisionWithoutSendingTheOldOne() {
        decisions.hold(speak("k1", "noah"))
        decisions.hold(speak("k1", "kati"))
        assertTrue(source.writes.isEmpty())
        decisions.flush()
        assertEquals(1, source.writes.size)
        assertEquals("kati", source.writes[0].second.getString("speaker"))
    }

    @Test fun anOldTimerNeverSendsANewerDecisionEarly() {
        val first = CompletableDeferred<Unit>()
        val second = CompletableDeferred<Unit>()
        val waits = ArrayDeque(listOf(first, second))
        val own = StudioDecisions(session, "b1", { waits.removeFirst().await() })
        own.hold(speak("k1", "noah"))
        own.hold(speak("k1", "kati"))
        first.complete(Unit)
        assertTrue(source.writes.isEmpty())
        second.complete(Unit)
        assertEquals(listOf("kati"), source.writes.map { it.second.getString("speaker") })
    }

    @Test fun aBusyAnswerSaysTheLineChangedAndNeverResends() {
        source.writeError = { StudioError.Busy("Máy đang bận") }
        decisions.hold(speak())
        gate.complete(Unit)
        assertEquals(WorkText.STALE, decisions.notice)
        assertTrue(decisions.away.isEmpty())
        assertEquals(listOf(false), after)
        decisions.flush()
        assertEquals(1, source.writes.size)
    }

    @Test fun aServerRefusalShowsTheServersWordsAndTheCardComesBack() {
        source.writeError = { StudioError.Server("Câu này đã đổi chữ", 400) }
        decisions.hold(speak())
        gate.complete(Unit)
        assertEquals("Câu này đã đổi chữ", decisions.notice)
        assertFalse("k1" in decisions.hiding())
    }

    @Test fun aGroupCardThatOnlyPartlyWroteSaysHowFarItGot() {
        val card = workItem(
            key = "g", current = "x", currentValue = "x", keepLabel = "Giữ nguyên",
            keepGroups = listOf(SpeakerRequest(listOf(lineRef("s1")), "a"), SpeakerRequest(listOf(lineRef("s2")), "b")),
            lines = listOf(lineRef("s1"), lineRef("s2")),
        )
        var calls = 0
        source.writeError = { if (++calls == 2) StudioError.Offline() else null }
        decisions.hold(WorkDecisions.keepAll(card)!!)
        gate.complete(Unit)
        assertEquals(2, source.writes.size)
        assertTrue(decisions.notice.startsWith("Mới ghi được 1/2 việc."))
    }

    @Test fun anIrreversibleDecisionIsSentImmediately() {
        val card = workItem(kind = WorkKind.Refused, key = "r", refused = RefusedRef("voice", "kati", 12.5))
        decisions.hold(WorkDecisions.dropRefused(card)!!)
        assertEquals(listOf("pending-changes/withdraw"), source.writes.map { it.first })
        assertNull(decisions.held)
    }

    @Test fun anEditMadeElsewhereIsReportedWithThePersonsName() {
        source.writeAnswers["speaker"] = JSONObject("""{"elsewhere":{"s1":"noah"}}""")
        decisions.hold(speak("k1", "kati"))
        gate.complete(Unit)
        assertTrue(decisions.notice, decisions.notice.startsWith("Chỗ này vừa được sửa ở máy hay cửa sổ khác"))
        assertTrue(decisions.notice, decisions.notice.contains("Trước đó đang là Noah"))
    }
}
