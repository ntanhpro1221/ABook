package vn.abook.player

import java.io.IOException
import java.io.OutputStream
import java.net.Socket
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Test

class A116CastLoggingTest {
    @Test fun failuresAreLimitedPerCategoryAndNeverCarryPeerDetails() {
        val lines = mutableListOf<String>()
        val log = Dlna.TransferFailures { lines.add(it) }
        log.record(true, 4, 0)
        log.record(true, 8, 1)
        log.record(false, 12, 1)
        log.record(true, 16, TimeUnit.SECONDS.toNanos(30))
        assertEquals(listOf("Cast transfer idle-timeout bytes_sent=4", "Cast transfer write-error bytes_sent=12",
            "Cast transfer idle-timeout bytes_sent=16"), lines)
    }

    @Test fun authenticatedWriteFailureCountsCompletedChunksAndUnknownConnectionStaysQuiet() {
        val lines = mutableListOf<String>()
        val failures = Dlna.TransferFailures { lines.add(it) }
        fun socket() = object : Socket() {
            override fun getOutputStream(): OutputStream = object : OutputStream() {
                var calls = 0
                override fun write(value: Int) { throw IOException("private URL/token/IP") }
                override fun write(bytes: ByteArray, offset: Int, length: Int) {
                    calls++
                    if (calls > 1) throw IOException("private URL/token/IP")
                }
            }
        }
        Dlna.Media.ProgressOutput(socket(), 120_000, failures).use { output ->
            output.authenticated = true
            assertTrue(runCatching { output.write(ByteArray(8193)) }.isFailure)
        }
        assertEquals(listOf("Cast transfer write-error bytes_sent=8192"), lines)
        lines.clear()
        Dlna.Media.ProgressOutput(socket(), 120_000, failures).use { output -> output.failure(timeout = true) }
        assertTrue(lines.isEmpty())
    }

    @Test fun watchdogReportsTimeoutOnceForAuthenticatedTransfer() {
        val lines = mutableListOf<String>()
        val socket = object : Socket() { override fun getOutputStream() = java.io.ByteArrayOutputStream() }
        Dlna.Media.ProgressOutput(socket, 120_000, Dlna.TransferFailures { lines.add(it) }).use { output ->
            output.authenticated = true
            output.write(ByteArray(12))
            output.failure(timeout = true)
            output.failure(timeout = false)
        }
        assertEquals(listOf("Cast transfer idle-timeout bytes_sent=12"), lines)
    }
}
