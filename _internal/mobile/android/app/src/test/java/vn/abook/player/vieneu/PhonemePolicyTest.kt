package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
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

    /** A case's `rulings` (contexts {key: "v" / "e"}, names, foreign) in the shape `sharedWords` of book.json carries them. */
    private fun rulingsOf(case: JSONObject): PhonemePolicy.Rulings? =
        case.optJSONObject("rulings")?.let { given ->
            val full = JSONObject(given.toString()).put("version", 2)
            if (!full.has("contexts")) full.put("contexts", JSONObject())
            if (!full.has("names")) full.put("names", org.json.JSONArray())
            if (!full.has("foreign")) full.put("foreign", org.json.JSONArray())
            PhonemePolicy.Rulings.of(full)
        }

    private fun sourceOf(case: JSONObject): String? = if (case.has("source")) case.getString("source") else null

    private fun sharedCases() = JSONObject(File("../../../tests/fixtures/readaloud/shared_vietnamese/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")

    @Test fun theSentenceDecidesWhichSharedWordsAreVietnamese() {
        val table = File("../../../abook/readaloud/shared_words.json").readText(Charsets.UTF_8).trim()
        assertEquals("SharedWords.kt is not the table: run scripts/build_shared_words.py", table, SharedWords.JSON)
        val listed = JSONObject(table).getJSONObject("words").keys().asSequence().toSet()
        val word = Regex("(<en>.*?</en>)|([\\p{L}\\p{N}_]+(?:['’][\\p{L}\\p{N}_]+)*)")
        val cases = sharedCases()
        assertTrue(cases.length() >= 30)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val text = case.getString("text")
            val words = word.findAll(text.lowercase()).map { m -> m.groups[1]?.value?.let { it.substring(4, it.length - 5).trim() } ?: m.groups[2]!!.value }
                .filter { it in listed }.toList()
            val expected = case.getJSONArray("claimed").let { a -> (0 until a.length()).map(a::getString) }
            val capitals = PhonemePolicy.capitalised(text, sourceOf(case))
            assertEquals(text, expected, PhonemePolicy.vietnameseShared(text.lowercase(), capitals, rulingsOf(case)).map { words[it] })
            case.optJSONArray("doubtful")?.let { a ->  // what tier 1 leaves to the second tier
                assertEquals(text, (0 until a.length()).map(a::getString),
                    PhonemePolicy.sharedWordVerdicts(text.lowercase(), capitals, rulingsOf(case)).filter { !it.sure }.map { it.word })
            }
        }
    }

    @Test fun aShoutedWordIsANameUnlessItsWholeSentenceIsShouted() {
        assertEquals(setOf("ban"), PhonemePolicy.capitalised("Hắn bị admin BAN nick rồi."))
        assertEquals(setOf("lalaport", "tokyo", "bay"), PhonemePolicy.capitalised("Cửa hàng ở Lalaport TOKYO BAY."))
        for (shout in listOf("LUNG LAY! LUNG LAY!", "“BAY ĐI!” Cô hét.", "Hắn hét: BAY ĐI!")) assertEquals(shout, emptySet<String>(), PhonemePolicy.capitalised(shout))
        assertEquals(setOf("ban"), PhonemePolicy.capitalised("Hắn bị admin ban nick rồi.", "Hắn bị admin BAN nick rồi."))
        assertEquals(emptySet<String>(), PhonemePolicy.capitalised("LUNG lay! LUNG lay!", "LUNG LAY! LUNG LAY!"))
        assertEquals(setOf("lung"), PhonemePolicy.capitalised("LUNG lay! LUNG lay!"))
    }

    @Test fun theBooksAnswersDecideWhereTierOneDoubts() {
        fun verdicts(text: String, capitals: Set<String> = emptySet(), rulings: PhonemePolicy.Rulings? = null) =
            PhonemePolicy.sharedWordVerdicts(text, capitals, rulings).map { listOf(it.word, it.vietnamese, it.sure, it.who) }
        val key = "^|do|trans sắp"
        assertEquals(listOf(key), PhonemePolicy.sharedWordContexts("do trans sắp thi."))
        assertEquals(listOf(listOf("do", false, false, "table")), verdicts("do trans sắp thi."))
        assertEquals(listOf(listOf("do", true, true, "ruling")), verdicts("do trans sắp thi.", rulings = PhonemePolicy.Rulings(mapOf(key to true))))
        assertEquals(listOf(listOf("do", false, true, "ruling")), verdicts("do trans sắp thi.", rulings = PhonemePolicy.Rulings(mapOf(key to false))))
        assertEquals(listOf(listOf("do", false, false, "table")), verdicts("danh hiệu kỵ sĩ tự do.", setOf("do")))
        assertEquals(listOf(listOf("man", false, true, "table")), verdicts("iron man đã đến.", setOf("man")))
        val names = PhonemePolicy.Rulings(names = setOf("an", "can"))
        assertEquals(List(2) { listOf("an", true, true, "roster") }, verdicts("an an.", setOf("an"), names))
        assertEquals(listOf(listOf("an", true, true, "roster")), verdicts("an nói.", rulings = names))
        assertEquals(listOf(listOf("can", true, true, "roster")), verdicts("cô hỏi: can đâu rồi?", rulings = names))
        assertEquals(listOf("can", false, true, "table"), verdicts("can you help me?", rulings = names)[0])
        assertEquals(listOf("can", false, true, "table"), verdicts("i can do it.", rulings = names)[0])
        assertEquals(List(2) { listOf("an", false, true, "table") }, verdicts("an an.", setOf("an")))
        // the clip key only moves where the book has an answer for a table word of the passage
        val rulings = PhonemePolicy.Rulings(mapOf(key to true), setOf("an"))
        assertEquals("", PhonemePolicy.rulingsTag("Do trans sắp thi.", null))
        assertEquals("", PhonemePolicy.rulingsTag("Trời hôm nay đẹp quá.", rulings))
        assertTrue(Regex("w[0-9a-f]{16}").matches(PhonemePolicy.rulingsTag("Do trans sắp thi.", rulings)))
        assertEquals(null, PhonemePolicy.Rulings.of(JSONObject("{\"version\":1,\"contexts\":{},\"names\":[\"an\"],\"foreign\":[]}")))
        assertEquals(null, PhonemePolicy.Rulings.of(JSONObject("{\"version\":2,\"contexts\":{},\"names\":[\"an\"]}")))  // no `foreign`: not this shape
        val read = PhonemePolicy.Rulings.of(JSONObject("{\"version\":2,\"contexts\":{\"a|do|b\":\"v\"},\"names\":[\"an\"],\"foreign\":[\"dan\"]}"))!!
        assertEquals(setOf("an"), read.names)
        assertEquals(setOf("dan"), read.foreign)
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
        G2pTestInputs.requireOrSkip("Native frontend files required", library.isFile && dictionary.isFile)
        val cases = sharedCases()
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { reader ->
            for (i in 0 until cases.length()) {
                val case = cases.getJSONObject(i)
                assertEquals(case.getString("text"), case.getString("phonemes"), reader.phonemize(listOf(case.getString("text")), sourceOf(case), rulingsOf(case)))
            }
        }
    }

    @Test fun theNativeFrontendPreservesTheSharedSyllablesAndEnglishDelivery() {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB") ?: "../../sea_g2p_jni/target/release/abook_sea_g2p.dll")
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT") ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        G2pTestInputs.requireOrSkip("Native frontend files required", library.isFile && dictionary.isFile)
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/phoneme_delivery/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { reader ->
            for (i in 0 until cases.length()) {
                val case = cases.getJSONObject(i)
                assertEquals(case.getString("text"), case.getString("phonemes"), reader.phonemize(listOf(case.getString("text")), sourceOf(case), rulingsOf(case)))
            }
        }
    }
}
