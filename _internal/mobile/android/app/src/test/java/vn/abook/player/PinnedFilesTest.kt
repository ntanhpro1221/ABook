package vn.abook.player

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.File
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.file.Files
import java.security.MessageDigest
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger

/**
 * The download behind every phone module ([PinnedFiles]) against a local HTTP server: a connection cut half-way is a network error (the `.part` is
 * kept and the next try resumes it with Range, never a failed hash), a cancel stops at the next read and keeps the `.part`, and the download after
 * it asks for exactly the bytes still missing.
 */
class PinnedFilesTest {
    private lateinit var server: ServerSocket
    private lateinit var root: File
    private val ranges = CopyOnWriteArrayList<String?>()
    private var body = ByteArray(400_000) { (it * 31 + it / 7).toByte() }

    /** The next [cuts] responses send only [cutAfter] bytes and close the connection (the Content-Length still says the whole rest). */
    @Volatile
    private var cutAfter = 0
    private val cuts = AtomicInteger(0)

    /** The file's version as the server reports it (ETag); a test changes it to play "the file was rebuilt". */
    @Volatile
    private var etag = "\"v1\""

    /** A server that ignores If-Range and answers 206 with the tail of a DIFFERENT version. */
    @Volatile
    private var ignoreIfRange = false

    /** A server that answers the next ranged request with 416 (the part is longer than the file it holds now). */
    @Volatile
    private var refuseRange = false

    private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private val part get() = PinnedFiles.Part("model.bin", digest(body), body.size.toLong())
    private val base get() = "http://127.0.0.1:${server.localPort}/"
    private val dir get() = File(root, "module")

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-pinned").toFile()
        server = ServerSocket(0, 5, InetAddress.getByName("127.0.0.1"))
        Thread {
            while (!server.isClosed) {
                val client = try {
                    server.accept()
                } catch (_: Exception) {
                    break
                }
                Thread { client.use { runCatching { serve(it) } } }.start()
            }
        }.apply { isDaemon = true }.start()
    }

    @After
    fun tearDown() {
        server.close()
        root.deleteRecursively()
    }

    private fun serve(client: Socket) {
        val input = client.getInputStream().bufferedReader(Charsets.ISO_8859_1)
        input.readLine() ?: return
        var range: String? = null
        var ifRange: String? = null
        while (true) {
            val line = input.readLine() ?: return
            if (line.isEmpty()) break
            if (line.startsWith("Range:", ignoreCase = true)) range = line.substringAfter(':').trim()
            if (line.startsWith("If-Range:", ignoreCase = true)) ifRange = line.substringAfter(':').trim()
        }
        ranges.add(range)
        if (range != null && refuseRange) {
            refuseRange = false
            client.getOutputStream().apply {
                write("HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */${body.size}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
                flush()
            }
            return
        }
        val partial = range != null && (ignoreIfRange || ifRange == null || ifRange == etag)
        val from = if (partial) range?.removePrefix("bytes=")?.removeSuffix("-")?.toIntOrNull() ?: 0 else 0
        val out = client.getOutputStream()
        val status = if (partial) "206 Partial Content\r\nContent-Range: bytes $from-${body.size - 1}/${body.size}" else "200 OK"
        out.write("HTTP/1.1 $status\r\nETag: $etag\r\nContent-Length: ${body.size - from}\r\nConnection: close\r\n\r\n".toByteArray())
        out.write(body, from, if (cuts.getAndUpdate { maxOf(it - 1, 0) } > 0) minOf(cutAfter, body.size - from) else body.size - from)
        out.flush()
    }

    private fun files() = PinnedFiles(dir, base)

    private class Watch(val stopAt: Long = Long.MAX_VALUE) : PinnedFiles.Progress {
        @Volatile
        var seen = 0L
        override fun current(bytes: Long) {
            seen = bytes
        }
        override fun done(part: PinnedFiles.Part) {}
        override fun cancelled() = seen >= stopAt
    }

    private val partial get() = File(dir, "model.bin.part")

    @Test
    fun unpackWriteFailureKeepsVerifiedArchiveAndOriginalCause() {
        val raw = "native runtime".toByteArray()
        val compressed = java.io.ByteArrayOutputStream()
        java.util.zip.GZIPOutputStream(compressed).use { it.write(raw) }
        body = compressed.toByteArray()
        val packed = PinnedFiles.Part("runtime.so", digest(raw), raw.size.toLong(),
            packed = PinnedFiles.Packed(digest(body), body.size.toLong()))
        File(dir, "runtime.so.part").mkdirs() // deterministic output failure, without filling a real disk
        File(dir, "runtime.so").writeText("old")
        try {
            files().download(listOf(packed), Watch())
            fail("unpack must fail")
        } catch (error: IOException) {
            assertFalse("output failure must not become a checksum error", error is PinnedFiles.ChecksumError)
        }
        assertTrue(File(dir, "runtime.so.gz").isFile)
        assertEquals("old", File(dir, "runtime.so").readText())
    }

    @Test
    fun enospcDuringUnpackIsActionableAndRetainsWire() {
        val raw = "native runtime".toByteArray()
        val compressed = java.io.ByteArrayOutputStream()
        java.util.zip.GZIPOutputStream(compressed).use { it.write(raw) }
        body = compressed.toByteArray()
        val packed = PinnedFiles.Part("runtime.so", digest(raw), raw.size.toLong(),
            packed = PinnedFiles.Packed(digest(body), body.size.toLong()))
        val files = PinnedFiles(dir, base, output = { throw IOException("ENOSPC: No space left on device") })
        try {
            files.download(listOf(packed), Watch())
            fail("unpack must fail")
        } catch (error: IOException) {
            assertFalse(error is PinnedFiles.ChecksumError)
            assertTrue(PinnedFiles.failure("gói", error).message.contains("Bạn giải phóng"))
        }
        assertTrue(File(dir, "runtime.so.gz").isFile)
        assertFalse(File(dir, "runtime.so").exists())
        val requests = ranges.size
        PinnedFiles(dir, base).download(listOf(packed), Watch())
        assertEquals(requests, ranges.size) // retry unpacks the already verified archive
        assertEquals(raw.toList(), File(dir, "runtime.so").readBytes().toList())
    }

    @Test
    fun spaceCheckIncludesUnpackedSizeBeforeAnyNetwork() {
        val part = PinnedFiles.Part("runtime.so", "unused", 100_000,
            packed = PinnedFiles.Packed("unused", 10))
        try {
            PinnedFiles(dir, base, freeBytes = { DownloadSpace.MARGIN + 100 }).download(listOf(part), Watch())
            fail("unpacked staging needs space too")
        } catch (_: PinnedFiles.SpaceError) { }
        assertTrue(ranges.isEmpty())
    }

    @Test
    fun aConnectionCutHalfWayKeepsThePartAndTheRetryResumesWithRange() {
        // the first answer stops after 100 000 bytes; the retry (Range) gets the rest
        cutAfter = 100_000
        cuts.set(1)
        files().download(listOf(part), Watch())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
        assertFalse(partial.exists())
        assertEquals(listOf(null, "bytes=100000-"), ranges.toList())
    }

    /** A download stopped by Huỷ after about 100 000 bytes: the `.part` and its version note stay. */
    private fun stopHalfWay(): Long {
        try {
            files().download(listOf(part), Watch(stopAt = 100_000))
            fail("the cancel must stop the download")
        } catch (_: PinnedFiles.Cancelled) {
        }
        assertTrue(partial.exists() && PartResume.tagFile(partial).exists())
        return partial.length()
    }

    @Test
    fun aFileRebuiltOnTheServerBetweenTwoTriesIsFetchedWholeNotStitched() {
        val kept = stopHalfWay()
        etag = "\"v2\"" // the server rebuilt the file: it answers If-Range with the whole new file
        ranges.clear()
        files().download(listOf(part), Watch())
        assertEquals(listOf("bytes=$kept-"), ranges.toList())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
        assertFalse(partial.exists() || PartResume.tagFile(partial).exists())
    }

    @Test
    fun aPartTheServerCannotContinue416IsDroppedAndTheWholeFileAskedAgain() {
        val kept = stopHalfWay()
        refuseRange = true
        ranges.clear()
        files().download(listOf(part), Watch())
        assertEquals("Range first, the 416 drops the part, then the whole file", listOf("bytes=$kept-", null), ranges.toList())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
        assertFalse(partial.exists() || PartResume.tagFile(partial).exists())
    }

    @Test
    fun aTailOfAnotherVersionIsDroppedAndTheWholeFileAskedAgain() {
        val kept = stopHalfWay()
        etag = "\"v2\""
        ignoreIfRange = true
        ranges.clear()
        files().download(listOf(part), Watch())
        assertEquals("Range first, the foreign 206 dropped, then the whole file", listOf("bytes=$kept-", null), ranges.toList())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
        assertFalse(partial.exists() || PartResume.tagFile(partial).exists())
    }

    @Test
    fun aPartWithNoRecordedVersionIsNeverResumed() {
        dir.mkdirs()
        partial.writeBytes(ByteArray(1000) { 9 }) // some older download: nobody knows which version it came from
        files().download(listOf(part), Watch())
        assertEquals(listOf<String?>(null), ranges.toList())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
    }

    @Test
    fun aServerThatKeepsCuttingIsANetworkErrorWithThePartKeptNotAFailedHash() {
        cutAfter = 50_000
        cuts.set(Int.MAX_VALUE)
        try {
            files().download(listOf(part), Watch())
            fail("a short body is not a finished download")
        } catch (failure: IOException) {
            assertFalse("not the pinned file", failure is PinnedFiles.ChecksumError)
        }
        assertEquals("the bytes got so far stay for the next tap", 150_000L, partial.length())
        assertFalse(File(dir, "model.bin").exists())
        assertEquals(listOf(null, "bytes=50000-", "bytes=100000-"), ranges.toList())
        // the network is back: the next download asks only for what is missing
        cuts.set(0)
        ranges.clear()
        files().download(listOf(part), Watch())
        assertEquals(listOf("bytes=150000-"), ranges.toList())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
    }

    @Test
    fun aCancelStopsAtTheNextReadKeepsThePartAndTheNextDownloadResumesFromThere() {
        val watch = Watch(stopAt = 100_000)
        try {
            files().download(listOf(part), watch)
            fail("the cancel must stop the download")
        } catch (_: PinnedFiles.Cancelled) {
        }
        val kept = partial.length()
        assertTrue("stopped well before the end: $kept", kept in 100_000 until body.size)
        assertFalse(File(dir, "model.bin").exists())
        assertEquals("a cancel is not retried", 1, ranges.size)
        // "tải lại": resumes from the kept bytes
        ranges.clear()
        files().download(listOf(part), Watch())
        assertEquals(listOf("bytes=$kept-"), ranges.toList())
        assertEquals(body.toList(), File(dir, "model.bin").readBytes().toList())
        assertFalse(partial.exists())
        assertEquals("the stamp says it is current", true, files().isCurrent(part))
    }

    @Test
    fun aCancelBeforeTheFirstFileAsksTheServerForNothing() {
        try {
            files().download(listOf(part), Watch(stopAt = 0))
            fail("already cancelled")
        } catch (_: PinnedFiles.Cancelled) {
        }
        assertTrue(ranges.isEmpty())
        assertFalse(partial.exists())
    }
}
