package vn.abook.player.ui.data

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tin của việc nền (xong / lỗi) không được rơi dù luồng chính bận lâu: tin cuối quyết định màn có kẹt ở "Đang xuất" không. */
class ListenerFlowTest {
    @Test
    fun `no news is lost while the collector is busy`() = runBlocking {
        lateinit var send: (Int) -> Unit
        val flow = listenerFlow<Int> { callback -> send = callback; {} }
        val gate = CompletableDeferred<Unit>()
        // Unconfined: người nghe đã đăng ký và đang kẹt ở tin đầu khi vòng gửi chạy.
        val received = async(Dispatchers.Unconfined) { flow.onEach { if (it == 0) gate.await() }.take(500).toList() }
        repeat(500) { send(it) }
        gate.complete(Unit)
        assertEquals((0 until 500).toList(), withTimeoutOrNull(3_000) { received.await() })
    }

    @Test
    fun `the listener is let go when nobody listens any more`() = runBlocking {
        var stopped = 0
        val flow = listenerFlow<Int> { callback -> callback(1); { stopped++ } }
        assertEquals(listOf(1), flow.take(1).toList())
        assertTrue(stopped == 1)
    }
}
