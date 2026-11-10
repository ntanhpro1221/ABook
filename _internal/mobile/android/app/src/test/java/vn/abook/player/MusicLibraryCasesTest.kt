package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Kho nhạc của điện thoại chạy CÙNG bảng ca với máy chủ (test_music_library.py) và Qt: tests/fixtures/music_library/cases.json -
 * cùng bộ lọc thì cùng bài, cùng thứ tự. Cộng: "Vì sao bài này", "Nhạc trong sách", sổ bài đã lưu.
 */
class MusicLibraryCasesTest {
    @get:Rule
    val folder = TemporaryFolder()

    private val fixture = JSONObject(File("../../../tests/fixtures/music_library/cases.json").readText(Charsets.UTF_8))
    private val tracks = fixture.getJSONObject("tracks").let { raw -> MusicLibrary.tracksOf(raw.keys().asSequence().associateWith { raw.getJSONObject(it) }) }
    private val playlists = fixture.getJSONObject("playlists").let { raw ->
        raw.keys().asSequence().associateWith { id -> raw.getJSONArray(id).let { list -> (0 until list.length()).map(list::getString) } }
    }
    private val downloaded = fixture.getJSONArray("downloaded").let { list -> (0 until list.length()).map(list::getString).toSet() }

    @Test
    fun everySharedCaseGivesTheSameTracksInTheSameOrder() {
        val cases = fixture.getJSONArray("cases")
        assertTrue("bảng ca quá ít: ${cases.length()}", cases.length() >= 20)
        for (at in 0 until cases.length()) {
            val case = cases.getJSONObject(at)
            val expect = case.getJSONArray("expect").let { list -> (0 until list.length()).map(list::getString) }
            val got = MusicLibrary.select(tracks, MusicLibrary.Filters.of(case.getJSONObject("filter")), playlists, downloaded).map { it.link }
            assertEquals(case.getString("name"), expect, got)
        }
    }

    @Test
    fun foldDropsVietnameseMarksCaseAndExtraSpaces() {
        assertEquals("dem trang", MusicLibrary.fold("  ĐÊM   Trăng "))
        assertEquals("anh sang", MusicLibrary.fold("Ánh Sáng"))
        assertEquals("", MusicLibrary.fold(""))
    }

    @Test
    fun tempoAndLengthBoundsMatchTheServer() {
        assertEquals("slow", MusicLibrary.tempoOf(89.9))
        assertEquals("mid", MusicLibrary.tempoOf(90.0))
        assertEquals("mid", MusicLibrary.tempoOf(130.0))
        assertEquals("fast", MusicLibrary.tempoOf(130.1))
        assertNull(MusicLibrary.tempoOf(null))
        assertNull(MusicLibrary.tempoOf(0.0))
        assertEquals("short", MusicLibrary.lengthOf(119.0))
        assertEquals("mid", MusicLibrary.lengthOf(120.0))
        assertEquals("mid", MusicLibrary.lengthOf(300.0))
        assertEquals("long", MusicLibrary.lengthOf(301.0))
    }

    @Test
    fun energyAndPercentAreLikeTheWeb() {
        assertEquals(0, MusicLibrary.energyPercent(-1.0))
        assertEquals(50, MusicLibrary.energyPercent(0.0))
        assertEquals(79, MusicLibrary.energyPercent(0.582))
        assertNull(MusicLibrary.energyPercent(null))
        assertEquals(95, MusicLibrary.percent(0.946))
        assertEquals(100, MusicLibrary.percent(1.2))
    }

    @Test
    fun whyShowsTheFitAndTheThreeStrongestSharedEmotions() {
        val scene = mapOf("joy" to 0.8, "power" to 0.6, "sadness" to 0.1, "fear" to 0.0)
        val track = mapOf("joy" to 0.7, "power" to 0.9, "sadness" to 0.5, "tension" to 0.4)
        val why = MusicLibrary.why(scene, track)!!
        assertEquals(listOf("joy", "power", "sadness"), why.matches.map { it.id }) // 0,56 > 0,54 > 0,05
        assertEquals(0.8, why.matches[0].scene, 1e-9)
        assertEquals(0.7, why.matches[0].track, 1e-9)
        assertTrue(why.fit in 0.0..1.0)
        assertNull("đoạn không có cảm xúc: ẩn khối", MusicLibrary.why(emptyMap(), track))
        assertNull(MusicLibrary.why(mapOf("joy" to 0.0), track))
    }

    @Test
    fun bookTracksMergeRepeatsAndCountScenes() {
        val got = MusicLibrary.bookTracks(listOf("1:1" to "https://a/1", "1:2" to "https://a/2", "2:1" to "https://a/1", null to ""))
        assertEquals(listOf(MusicLibrary.BookTrack("https://a/1", 2, "1:1"), MusicLibrary.BookTrack("https://a/2", 1, "1:2")), got)
    }

    @Test
    fun savedTracksKeepOrderAndSurviveARestart() {
        val file = File(folder.root, "music/saved.json")
        val saved = SavedTracks(file)
        assertEquals(listOf("https://a/1", "https://a/2"), saved.add(listOf("https://a/1", "https://a/2", "https://a/1", "http://insecure")))
        assertEquals(emptyList<String>(), saved.add(listOf("https://a/1")))
        assertEquals(listOf("https://a/2"), saved.remove(listOf("https://a/2", "https://a/9")))
        assertEquals(listOf("https://a/1"), SavedTracks(file).links())
        assertEquals(1, JSONObject(file.readText()).getInt("version"))
    }
}
