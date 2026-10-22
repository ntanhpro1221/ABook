package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.io.File

class MusicEdgesTest {
    private val cases = JSONObject(File("../../../tests/fixtures/music/edge_cases.json").readText())
    @Before fun mix() { MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText()) }

    @Test fun pinningShorterOrLongerTracksDoesNotMoveTheNextEntry() {
        val pins = cases.getJSONArray("pinCases")
        for (index in 0 until pins.length()) {
            val case = pins.getJSONObject(index)
            val applied = BookEdits.applyMusic(case.getJSONObject("music"), case.getJSONObject("edits")) as JSONObject
            val cues = MusicCues.of(applied, 1)
            assertTrue("same pinned package as Python", StrictJson.equal(applied, case.getJSONObject("applied")))
            assertFalse(cues[0].tail)
            val tracks = mapOf(cues[0].track to MusicTimeline.TrackInfo(case.getDouble("seconds")), cues[1].track to MusicTimeline.TrackInfo(200.0))
            val timeline = MusicTimeline.build(cues, null, tracks)
            val next = timeline.first { it.element.track == cues[1].track }
            assertEquals(case.getDouble("expectedNext"), next.element.from, 1e-9)
        }
    }

    @Test fun loopEndPastEofIsClampedEvenWhenEndLessCrossfadeIsValid() {
        val case = cases.getJSONObject("loop")
        val cue = MusicCues.Cue(0.0, 110.0, "a", -20.0, audibleStart = case.getDouble("audibleStart"), audibleEnd = case.getDouble("audibleEnd"),
            loopStart = case.getDouble("loopStart"), loopEnd = case.getDouble("loopEnd"))
        val bounds = MusicCues.loopBounds(cue, case.getDouble("seconds"))
        assertEquals(case.getDouble("expectedEnd"), bounds.loopEnd, 0.0)
        assertEquals(case.getDouble("loopStart"), bounds.loopStart, 0.0)
        assertEquals(case.getDouble("expectedOpen"), MusicCues.loopSchedule(bounds, 110.0).opens.first(), 0.0)
    }

    private fun scene(s: JSONObject): SceneScene {
        val sd = s.getJSONObject("sd")
        return SceneScene(s.getInt("chapterId"), s.getInt("firstSegment"), s.getInt("lastSegment"), s.getDouble("start"), s.getDouble("end"),
            s.getString("reason"), s.getInt("lines"), s.getDouble("valence"), s.getDouble("arousal"), s.getDouble("tension"),
            sd.getDouble("valence"), sd.getDouble("arousal"), sd.getDouble("tension"), s.getDouble("confidence"))
    }

    @Test fun selectorSpreadAndVarianceMatchTheSharedPythonRankingAndChoices() {
        val selectors = cases.getJSONArray("selectorCases")
        for (index in 0 until selectors.length()) {
            val c = selectors.getJSONObject(index)
            val raw = c.getJSONArray("tracks")
            val tracks = (0 until raw.length()).map { SceneTrack.of(raw.getJSONObject(it))!! }
            val scenes = c.getJSONArray("scenes").let { list -> (0 until list.length()).map { scene(list.getJSONObject(it)) } }
            val chooser = SceneChooser(SceneChoice(c.getString("bookKey"), trackInfo = { link -> tracks.first { it.link == link } })) { _, _ -> tracks }
            val ranked = chooser.rank(scenes[0], emptyList(), 10)
            val expected = c.getJSONArray("rank")
            assertEquals(expected.length(), ranked.size)
            for (i in ranked.indices) {
                assertEquals(c.getString("mode"), expected.getJSONObject(i).getString("link"), ranked[i].first.link)
                assertEquals(expected.getJSONObject(i).getDouble("score"), ranked[i].second, 1e-12)
            }
            val chosen = chooser.choose(scenes)
            assertEquals(c.getJSONArray("chosen").let { list -> (0 until list.length()).map { list.getString(it) } }, chosen.map { it.link })
        }
    }

    @Test fun aChapterContainingOnlyNotesCurrentlyGetsANormalMusicScene() {
        val notes = cases.getJSONObject("notes")
        val raw = notes.getJSONArray("segments")
        val segments = (0 until raw.length()).map { i -> raw.getJSONObject(i).let { SceneSegment(it.getInt("id"), it.getString("text"), it.getString("kind")) } }
        val scenes = SceneScenes.chapterScenes(1, segments)
        val expected = notes.getJSONArray("expectedScenes")
        assertEquals(1, scenes.size)
        val actual = scenes.single()
        assertEquals(expected.getJSONObject(0).getDouble("start"), actual.start, 0.0)
        assertEquals(expected.getJSONObject(0).getDouble("end"), actual.end, 0.0)
        assertEquals(2, actual.lines)
        val calm = SceneTrack.of(JSONObject("""{"link":"https://example.invalid/calm.mp3","valence":0.15,"arousal":-0.55,"duration":240,"source":"incompetech"}"""))!!
        val chosen = SceneChooser(SceneChoice("notes")) { _, _ -> listOf(calm) }.choose(scenes)
        assertEquals(calm.link, SceneMusic.chapterCues(chosen, 1, null).single().link)
    }

    @Test fun aValidEmptyCatalogBuildsSilentScenesAndAnEmptyPlayerArrival() {
        val root = BookEditsFixtures.tempDir("music-empty-catalog")
        try {
            val catalog = MusicCatalog(File(root, "catalog"), File("../../../tests/fixtures/music/empty_catalog").absolutePath, publicKey = CatalogSigning.publicKey)
            assertEquals("edge-empty", catalog.manifest().getString("revision"))
            assertTrue(catalog.near(.15, -.55).isEmpty())
            val book = SceneBook(File(root, "scenes"), listOf(1), { "Một câu chuyện dài đang được đọc trong căn phòng yên tĩnh." }, SceneChoice("empty")) { v, a ->
                catalog.near(v, a).mapNotNull(SceneTrack::of)
            }
            val record = book.build(1)!!
            assertTrue(record.getJSONArray("scenes").length() > 0)
            assertTrue(book.links(record).isEmpty())
            val response = book.response(record)
            assertTrue(SceneAnchor.cuesOf(response).isEmpty())
            val feed = SceneBed { null }
            feed.arrive(SceneBed.Arrival(SceneAnchor.cuesOf(response), response.optDouble("estSeconds"), -20.0, emptyMap()), 0.0)
            assertTrue(feed.cues.isEmpty())
            assertEquals(cases.getJSONObject("emptyResponse").getJSONArray("cues").toString(), response.getJSONArray("cues").toString())
            // Feed the actual silent arrival to MusicBed's playback entry. Any attempt to open a codec fails on this plain JVM.
            fun field(name: String) = MusicBed::class.java.getDeclaredField(name).also { it.isAccessible = true }
            val unsafeClass = Class.forName("sun.misc.Unsafe")
            val unsafe = unsafeClass.getDeclaredField("theUnsafe").also { it.isAccessible = true }.get(null)
            MusicBed.stop()
            field("context").set(MusicBed, unsafeClass.getMethod("allocateInstance", Class::class.java).invoke(unsafe, android.content.ContextWrapper::class.java))
            try {
                field("book").set(MusicBed, "empty-book")
                field("chapter").setInt(MusicBed, 1)
                field("cues").set(MusicBed, feed.cues)
                for (seconds in listOf(0.0, 1.0, 30.0)) {
                    MusicBed.sync("empty-book", 1, seconds, true)
                    assertNull(MusicBed.activeTrack)
                }
            } finally { field("context").set(MusicBed, null); MusicBed.stop(); android.os.Handler.reset() }
        } finally { root.deleteRecursively() }
    }
}
