package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import java.net.InetSocketAddress
import java.net.SocketAddress
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSession

/** F5/F6 exercise the actual Pin socket scope and deadline with deterministic time, no network. */
class PeerProbeTest {
    private class Clock { var now = 0L }
    private class Socket(private val clock: Clock, private val tcpMs: Long = 0, private val tlsMs: Long = 0) : SSLSocket() {
        var closed = false
        var tcpTimeout = 0
        var tlsTimeout = 0
        override fun connect(endpoint: SocketAddress?, timeout: Int) { tcpTimeout = timeout; clock.now += tcpMs * 1_000_000 }
        override fun setSoTimeout(timeout: Int) { tlsTimeout = timeout }
        override fun startHandshake() {
            if (tlsMs > tlsTimeout) { clock.now += tlsTimeout * 1_000_000L; throw java.net.SocketTimeoutException("TLS") }
            clock.now += tlsMs * 1_000_000
        }
        override fun close() { closed = true }
        override fun getSupportedCipherSuites(): Array<String> = emptyArray()
        override fun getEnabledCipherSuites(): Array<String> = emptyArray()
        override fun setEnabledCipherSuites(suites: Array<out String>?) = Unit
        override fun getSupportedProtocols(): Array<String> = emptyArray()
        override fun getEnabledProtocols(): Array<String> = emptyArray()
        override fun setEnabledProtocols(protocols: Array<out String>?) = Unit
        override fun getSession(): SSLSession = throw UnsupportedOperationException()
        override fun addHandshakeCompletedListener(listener: javax.net.ssl.HandshakeCompletedListener?) = Unit
        override fun removeHandshakeCompletedListener(listener: javax.net.ssl.HandshakeCompletedListener?) = Unit
        override fun setUseClientMode(mode: Boolean) = Unit
        override fun getUseClientMode() = true
        override fun setNeedClientAuth(need: Boolean) = Unit
        override fun getNeedClientAuth() = false
        override fun setWantClientAuth(want: Boolean) = Unit
        override fun getWantClientAuth() = false
        override fun setEnableSessionCreation(flag: Boolean) = Unit
        override fun getEnableSessionCreation() = true
    }

    /** The production deadline (Pin.probeTls) around a fake socket: `address` stands for name resolution, which counts against the same deadline. */
    private fun dial(socket: SSLSocket, address: () -> InetSocketAddress, timeoutMs: Int, nanoTime: () -> Long) {
        socket.use {
            Pin.probeTls(timeoutMs, nanoTime) { left ->
                val resolved = address()
                socket.connect(resolved, left())
                socket
            }
        }
    }

    @Test fun slowTcpLeavesOnlyRemainingBudgetForTls() {
        val clock = Clock()
        val socket = Socket(clock, tcpMs = 90, tlsMs = 90)
        try {
            dial(socket, { InetSocketAddress("127.0.0.1", 443) }, 100, { clock.now })
            fail("two independent phase timeouts")
        } catch (_: java.net.SocketTimeoutException) { }
        assertEquals(100, socket.tcpTimeout)
        assertEquals(10, socket.tlsTimeout)
        assertTrue(socket.closed)
    }

    @Test fun dnsTimeCountsBeforeTcpAndTls() {
        val clock = Clock()
        val socket = Socket(clock, tcpMs = 20, tlsMs = 10)
        dial(socket, { clock.now += 40_000_000; InetSocketAddress("127.0.0.1", 443) }, 100, { clock.now })
        assertEquals(60, socket.tcpTimeout)
        assertEquals(40, socket.tlsTimeout)
        assertTrue(socket.closed)
        val expired = Socket(clock)
        try {
            dial(expired, { clock.now += 101_000_000; InetSocketAddress("127.0.0.1", 443) }, 100, { clock.now })
            fail("DNS consumed deadline")
        } catch (_: java.net.SocketTimeoutException) { }
        assertEquals(0, expired.tcpTimeout)
        assertTrue(expired.closed)
    }

    @Test fun persistenceFailureAfterProbeCannotLeakTheSocket() {
        val clock = Clock()
        val socket = Socket(clock)
        try {
            dial(socket, { InetSocketAddress("127.0.0.1", 443) }, 100, { clock.now })
            assertTrue(socket.closed) // remember runs after Pin.probe has already left use.
            throw java.io.IOException("peer routes locked")
        } catch (_: java.io.IOException) { }
        assertTrue(socket.closed)
    }
}
