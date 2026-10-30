package vn.abook.player

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.IOException
import java.net.SocketTimeoutException
import javax.net.ssl.SSLException

/** Lõi thuần của Studio từ xa: phân loại lỗi, dựng đường, nhịp hỏi (port polling.ts), máy khách với đường gửi giả. */
class StudioErrorsTest {
    private val listenOnly = """{"error":"Máy tính chưa cho phép","listenOnly":true}"""

    @Test fun listenOnlyIsTheForbiddenWithTheFlag() {
        assertTrue(StudioErrors.classify(403, listenOnly) is StudioError.ListenOnly)
        // 403 không mang cờ là lỗi thường của máy chủ, không phải "chỉ nghe".
        assertTrue(StudioErrors.classify(403, """{"error":"Không được"}""") is StudioError.Server)
        assertTrue(StudioErrors.classify(403, """{"listenOnly":"true"}""") is StudioError.Server)
        assertTrue(StudioErrors.classify(500, listenOnly) is StudioError.Server)
    }

    @Test fun statusMapsToKind() {
        assertTrue(StudioErrors.classify(401, "") is StudioError.Unauthorized)
        assertTrue(StudioErrors.classify(404, "{}") is StudioError.Gone)
        assertTrue(StudioErrors.classify(413, "") is StudioError.TooBig)
        assertEquals("Đang bận", (StudioErrors.classify(409, """{"error":"Đang bận"}""") as StudioError.Busy).message)
        assertTrue(StudioErrors.classify(423, "") is StudioError.Busy)
        val other = StudioErrors.classify(400, """{"error":"Thiếu tên"}""") as StudioError.Server
        assertEquals("Thiếu tên", other.message)
        assertEquals(400, other.status)
    }

    @Test fun serverMessageFallsBackAndHidesPythonErrors() {
        assertEquals("Lỗi 502", StudioErrors.serverMessage(502, "<html>"))
        assertEquals("Lỗi 400", StudioErrors.serverMessage(400, """{"detail":"x"}"""))
        assertEquals(StudioErrors.UNEXPECTED, StudioErrors.serverMessage(500, """{"error":"TypeError: 'NoneType' object"}"""))
        // Lời tiếng Việt của máy chủ giữ nguyên, kể cả ở 500; "TypeError" ở 4xx cũng không bị che.
        assertEquals("Sổ làm việc đang bận", StudioErrors.serverMessage(500, """{"error":"Sổ làm việc đang bận"}"""))
        assertEquals("ValueError: x", StudioErrors.serverMessage(400, """{"error":"ValueError: x"}"""))
    }

    @Test fun exceptionsFromTheTransportBecomeKinds() {
        assertTrue(StudioErrors.of(NetErrors.Refused(403, "x", listenOnly)) is StudioError.ListenOnly)
        assertTrue(StudioErrors.of(NetErrors.Refused(404, "x")) is StudioError.Gone)
        assertTrue(StudioErrors.of(SocketTimeoutException()) is StudioError.Offline)
        assertTrue(StudioErrors.of(IOException("reset")) is StudioError.Offline)
        assertTrue(StudioErrors.of(Pin.ChangedException(SSLException("x"))) is StudioError.PinChanged)
        assertTrue(StudioErrors.of(IllegalArgumentException("Dữ liệu máy gửi không hợp lệ")) is StudioError.Server)
        val already = StudioError.Gone()
        assertTrue(StudioErrors.of(already) === already)
    }

    @Test fun cancellationPassesThrough() {
        try {
            StudioErrors.of(kotlinx.coroutines.CancellationException("huỷ"))
            fail("phải ném lại")
        } catch (expected: kotlinx.coroutines.CancellationException) {
            assertEquals("huỷ", expected.message)
        }
    }
}

class StudioPathsTest {
    @Test fun buildsBookPaths() {
        assertEquals("/api/books/abc_1-X", StudioPaths.book("abc_1-X"))
        assertEquals("/api/books/b1/start", StudioPaths.start("b1"))
        assertEquals("/api/books/b1/stop", StudioPaths.stop("b1"))
        assertEquals("/api/books/b1/pause", StudioPaths.pause("b1"))
        assertEquals("/api/books/b1/dequeue", StudioPaths.dequeue("b1"))
    }

    @Test fun strangeIdsAreRefusedBeforeSending() {
        for (bad in listOf("", "a/b", "../x", "a b", "a?b=1", "a#b", "sách")) {
            assertFalse(bad, StudioPaths.valid(bad))
            try {
                StudioPaths.book(bad)
                fail("mã lạ không được vào đường dẫn: $bad")
            } catch (expected: IllegalArgumentException) {
            }
        }
    }
}

class StudioPollerTest {
    private val offline = StudioError.Offline()

    @Test fun pollDelayMatchesTheWebTable() {
        // Cùng bảng với ui/src/studio/polling.test.ts.
        assertNull(StudioPolling.pollDelay(15_000, StudioError.Gone(), 3))
        assertNull(StudioPolling.pollDelay(15_000, StudioError.ListenOnly(), 1))
        assertEquals(30_000L, StudioPolling.pollDelay(15_000, offline, 1))
        assertEquals(60_000L, StudioPolling.pollDelay(15_000, offline, 2))
        assertEquals(120_000L, StudioPolling.pollDelay(15_000, offline, 9))
        assertEquals(15_000L, StudioPolling.pollDelay(15_000, null, 9))
        assertNull(StudioPolling.pollDelay(null, offline, 2))
        assertNull(StudioPolling.pollDelay(null, null, 0))
    }

    @Test fun unpairedAndChangedCertificateStopPollingToo() {
        assertNull(StudioPolling.pollDelay(15_000, StudioError.Unauthorized(), 1))
        assertNull(StudioPolling.pollDelay(15_000, StudioError.PinChanged(), 1))
    }

    @Test fun runKeepsStaleDataAndBacksOffThenRecovers() = runBlocking {
        val results = ArrayDeque<Any>(listOf("a", "b", offline, offline, "c"))
        val waits = mutableListOf<Long>()
        lateinit var job: Job
        val poller = StudioPoller<String>(
            fetch = { results.removeFirst().let { if (it is Throwable) throw it else it as String } },
            interval = { 3000 },
            pause = { ms ->
                waits += ms
                if (waits.size == 5) { job.cancel(); awaitCancellation() }
            },
        )
        job = launch { poller.run() }
        job.join()
        assertEquals(listOf(3000L, 3000L, 6000L, 12_000L, 3000L), waits)
        val last = poller.state.value
        assertEquals("c", last.data)
        assertNull(last.error)
        assertEquals(0, last.failures)
    }

    @Test fun failedAskKeepsTheOldDataWithTheError() = runBlocking {
        val results = ArrayDeque<Any>(listOf("a", offline))
        lateinit var job: Job
        var waits = 0
        val poller = StudioPoller<String>(
            fetch = { results.removeFirst().let { if (it is Throwable) throw it else it as String } },
            interval = { 1000 },
            pause = { if (++waits == 2) { job.cancel(); awaitCancellation() } },
        )
        job = launch { poller.run() }
        job.join()
        val state = poller.state.value
        assertEquals("a", state.data)
        assertTrue(state.error is StudioError.Offline)
        assertEquals(1, state.failures)
        assertTrue(state.loaded)
    }

    @Test fun runStopsForGoneAndListenOnly() = runBlocking {
        for (error in listOf<StudioError>(StudioError.Gone(), StudioError.ListenOnly())) {
            var asked = 0
            val poller = StudioPoller<String>(
                fetch = { asked++; throw error },
                interval = { 1000 },
                pause = { fail("không được chờ nhịp sau ${error.javaClass.simpleName}") },
            )
            poller.run() // trả về, không treo
            assertEquals(1, asked)
            assertTrue(poller.state.value.error === error)
        }
    }

    @Test fun withoutAnIntervalItWaitsForRefresh() = runBlocking {
        var asked = 0
        val poller = StudioPoller<Int>(fetch = { ++asked }, interval = { null }, pause = { fail("không có nhịp") })
        val job = launch(start = CoroutineStart.UNDISPATCHED) { poller.run() }
        assertEquals(1, asked)
        poller.refresh()
        yield()
        yield()
        assertEquals("refresh hỏi đúng một lần, run không hỏi trùng", 2, asked)
        assertEquals(2, poller.state.value.data)
        assertTrue(job.isActive)
        job.cancel()
    }

    @Test fun refreshDuringTheWaitDoesNotDoubleAsk() = runBlocking {
        var asked = 0
        val gate = CompletableDeferred<Unit>()
        val poller = StudioPoller<Int>(fetch = { ++asked }, interval = { 5000 }, pause = { gate.await() })
        val job = launch(start = CoroutineStart.UNDISPATCHED) { poller.run() }
        assertEquals(1, asked)
        poller.refresh()
        yield()
        yield()
        assertEquals(2, asked)
        job.cancel()
    }
}

class StudioApiTest {
    private fun api(reply: (String, String, JSONObject?) -> String) = StudioApi { method, path, body -> reply(method, path, body) }

    @Test fun readsObjectsAndArrays() = runBlocking {
        val api = api { _, path, _ -> if (path == "/api/library") """{"books":[]}""" else """[{"id":"a"}]""" }
        assertEquals(0, api.getObject("/api/library").getJSONArray("books").length())
        assertEquals("a", api.getArray("/api/voices").getJSONObject(0).getString("id"))
    }

    @Test fun postSendsTheBodyAndTheMethod() = runBlocking {
        var seen: Triple<String, String, String?>? = null
        val api = api { method, path, body -> seen = Triple(method, path, body?.toString()); """{"id":"b1","running":true}""" }
        val book = api.post(StudioPaths.pause("b1"), JSONObject().put("paused", true))
        assertEquals(Triple("POST", "/api/books/b1/pause", """{"paused":true}"""), seen)
        assertTrue(book.getBoolean("running"))
    }

    @Test fun wrongShapeAndBrokenJsonAreServerErrors() = runBlocking {
        val object1 = api { _, _, _ -> """{"a":1}""" }
        val array1 = api { _, _, _ -> "[1]" }
        val broken = api { _, _, _ -> "{broken" }
        for (call in listOf<suspend () -> Unit>({ object1.getArray("/x") }, { array1.getObject("/x") }, { broken.getObject("/x") })) {
            try {
                call()
                fail("phải ném StudioError.Server")
            } catch (expected: StudioError.Server) {
                assertEquals(0, expected.status)
            }
        }
    }

    @Test fun anEmptyReplyIsAnEmptyObject() = runBlocking {
        assertEquals(0, api { _, _, _ -> "" }.post("/api/books/b1/stop").length())
    }

    @Test fun transportFailuresAreClassified() = runBlocking {
        suspend fun kind(error: Throwable): StudioError = try {
            api { _, _, _ -> throw error }.getObject("/x"); fail("phải ném"); error("không tới")
        } catch (e: StudioError) { e }
        assertTrue(kind(NetErrors.Refused(403, "x", """{"listenOnly":true}""")) is StudioError.ListenOnly)
        assertTrue(kind(NetErrors.Refused(404, "x")) is StudioError.Gone)
        assertTrue(kind(SocketTimeoutException()) is StudioError.Offline)
        assertTrue(kind(StudioError.Unauthorized()) is StudioError.Unauthorized)
        Unit
    }

    @Test fun anArrayBodyIsNotMistakenForAnObject() = runBlocking {
        val array: JSONArray = api { _, _, _ -> "[]" }.getArray("/api/library")
        assertEquals(0, array.length())
    }
}
