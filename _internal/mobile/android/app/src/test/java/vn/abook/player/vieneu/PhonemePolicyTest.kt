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

    private fun sharedCases() = JSONObject(File("../../../tests/fixtures/readaloud/shared_vietnamese/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")

    @Test fun theSentenceDecidesWhichSharedWordsAreVietnamese() {
        val data = JSONObject(File("../../../abook/readaloud/english_policy.json").readText(Charsets.UTF_8)).getJSONObject("shared_vietnamese")
        fun list(key: String) = data.getJSONArray(key).let { a -> (0 until a.length()).map(a::getString) }
        val listed = (list("words") + list("echo") + list("pair_words")).toSet()
        val word = Regex("(<en>.*?</en>)|([\\p{L}\\p{N}_]+(?:['’][\\p{L}\\p{N}_]+)*)")
        val cases = sharedCases()
        assertTrue(cases.length() >= 30)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val text = case.getString("text")
            val words = word.findAll(text.lowercase()).mapNotNull { it.groups[2]?.value }.filter { it in listed }.toList()
            val expected = case.getJSONArray("claimed").let { a -> (0 until a.length()).map(a::getString) }
            assertEquals(text, expected, PhonemePolicy.vietnameseShared(text.lowercase(), PhonemePolicy.capitalised(text)).map { words[it] })
        }
    }

    @Test fun aCapitalInsideASentenceIsANameAndTheFirstWordIsNot() {
        assertEquals(setOf("do", "cheol", "iron", "man", "lucy"), PhonemePolicy.capitalised("Leo nhìn Do Cheol-ho. “Bay đi, Iron Man!” — Sang nhà Lucy?"))
        assertEquals(setOf("m", "go"), PhonemePolicy.capitalised("<en>G M</en> nói Go."))
        assertEquals(listOf(0), PhonemePolicy.vietnameseShared("leo lên xe đi."))
        assertEquals(emptyList<Int>(), PhonemePolicy.vietnameseShared("leo lên xe đi.", setOf("leo")))
    }

    @Test fun theNativeFrontendKeepsSharedWordsVietnamese() {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB") ?: "../../sea_g2p_jni/target/release/abook_sea_g2p.dll")
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT") ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        assumeTrue("Native frontend files required", library.isFile && dictionary.isFile)
        val cases = sharedCases()
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { reader ->
            for (i in 0 until cases.length()) {
                val case = cases.getJSONObject(i)
                assertEquals(case.getString("text"), case.getString("phonemes"), reader.phonemize(listOf(case.getString("text"))))
            }
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
