package vn.abook.player.ui.music.library

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test

class PreviewStateTest {
    private class Output : PreviewPlayer {
        data class Call(val start: Double, val volume: Float, val ended: () -> Unit, val playing: (Boolean) -> Unit, val failed: (String) -> Unit)
        val calls = mutableListOf<Call>()
        var stops = 0
        override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit, onPlaying: (Boolean) -> Unit, onError: (String) -> Unit) {
            calls += Call(startSeconds, volume, onEnd, onPlaying, onError)
        }
        override fun stop() { stops++ }
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
}
