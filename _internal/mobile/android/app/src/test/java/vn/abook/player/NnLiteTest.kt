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
 * chữ -> token -> ô băm tuyệt đối -> đặc trưng (sai < 1e-12) -> 4 số và mục chương (sai < 1e-3), cùng file `nnlite.bin` đóng trong app.
 */
class NnLiteTest {
    companion object {
        private val folder = File("../../../tests/fixtures/music/nnlite")
        private val modelFile = File("../../../abook/webui/assets/nnlite.bin")
        private lateinit var text: JSONObject
        private lateinit var out: JSONObject
        private lateinit var model: NnLite

        @JvmStatic
        @BeforeClass
        fun load() {
            text = JSONObject(File(folder, "nnlite_text_fixture.json").readText(Charsets.UTF_8))
            out = JSONObject(File(folder, "nnlite_out_fixture.json").readText(Charsets.UTF_8))
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
}
