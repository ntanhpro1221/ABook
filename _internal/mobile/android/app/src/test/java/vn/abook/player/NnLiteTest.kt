package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.BeforeClass
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * NN-lite trên điện thoại (NnLite.kt) phải ra GIỐNG HỆT bản Python (music_nnlite.py) trên hai bộ ví dụ dùng chung `tests/fixtures/music/nnlite/` (chữ dựng sẵn):
 * chữ -> token -> ô băm tuyệt đối -> đặc trưng (sai < 1e-12) -> 4 số và mục chương (sai < 1e-3), cùng file `nnlite.bin` đóng trong app; thêm `lb_fixture.json`: khối (tuyệt đối),
 * hồ sơ khối (sai < 1e-3) và ranh cảnh LB (tuyệt đối); `lvj_fixture.json`: chapterP và mức chương (sai < 1e-3), dời mức LVJ (sai <= 1e-9).
 */
class NnLiteTest {
    companion object {
        private val folder = File("../../../tests/fixtures/music/nnlite")
        private val modelFile = File("../../../abook/webui/assets/nnlite.bin")
        private lateinit var text: JSONObject
        private lateinit var out: JSONObject
        private lateinit var lb: JSONObject
        private lateinit var lvj: JSONObject
        private lateinit var model: NnLite

        @JvmStatic
        @BeforeClass
        fun load() {
            text = JSONObject(File(folder, "nnlite_text_fixture.json").readText(Charsets.UTF_8))
            out = JSONObject(File(folder, "nnlite_out_fixture.json").readText(Charsets.UTF_8))
            lb = JSONObject(File(folder, "lb_fixture.json").readText(Charsets.UTF_8))
            lvj = JSONObject(File(folder, "lvj_fixture.json").readText(Charsets.UTF_8))
            model = NnLite.parse(modelFile.readBytes())
        }

        /** `repr` của numpy ("np.float64(0.5)") hay của float, do bộ ví dụ ghi thành chuỗi. */
        fun number(raw: String): Double {
            val match = Regex("(?:np\\.float64\\()?(-?[0-9.e+-]+|nan|inf|-inf)\\)?").matchEntire(raw) ?: throw AssertionError(raw)
            return match.groupValues[1].toDouble()
        }
    }

    private fun ints(array: JSONArray): List<Int> = (0 until array.length()).map { array.getInt(it) }

    private fun strings(array: JSONArray): List<String> = (0 until array.length()).map { array.getString(it) }

    // ---- bảng khoảng trắng + dấu câu ----------------------------------------------------------------------------------------------------------
    @Test
    fun whitespace_is_the_python_isspace_set_not_javas() {
        val want = ints(text.getJSONArray("whitespace")).toSet()
        // Duyệt hết mặt phẳng 0 và 1: Py.split tách đúng ở điểm mã nào Python `isspace` đúng, kể cả U+001C-1F, U+0085, U+3000 (Java isWhitespace hiểu khác).
        for (code in 0..0x1FFFF) {
            if (code in 0xD800..0xDFFF) continue
            val glued = "a" + String(Character.toChars(code)) + "b"
            val pieces = Py.split(glued).size
            assertEquals("U+%04X".format(code), if (code in want) 2 else 1, pieces)
        }
    }

    @Test
    fun punctuation_and_dialog_tables_equal_the_python_ones() {
        assertEquals(ints(text.getJSONArray("punct")).sorted(), NnLite.PUNCT.sorted())
        assertEquals(ints(text.getJSONArray("dialog")).sorted(), NnLite.DIALOG.sorted())
    }

    // ---- chữ -> đặc trưng ----------------------------------------------------------------------------------------------------------------------
    @Test
    fun tokens_hashes_features_and_dense_match_python_on_every_text_sample() {
        val samples = text.getJSONArray("samples")
        assertTrue(samples.length() >= 20)
        for (index in 0 until samples.length()) {
            val sample = samples.getJSONObject(index)
            val raw = sample.getString("text")
            val label = "ca $index: ${raw.take(30)}"
            assertEquals("$label - normalize", sample.getString("normalized"), NnLite.normalize(raw))
            val words = NnLite.tokens(sample.getString("normalized"))
            assertEquals("$label - tokens", strings(sample.getJSONArray("tokens")), words)
            val wantEntries = sample.getJSONArray("entries")
            val entries = NnLite.entries(words)
            assertEquals("$label - số mục băm", wantEntries.length(), entries.size)
            for (at in 0 until wantEntries.length()) {
                val row = wantEntries.getJSONArray(at)
                val hash = NnLite.fnv1a(entries[at])
                assertEquals("$label - mục $at", row.getString(0), entries[at])
                assertEquals("$label - băm $at", row.getLong(1), hash)
                assertEquals("$label - ô 2^18 $at", row.getLong(2), hash % (1L shl 18))
                assertEquals("$label - ô 2^17 $at", row.getLong(3), hash % (1L shl 17))
            }
            for ((buckets, key) in listOf((1 shl 18) to "features_2_18", (1 shl 17) to "features_2_17")) {
                val want = sample.getJSONArray(key)
                val got = NnLite.features(raw, buckets)
                assertEquals("$label - $key số ô", want.length(), got.size)
                assertEquals("$label - $key ô tăng dần", got.map { it.first }.sorted(), got.map { it.first })
                for (at in 0 until want.length()) {
                    val row = want.getJSONArray(at)
                    assertEquals("$label - $key ô $at", row.getInt(0), got[at].first)
                    assertEquals("$label - $key giá trị $at", number(row.getString(1)), got[at].second, 1e-12)
                }
            }
            val dense = NnLite.dense(raw)
            val wantDense = sample.getJSONArray("dense")
            assertEquals("$label - dense", wantDense.length(), dense.size)
            for (at in dense.indices) assertEquals("$label - dense $at", number(wantDense.getString(at)), dense[at], 1e-12)
            assertEquals("$label - weight", sample.getInt("weight"), NnLite.weight(raw))
        }
    }

    // ---- 4 số + mục chương ----------------------------------------------------------------------------------------------------------------------
    @Test
    fun the_four_numbers_and_the_chapter_items_match_python() {
        val tolerance = out.getDouble("tolerance")
        val scenes = out.getJSONArray("scenes")
        for (index in 0 until scenes.length()) {
            val scene = scenes.getJSONObject(index)
            val got = model.scene(scene.getString("text"))
            val want = scene.getJSONArray("out")
            assertEquals(4, got.size)
            for (at in 0 until 4) assertEquals("cảnh $index số $at", number(want.getString(at)), got[at], tolerance)
            assertEquals("cảnh $index weight", scene.getInt("weight"), NnLite.weight(scene.getString("text")))
        }
        val chapters = out.getJSONArray("chapters")
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            val items = model.chapter(ints(chapter.getJSONArray("scenes")).map { scenes.getJSONObject(it).getString("text") })
            val want = chapter.getJSONArray("items")
            assertEquals("chương $index", want.length(), items.size)
            for (at in 0 until want.length()) {
                val row = want.getJSONObject(at)
                for ((slot, key) in listOf("dV", "dE", "dT", "chapterV").withIndex()) {
                    assertEquals("chương $index mục $at $key", number(row.getString(key)), items[at][slot], tolerance)
                }
            }
        }
        // Chương một cảnh: độ lệch 0, mức chương vẫn có.
        val single = model.chapter(listOf(scenes.getJSONObject(27).getString("text")))
        assertEquals(listOf(0.0, 0.0, 0.0), single.single().take(3))
        assertTrue(model.chapter(emptyList()).isEmpty())
    }

    @Test
    fun the_half_float_decoder_is_exact_on_every_bit_pattern() {
        assertEquals(0.0, NnLite.halfToDouble(0x0000), 0.0)
        assertEquals(1.0, NnLite.halfToDouble(0x3C00), 0.0)
        assertEquals(-2.0, NnLite.halfToDouble(0xC000), 0.0)
        assertEquals(65504.0, NnLite.halfToDouble(0x7BFF), 0.0)
        assertEquals(Math.scalb(1.0, -24), NnLite.halfToDouble(0x0001), 0.0)
        assertEquals(Math.scalb(1.0, -14), NnLite.halfToDouble(0x0400), 0.0)
        assertTrue(NnLite.halfToDouble(0x7C00).isInfinite() && NnLite.halfToDouble(0x7E00).isNaN())
        assertEquals(0.333251953125, NnLite.halfToDouble(0x3555), 0.0)
        // Short âm của JVM (0x8000..0xFFFF) đi qua `.toInt()` thành số âm: phải che về 16 bit.
        assertEquals(-1.0, NnLite.halfToDouble(0xBC00.toShort().toInt()), 0.0)
    }

    // ---- file hỏng -----------------------------------------------------------------------------------------------------------------------------
    @Test
    fun a_corrupt_model_is_refused() {
        val raw = modelFile.readBytes()
        assertEquals(out.getLong("model_bytes"), raw.size.toLong())
        fun refused(label: String, bytes: ByteArray) {
            try {
                NnLite.parse(bytes)
                fail("$label: phải bị từ chối")
            } catch (_: IllegalArgumentException) {
            }
        }
        refused("rỗng", ByteArray(0))
        refused("magic", "XXXX".toByteArray() + raw.copyOfRange(4, raw.size))
        refused("cỡ", raw.copyOf(raw.size - 4))
        refused("hình", ByteBuffer.wrap(raw.copyOf()).order(ByteOrder.LITTLE_ENDIAN).also { it.putInt(8, 5) }.array())
        assertNotNull(NnLite.parse(raw))
    }

    // ---- ghép mục với đoạn ---------------------------------------------------------------------------------------------------------------------
    @Test
    fun chapter_items_follow_the_scenes_and_give_up_when_a_scene_does_not_match() {
        val scenes = out.getJSONArray("scenes")
        val segments = (0 until 6).map { SceneSegment(it, scenes.getJSONObject(it).getString("text")) }
        val base = listOf(
            SceneScene(1, 0, 2, 0.0, 70.0, "chapter_start", 3),
            SceneScene(1, 3, 5, 70.0, 150.0, "subhead", 3),
        )
        val items = model.chapterItems(1, segments, base)!!
        assertEquals(2, items.size)
        assertEquals(listOf(0 to 2, 3 to 5), items.map { it.firstSegment to it.lastSegment })
        assertEquals(items[0].chapterV, items[1].chapterV)
        val direct = model.chapter(listOf(NnLite.sceneText(segments, 0, 2), NnLite.sceneText(segments, 3, 5)))
        assertEquals(direct[0][0], items[0].dV, 0.0)
        assertEquals(direct[1][2], items[1].dT, 0.0)
        assertNull(model.chapterItems(1, segments, listOf(base[0], base[1].copy(lastSegment = 99))))
        assertNull(model.chapterItems(1, segments, emptyList()))
    }

    // ---- ranh cảnh LB (SPEC_lb_app) -----------------------------------------------------------------------------------------------------------
    private fun segmentsOf(chapter: JSONObject, unique: Boolean = false): List<SceneSegment> {
        val rows = chapter.getJSONArray("segments")
        return (0 until rows.length()).map { SceneSegment(if (unique) it + 1 else rows.getJSONObject(it).getInt("id"), rows.getJSONObject(it).getString("text")) }
    }

    private fun sized(vararg words: Int): List<SceneSegment> = words.mapIndexed { index, count -> SceneSegment(index + 1, List(count) { "chữ" }.joinToString(" ")) }

    @Test
    fun lb_blocks_profiles_and_bounds_match_python_on_the_shared_fixture() {
        assertEquals(NnLite.LB_LAMBDA, lb.getDouble("lambda"), 0.0)
        assertEquals(NnLite.LB_BLOCK_WORDS, lb.getInt("block_words"))
        assertEquals(NnLite.LB_MIN_BLOCKS, lb.getInt("min_blocks"))
        assertEquals(modelFile.length(), lb.getLong("model_bytes"))
        val tolerance = lb.getDouble("tolerance_profile")
        val chapters = lb.getJSONArray("chapters")
        assertTrue(chapters.length() >= 5)
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            val name = chapter.getString("name")
            val segments = segmentsOf(chapter)
            val spans = NnLite.blocks(segments)
            val wantBlocks = chapter.getJSONArray("blocks")
            assertEquals("$name: số khối", wantBlocks.length(), spans.size)
            for ((at, span) in spans.withIndex()) assertEquals("$name: khối $at", ints(wantBlocks.getJSONArray(at)), listOf(span.first, span.second))
            val profile = model.blockProfile(segments, spans)
            val wantProfile = chapter.getJSONArray("profile")
            for ((at, row) in profile.withIndex()) {
                for (axis in 0 until 3) assertEquals("$name: hồ sơ khối $at trục $axis", number(wantProfile.getJSONArray(at).getString(axis)), row[axis], tolerance)
            }
            assertEquals("$name: ranh", ints(chapter.getJSONArray("bounds")), model.boundIds(segments))
        }
    }

    @Test
    fun lb_blocks_close_at_150_words_and_a_short_tail_joins_the_last_block() {
        assertEquals(listOf(0 to 2), NnLite.blocks(sized(100, 60, 40)))
        assertEquals(listOf(0 to 1, 2 to 2), NnLite.blocks(sized(100, 60, 80)))
        assertEquals(listOf(0 to 2), NnLite.blocks(sized(100, 60, 74)))
        assertEquals(listOf(0 to 1, 2 to 2), NnLite.blocks(sized(100, 60, 75)))
        assertEquals(listOf(0 to 1, 2 to 2), NnLite.blocks(sized(149, 1, 150)))
        assertEquals(listOf(0 to 1), NnLite.blocks(sized(20, 30)))
        assertTrue(NnLite.blocks(emptyList()).isEmpty())
        assertEquals(listOf(0 to 3), NnLite.blocks(listOf(SceneSegment(1, ""), SceneSegment(2, "   "), SceneSegment(3, "\u00a0\u3000")) + sized(200)))
        // Khoảng trắng của Python (NBSP, ideographic space, em space) cũng ngăn chữ.
        val odd = SceneSegment(1, "a\u00a0b\u3000c\u2003d e")
        assertEquals(listOf(0 to 29), NnLite.blocks(List(30) { odd }))
        assertEquals(listOf(0 to 30), NnLite.blocks(List(29) { odd } + listOf(SceneSegment(2, "x"), SceneSegment(3, "y"))))
    }

    @Test
    fun lb_fewer_than_four_blocks_never_cut_and_a_step_in_the_profile_is_found() {
        fun rows(vararg x: Double) = x.map { doubleArrayOf(it, it, it) }
        val wild = listOf(doubleArrayOf(0.0, 0.0, 0.0), doubleArrayOf(9.0, 9.0, 9.0), doubleArrayOf(-9.0, 5.0, 0.0))
        assertTrue(NnLite.partition(wild).isEmpty() && NnLite.partition(wild.take(2)).isEmpty() && NnLite.partition(emptyList()).isEmpty())
        assertEquals(listOf(3), NnLite.partition(rows(0.0, 0.0, 0.0, 2.0, 2.0, 2.0)))
        assertTrue("3 khối: không ranh", NnLite.partition(rows(0.0, 2.0, 2.0)).isEmpty())
        assertTrue("bốn khối xen kẽ", NnLite.partition(rows(0.0, 3.0, 0.0, 3.0)).isEmpty())
        assertTrue("đều một màu", NnLite.partition(rows(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)).isEmpty())
        assertTrue("bước nhỏ hơn phí ranh", NnLite.partition(rows(0.0, 0.0, 0.0, 0.0, 0.5, 0.5, 0.5, 0.5)).isEmpty())
        assertEquals(listOf(4), NnLite.partition(rows(0.0, 0.0, 0.0, 0.0, 1.2, 1.2, 1.2, 1.2)))
    }

    @Test
    fun lb_a_uniform_chapter_has_no_bounds() {
        val text = out.getJSONArray("scenes").getJSONObject(0).getString("text")
        val segments = List(60) { SceneSegment(10 * it + 1, text) }
        assertTrue(model.boundIds(segments).isEmpty() && model.sceneBounds(segments).isEmpty())
    }

    @Test
    fun lb_a_cue_wins_a_spot_the_lite_bound_also_claims() {
        val segments = listOf(SceneSegment(1, "Mở đầu."), SceneSegment(2, "Câu hai."), SceneSegment(3, "Tiêu đề.", "heading"), SceneSegment(4, "Câu bốn."))
        val lite = mapOf(NnLite.LB_SOURCE to mapOf(3 to NnLite.LB_REASON, 4 to NnLite.LB_REASON))
        val withBreaks = SceneCues.withSceneBreaks(segments, lite)
        assertEquals("cue" to "heading", withBreaks[1].sceneSource to withBreaks[1].sceneCue)
        assertEquals("lite" to "mood_shift", withBreaks[2].sceneSource to withBreaks[2].sceneCue)
        assertTrue(!withBreaks[0].sceneBreak)
        assertEquals("mood_shift", SceneCues.hardBreak(segments[3], withBreaks[2]))
        assertEquals("không nguồn ngoài: như trước", SceneCues.withSceneBreaks(segments).map { it.sceneSource }, listOf(null, "cue", null, null))
    }

    @Test
    fun lb_bounds_split_the_lite_scenes_the_student_guesses_on_the_new_scenes_and_n0_is_untouched() {
        val chapters = lb.getJSONArray("chapters")
        val chapter = (0 until chapters.length()).map { chapters.getJSONObject(it) }.first { it.getJSONArray("bounds").length() >= 2 }
        val segments = segmentsOf(chapter, unique = true)
        val spans = NnLite.blocks(segments)
        val cuts = NnLite.partition(model.blockProfile(segments, spans)).map { segments[spans[it].first].id }
        assertTrue(cuts.size >= 2)
        val seen = ArrayList<List<SceneScene>>()
        val student: SceneStudent = { id, segs, base -> seen.add(base); model.chapterItems(id, segs, base) }
        val plain = SceneBook.chapterScenes(7, segments, student)
        seen.clear()
        val lite = SceneBook.chapterScenes(7, segments, student, model::sceneBounds)
        assertEquals("học sinh chạy MỘT lần", 1, seen.size)
        val shifts = seen[0].filter { it.reason == "mood_shift" }.map { it.firstSegment }
        assertTrue(shifts.isNotEmpty() && cuts.containsAll(shifts))
        assertTrue(plain.map { it.firstSegment } != lite.map { it.firstSegment })
        assertEquals(seen[0].map { it.firstSegment }, lite.map { it.firstSegment })
        assertTrue(lite.all { it.moodSource == "student" && it.confidence >= SceneChooser.WEAK_MOOD })
        // N0 (không học sinh) và học sinh bỏ chương: không ranh LB.
        val n0 = SceneBook.chapterScenes(7, segments, null)
        assertEquals(n0, SceneBook.chapterScenes(7, segments, null, model::sceneBounds))
        assertEquals(n0, SceneBook.chapterScenes(7, segments, { _, _, _ -> null }, model::sceneBounds))
        assertTrue("khoá đệm plan đổi để plan cũ không dùng lại", SceneBook.ENGINE_VERSION >= 5)
    }

    // ---- mức chương chung LVJ (SPEC_lvj_app) --------------------------------------------------------------------------------------------------
    private fun doubles(array: JSONArray): List<Double> = (0 until array.length()).map { array.getDouble(it) }

    @Test
    fun the_lvj_constants_are_the_frozen_ones_of_the_shared_fixture() {
        val rows = lvj.getJSONArray("coef_rows_pV_pE_pT_q_1__cols_V_E_T")
        assertEquals(5, rows.length())
        for (row in 0 until 5) assertEquals("hàng $row", doubles(rows.getJSONArray(row)), SceneScenes.LVJ_COEF[row].toList())
        assertEquals(lvj.getInt("model_bytes"), modelFile.length().toInt())
    }

    @Test
    fun the_lvj_chapter_p_and_level_equal_the_shared_fixture() {
        val tolerance = lvj.getDouble("tolerance_chapter")
        val chapters = lvj.getJSONArray("chapters")
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            val texts = strings(chapter.getJSONArray("texts"))
            assertEquals(ints(chapter.getJSONArray("weights")), texts.map { NnLite.weight(it) })
            val rows = model.chapter(texts)
            assertEquals(texts.size, rows.size)
            val wantP = doubles(chapter.getJSONArray("chapterP"))
            for (row in rows) {
                for (axis in 0 until 4) assertEquals("${chapter.getString("name")} chapterP $axis", wantP[axis], row[4 + axis], tolerance)
                assertEquals(rows[0].toList().subList(4, 8), row.toList().subList(4, 8))
            }
            val level = SceneScenes.lvjLevel(doubleArrayOf(rows[0][4], rows[0][5], rows[0][6], rows[0][7]))
            val wantLevel = doubles(chapter.getJSONArray("level"))
            for (axis in 0 until 3) assertEquals("${chapter.getString("name")} mức $axis", wantLevel[axis], level[axis], tolerance)
        }
    }

    @Test
    fun the_lvj_shift_equals_the_shared_fixture_exactly() {
        val tolerance = lvj.getDouble("tolerance_shift")
        val cases = lvj.getJSONArray("shifts")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val raw = case.getJSONArray("scenes")
            val scenes = (0 until raw.length()).map {
                val scene = raw.getJSONObject(it)
                SceneScene(1, it, it, scene.getDouble("start"), scene.getDouble("end"), "length", 1,
                    valence = scene.getDouble("valence"), arousal = scene.getDouble("arousal"), tension = scene.getDouble("tension"))
            }
            val shifted = SceneScenes.shiftToLevel(scenes, doubles(case.getJSONArray("level")).toDoubleArray())
            val want = case.getJSONArray("out")
            assertEquals("ca $index - số đoạn", want.length(), shifted.size)
            for (at in shifted.indices) {
                assertEquals("ca $index đoạn $at valence", want.getJSONObject(at).getDouble("valence"), shifted[at].valence, tolerance)
                assertEquals("ca $index đoạn $at arousal", want.getJSONObject(at).getDouble("arousal"), shifted[at].arousal, tolerance)
                assertEquals("ca $index đoạn $at tension", want.getJSONObject(at).getDouble("tension"), shifted[at].tension, tolerance)
            }
        }
    }

    private fun StudentItem.withP(p: DoubleArray?) = StudentItem(chapterId, firstSegment, lastSegment, dV, dE, dT, chapterV, p)

    @Test
    fun an_item_without_chapter_p_gives_apply_student_exactly_what_it_gave_before() {
        val segments = (0 until 6).map { SceneSegment(it, out.getJSONArray("scenes").getJSONObject(it).getString("text")) }
        val base = listOf(
            SceneScene(1, 0, 2, 0.0, 70.0, "chapter_start", 3),
            SceneScene(1, 3, 5, 70.0, 150.0, "subhead", 3),
        )
        val items = model.chapterItems(1, segments, base)!!
        assertTrue(items.all { it.chapterP != null && it.chapterP!!.size == 4 })
        val plain = SceneScenes.applyStudent(base, items.map { it.withP(null) })!!
        val withLvj = SceneScenes.applyStudent(base, items)!!
        // Đường cũ = bước student thuần; LVJ chỉ dời mức và đúng bằng bước dời trên đoạn student.
        assertEquals(withLvj, SceneScenes.shiftToLevel(plain, SceneScenes.lvjLevel(items[0].chapterP!!)))
        assertTrue(plain.zip(withLvj).any { (before, after) -> before.valence != after.valence || before.arousal != after.arousal || before.tension != after.tension })
        // Thiếu / hỏng chapterP ở BẤT KỲ mục nào: cả chương như cũ.
        assertEquals(plain, SceneScenes.applyStudent(base, listOf(items[0], items[1].withP(null))))
        assertEquals(plain, SceneScenes.applyStudent(base, items.map { it.withP(doubleArrayOf(0.0, 0.0, 0.0, Double.NaN)) }))
        assertEquals(plain, SceneScenes.applyStudent(base, items.map { it.withP(doubleArrayOf(1.0, 2.0)) }))
    }
}
