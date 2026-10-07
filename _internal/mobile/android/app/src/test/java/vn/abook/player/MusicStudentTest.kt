package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Bộ phân tích nhạc "trò" trên điện thoại (MusicStudent*.kt) so với số của bản Python (webui/music_student.py, music_mel.py):
 * tests/fixtures/music_student/golden.json do `python -m tests.music_student_goldens` sinh. Phần cần ONNX Runtime thật + MediaCodec
 * (tháp CLAP, giải mã mp3) là bài thử trên máy Android: MusicStudentOnDeviceTest.
 */
class MusicStudentTest {
    private val dir = File("../../../tests/fixtures/music_student").also {
        if (!File(it, "golden.json").isFile) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile} (sinh lại bằng python -m tests.music_student_goldens)")
    }
    private val golden = JSONObject(File(dir, "golden.json").readText(Charsets.UTF_8))

    private fun doubles(array: JSONArray) = DoubleArray(array.length()) { array.getDouble(it) }

    /** Tín hiệu kiểm mel dựng bằng SỐ NGUYÊN - giống `lcg_signal` của tests/music_student_goldens.py từng bit. */
    private fun lcg(count: Int) = FloatArray(count) { i ->
        val noise = (((i.toLong() * 2_654_435_761L) and 0xFFFFFFFFL) shr 8).toDouble() / (1 shl 24).toDouble() - 0.5
        val saw = ((i % 100) / 100.0 - 0.5) * 0.5
        (noise * 0.25 + saw).toFloat()
    }

    // ---- npz ------------------------------------------------------------------------------------------------------------

    private fun npy(descr: String, shape: String, payload: ByteArray, fortran: Boolean = false, version: Int = 1): ByteArray {
        var header = "{'descr': '$descr', 'fortran_order': ${if (fortran) "True" else "False"}, 'shape': $shape, }"
        val prefix = if (version == 1) 10 else 12
        header += " ".repeat((64 - (prefix + header.length + 1) % 64) % 64) + "\n"
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0x93.toByte(), 'N'.code.toByte(), 'U'.code.toByte(), 'M'.code.toByte(), 'P'.code.toByte(), 'Y'.code.toByte(), version.toByte(), 0))
        val length = ByteBuffer.allocate(if (version == 1) 2 else 4).order(ByteOrder.LITTLE_ENDIAN)
        if (version == 1) length.putShort(header.length.toShort()) else length.putInt(header.length)
        out.write(length.array())
        out.write(header.toByteArray(Charsets.ISO_8859_1))
        out.write(payload)
        return out.toByteArray()
    }

    private fun floats(vararg values: Float) = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN).also { b -> values.forEach { b.putFloat(it) } }.array()

    @Test
    fun npy_arrays_of_numbers_and_text_are_read_in_c_order() {
        val matrix = npy("<f4", "(2, 3)", floats(1f, 2f, 3f, 4f, 5f, 6f))
        val parsed = Npz.parse(matrix)
        assertArrayEquals(intArrayOf(2, 3), parsed.shape)
        assertArrayEquals(doubleArrayOf(1.0, 2.0, 3.0, 4.0, 5.0, 6.0), parsed.doubles(), 0.0)
        val wide = ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN).putDouble(0.25).putDouble(-1e-300).array()
        assertArrayEquals(doubleArrayOf(0.25, -1e-300), Npz.parse(npy("<f8", "(2,)", wide, version = 2)).doubles(), 0.0)
        val scalar = Npz.parse(npy("<f4", "()", floats(7.5f)))
        assertEquals("mảng không chiều: một số", 1, scalar.size)
        // chữ: '<U5' = UTF-32LE, đệm 0 bên phải
        val text = ByteBuffer.allocate(2 * 5 * 4).order(ByteOrder.LITTLE_ENDIAN)
        for (word in listOf("joy", "nỗi")) {
            for (i in 0 until 5) text.putInt(if (i < word.length) word[i].code else 0)
        }
        assertEquals(listOf("joy", "nỗi"), Npz.parse(npy("<U5", "(2,)", text.array())).texts())
    }

    @Test
    fun an_npy_that_is_not_plain_c_order_numbers_or_text_is_refused_not_misread() {
        for ((label, bytes) in listOf(
            "thứ tự Fortran" to npy("<f4", "(2, 2)", floats(1f, 2f, 3f, 4f), fortran = true),
            "kiểu bool" to npy("|b1", "(2,)", byteArrayOf(1, 0)),
            "thiếu dữ liệu" to npy("<f4", "(4,)", floats(1f, 2f)),
            "không phải npy" to "PK nope".toByteArray(),
        )) {
            try {
                Npz.parse(bytes)
                fail("lẽ ra bị từ chối: $label")
            } catch (_: IllegalArgumentException) {
            }
        }
    }

    @Test
    fun an_npz_is_a_zip_of_npy_files_and_the_real_head_has_the_expected_shapes() {
        val zipped = ByteArrayOutputStream().also { sink ->
            ZipOutputStream(sink).use { zip ->
                zip.putNextEntry(ZipEntry("a.npy")); zip.write(npy("<f4", "(2,)", floats(1f, 2f))); zip.closeEntry()
                zip.putNextEntry(ZipEntry("b.npy")); zip.write(npy("<f4", "(1,)", floats(3f))); zip.closeEntry()
            }
        }.toByteArray()
        val read = Npz.read(zipped.inputStream())
        assertEquals(setOf("a", "b"), read.keys)
        assertArrayEquals(doubleArrayOf(3.0), read.getValue("b").doubles(), 0.0)

        val head = Npz.read(File(dir, "student_head_A.npz"))
        assertArrayEquals(intArrayOf(512), head.getValue("mu").shape)
        assertArrayEquals(intArrayOf(16, 512), head.getValue("coef").shape)
        assertEquals(13, head.getValue("emos").texts().size)
        assertEquals("peacefulness", head.getValue("emos").texts().first())
        assertArrayEquals(intArrayOf(2, 512), head.getValue("background_text").shape)
        assertEquals(7, head.getValue("family_names").texts().size)
        StudentHead(head) // đúng hình đầu A, không ném
    }

    @Test
    fun a_head_with_acoustic_columns_or_the_wrong_shape_is_refused() {
        val real = Npz.read(File(dir, "student_head_A.npz"))
        try {
            StudentHead(real + mapOf("names" to NpyArray(intArrayOf(1), null, listOf("rms"))))
            fail("đầu có cột âm học không phải đầu A")
        } catch (_: IllegalArgumentException) {
        }
        try {
            StudentHead(real + mapOf("mu" to NpyArray(intArrayOf(3), doubleArrayOf(0.0, 0.0, 0.0), null)))
            fail("sai hình")
        } catch (_: IllegalArgumentException) {
        }
        try {
            StudentHead(real - "coef")
            fail("thiếu mảng")
        } catch (_: IllegalArgumentException) {
        }
    }

    // ---- cửa sổ ---------------------------------------------------------------------------------------------------------

    @Test
    fun windows_start_exactly_where_the_python_rule_puts_them() {
        val cases = golden.getJSONArray("windows")
        assertTrue(cases.length() >= 10)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val starts = case.getJSONArray("starts")
            assertEquals("n=${case.getInt("n")}", List(starts.length()) { starts.getInt(it) }, MusicStudent.clapStarts(case.getInt("n")))
        }
    }

    // ---- mel ------------------------------------------------------------------------------------------------------------

    @Test
    fun log_mel_matches_the_numpy_extractor_for_a_full_window_and_a_repeatpadded_short_one() {
        for (label in listOf("full", "short")) {
            val want = golden.getJSONObject("mel").getJSONObject(label)
            val mel = MusicMel.logMel(lcg(want.getInt("samples")))
            assertEquals(MusicMel.FRAMES * MusicMel.N_MELS, mel.size)
            val frames = want.getJSONArray("frames")
            val rows = want.getJSONArray("rows")
            var worst = 0.0
            for (r in 0 until frames.length()) {
                val expected = doubles(rows.getJSONArray(r))
                for (m in 0 until MusicMel.N_MELS) worst = maxOf(worst, abs(mel[frames.getInt(r) * MusicMel.N_MELS + m] - expected[m]))
            }
            assertTrue("$label: lệch lớn nhất $worst dB (ngưỡng 1e-4)", worst < 1e-4)
            val total = mel.sumOf { it.toDouble() }
            assertEquals("$label: tổng", want.getDouble("sum"), total, abs(want.getDouble("sum")) * 1e-6)
            assertEquals("$label: tổng bình phương", want.getDouble("sumSquares"), mel.sumOf { it.toDouble() * it }, want.getDouble("sumSquares") * 1e-6)
        }
    }

    @Test
    fun the_packaged_preprocessor_config_is_the_one_the_mel_code_hardcodes() {
        MusicMel.checkConfig(File(dir, "preprocessor_config.json").readText(Charsets.UTF_8))
        try {
            MusicMel.checkConfig(File(dir, "preprocessor_config.json").readText(Charsets.UTF_8).replace("\"hop_length\": 480", "\"hop_length\": 512"))
            fail("cấu hình đổi thì phải báo")
        } catch (error: IllegalArgumentException) {
            assertTrue(error.message.orEmpty().contains("hop_length"))
        }
    }

    // ---- đầu trò --------------------------------------------------------------------------------------------------------

    @Test
    fun the_head_gives_the_python_numbers_for_the_same_embedding() {
        val head = StudentHead.load(File(dir, "student_head_A.npz"))
        val tracks = golden.getJSONObject("head")
        assertEquals(2, tracks.length())
        for (name in tracks.keys().asSequence()) {
            val entry = tracks.getJSONObject(name)
            val got = head.predict(doubles(entry.getJSONArray("embedding")))
            val want = entry.getJSONObject("result")
            for (key in listOf("valence", "arousal", "tension", "fitsUnderNarration", "confidence")) {
                assertEquals("$name $key", want.getDouble(key), got.getDouble(key), 1e-9)
            }
            for (axis in listOf("valence", "arousal", "tension")) {
                assertEquals("$name vetVar.$axis", want.getJSONObject("vetVar").getDouble(axis), got.getJSONObject("vetVar").getDouble(axis), 0.0)
            }
            assertEquals(want.getJSONObject("emotions").length(), got.getJSONObject("emotions").length())
            for (emotion in want.getJSONObject("emotions").keys().asSequence()) {
                assertEquals("$name $emotion", want.getJSONObject("emotions").getDouble(emotion), got.getJSONObject("emotions").getDouble(emotion), 1e-9)
            }
            assertEquals(want.getString("family"), got.getString("family"))
            // đầu dò lời hát (vox_head.npz cạnh đầu A): cùng hai khoá, cùng số với Python
            assertEquals("$name vocals", want.getDouble("vocals"), got.getDouble("vocals"), 1e-9)
            assertEquals("$name vocalsLikely", want.getBoolean("vocalsLikely"), got.getBoolean("vocalsLikely"))
        }
    }

    /** Đầu dò giả: coef = e_0, mu 0, sd 1, intercept 0 -> p = sigmoid(thành phần đầu của vector nhúng). */
    private fun vox(tau: Double = 0.5, size: Int = 512): Map<String, NpyArray> = mapOf(
        "mu" to NpyArray(intArrayOf(size), DoubleArray(size), null),
        "sd" to NpyArray(intArrayOf(size), DoubleArray(size) { 1.0 }, null),
        "coef" to NpyArray(intArrayOf(size), DoubleArray(size) { if (it == 0) 1.0 else 0.0 }, null),
        "intercept" to NpyArray(intArrayOf(1), doubleArrayOf(0.0), null),
        "tau" to NpyArray(intArrayOf(1), doubleArrayOf(tau), null),
    )

    private fun unit(first: Double): DoubleArray {
        val norm = Math.hypot(first, 1.0)
        return DoubleArray(512) { if (it == 0) first / norm else if (it == 1) 1.0 / norm else 0.0 }
    }

    @Test
    fun the_vox_head_flags_sung_vocals_from_the_same_embedding_and_is_absent_without_its_file() {
        val real = Npz.read(File(dir, "student_head_A.npz"))
        val head = StudentHead(real, vox())
        val sung = head.predict(unit(2.0))
        val plain = head.predict(unit(-2.0))
        assertTrue(sung.getBoolean("vocalsLikely"))
        assertFalse(plain.getBoolean("vocalsLikely"))
        assertEquals(Math.rint(1.0 / (1.0 + Math.exp(-unit(2.0)[0])) * 1000.0) / 1000.0, sung.getDouble("vocals"), 0.0)
        assertTrue(sung.getDouble("vocals") in 0.0..1.0 && plain.getDouble("vocals") in 0.0..1.0)
        assertFalse("tau của gói, không phải 0,5", StudentHead(real, vox(tau = 0.99)).predict(unit(2.0)).getBoolean("vocalsLikely"))
        val bare = StudentHead(real).predict(unit(2.0))
        assertFalse(bare.has("vocals") || bare.has("vocalsLikely"))
        for (key in listOf("valence", "arousal", "tension", "fitsUnderNarration", "family")) {
            assertEquals("khoá cũ giữ nguyên: $key", bare.get(key), sung.get(key))
        }
        try {
            StudentHead(real, vox(size = 3))
            fail("đầu dò sai hình")
        } catch (_: IllegalArgumentException) {
        }
    }

    @Test
    fun the_head_result_survives_the_store_cleaning_with_its_variance_and_a_family_inside_the_list() {
        val head = StudentHead.load(File(dir, "student_head_A.npz"))
        val first = golden.getJSONObject("head").keys().next()
        val raw = head.predict(doubles(golden.getJSONObject("head").getJSONObject(first).getJSONArray("embedding")))
        val clean = MusicStore.cleanAnalysis(raw)!!
        assertEquals(setOf("valence", "arousal", "tension"), clean.getJSONObject("vetVar").keys().asSequence().toSet())
        assertEquals(13, clean.getJSONObject("emotions").length())
        assertTrue(clean.getString("family") in StudentHead.FAMILIES)
        assertTrue(clean.has("background"))
        assertTrue("đường onnx không đo speechBand", !clean.has("speechBand"))
    }

    @Test
    fun embeddings_are_normalised_per_window_averaged_and_normalised_again() {
        val result = MusicStudent.embedding(listOf(doubleArrayOf(3.0, 0.0), doubleArrayOf(0.0, 10.0)))
        assertEquals(1.0, Math.hypot(result[0], result[1]), 1e-12)
        assertEquals("hai cửa sổ cùng nặng dù độ dài vector khác", result[0], result[1], 1e-12)
    }

    // ---- 48 kHz ---------------------------------------------------------------------------------------------------------

    private fun tone(rate: Int, hz: Double, seconds: Double) = FloatArray((rate * seconds).toInt()) { (0.5 * sin(2 * PI * hz * it / rate)).toFloat() }

    private fun rms(samples: FloatArray, from: Int, to: Int) = Math.sqrt((from until to).sumOf { samples[it].toDouble() * samples[it] } / (to - from))

    @Test
    fun resampling_keeps_a_tone_at_the_same_pitch_and_level_from_the_usual_rates() {
        for (rate in listOf(44_100, 22_050, 32_000, 96_000, 8_000, 16_000, 11_025)) {
            val out = Resampler.window(FloatPcm(rate, tone(rate, 1000.0, 1.0)), 0, 40_000)
            var worst = 0.0
            for (j in 2_000 until 38_000) worst = maxOf(worst, abs(out[j] - 0.5 * sin(2 * PI * 1000.0 * j / 48_000)))
            assertTrue("$rate Hz: lệch lớn nhất $worst", worst < 2e-3)
        }
    }

    @Test
    fun resampling_down_removes_what_cannot_be_represented_instead_of_folding_it_back() {
        // 30 kHz ở 96 kHz phải biến mất ở 48 kHz (Nyquist 24 kHz), không gập về 18 kHz
        val out = Resampler.window(FloatPcm(96_000, tone(96_000, 30_000.0, 1.0)), 0, 40_000)
        assertTrue("còn ${rms(out, 2_000, 38_000)}", rms(out, 2_000, 38_000) < 1e-3)
        val kept = Resampler.window(FloatPcm(96_000, tone(96_000, 10_000.0, 1.0)), 0, 40_000)
        assertEquals(0.5 / Math.sqrt(2.0), rms(kept, 2_000, 38_000), 2e-3)
    }

    @Test
    fun resampling_a_window_from_the_middle_equals_cutting_the_whole_conversion() {
        val pcm = FloatPcm(44_100, tone(44_100, 440.0, 3.0))
        val whole = Resampler.window(pcm, 0, 120_000)
        val part = Resampler.window(pcm, 50_000, 30_000)
        for (j in 0 until 30_000) assertEquals(whole[50_000 + j].toDouble(), part[j].toDouble(), 1e-6)
        assertEquals("làm tròn lên như ffmpeg xả nốt", 48_000L, Resampler.outputFrames(44_100, 44_100))
        assertEquals(144_000L, Resampler.outputFrames(132_300, 44_100))
        assertEquals(16_000L, Resampler.outputFrames(16_000, 48_000))
    }

    @Test
    fun a_48k_source_is_passed_through_and_outside_the_track_is_silence() {
        val samples = FloatArray(1000) { it / 1000f }
        val out = Resampler.window(FloatPcm(48_000, samples), 900, 200)
        assertEquals(0.95f, out[50], 0f)
        assertEquals(0f, out[150], 0f)
    }

    @Test
    fun the_spool_gives_back_what_was_written_with_zeros_outside() {
        val file = Files.createTempFile("spool", ".f32").toFile()
        val spool = PcmSpool(file, 44_100)
        val samples = FloatArray(100_000) { it * 0.001f }
        spool.append(samples, 60_000)
        spool.append(samples.copyOfRange(60_000, 100_000), 40_000)
        assertEquals(100_000L, spool.frames)
        val out = FloatArray(50)
        spool.read(99_990, out, 50)
        assertEquals(samples[99_990], out[0], 0f)
        assertEquals(samples[99_999], out[9], 0f)
        assertEquals(0f, out[10], 0f)
        spool.read(-5, out, 10)
        assertEquals(0f, out[4], 0f)
        assertEquals(samples[0], out[5], 0f)
        spool.close()
        assertTrue("đóng thì xoá file tạm", !file.exists())
    }

    // ---- cả đường ---------------------------------------------------------------------------------------------------------

    private class FakeTower : ClapTower {
        val seen = ArrayList<FloatArray>()

        override fun embed(logMel: FloatArray): DoubleArray {
            seen.add(logMel)
            return DoubleArray(512) { 1.0 + it % 7 } // cùng vector cho mọi cửa sổ
        }
    }

    private fun student(tower: ClapTower, pcm: PcmSource?) =
        MusicStudent(StudentHead.load(File(dir, "student_head_A.npz")), tower) { pcm }

    @Test
    fun a_long_track_gives_three_windows_a_short_one_gives_one_and_under_three_seconds_gives_nothing() {
        val tower = FakeTower()
        val long = student(tower, FloatPcm(44_100, tone(44_100, 220.0, 20.0))).analyze(File("x.mp3"))!!
        assertEquals(3, tower.seen.size)
        assertTrue(long.has("valence") && long.has("vetVar") && long.has("emotions"))
        tower.seen.clear()
        assertNotNull(student(tower, FloatPcm(22_050, tone(22_050, 220.0, 4.0))).analyze(File("x.mp3")))
        assertEquals(1, tower.seen.size)
        tower.seen.clear()
        assertNull("ngắn hơn 3 giây: không phân tích, không bịa", student(tower, FloatPcm(44_100, tone(44_100, 220.0, 2.9))).analyze(File("x.mp3")))
        assertTrue(tower.seen.isEmpty())
        assertNull("không giải mã được", student(tower, null).analyze(File("x.mp3")))
    }

    @Test
    fun the_window_fed_to_the_tower_is_the_log_mel_of_the_resampled_audio() {
        val tower = FakeTower()
        val pcm = FloatPcm(48_000, tone(48_000, 440.0, 12.0))
        student(tower, pcm).analyze(File("x.mp3"))
        val starts = MusicStudent.clapStarts(576_000)
        assertEquals(starts.size, tower.seen.size)
        val direct = MusicMel.logMel(Resampler.window(pcm, starts[1].toLong(), 480_000))
        assertArrayEquals(direct, tower.seen[1], 0f)
    }
}
