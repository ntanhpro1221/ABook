package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * Nhạc nền theo cảnh, đường N0, trên điện thoại (SceneCues / SceneScenes / SceneChoose / SceneSegmenter / SceneMusic / SceneBook) phải ra GIỐNG HỆT bản Python
 * (music_scenes.py + music_select.py + music_plan.chapter_cues + text_processing.segment_chapter_text) trên bộ ví dụ dùng chung `tests/fixtures/music/n0/`
 * (sinh bởi scripts/music_n0_fixtures.py, chữ và bài đều tự dựng): từng regex, từng câu của bộ tách, từng đoạn (ranh, lý do, giây ước), bài chọn, bài anh em,
 * `stopAt`, `stepDb`, các mốc của chương và vòng lặp của bài.
 */
class SceneMusicTest {
    private val folder = File("../../../tests/fixtures/music/n0")

    private fun json(name: String) = JSONObject(File(folder, name).readText(Charsets.UTF_8))

    @Before
    fun loadMix() {
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
    }

    private fun strings(array: JSONArray?): List<String> = if (array == null) emptyList() else (0 until array.length()).map { array.getString(it) }

    private fun doubles(array: JSONArray): List<Double?> = (0 until array.length()).map { if (array.isNull(it)) null else array.getDouble(it) }

    private fun maybe(json: JSONObject, key: String): Double? = if (!json.has(key) || json.isNull(key)) null else json.getDouble(key)

    // ---- danh mục + hằng số ------------------------------------------------------------------------------------------------------------------
    private val catalog by lazy { json("catalog.json") }

    private fun cells(): Map<String, List<JSONObject>> {
        val all = catalog.getJSONObject("cells")
        return all.keys().asSequence().associateWith { name -> (0 until all.getJSONArray(name).length()).map { all.getJSONArray(name).getJSONObject(it) } }
    }

    /** `catalog.near(v, a, radius=1)` của Python trên danh mục tự dựng: bài ở ô (v, a) và 8 ô quanh, theo thứ tự `SceneMusic.near`. */
    private fun nearAt(valence: Double, arousal: Double): List<SceneTrack> {
        val cells = cells()
        return SceneMusic.near(5, valence, arousal, 1) { v, a -> cells["${v}_$a"] ?: emptyList() }.mapNotNull { SceneTrack.of(it) }
    }

    private fun near(): List<SceneTrack> = nearAt(SceneChooser.TARGET[0], SceneChooser.TARGET[1])

    /** Mọi bài của mọi ô (cho tra vòng lặp theo link). */
    private fun allTracks(): List<SceneTrack> = cells().values.flatten().mapNotNull { SceneTrack.of(it) }

    /** NN-lite thật của app: cùng `nnlite.bin` với máy tính. */
    private val lite by lazy { NnLite.parse(File("../../../abook/webui/assets/nnlite.bin").readBytes()) }

    @Test
    fun constants_equal_the_python_ones() {
        val constants = catalog.getJSONObject("constants")
        assertEquals(doubles(constants.getJSONArray("target")), SceneChooser.TARGET.toList())
        assertEquals(doubles(constants.getJSONArray("sigma")), SceneChooser.SIGMA.toList())
        assertEquals(constants.getDouble("penaltyUnit"), SceneChooser.PENALTY_UNIT, 0.0)
        assertEquals(constants.getDouble("styleHalfPenalty"), SceneChooser.STYLE_HALF_PENALTY, 0.0)
        assertEquals(constants.getDouble("familyPenalty"), SceneChooser.FAMILY_PENALTY, 0.0)
        assertEquals(constants.getDouble("foregroundPenalty"), SceneChooser.FOREGROUND_PENALTY, 0.0)
        assertEquals(constants.getDouble("recentPenalty"), SceneChooser.RECENT_PENALTY, 0.0)
        val mix = catalog.getJSONObject("mix")
        assertEquals(mix.getDouble("tailMinSeconds"), MusicCues.mix.tailMinSeconds, 0.0)
        assertEquals(mix.getDouble("cueMergeGapSeconds"), MusicCues.mix.cueMergeGapSeconds, 0.0)
        assertEquals(mix.getDouble("loopCrossfadeSeconds"), MusicCues.mix.loopCrossfadeSeconds, 0.0)
    }

    @Test
    fun near_order_distance_and_tiebreak_are_the_same_as_python() {
        val order = strings(catalog.getJSONArray("nearOrder"))
        assertEquals(order, near().map { it.link })
        val tracks = near().associateBy { it.link }
        val samples = catalog.getJSONArray("samples")
        assertTrue(samples.length() >= 40)
        for (index in 0 until samples.length()) {
            val sample = samples.getJSONObject(index)
            val track = tracks.getValue(sample.getString("link"))
            assertEquals(sample.getDouble("z"), SceneChooser.zDistance(track, SceneChooser.TARGET, SceneChooser.SIGMA), 0.0)
            assertEquals(sample.getDouble("tiebreak"), SceneChooser.tiebreak("book-alpha", track.link), 0.0)
        }
    }

    @Test
    fun the_phone_catalog_reads_cells_and_near_like_the_desktop_one() {
        val root = Files.createTempDirectory("n0-catalog").toFile()
        try {
            val cloud = File(root, "cloud")
            File(cloud, "cells").mkdirs()
            val manifestCells = JSONObject()
            for ((name, items) in cells()) {
                File(cloud, "cells/$name.json").writeText(JSONArray(items).toString())
                manifestCells.put(name, items.size)
            }
            CatalogSigning.writeManifest(cloud, JSONObject().put("format", MusicCatalog.FORMAT).put("version", 1).put("revision", "n0").put("grid", 5).put("cells", manifestCells))
            val phone = MusicCatalog(File(root, "cache"), cloud.absolutePath, publicKey = CatalogSigning.publicKey)
            assertEquals(strings(catalog.getJSONArray("nearOrder")), phone.near(SceneChooser.TARGET[0], SceneChooser.TARGET[1], 1).map { it.getString("link") })
            assertEquals(cells().getValue("0_0").size, phone.cell(0, 0).size)
            assertEquals(cells().getValue("2_1").size, phone.cell(2, 1).size)
            assertEquals(25, manifestCells.length())
        } finally {
            root.deleteRecursively()
        }
    }

    // ---- regex ------------------------------------------------------------------------------------------------------------------------------
    @Test
    fun every_cue_regex_and_helper_matches_python_on_the_shared_cases() {
        val cases = json("regex_cases.json").getJSONArray("cases")
        assertTrue(cases.length() > 200)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val text = case.getString("text")
            val label = "ca $index: ${text.take(60)}"
            fun check(name: String, actual: Boolean) = assertEquals("$label - $name", case.getBoolean(name), actual)
            check("SEPARATOR", Py.match(SceneCues.SEPARATOR, text))
            check("TIME_JUMP", Py.match(SceneCues.TIME_JUMP, text))
            check("CUE_SYMBOLS", Py.match(SceneCues.CUE_SYMBOLS, text))
            check("CUE_SUBHEAD", Py.match(SceneCues.CUE_SUBHEAD, text))
            check("CUE_BRACKETED", Py.match(SceneCues.CUE_BRACKETED, text))
            check("CUE_BRACKET_POV", Py.search(SceneCues.CUE_BRACKET_POV, text))
            check("CUE_DECOR", Py.match(SceneCues.CUE_DECOR, text))
            check("CUE_HEAD_WORD", Py.match(SceneCues.CUE_HEAD_WORD, text))
            check("CUE_NUMERAL", Py.match(SceneCues.CUE_NUMERAL, text))
            check("CUE_NAME_PUNCT", Py.search(SceneCues.CUE_NAME_PUNCT, text))
            check("CUE_VIET_LETTERS", Py.search(SceneCues.CUE_VIET_LETTERS, text))
            check("CUE_PLAIN_END", Py.search(SceneCues.CUE_PLAIN_END, text))
            check("CUE_TIME_PLACE", Py.match(SceneCues.CUE_TIME_PLACE, text))
            check("bracketIsSubhead", SceneCues.bracketIsSubhead(text))
            check("subheadWords", SceneCues.subheadWords(Py.strip(text)))
            check("isHeading", SceneSegmenter.isHeading(text))
            fun kind(name: String): String? = if (case.isNull(name)) null else case.getString(name)
            assertEquals("$label - cueKind", kind("cueKind"), SceneCues.cueKind(SceneSegment(0, text)))
            assertEquals("$label - cueKindHeading", kind("cueKindHeading"), SceneCues.cueKind(SceneSegment(0, text, "heading")))
            assertEquals("$label - hardBreak", kind("hardBreak"), SceneCues.hardBreak(SceneSegment(1, text), null))
            assertEquals("$label - hardBreakPlain", kind("hardBreakPlain"), SceneCues.hardBreak(SceneSegment(1, text), SceneSegment(0, "x", sceneBreak = true)))
            assertEquals(
                "$label - hardBreakCue", kind("hardBreakCue"),
                SceneCues.hardBreak(SceneSegment(1, text), SceneSegment(0, "x", sceneBreak = true, sceneSource = "cue", sceneCue = "subhead")),
            )
        }
    }

    // ---- bộ tách câu ------------------------------------------------------------------------------------------------------------------------
    @Test
    fun the_segmenter_splits_like_segment_chapter_text() {
        val cases = json("segmenter_cases.json").getJSONArray("cases")
        assertTrue(cases.length() > 40)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val rows = SceneSegmenter.segment(case.getString("text"))
            if (case.has("error")) continue // Python từ chối chương này (đứt chữ dài không có khoảng trắng); điện thoại vẫn tách, không văng
            val expected = case.getJSONArray("segments")
            val label = "ca $index: ${case.getString("text").take(60)}"
            assertEquals("$label - số câu", expected.length(), rows.size)
            for (at in 0 until expected.length()) {
                val want = expected.getJSONObject(at)
                assertEquals("$label - câu $at", want.getString("text"), rows[at].text)
                assertEquals("$label - id $at", want.getInt("id"), rows[at].seq)
                assertEquals("$label - cờ ngăn cảnh $at", want.getBoolean("sceneBreak"), rows[at].sceneBreak)
            }
        }
    }

    // ---- đoạn + bài + mốc -------------------------------------------------------------------------------------------------------------------
    private fun segmentsOf(chapter: JSONObject): List<SceneSegment> {
        val list = chapter.getJSONArray("segments")
        return (0 until list.length()).map {
            val item = list.getJSONObject(it)
            SceneSegment(item.getInt("id"), item.getString("text"), item.optString("kind", "narration"), item.optBoolean("sceneBreak"))
        }
    }

    private fun choiceOf(case: JSONObject): SceneChoice {
        val options = case.getJSONObject("options")
        val genre = options.optString("genre", "").takeIf { it.isNotEmpty() }
        val styles = genre?.let { name ->
            val raw = catalog.getJSONObject("taxonomy").getJSONObject("genres").getJSONObject(name).getJSONObject("styles")
            raw.keys().asSequence().associateWith { raw.getDouble(it) }
        }
        val pins = options.optJSONObject("pins")?.let { raw -> raw.keys().asSequence().associateWith { raw.getString(it) } } ?: emptyMap()
        val blocked = strings(options.optJSONArray("unavailable")).toSet()
        return SceneChoice(
            case.getString("bookKey"), options.optString("family", "").takeIf { it.isNotEmpty() }, styles, pins, strings(options.optJSONArray("banned")).toSet(),
            strings(options.optJSONArray("silenced")).toSet(), { link -> link !in blocked && sizeUsable(link) },
        )
    }

    /** Cỡ (`bytes`) theo mảnh `tracks/` của danh mục tự dựng (ô `cells/` không có) - hàm THẬT của điện thoại ([MusicCatalog.usable], như `DeviceScenes`). */
    private val sizeCatalog by lazy { MusicCatalog(Files.createTempDirectory("n0-size").toFile(), "https://unused.invalid/") }

    private fun sizeUsable(link: String): Boolean {
        val bytes = catalog.getJSONObject("trackBytes")
        return sizeCatalog.usable(link, if (bytes.has(link)) JSONObject().put("bytes", bytes.getLong(link)) else null)
    }

    private fun assertScene(label: String, want: JSONObject, got: ChosenScene) {
        assertEquals("$label chapterId", want.getInt("chapterId"), got.scene.chapterId)
        assertEquals("$label firstSegment", want.getInt("firstSegment"), got.scene.firstSegment)
        assertEquals("$label lastSegment", want.getInt("lastSegment"), got.scene.lastSegment)
        assertEquals("$label start", want.getDouble("start"), got.scene.start, 0.0)
        assertEquals("$label end", want.getDouble("end"), got.scene.end, 0.0)
        assertEquals("$label reason", want.getString("reason"), got.scene.reason)
        assertEquals("$label lines", want.getInt("lines"), got.scene.lines)
        assertEquals("$label key", want.getString("key"), got.key)
        assertEquals("$label pinned", want.getBoolean("pinned"), got.pinned)
        assertEquals("$label link", if (want.isNull("link")) null else want.getString("link"), got.link)
        assertEquals("$label distance", maybe(want, "distance"), got.distance)
        assertEquals("$label continued", want.getBoolean("continued"), got.continued)
        assertEquals("$label silenced", want.getBoolean("silenced"), got.silenced)
        assertEquals("$label pinUnavailable", want.getBoolean("pinUnavailable"), got.pinUnavailable)
        assertEquals("$label stepDb", maybe(want, "stepDb"), got.stepDb)
        assertEquals("$label stopAt", maybe(want, "stopAt"), got.stopAt)
        val siblings = want.getJSONArray("siblings")
        assertEquals("$label siblings", (0 until siblings.length()).map { siblings.getJSONObject(it).getDouble("at") to siblings.getJSONObject(it).getString("link") },
            got.siblings.map { it.at to it.link })
    }

    private fun assertCues(label: String, want: JSONArray, got: List<SceneCue>) {
        assertEquals("$label - số mốc", want.length(), got.size)
        for (index in 0 until want.length()) {
            val cue = want.getJSONObject(index)
            val actual = got[index]
            assertEquals("$label mốc $index start", cue.getDouble("start"), actual.start, 0.0)
            assertEquals("$label mốc $index end", cue.getDouble("end"), actual.end, 0.0)
            assertEquals("$label mốc $index link", cue.getString("link"), actual.link)
            assertEquals("$label mốc $index key", cue.getString("key"), actual.key)
            assertEquals("$label mốc $index sibling", cue.optBoolean("sibling"), actual.sibling)
            assertEquals("$label mốc $index tail", cue.optBoolean("tail"), actual.tail)
            val steps = cue.optJSONArray("steps") ?: JSONArray()
            assertEquals("$label mốc $index steps", (0 until steps.length()).map { steps.getJSONObject(it).getDouble("at") to steps.getJSONObject(it).getDouble("db") },
                actual.steps.map { it.at to it.db })
        }
    }

    /** Bài quá MUSIC_TRACK_MAX_MB (40 MB) nằm ngay đích nên thắng nếu không lọc cỡ: lọc rồi thì không đoạn nào dùng nó - như `server.music_track_available` của máy tính (cỡ đã biết). */
    @Test
    fun a_track_over_the_size_cap_is_never_chosen_and_one_exactly_at_the_cap_still_is() {
        assertEquals("trần của hai bên bằng nhau", catalog.getLong("maxBytes"), MusicCatalog.TRACK_MAX_BYTES)
        val bytes = catalog.getJSONObject("trackBytes")
        val over = bytes.keys().asSequence().filter { bytes.getLong(it) > MusicCatalog.TRACK_MAX_BYTES }.toSet()
        assertEquals(2, over.size)
        val case = json("case_alpha.json")
        val chapters = json(case.getString("chaptersFile")).getJSONArray("chapters")
        val scenes = (0 until chapters.length()).flatMap { SceneScenes.chapterScenes(chapters.getJSONObject(it).getInt("chapterId"), segmentsOf(chapters.getJSONObject(it))) }
        val tracks = near()
        val unfiltered = SceneChooser(SceneChoice(case.getString("bookKey"))) { _, _ -> tracks }.choose(scenes).mapNotNull { it.link }
        assertTrue("không lọc cỡ thì bài quá cỡ thắng (ví dụ có tác dụng)", unfiltered.any { it in over })
        val filtered = SceneChooser(choiceOf(case)) { _, _ -> tracks }.choose(scenes).mapNotNull { it.link }
        assertTrue(filtered.isNotEmpty() && filtered.none { it in over })
        assertTrue("bài đúng bằng trần vẫn dùng được", filtered.contains("https://example.invalid/n0/edge.mp3"))
    }

    /** Đoạn của một ca như đường thật: N0 (`SceneScenes.chapterScenes`) hay NN-lite (mục học sinh -> `applyStudent` -> sàn WEAK_MOOD, như `SceneBook`). */
    private fun scenesOf(case: JSONObject, chapters: JSONArray): List<SceneScene> {
        val student: SceneStudent? = if (case.optBoolean("student")) lite::chapterItems else null
        return (0 until chapters.length()).flatMap {
            val chapter = chapters.getJSONObject(it)
            SceneBook.chapterScenes(chapter.getInt("chapterId"), segmentsOf(chapter), student)
        }
    }

    private fun checkCase(name: String, seen: MutableSet<String>) {
        val case = json("case_$name.json")
        val chapters = json(case.getString("chaptersFile")).getJSONArray("chapters")
        val scenes = scenesOf(case, chapters)
        val seconds = HashMap<Int, Double>()
        for (index in 0 until chapters.length()) seconds[chapters.getJSONObject(index).getInt("chapterId")] = chapters.getJSONObject(index).getDouble("seconds")
        val chosen = SceneChooser(choiceOf(case)) { v, a -> nearAt(v, a) }.choose(scenes)
        val expected = case.getJSONObject("expected")
        val want = expected.getJSONArray("scenes")
        assertEquals("$name - số đoạn", want.length(), chosen.size)
        for (index in 0 until want.length()) {
            assertScene("$name đoạn $index", want.getJSONObject(index), chosen[index])
            seen.add(chosen[index].scene.reason)
        }
        for ((chapterId, total) in seconds) {
            assertCues("$name chương $chapterId (kẹp)", expected.getJSONObject("cues").getJSONArray(chapterId.toString()), SceneMusic.chapterCues(chosen, chapterId, total))
            assertCues("$name chương $chapterId (không kẹp)", expected.getJSONObject("cuesUnclamped").getJSONArray(chapterId.toString()), SceneMusic.chapterCues(chosen, chapterId, null))
        }
        // Vòng lặp của từng bài đã chọn (cùng hàm với trình phát).
        val byLink = HashMap<String, SceneTrack>()
        for (track in allTracks()) byLink.putIfAbsent(track.link, track)
        val loops = expected.getJSONObject("loops")
        for (link in loops.keys()) {
            val track = byLink[link]
            val bounds = MusicTimeline.loopBounds(MusicTimeline.TrackInfo(track?.seconds?.takeIf { it != 0.0 } ?: track?.duration, track?.audibleStart, track?.audibleEnd))
            val got = listOf(bounds.start, bounds.end, bounds.period).map { if (it.isInfinite()) null else it }
            val expectedLoop = loops.getJSONArray(link)
            assertEquals("$name vòng lặp $link", (0 until 3).map { if (expectedLoop.isNull(it)) null else expectedLoop.getDouble(it) }, got)
            assertEquals("$name vòng lặp $link (mờ chéo)", expectedLoop.getBoolean(3), bounds.crossfade)
        }
    }

    @Test
    fun every_case_gives_the_same_scenes_tracks_cues_and_loops_as_python() {
        val seen = HashSet<String>()
        for (name in listOf("alpha", "beta", "options", "family", "handmade")) checkCase(name, seen)
        // Bộ ví dụ phải chạm đủ các lý do cắt đoạn đã nêu trong đặc tả.
        assertTrue(seen.toString(), seen.containsAll(listOf("chapter_start", "heading", "separator", "subhead", "time_jump", "length")))
    }

    // ---- NN-lite: chữ -> 4 số -> mục chương -> đoạn học sinh -> bài, so một lần với Python --------------------------------------------------------------
    @Test
    fun the_nn_lite_items_and_scene_moods_equal_the_python_ones() {
        for (name in listOf("lite_alpha", "lite_family", "lite_handmade", "lite_mood")) {
            val case = json("case_$name.json")
            assertTrue(case.getBoolean("student"))
            val chapters = json(case.getString("chaptersFile")).getJSONArray("chapters")
            val student = case.getJSONObject("expected").getJSONObject("student")
            val wantItems = student.getJSONArray("items")
            val items = ArrayList<StudentItem>()
            for (index in 0 until chapters.length()) {
                val chapter = chapters.getJSONObject(index)
                val segments = segmentsOf(chapter)
                val base = SceneScenes.chapterScenes(chapter.getInt("chapterId"), segments)
                items.addAll(lite.chapterItems(chapter.getInt("chapterId"), segments, base)!!)
            }
            assertEquals("$name - số mục", wantItems.length(), items.size)
            for (index in items.indices) {
                val want = wantItems.getJSONObject(index)
                val got = items[index]
                val label = "$name mục $index"
                assertEquals("$label chapterId", want.getInt("chapterId"), got.chapterId)
                assertEquals("$label firstSegment", want.getInt("firstSegment"), got.firstSegment)
                assertEquals("$label lastSegment", want.getInt("lastSegment"), got.lastSegment)
                // Fixture làm tròn 9 số lẻ.
                assertEquals("$label dV", want.getDouble("dV"), got.dV, 1e-8)
                assertEquals("$label dE", want.getDouble("dE"), got.dE, 1e-8)
                assertEquals("$label dT", want.getDouble("dT"), got.dT, 1e-8)
                assertEquals("$label chapterV", want.getDouble("chapterV"), got.chapterV!!, 1e-8)
            }
            val moods = student.getJSONArray("moods")
            val scenes = scenesOf(case, chapters)
            assertEquals("$name - số đoạn", moods.length(), scenes.size)
            for (index in scenes.indices) {
                val want = moods.getJSONObject(index)
                val got = scenes[index]
                val label = "$name đoạn $index"
                assertEquals("$label chapterId", want.getInt("chapterId"), got.chapterId)
                assertEquals("$label firstSegment", want.getInt("firstSegment"), got.firstSegment)
                assertEquals("$label valence", want.getDouble("valence"), got.valence, 0.0)
                assertEquals("$label arousal", want.getDouble("arousal"), got.arousal, 0.0)
                assertEquals("$label tension", want.getDouble("tension"), got.tension, 0.0)
                assertEquals("$label confidence", want.getDouble("confidence"), got.confidence, 0.0)
                assertEquals("$label moodSource", want.getString("moodSource"), got.moodSource)
            }
        }
    }

    @Test
    fun the_nn_lite_cases_choose_the_same_tracks_cues_and_loops_as_python() {
        val seen = HashSet<String>()
        for (name in listOf("lite_alpha", "lite_family", "lite_handmade", "lite_mood")) checkCase(name, seen)
        assertTrue(seen.toString(), seen.containsAll(listOf("chapter_start", "separator", "subhead", "length")))
        // Đích V / E riêng của từng đoạn: bộ chọn phải đã hỏi nhiều ô danh mục và dùng bước âm lượng.
        val expected = json("case_lite_mood.json").getJSONObject("expected")
        val moods = expected.getJSONObject("student").getJSONArray("moods")
        assertTrue((0 until moods.length()).map { moods.getJSONObject(it).getDouble("valence") }.toSet().size > 3)
        val scenes = expected.getJSONArray("scenes")
        assertTrue("có bước âm lượng", (0 until scenes.length()).any { !scenes.getJSONObject(it).isNull("stepDb") })
    }

    @Test
    fun two_books_with_different_keys_choose_differently_and_each_is_repeatable() {
        val alpha = json("case_alpha.json").getJSONObject("expected").getJSONArray("scenes")
        val beta = json("case_beta.json").getJSONObject("expected").getJSONArray("scenes")
        val differing = (0 until alpha.length()).count { alpha.getJSONObject(it).opt("link") != beta.getJSONObject(it).opt("link") }
        assertTrue("hai cuốn mã khác nhau chọn bài giống hệt nhau ($differing đoạn khác)", differing > 0)
    }

    // ---- cả cuốn: chữ -> mốc, dựng từng chương --------------------------------------------------------------------------------------------------
    @Test
    fun a_book_built_chapter_by_chapter_from_text_gives_the_python_cues_with_reading_screen_segments() = buildBookFromText("alpha")

    @Test
    fun an_nn_lite_book_built_chapter_by_chapter_from_text_gives_the_python_cues() = buildBookFromText("lite_alpha")

    private fun buildBookFromText(name: String) {
        val case = json("case_$name.json")
        val student: SceneStudent? = if (case.optBoolean("student")) lite::chapterItems else null
        val chapters = json(case.getString("chaptersFile")).getJSONArray("chapters")
        val order = (0 until chapters.length()).map { chapters.getJSONObject(it).getInt("chapterId") }
        val texts = (0 until chapters.length()).associate { chapters.getJSONObject(it).getInt("chapterId") to chapters.getJSONObject(it).getString("text") }
        val root = Files.createTempDirectory("n0-book").toFile()
        try {
            val book = SceneBook(root, order, { texts[it] }, choiceOf(case), student = student) { v, a -> nearAt(v, a) }
            val expected = case.getJSONObject("expected")
            for (chapterId in order) {
                assertNull(book.read(chapterId))
                val record = book.build(chapterId)!!
                val response = book.response(record)
                val cues = response.getJSONArray("cues")
                val want = expected.getJSONObject("cues").getJSONArray(chapterId.toString())
                val heads = expected.getJSONObject("firstSegments").getJSONArray(chapterId.toString())
                assertEquals("chương $chapterId - số mốc", want.length(), cues.length())
                for (index in 0 until want.length()) {
                    val cue = want.getJSONObject(index)
                    val got = cues.getJSONObject(index)
                    assertEquals("chương $chapterId mốc $index start", cue.getDouble("start"), got.getDouble("start"), 0.0)
                    assertEquals("chương $chapterId mốc $index end", cue.getDouble("end"), got.getDouble("end"), 0.0)
                    assertEquals("chương $chapterId mốc $index link", cue.getString("link"), got.getString("link"))
                    assertEquals("chương $chapterId mốc $index key", cue.getString("key"), got.getString("key"))
                    assertEquals("chương $chapterId mốc $index sibling", cue.optBoolean("sibling"), got.optBoolean("sibling"))
                    assertEquals("chương $chapterId mốc $index tail", cue.optBoolean("tail"), got.optBoolean("tail"))
                    assertEquals("chương $chapterId mốc $index steps", (cue.optJSONArray("steps") ?: JSONArray()).toString(), (got.optJSONArray("steps") ?: JSONArray()).toString())
                    if (heads.isNull(index)) assertTrue("chương $chapterId mốc $index không có firstSegment", !got.has("firstSegment"))
                    else assertEquals("chương $chapterId mốc $index firstSegment", heads.getInt(index), got.getInt("firstSegment"))
                }
                assertEquals(chapters.getJSONObject(order.indexOf(chapterId)).getDouble("seconds"), response.getDouble("estSeconds"), 0.0)
                assertTrue(book.read(chapterId) != null) // đã nhớ trên đĩa, chữ không đổi thì dùng lại
            }
            // Chữ đổi thì bản ghi chương ấy hết hiệu lực.
            val changed = SceneBook(root, order, { id -> texts[id] + "\n\nThêm một dòng.\n" }, choiceOf(case), student = student) { v, a -> nearAt(v, a) }
            assertNull(changed.read(order.first()))
        } finally {
            root.deleteRecursively()
        }
    }

    /** Bài ĐÃ CHỌN mà tra cỡ thấy quá cỡ thì bị loại và chương chọn lại, mỗi vòng một lượt tra (`music_nnscene.build_chapter(verify=...)`); bộ chọn không bao giờ tra cỡ từng ứng viên. */
    @Test
    fun a_chosen_track_found_over_the_cap_is_dropped_and_the_chapter_is_chosen_again() {
        val case = json("case_alpha.json")
        val chapters = json(case.getString("chaptersFile")).getJSONArray("chapters")
        val order = (0 until chapters.length()).map { chapters.getJSONObject(it).getInt("chapterId") }
        val texts = (0 until chapters.length()).associate { chapters.getJSONObject(it).getInt("chapterId") to chapters.getJSONObject(it).getString("text") }
        val tracks = near()
        val first = order.first()
        val plain = Files.createTempDirectory("n0-verify-a").toFile()
        val capped = Files.createTempDirectory("n0-verify-b").toFile()
        try {
            val firstLinks = SceneBook(plain, order, { texts[it] }, SceneChoice(case.getString("bookKey"))) { _, _ -> tracks }.let { it.links(it.build(first)!!) }.toList()
            assertTrue(firstLinks.size >= 2)
            val victims = firstLinks.sorted().take(2)
            val banned = HashSet<String>()
            val asked = ArrayList<List<String>>()
            val book = SceneBook(
                capped, order, { texts[it] }, SceneChoice(case.getString("bookKey"), available = { it !in banned }),
                { links ->
                    asked.add(links)
                    val fresh = victims.filter { it in links && it !in banned }
                    banned.addAll(fresh.take(1)) // mỗi vòng chỉ phát hiện MỘT bài quá cỡ
                    fresh.isNotEmpty()
                },
            ) { _, _ -> tracks }
            val record = book.build(first)!!
            val links = book.links(record)
            assertEquals(victims.toSet(), banned)
            assertTrue("bài quá cỡ không còn trong plan", links.none { it in banned })
            assertEquals(3, asked.size)
            assertEquals("vòng cuối xác nhận đúng các bài đã chọn", links.toList(), asked.last())
            assertTrue("mỗi vòng một lượt, không trùng", asked.all { it.size == it.toSet().size })
        } finally {
            plain.deleteRecursively()
            capped.deleteRecursively()
        }
    }
}
