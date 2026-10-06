package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** "Xuất MP3" trên điện thoại (Mp3Export): tên file như máy tính (bộ ví dụ chung tests/fixtures/mp3_export) và cả lượt xuất một cuốn giả. */
class Mp3ExportTest {
    private lateinit var root: File
    private lateinit var out: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-mp3").toFile()
        out = Files.createTempDirectory("abook-mp3-out").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
        out.deleteRecursively()
    }

    private fun json(name: String): Any = StrictJson.parse(File(Id3TagTest.dir, name).readText(Charsets.UTF_8))!!

    /** Cuốn giả trên điện thoại: ba chương, hai đã có audio (MP3 của bộ ví dụ), chương 3 chưa làm xong; có bìa nếu `cover`. */
    private fun book(id: String, cover: Boolean, chapters: List<Pair<String, Boolean>>) {
        val dir = File(root, "books/$id").apply { mkdirs() }
        val list = JSONArray()
        chapters.forEachIndexed { index, (title, done) ->
            val chapter = JSONObject().put("id", index + 1).put("index", index + 1).put("fullTitle", title)
                .put("duration", if (done) 12.5 + index else 0.0).put("available", done)
            if (done) {
                File(dir, "chapters").mkdirs()
                File(Id3TagTest.dir, "source.mp3").copyTo(File(dir, "chapters/${index + 1}.mp3"))
                chapter.put("file", "chapters/${index + 1}.mp3")
            }
            list.put(chapter)
        }
        if (cover) File(Id3TagTest.dir, "cover.jpg").copyTo(File(dir, "cover.jpg"))
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Sách thử: Tập 1")
            .put("narrator", "Đức Trí").put("chaptersTotal", chapters.size).put("chapters", list).toString())
    }

    @Test
    fun namesAreTheDesktopNames() {
        val names = json("names.json") as JSONObject
        val safe = names.getJSONArray("safeName")
        for (index in 0 until safe.length()) {
            val case = safe.getJSONObject(index)
            assertEquals(case.getString("text"), case.getString("name"), Mp3Export.safeName(case.getString("text"), case.getInt("limit")))
        }
        val files = names.getJSONArray("chapterFileName")
        for (index in 0 until files.length()) {
            val case = files.getJSONObject(index)
            assertEquals(case.getString("name"), Mp3Export.chapterFileName(case.getInt("number"), case.getInt("total"), case.getString("fullTitle")))
        }
    }

    @Test
    fun playlistIsTheDesktopPlaylist() {
        val case = json("playlist.json") as JSONObject
        val entries = case.getJSONArray("entries").let { array ->
            (0 until array.length()).map { array.getJSONArray(it).let { entry -> Triple(entry.getDouble(0), entry.getString(1), entry.getString(2)) } }
        }
        assertEquals(case.getString("text"), Mp3Export.playlist(case.getString("title"), entries))
    }

    @Test
    fun namesTooLongForThePhoneAreCutToFit() {
        val title = "Chương " + "ờ".repeat(89)
        val name = Mp3Export.chapterFileName(1, 2, title)
        assertTrue(name.toByteArray(Charsets.UTF_8).size <= 255)
        assertTrue(name.startsWith("01 - Chương ờ") && name.endsWith("ờ.mp3"))
        // Vừa thì không đổi gì.
        assertEquals("01 - Chương 1.mp3", Mp3Export.chapterFileName(1, 2, "Chương 1"))
    }

    @Test
    fun exportsOnlyFinishedChaptersWithTagsCoverAndPlaylist() {
        book("b1", cover = true, chapters = listOf("Chương 1 · Mở đầu" to true, "Chương 2: Đi/về" to true, "Chương 3" to false))
        val seen = ArrayList<Pair<Int, Int>>()
        val result = Mp3Export.run(Mp3Export.plan("b1"), Mp3Export.FileDestination(out), progress = { done, total -> seen += done to total })
        assertEquals(2, result.files)
        assertEquals(3, result.chaptersTotal)
        assertEquals("${out.name}/Sách thử Tập 1", result.folder)
        assertEquals(listOf(0 to 2, 1 to 2, 2 to 2), seen)
        val folder = File(out, "Sách thử Tập 1")
        assertEquals(listOf("01 - Chương 1 · Mở đầu.mp3", "02 - Chương 2 Đi về.mp3", "Sách thử Tập 1.m3u8", "cover.jpg"),
            folder.list()!!.sorted())
        val cover = Id3Tag.Cover.of(File(Id3TagTest.dir, "cover.jpg").readBytes())
        val second = File(folder, "02 - Chương 2 Đi về.mp3").readBytes()
        val fields = Id3Tag.Fields("Chương 2: Đi/về", "Sách thử: Tập 1", "Đức Trí", 2, 2, cover)
        val tag = Id3Tag.v2(fields)
        assertArrayEquals(tag, second.copyOfRange(0, tag.size))
        assertArrayEquals(Id3Tag.v1(fields), second.copyOfRange(second.size - 128, second.size))
        assertArrayEquals(File(Id3TagTest.dir, "cover.jpg").readBytes(), File(folder, "cover.jpg").readBytes())
        assertEquals("#EXTM3U\n#PLAYLIST:Sách thử: Tập 1\n#EXTINF:12,Chương 1 · Mở đầu\n01 - Chương 1 · Mở đầu.mp3\n" +
            "#EXTINF:14,Chương 2: Đi/về\n02 - Chương 2 Đi về.mp3\n", File(folder, "Sách thử Tập 1.m3u8").readText())
    }

    @Test
    fun aBookWithoutCoverUsesTheDrawnPng() {
        book("b2", cover = false, chapters = listOf("Chương 1" to true))
        val png = File(Id3TagTest.dir, "cover.png").readBytes()
        val plan = Mp3Export.plan("b2", drawnCover = png)
        assertEquals("image/png", plan.cover?.mime)
        Mp3Export.run(plan, Mp3Export.FileDestination(out))
        assertArrayEquals(png, File(out, "Sách thử Tập 1/cover.png").readBytes())
        // Không có bìa nào: không có khung APIC, không có file bìa.
        val bare = Mp3Export.plan("b2")
        assertEquals(null, bare.cover)
    }

    @Test
    fun stoppingMidwayKeepsFinishedChaptersAndLeavesNoPartFile() {
        book("b3", cover = false, chapters = listOf("Một" to true, "Hai" to true, "Ba" to true))
        var finished = 0
        try {
            Mp3Export.run(Mp3Export.plan("b3"), Mp3Export.FileDestination(out), progress = { done, _ -> finished = done }, stopped = { finished >= 1 })
            fail("phải dừng")
        } catch (_: Mp3Export.Stopped) {
        }
        val folder = File(out, "Sách thử Tập 1")
        assertEquals(listOf("01 - Một.mp3"), folder.list()!!.sorted())
    }

    @Test
    fun stoppingInsideAChapterRemovesIt() {
        book("b4", cover = false, chapters = listOf("Một" to true))
        var asked = 0
        try {
            Mp3Export.run(Mp3Export.plan("b4"), Mp3Export.FileDestination(out), stopped = { ++asked > 1 })
            fail("phải dừng")
        } catch (_: Mp3Export.Stopped) {
        }
        assertFalse(File(out, "Sách thử Tập 1").list()!!.any { it.endsWith(".mp3") || it.endsWith(".part") })
    }

    @Test
    fun aBookWithNothingFinishedIsRefused() {
        book("b5", cover = false, chapters = listOf("Một" to false))
        try {
            Mp3Export.plan("b5")
            fail("phải từ chối")
        } catch (error: Mp3Export.Refused) {
            assertEquals("Sách chưa có chương nào nghe được để xuất", error.message)
        }
    }

    @Test
    fun exportingAgainReplacesTheFiles() {
        book("b6", cover = false, chapters = listOf("Một" to true))
        Mp3Export.run(Mp3Export.plan("b6"), Mp3Export.FileDestination(out))
        val result = Mp3Export.run(Mp3Export.plan("b6"), Mp3Export.FileDestination(out))
        assertEquals(1, result.files)
        assertEquals(listOf("01 - Một.mp3", "Sách thử Tập 1.m3u8"), File(out, "Sách thử Tập 1").list()!!.sorted())
    }
}
