package vn.abook.player.ui

import android.os.Looper
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class GapLogicTest {
    private fun advance(ms: Long) = shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms))

    @Test fun localRemovalStopsAudioImmediatelyAndUndoOnlyRestoresTheBook() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val core = FakePlaybackCore(playerSnapshot(playing = true), simulate = true)
        val repo = PlayerRepo(core, scope, Dispatchers.Unconfined, { null }, { null })
        repo.attach()
        val deletes = UndoDelete(scope, { "token" }, {}, {}, repo::bookRemoved)
        deletes.remove("b1")
        assertFalse(repo.state.value.hasTrack)
        assertEquals(listOf("close"), core.calls)
        deletes.undo()
        assertFalse(deletes.contains("b1"))
        assertFalse(repo.state.value.hasTrack)
        scope.cancel()
    }

    @Test fun removalClearsTheCoreTheRepoAndItsClockAndCannotReviveOnAttach() {
        val core = FakePlaybackCore(playerSnapshot(playing = true), simulate = true)
        val repo = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null })
        repo.attach()
        repo.reconcile(listOf(ListenBook("b1", "Sách", remote = RemoteRef("Máy tính"))))
        assertTrue(repo.state.value.hasTrack)
        repo.reconcile(emptyList())
        assertEquals(listOf("close"), core.calls)
        assertEquals(PlayerState.Empty, repo.state.value)
        assertEquals(0L, repo.clock.positionMs.value)
        repo.detach(); repo.attach()
        assertFalse(repo.state.value.hasTrack)
    }

    @Test fun remoteControlsReachTheCoreWithTheExactProtocol() = runBlocking {
        val core = FakeCompanionCore()
        val repo = CompanionRepo(core) { 1_000 }
        repo.refresh()
        val player = repo.state.value.players.single()
        assertEquals("Máy tính phòng khách", player.name)
        assertEquals(65.0, player.positionAfter(2.0), 0.0)
        assertTrue(repo.send(player, "skip", -15.0))
        assertEquals("main", core.commands.last().first)
        assertEquals(-15.0, core.commands.last().second.getDouble("seconds"), 0.0)
        repo.send(player, "sleep", mode = "chapter")
        assertTrue(core.commands.last().second.getBoolean("endOfChapter"))
        repo.send(player, "sleep", minutes = 0)
        assertEquals(0, core.commands.last().second.getInt("minutes"))
    }

    @Test fun listenHereWaitsForPauseAndFailureDoesNotStartLocalAudio() = runBlocking {
        val core = FakeCompanionCore()
        var clock = 1_000L
        val delayed = object : CompanionCore by core {
            override suspend fun command(device: String, command: JSONObject) {
                core.command(device, command)
                clock += 2_000
            }
        }
        val repo = CompanionRepo(delayed) { clock }
        repo.refresh()
        var started = 0
        assertTrue(repo.listenHere(repo.state.value.players.single()) { book, chapter, seconds ->
            assertEquals("pause", core.commands.last().second.getString("action"))
            assertEquals("b1", book); assertEquals(1, chapter); assertEquals(65.0, seconds, 0.0)
            started++
        })
        core.fail = true
        assertFalse(repo.listenHere(repo.state.value.players.single()) { _, _, _ -> started++ })
        assertEquals(1, started)
    }

    @Test fun handoffOnlyPausesLocalAfterAcknowledgementAndReportsFailure() = runBlocking {
        val core = FakeCompanionCore()
        val repo = CompanionRepo(core) { 1_000 }
        repo.refresh()
        var paused = 0
        val local = PlayerState(bookId = "b1", chapterId = 2, rate = 1.5)
        assertTrue(repo.handOff(repo.state.value.players.single(), local, 42.0) { paused++ })
        assertEquals(1, paused)
        val command = core.commands.single().second
        assertEquals("load", command.getString("action")); assertEquals(42.0, command.getDouble("seconds"), 0.0)
        core.fail = true
        assertFalse(repo.handOff(repo.state.value.players.single(), local, 42.0) { paused++ })
        assertEquals(1, paused)
        assertTrue(repo.state.value.problem.isNotEmpty())
    }

    @Test fun noticesUseTheExistingOptInAndPermissionState() = runBlocking {
        val core = FakeCompanionCore()
        core.noticeState = StudioNoticeState(false, false)
        val repo = CompanionRepo(core)
        repo.refresh(); repo.setNotices(true)
        assertTrue(core.noticeState.enabled)
        assertFalse(repo.state.value.notices.permitted)
        repo.setNotices(false)
        assertFalse(repo.state.value.notices.enabled)
    }
}
