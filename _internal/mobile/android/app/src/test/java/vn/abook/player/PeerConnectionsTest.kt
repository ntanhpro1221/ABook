package vn.abook.player

import java.net.InetAddress
import java.net.Socket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import org.junit.Assert.*
import org.junit.Test
import org.junit.After

class PeerConnectionsTest {
    @After fun drain() {
        val field = LibraryServer::class.java.getDeclaredField("connections").apply { isAccessible = true }
        val until = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (field.getInt(LibraryServer) != 0 && System.nanoTime() < until) Thread.sleep(5)
        assertEquals(0, field.getInt(LibraryServer))
    }
    @Test fun failure_before_worker_submission_does_not_leak_slots_or_stop_accepting() {
        for (i in 1..LibraryServer.PEER_MAX_CONNECTIONS) {
            val client = object : Socket() {
                override fun getInetAddress() = InetAddress.getByName("192.0.2.100")
                override fun setSoTimeout(timeout: Int) { throw java.net.SocketException("closed") }
            }
            LibraryServer.dispatch(client) {}
            assertTrue(client.isClosed)
        }
        val done = CountDownLatch(1)
        LibraryServer.dispatch(Client("192.0.2.100")) { done.countDown() }
        assertTrue(done.await(1, TimeUnit.SECONDS))
    }
    private class Client(private val ip: String) : Socket() {
        val closed = CountDownLatch(1)
        override fun getInetAddress() = InetAddress.getByName(ip)
        override fun setSoTimeout(timeout: Int) {}
        override fun close() { closed.countDown() }
    }

    @Test fun excess_source_connections_close_without_queueing_other_sources() {
        val release = CountDownLatch(1)
        val cap = LibraryServer.PEER_MAX_PER_SOURCE
        val started = CountDownLatch(cap)
        val clients = (1..cap + 1).map { Client("192.0.2.1") }
        try {
            clients.take(cap).forEach { LibraryServer.dispatch(it) { started.countDown(); release.await(5, TimeUnit.SECONDS) } }
            assertTrue(started.await(5, TimeUnit.SECONDS))
            LibraryServer.dispatch(clients[cap]) { release.await(5, TimeUnit.SECONDS) }
            assertTrue("excess socket queued or served", clients[cap].closed.await(1, TimeUnit.SECONDS))
            val other = Client("192.0.2.2")
            val served = CountDownLatch(1)
            LibraryServer.dispatch(other) { served.countDown() }
            assertTrue(served.await(1, TimeUnit.SECONDS))
        } finally { release.countDown() }
    }

    @Test fun eight_requests_from_authenticated_source_are_all_served() {
        val ip = "192.0.2.80"
        LibraryServer.authenticatedSource(ip)
        val release = CountDownLatch(1)
        val active = CountDownLatch(LibraryServer.PEER_MAX_PER_SOURCE)
        val served = CountDownLatch(8)
        val clients = (1..8).map { Client(ip) }
        try {
            clients.forEach { client -> LibraryServer.dispatch(client) {
                active.countDown()
                release.await(5, TimeUnit.SECONDS)
                served.countDown()
            } }
            assertTrue(active.await(5, TimeUnit.SECONDS))
            assertTrue(clients.all { it.closed.count == 1L })
        } finally { release.countDown() }
        assertTrue(served.await(5, TimeUnit.SECONDS))
        assertTrue(clients.all { it.closed.await(5, TimeUnit.SECONDS) })
    }

    @Test fun authenticated_queue_is_bounded_and_another_source_can_still_run() {
        val ip = "192.0.2.81"
        LibraryServer.authenticatedSource(ip)
        val release = CountDownLatch(1)
        val active = CountDownLatch(LibraryServer.PEER_MAX_PER_SOURCE)
        val served = CountDownLatch(LibraryServer.PEER_MAX_PER_SOURCE + LibraryServer.PEER_MAX_QUEUED)
        try {
            repeat(LibraryServer.PEER_MAX_PER_SOURCE) { LibraryServer.dispatch(Client(ip)) {
                active.countDown(); release.await(5, TimeUnit.SECONDS); served.countDown()
            } }
            assertTrue(active.await(5, TimeUnit.SECONDS))
            repeat(LibraryServer.PEER_MAX_QUEUED) { LibraryServer.dispatch(Client(ip)) { served.countDown() } }
            val excess = Client(ip)
            LibraryServer.dispatch(excess) { fail("excess served") }
            assertTrue(excess.closed.await(1, TimeUnit.SECONDS))
            val other = CountDownLatch(1)
            LibraryServer.dispatch(Client("192.0.2.82")) { other.countDown() }
            assertTrue(other.await(1, TimeUnit.SECONDS))
        } finally { release.countDown() }
        assertTrue(served.await(5, TimeUnit.SECONDS))
    }

    @Test fun queued_socket_expires_without_ever_entering_worker() {
        val ip = "192.0.2.83"
        LibraryServer.authenticatedSource(ip)
        val active = CountDownLatch(LibraryServer.PEER_MAX_PER_SOURCE)
        val release = CountDownLatch(1)
        try {
            repeat(LibraryServer.PEER_MAX_PER_SOURCE) { LibraryServer.dispatch(Client(ip)) {
                active.countDown(); release.await(5, TimeUnit.SECONDS)
            } }
            assertTrue(active.await(5, TimeUnit.SECONDS))
            val queued = Client(ip)
            LibraryServer.dispatch(queued, queueMillis = 50) { fail("expired socket entered worker") }
            assertTrue(queued.closed.await(2, TimeUnit.SECONDS))
        } finally { release.countDown() }
    }

    @Test fun total_worker_limit_closes_unknown_excess_connections() {
        val release = CountDownLatch(1)
        val active = CountDownLatch(LibraryServer.PEER_MAX_CONNECTIONS)
        try {
            repeat(LibraryServer.PEER_MAX_CONNECTIONS) { index ->
                LibraryServer.dispatch(Client("192.0.2.${120 + index}")) {
                    active.countDown(); release.await(5, TimeUnit.SECONDS)
                }
            }
            assertTrue(active.await(5, TimeUnit.SECONDS))
            val excess = Client("192.0.2.150")
            LibraryServer.dispatch(excess) { fail("over total worker limit") }
            assertTrue(excess.closed.await(1, TimeUnit.SECONDS))
        } finally { release.countDown() }
    }
}
