package vn.abook.player

import androidx.work.WorkInfo
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.io.RandomAccessFile
import java.net.Socket
import java.net.URI
import java.nio.file.Files
import java.util.UUID
import java.util.concurrent.ThreadFactory
import java.util.concurrent.atomic.AtomicBoolean

class A113SecurityTest {
    private fun await(message: String, timeoutMs: Long = 4000, check: () -> Boolean) {
        val end = System.nanoTime() + timeoutMs * 1_000_000
        while (!check() && System.nanoTime() < end) Thread.sleep(10)
        assertTrue(message, check())
    }

    @Test fun a_receiver_that_never_reads_is_closed_and_returns_its_slot() {
        val audio = Files.createTempFile("a113", ".mp3").toFile()
        RandomAccessFile(audio, "rw").use { it.setLength(64L * 1024 * 1024) }
        val media = Dlna.Media("127.0.0.1", writeIdleMs = 200)
        var client: Socket? = null
        try {
            val uri = URI(media.share(audio, "127.0.0.1"))
            client = Socket().apply {
                receiveBufferSize = 1024
                connect(java.net.InetSocketAddress("127.0.0.1", uri.port), 2000)
                getOutputStream().write("GET ${uri.path} HTTP/1.1\r\nHost: x\r\n\r\n".toByteArray())
            }
            await("worker đã giữ slot") { media.activeConnections() == 1 }
            await("không đọc: canh ghi đóng socket và nhả slot") { media.activeConnections() == 0 }
            assertEquals(200, uri.toURL().openConnection().apply { connectTimeout = 2000; readTimeout = 2000; setRequestProperty("Range", "bytes=0-9") }
                .let { it as java.net.HttpURLConnection }.run { try { responseCode } finally { disconnect() } })
        } finally {
            client?.close()
            media.close()
            // Giữ artifact nhỏ/rỗng cho harness; không xoá bằng JVM.
            RandomAccessFile(audio, "rw").use { it.setLength(0) }
        }
    }

    @Test fun progress_keeps_a_stream_alive_past_the_idle_limit() {
        val audio = Files.createTempFile("a113-progress", ".mp3").toFile()
        audio.writeBytes(ByteArray(8 * 1024 * 1024) { 7 })
        val media = Dlna.Media("127.0.0.1", writeIdleMs = 500)
        try {
            val uri = URI(media.share(audio, "127.0.0.1"))
            Socket().apply {
                receiveBufferSize = 65536
                connect(java.net.InetSocketAddress("127.0.0.1", uri.port), 2000)
            }.use { client ->
                client.soTimeout = 2000
                client.getOutputStream().write("GET ${uri.path} HTTP/1.1\r\nHost: x\r\n\r\n".toByteArray())
                val input = client.getInputStream()
                val header = StringBuilder()
                while (!header.endsWith("\r\n\r\n")) {
                    val byte = input.read()
                    assertTrue("header đủ trước khi đọc audio", byte >= 0)
                    header.append(byte.toChar())
                }
                val buffer = ByteArray(65536)
                var total = 0
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    Thread.sleep(10)
                }
                assertEquals(audio.length(), total.toLong())
            }
        } finally { media.close() }
    }

    @Test fun a_thread_creation_error_does_not_leak_the_socket_or_kill_accept() {
        val fail = AtomicBoolean(true)
        val factory = ThreadFactory { task ->
            if (fail.getAndSet(false)) throw OutOfMemoryError("injected thread creation failure")
            Thread(task, "a113-worker").apply { isDaemon = true }
        }
        val media = Dlna.Media("127.0.0.1", workerFactory = factory)
        val audio = Files.createTempFile("a113-thread", ".mp3").toFile().apply { writeText("ID3") }
        try {
            val uri = URI(media.share(audio, "127.0.0.1"))
            Socket("127.0.0.1", uri.port).use { client ->
                client.soTimeout = 2000
                assertEquals("socket bị từ chối phải đóng", -1, client.getInputStream().read())
            }
            await("slot được trả sau lỗi tạo thread") { media.activeConnections() == 0 }
            assertEquals("ID3", uri.toURL().openConnection().apply { connectTimeout = 2000; readTimeout = 2000 }.getInputStream().use { it.reader().readText() })
        } finally { media.close() }
    }

    @Test fun a_transient_accept_error_does_not_kill_the_port() {
        val fail = AtomicBoolean(true)
        val media = Dlna.Media("127.0.0.1", acceptClient = { socket ->
            if (fail.getAndSet(false)) throw IOException("injected EMFILE")
            socket.accept()
        })
        val audio = Files.createTempFile("a113-accept", ".mp3").toFile().apply { writeText("ID3") }
        try {
            val uri = URI(media.share(audio, "127.0.0.1"))
            assertEquals("ID3", uri.toURL().openConnection().apply { connectTimeout = 2000; readTimeout = 2000 }.getInputStream().use { it.reader().readText() })
        } finally { media.close() }
    }

    @Test fun a_failed_work_query_keeps_the_book_protected_and_can_be_queried_again() {
        val book = "a113-${UUID.randomUUID()}"
        val run = UUID.randomUUID().toString()
        BookDownloads.runs.add(book, run)
        try {
            assertTrue(BookDownloads.isActive(book) { throw IOException("query failed") })
            assertEquals(run, BookDownloads.active[book])
            assertTrue(BookDownloads.enter(book, run))
        } finally { BookDownloads.leave(book, run) }
    }

    @Test fun a_known_finished_work_is_removed_but_an_ended_run_cannot_enter_again() {
        val book = "a113-${UUID.randomUUID()}"
        val run = UUID.randomUUID().toString()
        BookDownloads.runs.add(book, run)
        assertFalse(BookDownloads.isActive(book) { WorkInfo.State.SUCCEEDED })
        assertFalse(BookDownloads.enter(book, run))
        assertFalse(BookDownloads.isActive(book) { WorkInfo.State.RUNNING })
        BookDownloads.leave(book, run)
    }
}
