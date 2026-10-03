package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Điện thoại phục vụ NHẠC NỀN của sách cho máy đã ghép, như máy tính (sync.manifest / SyncApp.resolve_file): mục `music` của gói
 * kèm đúng các file bài mà một mốc đang dùng - bài trong file sách và bài người nghe ghim - và không file nào khác.
 */
class LibraryServerMusicTest {
    private lateinit var root: File
    private val id = "0123456789abcdef01234567"
    private val token = "tok-ghep-noi"
    private val dir get() = Store.bookDir(id)
    private val calm = "music/c4c39b8782f721b05358033359f25876e70597f8.mp3"
    private val battle = "music/bf36d3af630dc0c7d83324b545ade933affdfd90.mp3"
    private val tone get() = BookEditsFixtures.file("track/tone.wav")
    private val toneSha get() = MessageDigest.getInstance("SHA-1").digest(tone.readBytes()).joinToString("") { "%02x".format(it) }

    private class Reply(val status: Int, val headers: Map<String, String>, val body: ByteArray) {
        fun json() = JSONObject(String(body, Charsets.UTF_8))
    }

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-share-music")
        BookEditsFixtures.useStoreRoot(root)
        BookEditsFixtures.copyBase(dir) // sách nhập từ file: có book.json mang `music`, hai bài của người làm sách trong music/
        // Thiết bị đã ghép: share.json lưu băm SHA-256 của mã (LibraryServer.hash), không lưu mã thật.
        val devices = File(root, "share.json")
        val hash = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }
        devices.writeText(JSONObject().put("devices", JSONObject().put(hash, JSONObject().put("name", "Máy thử").put("lastSeen", 1e12))).toString())
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, devices)
        LocalStudio.musicStore = MusicStore(File(root, "music"), FakeTags)
        LocalStudio.now = { 1_790_950_256.0 }
    }

    @After
    fun tearDown() {
        LocalStudio.musicStore = null
        LocalStudio.now = { System.currentTimeMillis() / 1000.0 }
    }

    private fun get(path: String, range: String? = null, authorized: Boolean = true): Reply {
        val headers = buildMap {
            if (authorized) put("authorization", "Bearer $token")
            if (range != null) put("range", range)
        }
        val out = ByteArrayOutputStream()
        LibraryServer.route(LibraryServer.Request("GET", path, headers, ByteArray(0)), out)
        val raw = out.toByteArray()
        val split = String(raw, Charsets.ISO_8859_1).indexOf("\r\n\r\n")
        val lines = String(raw, 0, split, Charsets.ISO_8859_1).split("\r\n")
        val headerMap = lines.drop(1).associate { line -> line.substringBefore(':').lowercase() to line.substringAfter(':').trim() }
        return Reply(lines[0].split(" ")[1].toInt(), headerMap, raw.copyOfRange(split + 4, raw.size))
    }

    private fun manifest() = get("/sync/v1/books/$id/manifest").also { assertEquals(200, it.status) }.json()

    private fun file(name: String, range: String? = null) = get("/sync/v1/books/$id/files/$name", range)

    private fun edit(body: JSONObject) = assertEquals(200, LocalStudio.handle("PUT", "/api/books/$id/music", body).first)

    private fun cuedTracks(manifest: JSONObject): List<String> {
        val chapters = manifest.getJSONObject("music").getJSONObject("chapters")
        return chapters.keys().asSequence().flatMap { key ->
            val cues = chapters.getJSONArray(key)
            (0 until cues.length()).map { cues.getJSONObject(it).getString("track") }
        }.toList()
    }

    @Test
    fun the_manifest_carries_the_cues_and_every_cued_file_is_served_byte_for_byte() {
        val shown = manifest()
        val music = shown.getJSONObject("music")
        assertEquals(-18.0, music.getDouble("levelDb"), 0.0)
        assertEquals(listOf(calm, battle), cuedTracks(shown))
        assertEquals(setOf(calm, battle), music.getJSONObject("tracks").keys().asSequence().toSet())
        // Cỡ file thật đi kèm từng bài để máy kia kiểm lúc tải (BookMusic.problem).
        for (name in listOf(calm, battle)) {
            assertEquals(BookEditsFixtures.bytes("base/$name").size.toLong(), music.getJSONObject("tracks").getJSONObject(name).getLong("size"))
        }
        val cue = music.getJSONObject("chapters").getJSONArray("1").getJSONObject(0)
        assertEquals(-7.39, cue.getDouble("gainDb"), 0.0)
        for (name in listOf(calm, battle)) {
            val reply = file(name)
            assertEquals(200, reply.status)
            assertEquals("audio/mpeg", reply.headers["content-type"])
            assertArrayEquals(BookEditsFixtures.bytes("base/$name"), reply.body)
        }
    }

    @Test
    fun a_track_can_be_played_while_seeking_with_a_range() {
        val whole = BookEditsFixtures.bytes("base/$calm")
        val reply = file(calm, "bytes=10-49")
        assertEquals(206, reply.status)
        assertEquals("bytes 10-49/${whole.size}", reply.headers["content-range"])
        assertArrayEquals(whole.copyOfRange(10, 50), reply.body)
    }

    @Test
    fun a_track_no_cue_uses_is_refused_even_when_it_sits_in_the_book_folder() {
        val stray = "music/${"a".repeat(40)}.mp3"
        File(dir, stray).writeText("khong ai dung")
        assertEquals(404, file(stray).status)
        // Nằm trong kho "Nhạc của tôi" nhưng chưa ghim vào đâu: không có trong sách, không ai lấy được.
        LocalStudio.musicStore!!.importFile(tone)
        assertEquals(404, file("music/$toneSha.wav").status)
        assertFalse(manifest().getJSONObject("music").getJSONObject("tracks").has("music/$toneSha.wav"))
        // Tên ngoài khuôn music/<sha1>.<đuôi> hay đi ra ngoài thư mục: từ chối.
        for (name in listOf("music/..%2Fbook.json", "music/%2e%2e/book.json", "music/x.mp3", "music/", "music/$toneSha.exe")) {
            assertEquals(name, 404, file(name).status)
        }
    }

    @Test
    fun an_unpaired_device_gets_neither_the_cues_nor_the_files() {
        assertEquals(401, get("/sync/v1/books/$id/manifest", authorized = false).status)
        assertEquals(401, get("/sync/v1/books/$id/files/$calm", authorized = false).status)
    }

    @Test
    fun a_track_the_listener_pinned_is_served_and_the_one_it_replaced_is_not() {
        LocalStudio.musicStore!!.importFile(tone)
        edit(JSONObject().put("pins", JSONObject().put("1:0", "local:$toneSha")))
        val pinned = "music/$toneSha.wav"
        val shown = manifest()
        assertEquals(listOf(pinned, battle), cuedTracks(shown))
        val info = shown.getJSONObject("music").getJSONObject("tracks").getJSONObject(pinned)
        assertEquals("local:$toneSha", info.getString("link"))
        val reply = file(pinned)
        assertEquals(200, reply.status)
        assertEquals("audio/wav", reply.headers["content-type"])
        assertArrayEquals(tone.readBytes(), reply.body)
        assertEquals(200, file(battle).status)
        assertEquals("bài đã bị thay: không mốc nào dùng nữa", 404, file(calm).status)
        assertFalse(shown.getJSONObject("music").getJSONObject("tracks").has(calm))
    }

    @Test
    fun a_cue_whose_file_is_missing_is_left_out_instead_of_promising_a_404() {
        assertTrue(File(dir, battle).delete())
        val shown = manifest()
        assertEquals(listOf(calm), cuedTracks(shown))
        assertEquals(404, file(battle).status)
        assertEquals(200, file(calm).status)
    }

    @Test
    fun silenced_cues_and_a_switched_off_music_track_are_not_shared() {
        edit(JSONObject().put("silence", JSONObject().put("1:60000", true)))
        val shown = manifest()
        assertEquals(listOf(calm), cuedTracks(shown))
        assertEquals(404, file(battle).status)
        edit(JSONObject().put("enabled", false))
        val off = manifest()
        assertFalse(off.has("music"))
        assertEquals(404, file(calm).status)
        assertNotNull(off.optJSONArray("chapters"))
    }

    @Test
    fun a_book_without_music_has_no_music_entry() {
        val bare = JSONObject(File(dir, "book.json").readText())
        bare.remove("music")
        File(dir, "book.json").writeText(bare.toString())
        assertFalse(manifest().has("music"))
        assertEquals(404, file(calm).status)
    }
}
