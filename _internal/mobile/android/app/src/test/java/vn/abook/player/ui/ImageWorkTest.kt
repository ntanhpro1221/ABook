package vn.abook.player.ui

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.data.ImageWork
import vn.abook.player.ui.data.ImageWorkScope
import java.util.concurrent.Executor

class ImageWorkTest {
    @After fun nothingLeaks() = assertEquals(emptyList<String>(), ImageWork.drain())

    @Test fun staysBusyThroughAllProducersAndPublication() = runBlocking {
        val release = CompletableDeferred<Unit>()
        var published = false
        val first = launch(start = CoroutineStart.UNDISPATCHED) {
            ImageWorkScope("first").track { release.await(); published = true }
        }
        val cancelled = launch(start = CoroutineStart.UNDISPATCHED) {
            ImageWorkScope("cancelled").track { CompletableDeferred<Unit>().await() }
        }
        assertEquals(listOf("cancelled", "first"), ImageWork.pendingSources)
        assertFalse(ImageWorkIdlingResource.isIdleNow)
        cancelled.cancelAndJoin()
        assertEquals("another image is still pending", listOf("first"), ImageWork.pendingSources)
        release.complete(Unit)
        first.join()
        assertTrue(published)
        assertTrue(ImageWorkIdlingResource.isIdleNow)
    }

    @Test fun failureDoesNotLeaveTheRuleBusy() = runBlocking {
        try {
            ImageWorkScope("failing").track<Unit> { throw IllegalStateException("failed image") }
            fail("must propagate failure")
        } catch (_: IllegalStateException) { }
        assertTrue(ImageWork.isIdle)
    }

    // Gate 22: a cancelled producer runs `finally` only when its dispatcher resumes it. Robolectric drops the main
    // looper's queue after each test, so that resumption never ran and every later class waited 60 s on a dead decode.
    @Test fun forgettingTheProducerReleasesItEvenIfItsDispatcherNeverRunsAgain() {
        val parked = mutableListOf<Runnable>()
        val deadHost = Executor { parked += it }.asCoroutineDispatcher()
        val work = ImageWorkScope("BookCover.kt:87")
        val job = CoroutineScope(deadHost).launch(start = CoroutineStart.UNDISPATCHED) { work.track { awaitCancellation() } }
        assertEquals(listOf("BookCover.kt:87"), ImageWork.pendingSources)
        job.cancel()
        assertEquals("the resumption is parked, so finally has not run", listOf("BookCover.kt:87"), ImageWork.pendingSources)
        assertTrue(parked.isNotEmpty())
        work.onForgotten()
        assertTrue("leaving the composition releases synchronously", ImageWork.isIdle)
        parked.forEach(Runnable::run) // A late resumption must not release (or count) twice.
        assertTrue(ImageWork.isIdle)
    }

    @Test fun anAbandonedProducerThatStartsLateIsNotCounted() = runBlocking {
        val work = ImageWorkScope("abandoned")
        work.onAbandoned()
        work.track { assertTrue("closed scope: nothing to wait for", ImageWork.isIdle) }
        assertTrue(ImageWork.isIdle)
    }

    @Test fun theSharedRuleNamesALeakAndClearsItSoTheNextTestStartsClean() {
        ImageWork.begin("PipContent.kt:136")
        val error = assertThrows(AssertionError::class.java) { ImageWorkIdlingResource.requireNoneOpen("after a test") }
        assertTrue(error.message!!, "PipContent.kt:136" in error.message!!)
        assertTrue(ImageWork.isIdle)
        ImageWorkIdlingResource.requireNoneOpen("before the next test")
    }
}
