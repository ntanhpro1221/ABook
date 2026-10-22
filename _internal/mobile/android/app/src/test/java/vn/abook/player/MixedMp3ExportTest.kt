package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * Soát a99 V3: "Xuất MP3" kèm nhạc nền trên điện thoại. Điện thoại không có bộ mã hoá MP3 (chỉ AAC), nên khi tích ô, mỗi chương ra một file .m4a đã trộn nhạc
 * qua đúng đường của M4B; còn lại như bản xuất MP3 (thư mục tên sách, tên file, bìa, danh sách phát, file ghi công). Bộ mã hoá là bản giả (bộ thật dùng MediaCodec).
 */
class MixedMp3ExportTest {
    private lateinit var root: File
    private lateinit var out: File
    private lateinit var work: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-mixed").toFile()
        out = Files.createTempDirectory("abook-mixed-out").toFile()
        work = File(out, "work.m4a")
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
        out.deleteRecursively()
    }

    private fun book(id: String, titles: List<String>) {
        val dir = File(root, "books/$id").apply { mkdirs() }
        File(dir, "chapters").mkdirs()
        val list = JSONArray()
        titles.forEachIndexed { index, title ->
            File(Id3TagTest.dir, "source.mp3").copyTo(File(dir, "chapters/${index + 1}.mp3"))
            list.put(JSONObject().put("id", index + 1).put("index", index + 1).put("fullTitle", title).put("duration", 12.5 + index)
                .put("available", true).put("file", "chapters/${index + 1}.mp3"))
        }
        File(Id3TagTest.dir, "cover.jpg").copyTo(File(dir, "cover.jpg"))
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Sách thử: Tập 1")
            .put("narrator", "Đức Trí").put("chaptersTotal", titles.size).put("chapters", list).toString())
    }

    /** Bộ trộn có nhạc ở chương 1 (bài CC BY cần ghi công); chương 2 không có nhạc. */
    private fun mixer(): MusicExport.Mixer {
        val track = JSONObject().put("title", "Bài A").put("creator", "Kevin").put("license", "by").put("attribution", "\"Bài A\" Kevin")
        val music = mapOf(1 to MusicExport.ChapterMusic(listOf(MusicCues.Cue(0.0, 10.0, "a", -20.0)), emptyMap(), tracks = mapOf("a" to track)))
        return MusicExport.Mixer(music, TrackPcmCache(File(root, "pcm"), { _, _, _, _ -> }),
            MusicRender.Params.parse(JSONObject(File("../../../abook/webui/assets/music_mix.json").readText())))
    }

    private fun plan(id: String) = Mp3Export.plan(id).with(mixer(), null)

    /** Bộ mã hoá giả: ghi MP4 tối thiểu, mốc 1 giây mỗi chương; nhớ tên chương nó được giao. */
    private fun fake(seen: MutableList<String> = ArrayList()) = M4bExport.AudioEncoder { plan, target, stopped, progress ->
        progress(0, plan.chapters.size, 0.0)
        val marks = plan.chapters.mapIndexed { index, chapter ->
            if (stopped()) throw Mp3Export.Stopped()
            seen += chapter.fullTitle
            progress(index + 1, plan.chapters.size, 1.0)
            Mp4Finish.Mark(chapter.fullTitle, index * 1000L, (index + 1) * 1000L)
        }
        Mp4Fixtures.muxerFile(ByteArray(64) { it.toByte() }, target, durationMs = plan.chapters.size * 1000)
        marks
    }

    private fun has(bytes: ByteArray, text: String): Boolean {
        val needle = text.toByteArray(Charsets.UTF_8)
        return (0..bytes.size - needle.size).any { start -> needle.indices.all { bytes[start + it] == needle[it] } }
    }

    @Test
    fun everyChapterBecomesAnM4aInTheSameFolderAndPlaylistAsTheMp3Export() {
        book("x1", listOf("Chương 1: Mở đầu", "Chương 2"))
        val seen = ArrayList<String>()
        val progress = ArrayList<Pair<Int, Int>>()
        val result = Mp3Export.runMixed(plan("x1"), Mp3Export.FileDestination(out), work, fake(seen), progress = { done, total -> progress += done to total })
        assertEquals(2, result.files)
        assertEquals(listOf("Chương 1: Mở đầu", "Chương 2"), seen)
        assertEquals(2 to 2, progress.last())
        val folder = File(out, "Sách thử Tập 1")
        assertEquals(listOf("01 - Chương 1 Mở đầu.m4a", "02 - Chương 2.m4a"), folder.listFiles()!!.map { it.name }.filter { it.endsWith(".m4a") }.sorted())
        assertTrue("bìa nằm cạnh các chương như bản MP3", folder.listFiles()!!.any { it.name.startsWith("cover") })
        val playlist = File(folder, Mp3Export.playlistName("Sách thử: Tập 1")).readText()
        assertTrue(playlist.contains("01 - Chương 1 Mở đầu.m4a") && playlist.contains("02 - Chương 2.m4a"))
        assertFalse("danh sách phát không còn nhắc .mp3", playlist.contains(".mp3"))
        assertFalse("file trung gian dọn sau mỗi chương", work.exists())
    }

    @Test
    fun eachFileCarriesItsOwnChapterTitleAndTheBookAsAlbum() {
        book("x2", listOf("Chương 1: Mở đầu", "Chương 2"))
        Mp3Export.runMixed(plan("x2"), Mp3Export.FileDestination(out), work, fake())
        val folder = File(out, "Sách thử Tập 1")
        val first = File(folder, "01 - Chương 1 Mở đầu.m4a").readBytes()
        val second = File(folder, "02 - Chương 2.m4a").readBytes()
        assertTrue(has(first, "Chương 1: Mở đầu") && has(first, "Sách thử: Tập 1") && has(first, "Đức Trí"))
        assertTrue(has(second, "Chương 2") && has(second, "Sách thử: Tập 1"))
        assertFalse("tên chương 1 không lọt vào file chương 2", has(second, "Mở đầu"))
        // ghi công của chính chương có nhạc nằm ở thẻ ghi chú; chương không có nhạc thì không mang ghi công
        assertTrue(has(first, "Kevin"))
        assertFalse(has(second, "Kevin"))
    }

    @Test
    fun theCreditsFileSitsNextToTheChaptersWhenSomeMusicNeedsCredit() {
        book("x3", listOf("Chương 1", "Chương 2"))
        Mp3Export.runMixed(plan("x3"), Mp3Export.FileDestination(out), work, fake())
        val credits = File(out, "Sách thử Tập 1/${Mp3Export.CREDITS_FILE}")
        assertTrue(credits.isFile)
        assertTrue(credits.readText().contains("\"Bài A\" Kevin"))
    }

    @Test
    fun noCreditsFileWhenNoMusicWasMixed() {
        book("x4", listOf("Chương 1"))
        val bare = Mp3Export.plan("x4").with(MusicExport.Mixer(emptyMap(), TrackPcmCache(File(root, "pcm"), { _, _, _, _ -> }),
            MusicRender.Params.parse(JSONObject(File("../../../abook/webui/assets/music_mix.json").readText()))), null)
        Mp3Export.runMixed(bare, Mp3Export.FileDestination(out), work, fake())
        assertFalse(File(out, "Sách thử Tập 1/${Mp3Export.CREDITS_FILE}").exists())
    }

    @Test
    fun stoppingBetweenChaptersKeepsTheFinishedOnesAndNoPartFiles() {
        book("x5", listOf("Chương 1", "Chương 2", "Chương 3"))
        var finished = 0
        try {
            Mp3Export.runMixed(plan("x5"), Mp3Export.FileDestination(out), work, fake(), progress = { done, _ -> finished = done }, stopped = { finished >= 1 })
            fail("phải dừng")
        } catch (_: Mp3Export.Stopped) {
        }
        val names = File(out, "Sách thử Tập 1").listFiles()!!.map { it.name }
        assertTrue(names.contains("01 - Chương 1.m4a"))
        assertFalse(names.any { it.contains("Chương 2") || it.endsWith(".part") })
        assertFalse(work.exists())
    }

    @Test
    fun theMixedFileNameKeepsTheDesktopNumberingAndFitsThePhone() {
        assertEquals("01 - Chương 1.m4a", Mp3Export.chapterFileName(1, 2, "Chương 1", Mp3Export.MIXED_EXTENSION))
        assertEquals("01 - Chương 1.mp3", Mp3Export.chapterFileName(1, 2, "Chương 1"))
        assertTrue(Mp3Export.chapterFileName(1, 2, "Chương " + "ờ".repeat(89), Mp3Export.MIXED_EXTENSION).toByteArray(Charsets.UTF_8).size <= 255)
    }
}
