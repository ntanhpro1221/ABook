package vn.abook.player.vieneu

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/** Exercise the pinned phone JNI frontend, including generated English spans. */
class EnglishDirectFrontendTest {
    @Test
    fun generatedSpansReachTheEnglishPhonemesThroughNativeFrontend() {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB") ?: "../../sea_g2p_jni/target/release/abook_sea_g2p.dll")
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT") ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        G2pTestInputs.requireOrSkip("Native frontend files required", library.isFile && dictionary.isFile)
        val fixture = JSONObject(File("../../../tests/fixtures/readaloud/english_direct/frontend.json").readText(Charsets.UTF_8))
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { g2p ->
            val cases = fixture.getJSONArray("cases")
            for (i in 0 until cases.length()) {
                val case = cases.getJSONObject(i)
                val text = case.getString("text")
                assertEquals(text, case.getString("phonemes"), g2p.phonemize(listOf(text)))
            }
        }
    }
}
