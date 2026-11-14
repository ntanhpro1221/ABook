package vn.abook.player.ui.studio

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.StudioError
import vn.abook.player.StudioPaths

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class CastHistoryStateTest {
    private val scope = CoroutineScope(Dispatchers.Unconfined + Job())
    private val source = FakeStudioSource(listOf(studioBook()))
    private val session = StudioSession("", source, scope)
    private val state = StudioProjectState(session, "b1").cast
    private val id = "12345678123456781234567812345678"
    @After fun close() { scope.cancel() }

    @Test fun undoSendsTheExactReferenceAndIgnoresASecondTapWhileBusy() {
        source.writeGate = CompletableDeferred()
        state.undoCast(id)
        state.undoCast(id)
        assertEquals(1, source.writes.size)
        val (endpoint, body) = source.writes.single()
        assertEquals("/api/books/b1/cast-history/undo", StudioPaths.write("b1", endpoint))
        assertEquals(id, body.getString("operationId"))
        source.writeGate!!.complete(Unit)
        assertNull(state.undoing)
    }

    @Test fun offlineRetryKeepsTheSameReference() {
        source.writeError = { StudioError.Offline() }
        state.undoCast(id)
        assertTrue(state.historyProblem.isNotEmpty())
        source.writeError = { null }
        state.undoCast(id)
        assertEquals(listOf(id, id), source.writes.map { it.second.getString("operationId") })
    }

    @Test fun listenOnlyRefusalStopsFurtherWrites() {
        source.writeError = { StudioError.ListenOnly() }
        state.undoCast(id)
        assertTrue(session.listenOnly)
        state.undoCast(id)
        assertEquals(1, source.writes.size)
    }
}
