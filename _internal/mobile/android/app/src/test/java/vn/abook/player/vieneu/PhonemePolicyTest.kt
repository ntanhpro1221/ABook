package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.json.JSONObject
import java.io.File

class PhonemePolicyTest {
    @Test fun aSyllableRetainsItsNucleusAndPunctuation() {
        assertEquals("hˈaː zˈi mˈɛ.", PhonemePolicy.repairSyllabicGi("ha gi me.", "hˈaː z mˈɛ."))
        assertEquals("zˈi zˈi?", PhonemePolicy.repairSyllabicGi("Gi-gi?", "z z?"))
        assertEquals("zˈi.", PhonemePolicy.repairSyllabicGi("gi.", "zˈi."))
    }

    @Test fun otherConsonantsAndAmbiguousCountsStayIntact() {
        for ((text, phones) in listOf("gì" to "zˈi2.", "giô" to "zˈo.", "gin" to "z.", "gi" to "z z.")) {
            assertEquals(phones, PhonemePolicy.repairSyllabicGi(text, phones))
        }
    }

    @Test fun theNativeFrontendPreservesTheSharedSyllablesAndEnglishDelivery() {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB") ?: "../../sea_g2p_jni/target/release/abook_sea_g2p.dll")
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT") ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        assumeTrue("Native frontend files required", library.isFile && dictionary.isFile)
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/phoneme_delivery/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { reader ->
            for (i in 0 until cases.length()) {
                val case = cases.getJSONObject(i)
                assertEquals(case.getString("text"), case.getString("phonemes"), reader.phonemize(listOf(case.getString("text"))))
            }
        }
    }
}
