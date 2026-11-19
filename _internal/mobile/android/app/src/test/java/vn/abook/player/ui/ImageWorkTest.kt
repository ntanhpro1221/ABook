package vn.abook.player.ui

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.data.ImageWork

class ImageWorkTest {
    @Test fun staysBusyThroughAllProducersAndPublication() = runBlocking {
        val release = CompletableDeferred<Unit>()
        var published = false
        val first = launch(start = CoroutineStart.UNDISPATCHED) {
            ImageWork.track { release.await(); published = true }
        }
        val cancelled = launch(start = CoroutineStart.UNDISPATCHED) {
            ImageWork.track { CompletableDeferred<Unit>().await() }
        }
        assertFalse(ImageWork.isIdle)
        assertFalse(ImageWorkIdlingResource.isIdleNow)
        cancelled.cancelAndJoin()
        assertFalse("another image is still pending", ImageWork.isIdle)
        release.complete(Unit)
        first.join()
        assertTrue(published)
        assertTrue(ImageWorkIdlingResource.isIdleNow)
    }

    @Test fun failureDoesNotLeaveTheRuleBusy() = runBlocking {
        try {
            ImageWork.track<Unit> { throw IllegalStateException("failed image") }
            fail("must propagate failure")
        } catch (_: IllegalStateException) { }
        assertTrue(ImageWork.isIdle)
    }
}
