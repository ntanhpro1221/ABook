package vn.abook.player

import java.net.ServerSocket
import java.net.Socket
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Tải gói model của bộ phân tích nhạc (MusicStudentSetup): chỉ tải khi được bấm, ghim cỡ + SHA-256, `.part` rồi mới đổi tên, tải
 * tiếp bằng Range, hỏng thì nói rõ và cho thử lại; tải xong thì cắm bộ phân tích và phân tích nốt bài đã nhập. Máy chủ giả trên
 * localhost (HTTP) với gói nhỏ - cùng đường mã với HTTPS thật.
 */
class MusicStudentSetupTest {
    private lateinit var server: ServerSocket
    private lateinit var root: File
    private val requests = CopyOnWriteArrayList<String>()
    private val ranges = CopyOnWriteArrayList<String?>()
    private var broken = false
    private var missing = false
    private val big = ByteArray(300_000) { (it * 31 + it / 7).toByte() }
    private val small = """{"x": 1}""".toByteArray()
    private val tone = BookEditsFixtures.file("track/tone.wav")

    private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private val parts get() = listOf(
        MusicStudentSetup.Part("big.bin", digest(big), big.size.toLong()),
        MusicStudentSetup.Part("small.json", digest(small), small.size.toLong()),
    )

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-student").toFile()
        server = ServerSocket(0, 5, java.net.InetAddress.getByName("127.0.0.1"))
        Thread {
            while (!server.isClosed) {
                val client = try {
                    server.accept()
                } catch (_: Exception) {
                    break
                }
                Thread { client.use { serve(it) } }.start()
            }
        }.apply { isDaemon = true }.start()
    }

    /** Một lời đáp HTTP/1.1 tối thiểu: GET /<tên> kèm Range tuỳ chọn. */
    private fun serve(client: Socket) {
        val input = client.getInputStream().bufferedReader(Charsets.ISO_8859_1)
        val name = (input.readLine() ?: return).split(' ')[1].removePrefix("/")
        var range: String? = null
        while (true) {
            val line = input.readLine() ?: return
            if (line.isEmpty()) break
            if (line.startsWith("Range:", ignoreCase = true)) range = line.substringAfter(':').trim()
        }
        requests.add(name)
        ranges.add(range)
        val body = when (name) {
            "big.bin" -> if (broken) big.copyOf().also { it[10] = (it[10] + 1).toByte() } else big
            "small.json" -> small
            else -> null
        }
        val out = client.getOutputStream()
        if (body == null || missing) {
            out.write("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
        } else {
            val from = range?.removePrefix("bytes=")?.removeSuffix("-")?.toIntOrNull()
            val status = if (from != null) "206 Partial Content" else "200 OK"
            out.write("HTTP/1.1 $status\r\nContent-Length: ${body.size - (from ?: 0)}\r\nConnection: close\r\n\r\n".toByteArray())
            out.write(body, from ?: 0, body.size - (from ?: 0))
        }
        out.flush()
    }

    @After
    fun tearDown() {
        server.close()
    }

    private val base get() = "http://127.0.0.1:${server.localPort}/"

    private fun store() = MusicStore(File(root, "mine"), FakeTags) { 1_790_000_000.0 }

    private fun setup(store: MusicStore, open: (File) -> ((File) -> JSONObject?) = { { JSONObject().put("valence", 0.25).put("arousal", -0.5) } }) =
        MusicStudentSetup(File(root, "student"), store, open, base, parts)

    @Test
    fun nothing_is_downloaded_until_the_user_asks_and_the_status_says_how_big_it_is() {
        val store = store()
        val setup = setup(store)
        assertFalse(setup.attachIfPresent())
        val status = setup.status()
        assertEquals("missing", status.getString("state"))
        assertEquals((big.size + small.size).toLong(), status.getLong("total"))
        assertFalse(status.getBoolean("ready"))
        assertTrue("chưa bấm thì không gọi mạng", requests.isEmpty())
        assertNull(store.analyzer)
    }

    @Test
    fun a_tap_downloads_the_pinned_files_plugs_the_analyzer_in_and_analyses_what_was_waiting() {
        val store = store()
        val (before, _) = store.importFile(tone)
        assertFalse(before.getBoolean("analysed"))
        val setup = setup(store)
        setup.start()
        setup.join()
        val status = setup.status()
        assertEquals(status.toString(), "ready", status.getString("state"))
        assertEquals(status.getLong("total"), status.getLong("done"))
        assertEquals(big.toList(), File(root, "student/big.bin").readBytes().toList())
        assertFalse("không để .part lại", File(root, "student/big.bin.part").exists())
        assertNotNull(store.analyzer)
        assertTrue(store.entries().single().getBoolean("analysed"))
        assertTrue(setup.complete())
        // lần chạy sau: có đủ file thì cắm luôn, không gọi mạng
        val count = requests.size
        val again = store()
        assertTrue(setup(again).attachIfPresent())
        assertNotNull(again.analyzer)
        assertEquals(count, requests.size)
        // bài nhập SAU khi có bộ phân tích thì được phân tích ngay lúc nhập
        val (fresh, _) = again.importStream("khac.wav") { tone.readBytes().let { it.copyOf(it.size - 1) + byteArrayOf(0) }.inputStream() }
        assertTrue(fresh.getBoolean("analysed"))
    }

    @Test
    fun a_partial_download_resumes_with_a_range_request() {
        val dir = File(root, "student").apply { mkdirs() }
        File(dir, "big.bin.part").writeBytes(big.copyOf(100_000))
        val setup = setup(store())
        setup.start()
        setup.join()
        assertEquals(setup.status().toString(), "ready", setup.status().getString("state"))
        assertEquals("bytes=100000-", ranges[requests.indexOf("big.bin")])
        assertEquals(big.toList(), File(dir, "big.bin").readBytes().toList())
    }

    @Test
    fun a_download_that_does_not_match_its_hash_is_thrown_away_and_the_user_can_retry() {
        val store = store()
        val setup = setup(store)
        broken = true
        setup.start()
        setup.join()
        var status = setup.status()
        assertEquals("error", status.getString("state"))
        assertTrue(status.getString("error"), status.getString("error").contains("mã kiểm"))
        assertFalse(File(root, "student/big.bin").exists())
        assertFalse("bản hỏng không được giữ để tải tiếp", File(root, "student/big.bin.part").exists())
        assertNull("không cắm bộ phân tích từ bản hỏng", store.analyzer)
        broken = false
        setup.start() // "Thử lại"
        setup.join()
        status = setup.status()
        assertEquals(status.toString(), "ready", status.getString("state"))
        assertNotNull(store.analyzer)
    }

    @Test
    fun a_server_that_has_no_such_file_gives_a_readable_error_not_a_crash() {
        val setup = setup(store())
        missing = true
        setup.start()
        setup.join()
        val status = setup.status()
        assertEquals("error", status.getString("state"))
        assertTrue(status.getString("error"), status.getString("error").startsWith("Không tải được bộ phân tích nhạc"))
        assertTrue(status.getString("error").contains("404"))
        assertFalse(status.getBoolean("ready"))
    }

    @Test
    fun a_package_that_downloads_fine_but_cannot_be_opened_is_deleted_so_the_next_try_starts_clean() {
        val store = store()
        val setup = setup(store) { throw IllegalArgumentException("preprocessor_config hop_length=512") }
        setup.start()
        setup.join()
        val status = setup.status()
        assertEquals("error", status.getString("state"))
        assertTrue(status.getString("error").contains("hop_length"))
        assertFalse(File(root, "student/big.bin").exists())
        assertNull(store.analyzer)
    }

    @Test
    fun studio_starts_the_download_on_a_tap_and_the_view_shows_progress_without_a_student_key_when_there_is_none() {
        val store = store()
        LocalStudio.musicStore = store
        try {
            LocalStudio.student = null
            assertFalse("máy tính / test không có khoá student", (LocalStudio.handle("GET", "/api/music/local", null).second as JSONObject).has("student"))
            assertEquals(404, LocalStudio.handle("POST", "/api/music/local/student", null).first)
            val setup = setup(store)
            LocalStudio.student = setup
            val (status, view) = LocalStudio.handle("GET", "/api/music/local", null)
            assertEquals(200, status)
            assertEquals("missing", (view as JSONObject).getJSONObject("student").getString("state"))
            assertTrue(requests.isEmpty())
            val (started, answer) = LocalStudio.handle("POST", "/api/music/local/student", null)
            assertEquals(200, started)
            assertTrue((answer as JSONObject).has("student"))
            setup.join()
            val done = (LocalStudio.handle("GET", "/api/music/local", null).second as JSONObject)
            assertEquals("ready", done.getJSONObject("student").getString("state"))
            assertTrue(done.getBoolean("analyzer"))
        } finally {
            LocalStudio.student = null
            LocalStudio.musicStore = null
        }
    }

    @Test
    fun analysis_runs_outside_the_store_lock_so_the_list_stays_readable_and_a_removed_track_is_not_resurrected() {
        val store = store()
        val (track, _) = store.importFile(tone)
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        store.analyzer = {
            started.countDown()
            release.await(10, TimeUnit.SECONDS)
            JSONObject().put("valence", 0.1).put("arousal", 0.2)
        }
        val worker = Thread { store.analyzePending() }.apply { start() }
        assertTrue(started.await(10, TimeUnit.SECONDS))
        val reader = Thread { store.entries() }.apply { start() }
        reader.join(2_000)
        assertFalse("đang phân tích mà danh sách vẫn đọc được", reader.isAlive)
        assertTrue(store.remove(track.getString("link").removePrefix("local:")))
        release.countDown()
        worker.join(10_000)
        assertTrue(store.entries().isEmpty())
    }
}
