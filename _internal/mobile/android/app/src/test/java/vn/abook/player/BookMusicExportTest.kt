package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * "Kèm nhạc nền" khi xuất trên điện thoại (BookMusic.exportMusic / exportState / chapterMusic / missing / pcmBytes, chỗ trống của M4B): nhạc theo lớp sửa nhưng bỏ
 * công tắc tắt, ô mặc định theo công tắc, bài thiếu thì mốc bị bỏ và đếm, ước chỗ trống cộng bộ đệm PCM bài.
 */
class BookMusicExportTest {
    private lateinit var root: File
    private val id = "sach"
    private val a = "music/${"a".repeat(40)}.mp3"
    private val b = "music/${"b".repeat(40)}.mp3"

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-music-export").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun dir() = Store.bookDir(id)

    private fun cue(start: Double, track: String, gainDb: Double? = null) = JSONObject().put("start", start).put("end", start + 30).put("track", track).apply {
        gainDb?.let { put("gainDb", it) }
    }

    private fun book(chapters: JSONObject, tracks: JSONObject = JSONObject().put(a, JSONObject().put("size", 3).put("seconds", 120.0))
        .put(b, JSONObject().put("size", 4).put("lufs", -16.0))) {
        dir().mkdirs()
        val music = JSONObject().put("levelDb", -20.0).put("tracks", tracks).put("chapters", chapters)
        File(dir(), "book.json").writeText(JSONObject().put("title", "Sách").put("chapters", JSONArray()).put("music", music).toString())
    }

    private fun file(name: String, size: Int) = File(dir(), name).apply { parentFile.mkdirs(); writeBytes(ByteArray(size)) }

    private fun edits(music: JSONObject) = BookEdits.save(dir(), BookEdits.empty().put("music", music))

    @Test
    fun theExportUsesTheListenersLevelButIgnoresTheMusicSwitchWhichOnlySetsTheDefault() {
        book(JSONObject().put("1", JSONArray().put(cue(0.0, a, -30.0))))
        assertEquals(true to true, BookMusic.exportState(id))
        edits(JSONObject().put("enabled", false).put("levelDb", -14.0))
        val music = BookMusic.exportMusic(id)!!
        assertEquals("tắt nhạc không xoá mốc khi đã tích ô", 1, music.getJSONObject("chapters").getJSONArray("1").length())
        assertEquals(true to false, BookMusic.exportState(id))
        // lớp sửa (mức mới) vẫn áp: mức chung đổi thì mức mốc tính lại
        assertTrue(music.getJSONObject("chapters").getJSONArray("1").getJSONObject(0).getDouble("gainDb") != -30.0)
    }

    @Test
    fun aBookWithoutCuesHasNoMusicToOffer() {
        book(JSONObject().put("1", JSONArray()))
        assertEquals(false to false, BookMusic.exportState(id))
        File(dir(), "book.json").writeText(JSONObject().put("title", "Sách").toString())
        assertNull(BookMusic.exportMusic(id))
        assertEquals(false to false, BookMusic.exportState(id))
    }

    @Test
    fun aMissingTrackIsFetchedFirstAndIfStillMissingItsCuesAreDroppedAndCounted() {
        book(JSONObject().put("1", JSONArray().put(cue(0.0, a)).put(cue(40.0, b))).put("2", JSONArray().put(cue(0.0, b))))
        file(a, 3)
        file(b, 99) // sai cỡ = hỏng
        val music = BookMusic.exportMusic(id)!!
        assertEquals(listOf(b), BookMusic.missing(dir(), music).map { it.name })
        val chapters = BookMusic.chapterMusic(dir(), music, listOf(1, 2, 3))
        assertEquals(setOf(1, 2), chapters.keys)
        assertEquals(listOf(a), chapters.getValue(1).cues.map { it.track })
        assertEquals(1, chapters.getValue(1).dropped)
        assertTrue(chapters.getValue(2).cues.isEmpty())
        assertEquals(1, chapters.getValue(2).dropped)
        // mốc không có gainDb (gói cũ): lấy mức chung như trình phát
        assertTrue(chapters.getValue(1).cues[0].gainDb != null)
        // bộ trộn: chương 2 không còn gì để trộn - xuất như không nhạc, nhưng vẫn đếm đoạn thiếu
        assertNull(MusicExport.audible(chapters, 2))
        val mixer = MusicExport.Mixer(chapters, TrackPcmCache(File(root, "pcm"), { _, _, _, _ -> }), MusicRender.Params.parse(
            JSONObject(File("../../../abook/webui/assets/music_mix.json").readText())))
        assertFalse(mixer.has(2))
        assertEquals(2, mixer.missing(listOf(1, 2)))
        file(b, 4)
        assertTrue(BookMusic.missing(dir(), music).isEmpty())
        assertEquals(0, BookMusic.chapterMusic(dir(), music, listOf(1)).getValue(1).dropped)
    }

    @Test
    fun theSpaceEstimateAddsThreeTimesTheLargestTrackAsPcm() {
        book(JSONObject().put("1", JSONArray().put(cue(0.0, a)).put(cue(40.0, b))))
        file(b, 1_200_000) // không có độ dài trong gói: ước theo cỡ file, 12 000 byte/giây = 100 s
        val music = BookMusic.exportMusic(id)!!
        assertEquals(TrackPcmCache.bytesFor(120.0, 48000, 1) * 3, BookMusic.pcmBytes(dir(), music, 48000, 1))
        file(b, 2_400_000) // 200 s > 120 s
        assertEquals(TrackPcmCache.bytesFor(200.0, 44100, 2) * 3, BookMusic.pcmBytes(dir(), music, 44100, 2))
        assertEquals(0L, BookMusic.pcmBytes(dir(), null, 48000, 1))
    }

    @Test
    fun anM4bWithMusicNeedsTheFrameStoreTwiceAndTheTrackCache() {
        val chapter = Mp3Export.Chapter(1, "Chương 1", 3600.0, File(root, "1.mp3"))
        val plain = Mp3Export.Plan("S", "", listOf(chapter), 1, 1, null, "")
        val base = M4bExport.estimatedBytes(plain)
        assertEquals(base, M4bExport.estimatedBytes(plain, 0))
        val mixer = MusicExport.Mixer(emptyMap(), TrackPcmCache(File(root, "pcm"), { _, _, _, _ -> }), MusicRender.Params.parse(
            JSONObject(File("../../../abook/webui/assets/music_mix.json").readText())))
        val music = plain.with(mixer, null)
        val audio = base - (16L shl 20)
        assertEquals(2 * audio + (16L shl 20) + 1000, M4bExport.estimatedBytes(music, 1000))
    }
}
