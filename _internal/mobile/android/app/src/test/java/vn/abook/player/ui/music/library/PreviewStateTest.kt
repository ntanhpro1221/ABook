package vn.abook.player.ui.music.library

import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

class PreviewStateTest {
    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun cancelAtTheCommitBoundaryKeepsTheCompleteFile() = runTest {
        val base = FakeLibrarySource()
        lateinit var state: LibraryState
        var discarded = 0
        val source = object : LibrarySource by base {
            override fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean) {
                base.download(link, progress, cancelled)
                state.cancel(listOf(link))
            }
            override fun discardPartial(link: String) { discarded++ }
            override fun forget(link: String) { fail("Stopping a transfer must not delete a complete file") }
        }
        state = LibraryState(source, backgroundScope, Output(), io = StandardTestDispatcher(testScheduler))
        state.open(); runCurrent()
        val link = state.ui.value.index!!.tracks.first { it.link !in base.onDisk }.link
        state.save(listOf(link)); runCurrent()
        assertTrue(link in base.onDisk)
        assertTrue(link in state.ui.value.downloaded)
        assertFalse(link in state.ui.value.active)
        assertEquals(1, discarded)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun fullTrackSurvivesThirtySecondsAndEndsWithoutStartingAnotherTrack() = runTest {
        val output = Output()
        val dispatcher = StandardTestDispatcher(testScheduler)
        val state = LibraryState(FakeLibrarySource(), backgroundScope, output, io = dispatcher)
        state.open(); runCurrent()
        val link = state.ui.value.index!!.tracks[1].link
        state.togglePreview(link)
        output.calls.single().playing(true)
        val stops = output.stops
        advanceTimeBy(35_000); runCurrent()
        assertEquals(link, state.ui.value.previewing)
        assertEquals(stops, output.stops)
        state.seekPreview(112.0)
        assertEquals(112.0, output.sought, 0.0)
        output.calls.single().ended()
        assertNull(state.ui.value.previewing)
        assertEquals(1, output.calls.size)
    }
    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun fileMutationLocksImmediatelyAndFailureKeepsDownloadedStateUntilRetrySucceeds() = runTest {
        val base = FakeLibrarySource()
        var calls = 0
        val source = object : LibrarySource by base {
            override fun unsave(links: List<String>) {
                calls++
                if (calls == 1) throw java.io.IOException("disk busy")
                base.unsave(links)
            }
        }
        val dispatcher = StandardTestDispatcher(testScheduler)
        val state = LibraryState(source, backgroundScope, Output(), io = dispatcher)
        state.open()
        runCurrent()
        val link = state.ui.value.downloaded.first()
        state.forget(link)
        state.forget(link)
        assertTrue(link in state.ui.value.pendingLinks)
        runCurrent()
        assertEquals(1, calls)
        assertTrue(link in state.ui.value.downloaded)
        assertTrue(state.ui.value.actionError.isNotEmpty())
        assertFalse(link in state.ui.value.pendingLinks)
        state.retryAction()
        runCurrent()
        assertEquals(2, calls)
        assertFalse(link in state.ui.value.downloaded)
        assertTrue(state.ui.value.actionError.isEmpty())
    }
    private class Output : PreviewPlayer {
        data class Call(val start: Double, val volume: Float, val ended: () -> Unit, val playing: (Boolean) -> Unit, val failed: (String) -> Unit)
        val calls = mutableListOf<Call>()
        var stops = 0
        var pauses = 0
        var resumes = 0
        var sought = 0.0
        override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit, onPlaying: (Boolean) -> Unit, onError: (String) -> Unit) {
            calls += Call(startSeconds, volume, onEnd, onPlaying, onError)
        }
        override fun stop() { stops++ }
        override fun pause() { pauses++ }
        override fun resume() { resumes++ }
        override fun seek(seconds: Double) { sought = seconds }
        override fun position() = sought
        override fun duration() = 180.0
    }

    @Test fun loadingAndFailureFollowActualOutputAndOldCallbacksCannotStopANewerRequest() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val source = FakeLibrarySource()
            val output = Output()
            var pauses = 0
            val state = LibraryState(source, scope, output, { pauses++ }, Dispatchers.Unconfined)
            state.open()
            val link = state.ui.value.index!!.tracks[1].link
            state.togglePreview(link)
            assertTrue(state.ui.value.previewLoading)
            assertEquals(0.4, output.calls[0].start, 0.0)
            output.calls[0].playing(true)
            assertFalse(state.ui.value.previewLoading)
            output.calls[0].playing(false)
            assertTrue(state.ui.value.previewLoading)
            state.stopPreview()
            state.togglePreview(link)
            output.calls[0].failed("old error")
            output.calls[0].ended()
            output.calls[0].playing(true)
            assertEquals(link, state.ui.value.previewing)
            assertTrue(state.ui.value.previewLoading)
            output.calls[1].failed("Mạng chậm, thử nghe lại.")
            assertNull(state.ui.value.previewing)
            assertFalse(state.ui.value.previewLoading)
            assertEquals("Mạng chậm, thử nghe lại.", state.ui.value.previewError)
            assertEquals(2, pauses)
        } finally { scope.cancel() }
    }

    @Test fun sameTrackPausesAndResumesAndSeekingUsesTheWholeTrack() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        try {
            val output = Output()
            val state = LibraryState(FakeLibrarySource(), scope, output, io = Dispatchers.Unconfined)
            state.open()
            val track = state.ui.value.index!!.tracks[1]
            state.togglePreview(track.link)
            output.calls.single().playing(true)
            state.togglePreview(track.link)
            assertTrue(state.ui.value.previewPaused)
            assertFalse(state.ui.value.previewLoading)
            assertEquals(1, output.pauses)
            state.togglePreview(track.link)
            assertFalse(state.ui.value.previewPaused)
            assertTrue(state.ui.value.previewLoading)
            assertEquals(1, output.resumes)
            state.seekPreview(40.0)
            assertEquals(40.0, output.sought, 0.0)
            assertEquals(track.link, state.ui.value.previewing)
            output.calls.single().ended()
            assertNull(state.ui.value.previewing)
        } finally { scope.cancel() }
    }
}
