package vn.abook.player.vieneu

import org.json.JSONObject
import org.junit.AfterClass
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.BeforeClass
import org.junit.Test
import java.io.File

/**
 * sea-g2p through the JNI wrapper (mobile/sea_g2p_jni, built for this computer by scripts/prepare_sea_g2p_android.py) gives the desktop's
 * phonemes byte for byte on the shared set (tests/fixtures/vieneu/android/text.json: 209 sentences + multi-sentence units - numbers, dates,
 * money, units, abbreviations, Roman numerals, foreign names, URLs, punctuation). The phone runs the same crate built for Android
 * (VieneuOnDeviceTest repeats this on the device).
 *
 * Needs the host library and the 63 MB dictionary; skipped (with the reason) when they are not on this machine:
 * `ABOOK_SEA_G2P_LIB` (default mobile/sea_g2p_jni/target/release/abook_sea_g2p.dll|libabook_sea_g2p.so) and `ABOOK_SEA_G2P_DICT`
 * (default: sea_g2p.bin of the runtime venv's sea-g2p).
 */
class SeaG2pParityTest {
    companion object {
        private var g2p: SeaG2p? = null

        private fun library(): File {
            System.getenv("ABOOK_SEA_G2P_LIB")?.let { return File(it) }
            val name = if (System.getProperty("os.name").lowercase().contains("win")) "abook_sea_g2p.dll" else "libabook_sea_g2p.so"
            return File("../../sea_g2p_jni/target/release/$name")
        }

        private fun dictionary(): File {
            System.getenv("ABOOK_SEA_G2P_DICT")?.let { return File(it) }
            return listOf("../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin", "../../../../../ABook/_internal/runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
                .map(::File).firstOrNull { it.isFile } ?: File("sea_g2p.bin")
        }

        @BeforeClass
        @JvmStatic
        fun open() {
            val lib = library()
            val dict = dictionary()
            if (lib.isFile && dict.isFile) g2p = SeaG2p(lib.absoluteFile, dict.absoluteFile)
        }

        @AfterClass
        @JvmStatic
        fun close() {
            g2p?.close()
        }
    }

    private fun reader(): SeaG2p {
        assumeTrue("sea-g2p host library or dictionary missing (${library().absolutePath}, ${dictionary().absolutePath})", g2p != null)
        return g2p!!
    }

    private val fixture = JSONObject(File("../../../tests/fixtures/vieneu/android/text.json").readText(Charsets.UTF_8))

    @Test
    fun everyUnitGetsTheDesktopsPhonemes() {
        val g2p = reader()
        val cases = fixture.getJSONArray("g2p")
        assertTrue(fixture.getInt("sentences") >= 200)
        val wrong = ArrayList<String>()
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val sentences = case.getJSONArray("sentences").let { array -> (0 until array.length()).map { array.getString(it) } }
            val got = g2p.phonemize(sentences)
            if (got != case.getString("phonemes")) wrong.add("$sentences\n  desktop: ${case.getString("phonemes")}\n  phone:   $got")
        }
        assertTrue("${wrong.size} of ${cases.length()} differ:\n" + wrong.take(5).joinToString("\n"), wrong.isEmpty())
    }

    @Test
    fun normaliserAndPunctuationRuleMatch() {
        val g2p = reader()
        val cases = fixture.getJSONArray("normalize")
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val text = case.getString("text")
            assertEquals(text, case.getString("plain"), g2p.normalize(text, false))
            assertEquals(text, case.getString("punc"), g2p.normalize(text, true))
            assertEquals(text, case.getString("puncNorm"), g2p.puncNorm(text))
        }
    }

    @Test
    fun unitsOfParagraphsGetTheDesktopsPhonemes() {
        val g2p = reader()
        val cases = fixture.getJSONArray("units")
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val (_, units) = VieneuUnits.units(case.getString("text"), case.getInt("max"))
            val want = case.getJSONArray("units")
            for (i in units.indices) assertEquals(want.getJSONObject(i).getString("phonemes"), g2p.phonemize(units[i].pieces))
        }
    }
}
