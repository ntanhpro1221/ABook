package vn.abook.player

import java.io.ByteArrayInputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Tải sách kèm nhạc nền (LibraryPlugin.downloadBook -> BookMusic): chỉ các bài mà một mốc dùng; cỡ và (khi biết) mã sha1 phải khớp
 * mới đổi tên khỏi `.part`; bài hỏng bị bỏ mà không để lại gì.
 */
class BookMusicTest {
    private lateinit var dir: File
    private val bytes = ByteArray(300) { (it * 7).toByte() }
    private val sha = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }
    private val catalog = "music/${"c".repeat(40)}.mp3"
    private val local get() = "music/$sha.wav"

    @Before
    fun setUp() {
        dir = BookEditsFixtures.tempDir("abook-book-music")
    }

    private fun music(vararg tracks: Pair<String, JSONObject>, cued: List<String> = tracks.map { it.first }): JSONObject {
        val listed = JSONObject()
        for ((name, info) in tracks) listed.put(name, info)
        val cues = JSONArray()
        cued.forEachIndexed { index, name -> cues.put(JSONObject().put("start", index * 60.0).put("end", index * 60.0 + 60).put("track", name)) }
        return JSONObject().put("levelDb", -20.0).put("tracks", listed).put("chapters", JSONObject().put("1", cues))
    }

    private fun source(data: ByteArray = bytes, length: Long = data.size.toLong(), closed: MutableList<Boolean>? = null) =
        BookMusic.Source(ByteArrayInputStream(data), length) { closed?.add(true) }

    private fun parts() = File(dir, "music").listFiles { f -> f.name.endsWith(".part") }.orEmpty().toList()

    @Test
    fun only_tracks_a_cue_uses_are_wanted_with_their_size_and_the_hash_the_name_proves() {
        val unused = "music/${"d".repeat(40)}.mp3"
        val info = music(catalog to JSONObject().put("link", "https://x/a.mp3").put("size", 300),
            local to JSONObject().put("link", "local:$sha"), unused to JSONObject(), cued = listOf(catalog, local, catalog))
            .also { it.getJSONObject("tracks").put("../evil.mp3", JSONObject()).put("music/x.mp3", JSONObject()) }
        info.getJSONObject("chapters").getJSONArray("1").put(JSONObject().put("start", 200.0).put("end", 260.0).put("track", "music/x.mp3"))
        info.getJSONObject("chapters").getJSONArray("1").put(JSONObject().put("start", 300.0).put("end", 360.0).put("track", "music/${"e".repeat(40)}.mp3"))
        val wanted = BookMusic.tracks(info)
        assertEquals(listOf(catalog, local), wanted.map { it.name })
        assertEquals(300L, wanted[0].size)
        assertNull("bài danh mục: tên là băm của link, không nói gì về nội dung", wanted[0].sha1)
        assertEquals(0L, wanted[1].size)
        assertEquals(sha, wanted[1].sha1)
        assertTrue(BookMusic.tracks(null).isEmpty())
        assertTrue(BookMusic.tracks(JSONObject().put("tracks", JSONObject())).isEmpty())
    }

    @Test
    fun a_good_download_lands_under_its_real_name_with_nothing_left_behind() {
        val track = BookMusic.Track(catalog, 300, null)
        val closed = mutableListOf<Boolean>()
        assertTrue(BookMusic.fetch(dir, track) { source(closed = closed) })
        assertArrayEquals(bytes, File(dir, catalog).readBytes())
        assertTrue(parts().isEmpty())
        assertEquals(1, closed.size)
    }

    @Test
    fun a_track_already_there_and_right_is_not_downloaded_again() {
        File(dir, catalog).apply { parentFile.mkdirs() }.writeBytes(bytes)
        assertTrue(BookMusic.fetch(dir, BookMusic.Track(catalog, 300, null)) { throw AssertionError("không được tải lại") })
    }

    @Test
    fun a_wrong_sized_or_cut_short_download_is_dropped() {
        assertFalse(BookMusic.fetch(dir, BookMusic.Track(catalog, 301, null)) { source() })
        assertFalse("máy kia báo 400 byte nhưng chỉ đến 300", BookMusic.fetch(dir, BookMusic.Track(catalog, 0, null)) { source(length = 400) })
        assertFalse("rỗng", BookMusic.fetch(dir, BookMusic.Track(catalog, 0, null)) { source(ByteArray(0)) })
        assertFalse(File(dir, catalog).exists())
        assertTrue(parts().isEmpty())
    }

    @Test
    fun a_pinned_track_must_hash_to_its_name() {
        val wrong = ByteArray(300) { 9 }
        assertFalse(BookMusic.fetch(dir, BookMusic.Track(local, 300, sha)) { source(wrong) })
        assertFalse(File(dir, local).exists())
        assertTrue(parts().isEmpty())
        assertTrue(BookMusic.fetch(dir, BookMusic.Track(local, 300, sha)) { source() })
        assertArrayEquals(bytes, File(dir, local).readBytes())
    }

    @Test
    fun a_bad_copy_already_in_the_folder_is_replaced_by_a_good_download() {
        File(dir, local).apply { parentFile.mkdirs() }.writeBytes(ByteArray(10))
        assertTrue(BookMusic.fetch(dir, BookMusic.Track(local, 300, sha)) { source() })
        assertArrayEquals(bytes, File(dir, local).readBytes())
    }

    @Test
    fun the_other_device_refusing_or_dropping_the_connection_skips_the_track_without_throwing() {
        assertFalse(BookMusic.fetch(dir, BookMusic.Track(catalog, 300, null)) { null })
        val broken = object : InputStream() {
            override fun read(): Int = throw IOException("đứt mạng")
        }
        assertFalse(BookMusic.fetch(dir, BookMusic.Track(catalog, 300, null)) { BookMusic.Source(broken, 300) })
        assertFalse(BookMusic.fetch(dir, BookMusic.Track(catalog, 300, null)) { throw IOException("không kết nối được") })
        assertFalse(File(dir, catalog).exists())
        assertTrue(parts().isEmpty())
    }
}
