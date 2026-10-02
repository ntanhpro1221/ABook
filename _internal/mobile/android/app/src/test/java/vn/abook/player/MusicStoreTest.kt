package vn.abook.player

import java.io.ByteArrayInputStream
import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * "Nhạc của tôi" trên điện thoại (MusicStore) - cùng luật với `music_local.LocalMusic` của máy tính (tests/test_music_local.py):
 * chép theo sha1 nội dung, trùng nội dung thì một bản, đọc thẻ + độ dài, từ chối kèm lý do bằng tiếng Việt, sổ sống qua lần mở lại.
 */
class MusicStoreTest {
    private lateinit var root: File
    private val tone = BookEditsFixtures.file("track/tone.wav")
    private val toneSha = java.security.MessageDigest.getInstance("SHA-1").digest(tone.readBytes()).joinToString("") { "%02x".format(it) }
    private var now = 1_790_000_000.0

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-music").toFile()
    }

    private fun store(loudness: MusicStore.LoudnessMeter? = null) = MusicStore(root, FakeTags, loudness) { now++ }

    private fun refused(block: () -> Unit): String {
        try {
            block()
        } catch (error: MusicStore.ImportError) {
            return error.message.orEmpty()
        }
        fail("lẽ ra bị từ chối")
        return ""
    }

    @Test
    fun a_track_is_copied_by_its_content_hash_and_listed_like_a_catalogue_track() {
        val store = store { 1.0 }.also { assertTrue(it.entries().isEmpty()) }
        val (track, duplicate) = store.importFile(tone)
        assertFalse(duplicate)
        assertEquals("local:$toneSha", track.getString("link"))
        assertArrayEquals(tone.readBytes(), File(root, "files/$toneSha.wav").readBytes())
        assertEquals("không có thẻ thì tên bài là tên file", "tone", track.getString("title"))
        assertEquals("", track.getString("creator"))
        assertEquals(1, track.getInt("duration"))
        assertEquals("local", track.getString("source"))
        assertFalse("chưa có bộ phân tích: chưa phân tích, không bịa số", track.getBoolean("analysed"))
        assertFalse(track.has("valence"))
        assertEquals(1.0, track.getDouble("lufs"), 0.0)
        assertEquals("tone.wav", track.getString("name"))
        assertFalse("không có giấy phép / ghi công", track.has("license") || track.has("attribution"))
        assertEquals(tone.length(), track.getLong("bytes"))
    }

    @Test
    fun importing_the_same_content_twice_keeps_one_copy_whatever_the_name() {
        val store = store()
        store.importFile(tone)
        val renamed = File(root, "another name.wav").also { tone.copyTo(it) }
        val (track, duplicate) = store.importFile(renamed)
        assertTrue(duplicate)
        assertEquals(1, store.entries().size)
        assertEquals("tone.wav", track.getString("name"))
        assertEquals(1, File(root, "files").listFiles { file -> !file.name.startsWith(".") }!!.size)
        assertEquals("không còn file tạm", 0, File(root, "files").listFiles { file -> file.name.startsWith(".") }!!.size)
    }

    @Test
    fun a_file_that_cannot_be_a_track_is_refused_in_the_servers_words() {
        val store = store()
        val text = File(root, "ghi chu.txt").also { it.writeText("không phải nhạc") }
        assertEquals("“ghi chu.txt”: chưa nhập được định dạng này - dùng .mp3, .m4a, .ogg, .opus, .flac, .wav.", refused { store.importFile(text) })
        val fake = File(root, "gia.mp3").also { it.writeText("không phải nhạc") }
        assertEquals("“gia.mp3”: không đọc được như một bản nhạc.", refused { store.importFile(fake) })
        assertEquals("“mat.mp3”: không thấy file này.", refused { store.importFile(File(root, "mat.mp3")) })
        assertEquals("“khong-doc-duoc.mp3”: không đọc được file này.", refused { store.importStream("khong-doc-duoc.mp3") { null } })
        assertTrue(store.entries().isEmpty())
        assertFalse(File(root, "files/$toneSha.wav").exists())
        assertEquals("không còn file tạm sau khi từ chối", 0, File(root, "files").listFiles()!!.size)
    }

    @Test
    fun the_index_survives_reopening_and_a_removed_track_leaves_nothing_behind() {
        store().importFile(tone)
        val reopened = store()
        assertEquals(1, reopened.entries().size)
        assertNotNull(reopened.file("local:$toneSha"))
        assertEquals("local:$toneSha", reopened.lookup("local:$toneSha")!!.getString("link"))
        assertNull(reopened.lookup("local:" + "0".repeat(40)))
        assertNull(reopened.lookup("https://x/y.mp3"))
        assertNull(reopened.file("local:xyz"))
        val saved = JSONObject(File(root, "library.json").readText())
        assertEquals("cùng hình sổ như máy tính", 1, saved.getInt("version"))
        assertEquals("wav", saved.getJSONObject("tracks").getJSONObject(toneSha).getString("ext"))
        assertTrue(reopened.remove(toneSha))
        assertFalse(reopened.remove(toneSha))
        assertFalse(File(root, "files/$toneSha.wav").exists())
        assertTrue(store().entries().isEmpty())
    }

    @Test
    fun a_stream_is_imported_under_the_name_the_user_sees_and_newest_comes_first() {
        val store = store()
        val first = store.importStream("Bài một.wav") { ByteArrayInputStream(tone.readBytes()) }.first
        val changed = tone.readBytes().also { it[100] = (it[100] + 1).toByte() }
        val second = store.importStream("Bài hai.wav") { ByteArrayInputStream(changed) }.first
        assertEquals("Bài một", first.getString("title"))
        assertEquals(listOf("Bài hai", "Bài một"), store.entries().map { it.getString("title") })
        val third = tone.readBytes().also { it[101] = (it[101] + 1).toByte() }
        assertEquals("tên có đường dẫn thì chỉ lấy tên file", "x.wav", store.importStream("a/b/x.wav") { ByteArrayInputStream(third) }.first.getString("name"))
        assertTrue(second.getString("link") != first.getString("link"))
    }

    @Test
    fun a_loudness_meter_that_throws_does_not_break_the_import() {
        val (track, _) = store { error("không giải mã được") }.importFile(tone)
        assertFalse(track.has("lufs"))
    }

    @Test
    fun an_analyzer_result_is_cleaned_like_the_python_one() {
        val clean = MusicStore.cleanAnalysis(
            JSONObject().put("valence", -2).put("arousal", 0.5).put("tension", 0.3).put("sd", JSONObject().put("valence", -1).put("x", "no"))
                .put("emotions", JSONObject().put("joy", 3).put("mystery", 0.25).put("bored", 1)).put("confidence", 7)
                .put("fitsUnderNarration", 0.5).put("loudness", JSONObject().put("lufs", -14.5).put("speechBand", 0.4)).put("family", "piano").put("style", "x"),
        )!!
        assertEquals(-1.0, clean.getDouble("valence"), 0.0)
        assertEquals(0.0, clean.getJSONObject("sd").getDouble("valence"), 0.0)
        assertFalse(clean.getJSONObject("sd").has("x"))
        assertEquals(1.0, clean.getJSONObject("emotions").getDouble("joy"), 0.0)
        assertFalse("khoá cảm xúc lạ bị bỏ", clean.getJSONObject("emotions").has("bored"))
        assertEquals(1.0, clean.getDouble("confidence"), 0.0)
        assertEquals(0.5, clean.getDouble("background"), 0.0)
        assertEquals(-14.5, clean.getDouble("lufs"), 0.0)
        assertEquals(0.4, clean.getDouble("speechBand"), 0.0)
        assertEquals("piano", clean.getString("family"))
        assertNull(MusicStore.cleanAnalysis(JSONObject().put("arousal", 0.1)))
        assertNull(MusicStore.cleanAnalysis("không phải đối tượng"))
        // số đo từ chính file thắng số của bộ phân tích
        val store = store { -23.0 }
        store.analyzer = { JSONObject().put("valence", 0.1).put("arousal", 0.2).put("loudness", -10.0) }
        val (track, _) = store.importFile(tone)
        assertTrue(track.getBoolean("analysed"))
        assertEquals(-23.0, track.getDouble("lufs"), 0.0)
    }
}
