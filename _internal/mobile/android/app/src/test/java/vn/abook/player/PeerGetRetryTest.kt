package vn.abook.player

import java.io.EOFException
import java.net.HttpURLConnection
import java.net.SocketException
import java.net.URL
import java.security.cert.CertificateException
import javax.net.ssl.SSLHandshakeException
import org.junit.Assert.*
import org.junit.Test

class PeerGetRetryTest {
    private class Connection(private val status: Int = 200, private val fault: Exception? = null) :
        HttpURLConnection(URL("http://127.0.0.1/")) {
        var closed = false
        override fun connect() {}
        override fun disconnect() { closed = true }
        override fun usingProxy() = false
        override fun getResponseCode(): Int { fault?.let { throw it }; return status }
    }

    @Test fun get_retries_closed_and_503_with_backoff_and_closes_old_connections() {
        val connections = listOf(Connection(fault = EOFException()), Connection(503), Connection())
        val pauses = mutableListOf<Long>()
        var attempt = 0
        val got = PeerTransfer.openGet(pause = { pauses.add(it) }) { connections[attempt++] }
        assertSame(connections[2], got)
        assertEquals(listOf(200L, 800L), pauses)
        assertTrue(connections.take(2).all { it.closed })
        assertFalse(connections[2].closed)
        got.disconnect()
    }

    @Test fun get_stops_after_two_retries() {
        var attempts = 0
        val connections = mutableListOf<Connection>()
        val error = runCatching { PeerTransfer.openGet(pause = {}) {
            attempts++; Connection(fault = SocketException("closed")).also { connections.add(it) }
        } }.exceptionOrNull()
        assertTrue(error is SocketException)
        assertEquals(3, attempts)
        assertTrue(connections.all { it.closed })
    }

    @Test fun post_is_never_sent_by_get_helper() {
        var attempts = 0
        val connection = Connection().apply { requestMethod = "POST" }
        assertTrue(runCatching { PeerTransfer.openGet(pause = { fail("POST retry") }) {
            attempts++; connection
        } }.isFailure)
        assertEquals(1, attempts)
        assertTrue(connection.closed)
    }

    @Test fun pin_failure_never_retries() {
        var attempts = 0
        val connection = Connection(fault = SSLHandshakeException("pin").apply { initCause(CertificateException("changed")) })
        assertTrue(runCatching { PeerTransfer.openGet(pause = { fail("pin retry") }) {
            attempts++; connection
        } }.exceptionOrNull() is SSLHandshakeException)
        assertEquals(1, attempts)
        assertTrue(connection.closed)
    }

    @Test fun ordinary_http_error_is_returned_once() {
        var attempts = 0
        val connection = Connection(401)
        assertSame(connection, PeerTransfer.openGet(pause = { fail("401 retry") }) { attempts++; connection })
        assertEquals(1, attempts)
        connection.disconnect()
    }
}
