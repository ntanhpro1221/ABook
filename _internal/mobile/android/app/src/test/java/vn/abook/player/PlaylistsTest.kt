package vn.abook.player

import java.io.File
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Danh sách phát cho "Nghe ngay" trên điện thoại (Playlists, MusicCatalog, đường `/api/music/playlists` của LocalStudio) - cùng luật
 * với tests/test_music_playlist.py: chỉ nhận danh sách đúng hình dạng, giữ thứ tự trộn sẵn, mỗi bài một độ khuếch đại theo công
 * thức Pha 4, và các bài nối nhau trên đồng hồ nhạc của cuốn (qua mọi chương, hết danh sách thì quay lại đầu).
 */
class PlaylistsTest {
    private lateinit var root: File
    private val calm = listOf("https://x/calm2.mp3", "https://x/calm.mp3", "https://x/sad.mp3")
    private val tracks = mapOf(
        "https://x/calm.mp3" to JSONObject().put("duration", 180).put("title", "Calm").put("lufs", -14.0).put("speechBand", 0.5),
        "https://x/calm2.mp3" to JSONObject().put("duration", 200),
        "https://x/sad.mp3" to JSONObject().put("duration", 240),
    )

    /** Luật chọn của mục lục thử: mặc định "calm", không từ khoá nào - cuốn thử nào cũng được chọn "calm". */
    private val picker = JSONObject("""{"version":1,"cap":5,"title_weight":12.0,"min_score":4.0,"default":"calm","order":["calm","battle"],
        "playlists":{"calm":{"title":[],"text":{}},"battle":{"title":[],"text":{"trận chiến":1}}}}""")

    private fun manifest(withPicker: Boolean = false): JSONObject = JSONObject().put("format", "abook-music-catalog").put("version", 1).put("revision", "r1")
        .put("shards", JSONArray(tracks.keys.map { MusicCatalog.shardOf(it) }.distinct()))
        .apply { if (withPicker) put("playlistPicker", picker) }
        .put("playlists", JSONArray()
            .put(JSONObject().put("id", "off").put("name", "tắt không phải mã danh sách").put("tracks", JSONArray(calm)))
            .put(JSONObject().put("id", "calm").put("name", "Êm  đềm").put("description", "Cho truyện chậm.").put("minutes", 10).put("tracks", JSONArray(calm)))
            .put(JSONObject().put("id", "battle").put("name", "Hành động").put("description", "").put("minutes", 3).put("tracks", JSONArray(listOf("https://x/battle.mp3"))))
            .put(JSONObject().put("id", "Bad Id").put("name", "x").put("tracks", JSONArray(calm)))
            .put(JSONObject().put("id", "calm").put("name", "trùng mã").put("tracks", JSONArray(calm)))
            .put(JSONObject().put("id", "mine").put("name", "trùng lựa chọn Nhạc của tôi").put("tracks", JSONArray(calm)))
            .put(JSONObject().put("id", "empty").put("name", "không bài").put("tracks", JSONArray(listOf("http://x/insecure.mp3", 7))))
            .put("không phải đối tượng"))

    /** Danh mục giả trên đĩa: mục lục + mảnh dữ liệu + một file bài (đúng hình như trên mây). */
    private fun cloud(withPicker: Boolean = false): File {
        val cloud = File(root, "cloud").apply { mkdirs() }
        for ((shard, links) in tracks.keys.groupBy { MusicCatalog.shardOf(it) }) {
            val data = JSONObject()
            for (link in links) data.put(link, tracks.getValue(link))
            File(cloud, "tracks").mkdirs()
            File(cloud, "tracks/$shard.json").writeText(data.toString())
        }
        CatalogSigning.writeManifest(cloud, manifest(withPicker)) // mục lục ký bằng khoá TEST, `files` = sha256 các mảnh vừa ghi
        return cloud
    }

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-playlists")
    }

    @After
    fun tearDown() {
        LocalStudio.catalog = null
        LocalStudio.musicStore = null
        LocalStudio.bundledPicker = null
    }

    @Test
    fun only_well_formed_playlists_of_the_catalogue_are_offered() {
        val kept = Playlists.catalogue(manifest())
        assertEquals(listOf("calm", "battle"), kept.map { it.getString("id") })
        assertEquals("Êm đềm", kept[0].getString("name"))
        assertEquals(calm, Playlists.linksOf(kept, "calm"))
        assertEquals(emptyList<String>(), Playlists.linksOf(kept, "gone"))
        val summary = Playlists.summaries(kept).getJSONObject(1)
        assertTrue(StrictJson.equal(JSONObject("""{"id":"battle","name":"Hành động","description":"","minutes":3,"count":1}"""), summary))
        assertEquals(0, Playlists.catalogue(JSONObject()).size)
    }

    @Test
    fun the_queue_keeps_the_shuffled_order_with_the_phase_4_gain_and_skips_what_cannot_play() {
        val queue = Playlists.queue(calm, tracks, -20.0) { it != "https://x/calm2.mp3" }
        assertEquals(listOf("https://x/calm.mp3", "https://x/sad.mp3"), queue.map { it.link })
        assertEquals(180.0, queue[0].duration!!, 0.0)
        assertEquals(MusicGain.cueGainDb(-20.0, -14.0, 0.5), queue[0].gainDb, 0.0)
        assertEquals(MusicGain.cueGainDb(-20.0, null, null), queue[1].gainDb, 0.0)
        assertNull(Playlists.queue(listOf("https://x/khong-biet.mp3"), emptyMap(), -20.0).single().duration)
    }

    @Test
    fun the_tracks_follow_each_other_on_the_books_music_clock_and_wrap_around() {
        val spans = Playlists.timeline(Playlists.queue(calm, tracks, -20.0) + Playlists.Track("https://x/x.mp3", null, -10.0))
        // mỗi bài: độ dài - 2 giây chuyển mờ; bài không biết độ dài: 180 giây mặc định
        assertEquals(listOf(0.0, 198.0, 376.0, 614.0), spans.map { it.start })
        assertEquals(792.0, spans.last().end, 0.0)
        val (second, offset) = Playlists.at(spans, 200.0)!!
        assertEquals("https://x/calm.mp3" to 2.0, second.track.link to offset)
        // Đồng hồ không theo chương: chỗ đang tới chỉ là số giây đã nghe của cả cuốn; hết danh sách thì quay lại bài đầu.
        val (wrapped, into) = Playlists.at(spans, 792.0 + 10.0)!!
        assertEquals(0 to 10.0, wrapped.index to into)
        assertNull(Playlists.at(emptyList(), 5.0))
    }

    @Test
    fun the_catalogue_reads_playlists_and_track_data_and_keeps_working_from_its_cache() {
        val source = cloud()
        val catalog = MusicCatalog(File(root, "cache"), source.path, publicKey = CatalogSigning.publicKey)
        assertEquals(listOf("calm", "battle"), catalog.playlists().map { it.getString("id") })
        val found = catalog.lookup(calm + "https://khong/co.mp3")
        assertEquals(calm.toSet(), found.keys)
        assertEquals("Calm", found.getValue("https://x/calm.mp3").getString("title"))
        source.deleteRecursively() // mất mạng: mục lục và mảnh đã cất vẫn dùng được
        val offline = MusicCatalog(File(root, "cache"), source.path, publicKey = CatalogSigning.publicKey)
        assertEquals(calm.toSet(), offline.lookup(calm).keys)
        val fresh = MusicCatalog(File(root, "khong_co_cache"), source.path)
        val message = runCatching { fresh.playlists() }.exceptionOrNull()?.message
        assertEquals("Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.", message)
    }

    @Test
    fun a_track_is_downloaded_once_and_a_mirror_is_used_only_when_it_matches_the_original() {
        val bytes = "ID3 bài thật".toByteArray()
        val sha = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }
        val served = mutableMapOf("https://mirror/good.mp3" to bytes, "https://mirror/bad.mp3" to "khác".toByteArray())
        val asked = mutableListOf<String>()
        val catalog = MusicCatalog(File(root, "cache"), "https://catalog/", open = { url ->
            asked += url
            served[url]?.inputStream() ?: throw java.io.IOException("404")
        })
        val link = "https://x/gone.mp3"
        val bad = JSONObject().put("sha1", sha).put("bytes", bytes.size).put("mirrors", JSONArray(listOf("https://mirror/bad.mp3")))
        assertNull(catalog.download(link, bad))
        assertNull("bản sao không kèm sha1 của bản gốc thì không dùng", catalog.download(link, JSONObject().put("mirrors", JSONArray(listOf("https://mirror/good.mp3")))))
        val good = JSONObject().put("sha1", sha).put("bytes", bytes.size).put("mirrors", JSONArray(listOf("https://mirror/bad.mp3", "https://mirror/good.mp3")))
        val file = catalog.download(link, good)!!
        assertTrue(file.readBytes().contentEquals(bytes))
        assertEquals(file, catalog.cached(link))
        asked.clear()
        assertEquals(file, catalog.download(link, good))
        assertEquals("đã có thì không tải lại", emptyList<String>(), asked)
        assertNull("chỉ link https", catalog.download("http://x/y.mp3", null))
    }

    /** Bài lớn hơn 40 MB (MUSIC_TRACK_MAX_MB của máy tính): máy này không dùng - không tải, không vào hàng phát, nhớ qua lần mở sau. */
    @Test
    fun a_track_over_the_size_cap_is_never_downloaded_and_leaves_the_queue() {
        val over = MusicCatalog.TRACK_MAX_BYTES + 1
        val asked = mutableListOf<String>()
        val lengths = mutableMapOf<String, Long?>("https://x/long.mp3" to over, "https://x/unsized.mp3" to null)
        val open = { url: String ->
            asked += url
            if (url == "https://x/unsized.mp3") {
                object : java.io.InputStream() { // nguồn không báo Content-Length: đếm khi tải
                    var left = over
                    override fun read(): Int = if (left-- > 0) 0 else -1
                    override fun read(b: ByteArray, off: Int, len: Int): Int {
                        if (left <= 0) return -1
                        val n = minOf(len.toLong(), left).toInt()
                        left -= n
                        return n
                    }
                }
            } else {
                MusicCatalog.Sized("ID3".toByteArray().inputStream(), lengths[url])
            }
        }
        val catalog = MusicCatalog(File(root, "cache"), "https://catalog/", open = open)
        val big = JSONObject().put("bytes", over)
        assertFalse("danh mục ghi cỡ quá trần", catalog.usable("https://x/big.mp3", big))
        assertTrue(runCatching { catalog.download("https://x/big.mp3", big) }.exceptionOrNull() is MusicCatalog.TrackTooBig)
        assertEquals("không tải byte nào", emptyList<String>(), asked)
        for (link in listOf("https://x/long.mp3", "https://x/unsized.mp3")) {
            assertTrue("chưa biết cỡ: cứ coi là dùng được", catalog.usable(link, null))
            assertTrue(link, runCatching { catalog.download(link, null) }.exceptionOrNull() is MusicCatalog.TrackTooBig)
            assertNull(catalog.cached(link))
            assertFalse(link, catalog.usable(link, null))
        }
        assertEquals("không để file dở", emptyList<String>(), File(root, "cache/files").list()?.toList() ?: emptyList<String>())
        val reopened = MusicCatalog(File(root, "cache"), "https://catalog/", open = open)
        assertFalse("nhớ qua lần mở sau", reopened.usable("https://x/long.mp3", null))
        val links = listOf("https://x/small.mp3", "https://x/big.mp3", "https://x/long.mp3")
        val infos = mapOf("https://x/big.mp3" to big)
        assertEquals(listOf("https://x/small.mp3"), Playlists.queue(links, infos, -20.0) { reopened.usable(it, infos[it]) }.map { it.link })
    }

    @Test
    fun the_phone_menu_lists_the_playlists_and_counts_my_music() {
        LocalStudio.catalog = MusicCatalog(File(root, "cache"), cloud().path, publicKey = CatalogSigning.publicKey)
        LocalStudio.musicStore = MusicStore(File(root, "music"), FakeTags)
        LocalStudio.musicStore!!.importFile(BookEditsFixtures.file("track/tone.wav"))
        val (status, body) = LocalStudio.handle("GET", "/api/music/playlists", null)
        assertEquals(200, status)
        body as JSONObject
        assertEquals(listOf("calm", "battle"), (0 until body.getJSONArray("playlists").length()).map { body.getJSONArray("playlists").getJSONObject(it).getString("id") })
        assertEquals(1, body.getInt("mine"))
        assertEquals("", body.getString("error"))
        LocalStudio.catalog = MusicCatalog(File(root, "trong"), File(root, "khong_co").path)
        val (_, offline) = LocalStudio.handle("GET", "/api/music/playlists", null)
        offline as JSONObject
        assertEquals(0, offline.getJSONArray("playlists").length())
        assertEquals("Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.", offline.getString("error"))
    }

    @Test
    fun the_choice_is_saved_in_the_listeners_edits_and_travels_with_them() {
        BookEditsFixtures.useStoreRoot(root)
        val id = "f-0123456789abcdef01234567"
        BookEditsFixtures.copyBase(Store.bookDir(id))
        Store.rememberChapters(id, JSONObject(), imported = true)
        val (status, view) = LocalStudio.handle("PUT", "/api/books/$id/music", JSONObject().put("playlist", "calm"))
        assertEquals(200, status)
        assertEquals("calm", (view as JSONObject).getString("playlist"))
        val edits = BookEdits.load(Store.bookDir(id))
        assertEquals("""{"playlist":"calm"}""", edits.getJSONObject("music").toString())
        assertEquals(1, BookEdits.countApplied(edits))
        val merged = BookEdits.merge(edits, BookEdits.validate(JSONObject().put("format", "abook-edits").put("version", 1)
            .put("music", JSONObject().put("playlist", "mine")))).first
        assertEquals("calm", merged.getJSONObject("music").getString("playlist"))
        LocalStudio.handle("PUT", "/api/books/$id/music", JSONObject().put("playlist", JSONObject.NULL))
        assertTrue(!BookEdits.load(Store.bookDir(id)).has("music"))
    }

    /** Sách chỉ có chữ đã nhập trên máy (một chương chữ, không audio). */
    private fun textBook(id: String): File {
        val dir = Store.bookDir(id).apply { mkdirs() }
        File(dir, "texts").mkdirs()
        File(dir, "texts/1.txt").writeText("Một câu tự đặt, chẳng có từ khoá nào cả. ".repeat(60))
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Sách thử").put("package", JSONObject())
            .put("chapters", JSONArray().put(JSONObject().put("id", 1).put("state", "text").put("text", "texts/1.txt"))).toString())
        Store.rememberChapters(id, JSONObject(), imported = true)
        return dir
    }

    private fun musicView(id: String): JSONObject = LocalStudio.handle("GET", "/api/books/$id/music", null).second as JSONObject

    @Test
    fun a_text_book_with_no_choice_shows_the_machines_pick_until_the_listener_chooses_or_turns_it_off() {
        BookEditsFixtures.useStoreRoot(root)
        val id = "f-0123456789abcdef01234567"
        textBook(id)
        LocalStudio.catalog = MusicCatalog(File(root, "cache"), cloud(withPicker = true).path, publicKey = CatalogSigning.publicKey)
        val auto = musicView(id)
        assertEquals("calm", auto.getString("playlist"))
        assertTrue(auto.getBoolean("playlistAuto"))
        // "Tắt" là một lựa chọn: lưu "off", không phải mã danh sách, và không còn máy chọn
        val (_, off) = LocalStudio.handle("PUT", "/api/books/$id/music", JSONObject().put("playlist", "off"))
        off as JSONObject
        assertEquals("off", off.getString("playlist"))
        assertTrue(!off.has("playlistAuto"))
        assertEquals("""{"playlist":"off"}""", BookEdits.load(Store.bookDir(id)).getJSONObject("music").toString())
        // null xoá khoá: máy chọn lại, và lời đáp của chính lần xoá đã là màn của máy chọn
        val (_, again) = LocalStudio.handle("PUT", "/api/books/$id/music", JSONObject().put("playlist", JSONObject.NULL))
        again as JSONObject
        assertTrue(again.getBoolean("playlistAuto"))
        assertTrue(!BookEdits.load(Store.bookDir(id)).has("music"))
        val (_, chosen) = LocalStudio.handle("PUT", "/api/books/$id/music", JSONObject().put("playlist", "battle"))
        assertTrue(!(chosen as JSONObject).has("playlistAuto"))
    }

    @Test
    fun without_a_downloaded_catalogue_the_machine_picks_with_the_bundled_rules() {
        BookEditsFixtures.useStoreRoot(root)
        val id = "f-0123456789abcdef01234567"
        textBook(id)
        LocalStudio.catalog = MusicCatalog(File(root, "trong"), File(root, "khong_co").path)
        LocalStudio.bundledPicker = null
        assertTrue(!musicView(id).has("playlist"))
        LocalStudio.bundledPicker = JSONObject(File("../../../abook/webui/assets/playlist_picker.json").readText(Charsets.UTF_8))
        val view = musicView(id)
        assertEquals("fantasy_adventure", view.getString("playlist"))
        assertTrue(view.getBoolean("playlistAuto"))
    }
}
