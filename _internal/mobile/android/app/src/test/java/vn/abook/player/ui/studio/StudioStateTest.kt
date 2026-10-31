package vn.abook.player.ui.studio

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.StudioError

/** Trạng thái Studio (mutableStateOf cần Looper nên chạy dưới Robolectric) không cần màn: phiên theo máy, danh sách, và lệnh của nút chính (mỗi lúc một lệnh, lỗi nói bằng lời, chỉ nghe thì cả phiên). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioStateTest {
    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }

    private fun session(source: FakeStudioSource, computer: String = "") = StudioHub(source, scope).session(computer)

    @Test fun theHubKeepsOneSessionPerComputer() {
        val hub = StudioHub(FakeStudioSource(), scope)
        assertSame(hub.session("a"), hub.session("a"))
        assertFalse(hub.session("a") === hub.session("b"))
    }

    @Test fun listenOnlyIsKeptUntilRetry() {
        val session = session(FakeStudioSource())
        session.note(StudioError.Offline())
        assertFalse(session.listenOnly)
        session.note(StudioError.ListenOnly())
        assertTrue(session.listenOnly)
        val before = session.retries
        session.retry()
        assertFalse(session.listenOnly)
        assertEquals(before + 1, session.retries)
    }

    @Test fun theHomeListLoadsThenKeepsItWhenTheNextAskFails() = runBlocking {
        val source = FakeStudioSource(listOf(studioBook("a"), studioBook("b", running = true)))
        val home = StudioHomeState(session(source), never)
        val job = launch(Dispatchers.Unconfined) { home.run() }
        assertEquals(listOf("a", "b"), home.poll.value.data?.map { it.id })
        source.error = StudioError.Offline()
        home.refresh()
        assertEquals(listOf("a", "b"), home.poll.value.data?.map { it.id })
        assertTrue(home.poll.value.error is StudioError.Offline)
        job.cancelAndJoin()
    }

    @Test fun aListenOnlyAnswerStopsTheHomePolling() = runBlocking {
        val source = FakeStudioSource(listOf(studioBook("a")))
        source.error = StudioError.ListenOnly()
        val home = StudioHomeState(session(source), never)
        home.run() // trả về luôn: hỏi tiếp vô ích
        assertTrue(home.poll.value.error is StudioError.ListenOnly)
        assertEquals(1, source.libraryCalls.size)
    }

    @Test fun aCommandRunsOnceAtATimeAndThenReads() = runBlocking {
        val source = FakeStudioSource(listOf(studioBook("b1", running = true, canPause = true)))
        val gate = CompletableDeferred<Unit>()
        source.commandGate = gate
        val project = StudioProjectState(session(source), "b1", pause = never)
        project.send(StudioCommand.Pause(true))
        assertTrue(project.busy)
        project.send(StudioCommand.Stop) // bị bỏ: đang có lệnh
        gate.complete(Unit)
        assertFalse(project.busy)
        assertEquals(listOf("b1" to StudioCommand.Pause(true)), source.commands)
        // Xong lệnh thì đọc lại để nút chính đổi theo trạng thái thật.
        assertEquals(listOf("b1"), source.bookCalls)
        assertEquals("", project.problem)
    }

    @Test fun aFailedCommandSaysWhyAndRetriesTheSameOne() = runBlocking {
        val source = FakeStudioSource(listOf(studioBook("b1")))
        source.commandError = StudioError.Busy("Máy đang bận việc khác")
        val project = StudioProjectState(session(source), "b1", pause = never)
        project.send(StudioCommand.Start)
        assertEquals("Máy đang bận việc khác", project.problem)
        assertFalse(project.busy)
        source.commandError = null
        project.retryLast()
        assertEquals("", project.problem)
        assertEquals(listOf("b1" to StudioCommand.Start, "b1" to StudioCommand.Start), source.commands)
    }

    @Test fun aListenOnlyRefusalOfACommandTurnsTheWholeSessionReadOnly() = runBlocking {
        val source = FakeStudioSource(listOf(studioBook("b1")))
        source.commandError = StudioError.ListenOnly()
        val session = session(source)
        val project = StudioProjectState(session, "b1", pause = never)
        project.send(StudioCommand.Start)
        assertTrue(session.listenOnly)
        assertNotNull(project.problem.takeIf { it.isNotEmpty() })
    }

    @Test fun theProjectOpensOnTheRequestedTab() {
        val project = StudioProjectState(session(FakeStudioSource()), "b1", StudioTab.Cast, never)
        assertEquals(StudioTab.Cast, project.tab)
        assertNull(project.poll.value.data)
    }
}
