package vn.abook.player.ui

import android.os.Looper
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.refreshWhenStarted
import vn.abook.player.ui.data.refreshRemoteWhileStarted
import vn.abook.player.ui.data.RefreshClock
import vn.abook.player.ui.devices.CompanionRepo
import vn.abook.player.ui.nowplaying.FakeNowPlayingModel
import vn.abook.player.ui.nowplaying.NowPlayingModel
import vn.abook.player.ui.nowplaying.PlayerPosition
import vn.abook.player.ui.nowplaying.samplePlayerClock

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ForegroundWorkTest {
    private class Owner : LifecycleOwner {
        override val lifecycle = LifecycleRegistry.createUnsafe(this)
    }

    private fun drain() = shadowOf(Looper.getMainLooper()).idle()

    @Test fun `refreshes on visible entry and events including PiP and unsubscribes on stop`() {
        val owner = Owner()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val events = MutableSharedFlow<Unit>(extraBufferCapacity = 8)
        var reads = 0
        try {
            scope.launch { refreshWhenStarted(owner.lifecycle, events) { reads++ } }
            owner.lifecycle.currentState = Lifecycle.State.CREATED
            drain()
            assertEquals(0, reads)
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            drain()
            assertEquals(1, reads)
            events.tryEmit(Unit)
            drain()
            assertEquals(2, reads)
            drain()
            assertEquals("Idle UI must not refresh", 2, reads)
            owner.lifecycle.currentState = Lifecycle.State.CREATED
            drain()
            assertEquals(0, events.subscriptionCount.value)
            events.tryEmit(Unit)
            drain()
            assertEquals(2, reads)
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            drain()
            assertEquals("Visible entry takes a fresh snapshot", 3, reads)
        } finally {
            scope.cancel()
            drain()
        }
        assertEquals(0, events.subscriptionCount.value)
    }

    @Test fun `player samples frames while expanded playing and STARTED including paused PiP`() {
        val owner = Owner()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val frames = MutableSharedFlow<Unit>(extraBufferCapacity = 8)
        val open = MutableStateFlow(true)
        val fake = FakeNowPlayingModel(FakeNowPlayingModel.demoState().copy(playing = true))
        var samples = 0
        val model = object : NowPlayingModel by fake {
            override val position = object : PlayerPosition by fake.position {
                override fun sample() { samples++ }
            }
        }
        try {
            owner.lifecycle.currentState = Lifecycle.State.RESUMED
            scope.launch { samplePlayerClock(owner.lifecycle, model, open) { frames } }
            drain()
            assertEquals(1, frames.subscriptionCount.value)
            val before = samples
            frames.tryEmit(Unit)
            drain()
            assertEquals(before + 1, samples)
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            drain()
            assertEquals("PiP still consumes frames", 1, frames.subscriptionCount.value)
            val pipSamples = samples
            frames.tryEmit(Unit)
            drain()
            assertEquals(pipSamples + 1, samples)
            owner.lifecycle.currentState = Lifecycle.State.CREATED
            drain()
            assertEquals(0, frames.subscriptionCount.value)
            val paused = samples
            frames.tryEmit(Unit)
            drain()
            assertEquals(paused, samples)
            owner.lifecycle.currentState = Lifecycle.State.RESUMED
            drain()
            assertEquals(1, frames.subscriptionCount.value)
            open.value = false
            drain()
            assertEquals(0, frames.subscriptionCount.value)
            open.value = true
            drain()
            assertEquals(1, frames.subscriptionCount.value)
            fake.update(fake.state.value.copy(playing = false))
            drain()
            assertEquals(0, frames.subscriptionCount.value)
            owner.lifecycle.currentState = Lifecycle.State.DESTROYED
            drain()
            assertEquals(0, frames.subscriptionCount.value)
        } finally {
            scope.cancel()
            drain()
        }
    }

    /** Each step advances one requested interval, with no wall-clock wait or timer threads. */
    private class Clock : RefreshClock {
        val steps = Channel<Unit>(Channel.RENDEZVOUS)
        val intervals = mutableListOf<Long>()
        var waiting = 0
        override suspend fun delay(milliseconds: Long) {
            intervals += milliseconds
            waiting++
            try { steps.receive() } finally { waiting-- }
        }
        fun tick() { check(steps.trySend(Unit).isSuccess) { "No active ticker" } }
    }

    @Test fun `remote ticker runs only for visible playing peers and syncs streamed data every four ticks`() {
        val owner = Owner()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val playing = MutableStateFlow(false)
        val clock = Clock()
        var reads = 0
        var syncs = 0
        try {
            owner.lifecycle.currentState = Lifecycle.State.CREATED
            scope.launch { refreshRemoteWhileStarted(owner.lifecycle, playing, clock, { reads++ }, { syncs++ }) }
            playing.value = true
            drain()
            assertEquals(0, clock.waiting)
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            drain()
            assertEquals(1, clock.waiting)
            repeat(4) { clock.tick(); drain() }
            assertEquals(4, reads)
            assertEquals(1, syncs)
            assertEquals(listOf(2_000L, 2_000L, 2_000L, 2_000L, 2_000L), clock.intervals)
            owner.lifecycle.currentState = Lifecycle.State.RESUMED
            drain()
            owner.lifecycle.currentState = Lifecycle.State.STARTED // onPause / PiP
            drain()
            clock.tick()
            drain()
            assertEquals(5, reads)
            playing.value = false
            drain()
            assertEquals("Final position is synchronized", 2, syncs)
            assertEquals(0, clock.waiting)
            assertEquals(false, clock.steps.trySend(Unit).isSuccess)
            val idleIntervals = clock.intervals.size
            drain()
            assertEquals(idleIntervals, clock.intervals.size)
            playing.value = true
            drain()
            assertEquals(1, clock.waiting)
            owner.lifecycle.currentState = Lifecycle.State.CREATED
            drain()
            assertEquals(0, clock.waiting)
            assertEquals(0, playing.subscriptionCount.value)
            assertEquals(false, clock.steps.trySend(Unit).isSuccess)
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            drain()
            clock.tick()
            drain()
            assertEquals(6, reads)
            owner.lifecycle.currentState = Lifecycle.State.DESTROYED
            drain()
            assertEquals(0, clock.waiting)
            assertEquals(0, playing.subscriptionCount.value)
        } finally {
            scope.cancel()
            drain()
        }
    }

    @Test fun `stopping a remote cancels a suspended refresh and does not overlap requests`() {
        val owner = Owner()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val playing = MutableStateFlow(true)
        val clock = Clock()
        val response = CompletableDeferred<Unit>()
        var requests = 0
        var cancelled = 0
        var syncs = 0
        try {
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            scope.launch {
                refreshRemoteWhileStarted(owner.lifecycle, playing, clock, {
                    requests++
                    try { response.await() } finally { cancelled++ }
                }, { syncs++ })
            }
            drain()
            clock.tick()
            drain()
            assertEquals(1, requests)
            assertEquals(0, clock.waiting)
            assertEquals(false, clock.steps.trySend(Unit).isSuccess)
            playing.value = false
            drain()
            assertEquals(1, cancelled)
            assertEquals(1, syncs)
            response.complete(Unit)
            drain()
            assertEquals(1, requests)
            assertEquals(0, clock.waiting)
        } finally {
            scope.cancel()
            drain()
        }
    }

    @Test fun `companion snapshots advance live progress and stop ticker when the last remote stops`() {
        val owner = Owner()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val core = FakeCompanionCore()
        val clock = Clock()
        val repo = CompanionRepo(core) { 1_000L }
        var syncs = 0
        try {
            owner.lifecycle.currentState = Lifecycle.State.STARTED
            scope.launch {
                refreshRemoteWhileStarted(owner.lifecycle, repo.state.map { it.players.any { player -> player.playing } },
                    clock, { repo.refresh() }, { syncs++ })
            }
            drain()
            assertEquals("No peer is known to be playing yet", 0, clock.waiting)
            scope.launch { repo.refresh() } // Entry/network/user refresh discovers a playing peer.
            drain()
            assertEquals(1, clock.waiting)
            val first = core.rows.getJSONObject(0).getJSONObject("state")
            first.put("position", 75.0)
            clock.tick()
            drain()
            assertEquals(75.0, repo.state.value.players.single().position, 0.0)
            // The ticker must continue if one peer pauses while another is still playing.
            val second = org.json.JSONObject(core.rows.getJSONObject(0).toString()).put("device", "peer2")
            core.rows.put(second)
            first.put("playing", false)
            clock.tick()
            drain()
            assertEquals(1, clock.waiting)
            second.getJSONObject("state").put("position", 90.0).put("playing", false)
            clock.tick()
            drain()
            assertEquals(false, repo.state.value.players.any { it.playing })
            assertEquals(90.0, repo.state.value.players.last().position, 0.0)
            assertEquals("Capture final progress even before eight seconds", 1, syncs)
            assertEquals(0, clock.waiting)
        } finally {
            scope.cancel()
            drain()
        }
    }
}
