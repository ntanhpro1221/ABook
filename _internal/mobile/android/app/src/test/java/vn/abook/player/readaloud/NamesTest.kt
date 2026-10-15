package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits
import java.io.File

/**
 * Tên Nhật / Hàn đọc theo luật phiên âm (Names.kt) trên bộ ví dụ dùng chung với Python (tests/fixtures/vieneu/android/text.json, phần `origins`; các khúc có `origin`
 * nằm trong VieneuParityTest) và danh sách từ Anh (EnglishWords.kt = abook/readaloud/english_words.txt).
 */
class NamesTest {
    private val dir = File("../../../tests/fixtures/vieneu/android")
    private fun said(text: String, origin: String?) = VieneuUnits.spokenTokens(VieneuUnits.tokens(text), origin)

    @Test
    fun theEnglishListIsTheSameAsThePythonFile() {
        val python = File("../../../abook/readaloud/english_words.txt").readText(Charsets.UTF_8).split('\n').filter { it.isNotEmpty() }
        assertEquals(python.size, EnglishWords.ALL.size)
        assertEquals(python.toSet(), EnglishWords.ALL)
        assertTrue("kate" in EnglishWords.ALL && "mike" in EnglishWords.ALL && "hana" !in EnglishWords.ALL && "haruto" !in EnglishWords.ALL)
    }

    @Test
    fun everySharedOriginCaseGivesPythonsAnswer() {
        val cases = JSONObject(File(dir, "text.json").readText(Charsets.UTF_8)).getJSONArray("origins")
        assertTrue(cases.length() >= 23)
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val array = case.getJSONArray("texts")
            val texts = (0 until array.length()).map { array.getString(it) }
            val sample = if (case.has("sample")) case.getInt("sample") else Names.SAMPLE_CHAPTERS
            val scan = Names.scanNames(texts.asSequence().take(sample))
            val shares = Names.originShares(scan.found, scan.suffixed, scan.terms)
            val want = if (case.isNull("origin")) null else case.getString("origin")
            assertEquals("ca $n", want, Names.bookOrigin(texts.asSequence(), sample))
            assertEquals("ca $n total", case.getInt("total"), shares.total)
            assertEquals("ca $n names", case.getInt("names"), shares.names)
            assertEquals("ca $n ja_names", case.getInt("ja_names"), shares.jaNames)
            assertEquals("ca $n ko_names", case.getInt("ko_names"), shares.koNames)
            assertEquals("ca $n honorific", case.getInt("honorific"), shares.honorific)
            assertEquals("ca $n honorific_names", case.getInt("honorific_names"), shares.honorificNames)
            assertEquals("ca $n ja_marked", case.getInt("ja_marked"), shares.jaMarked)
            assertEquals("ca $n ko_marked", case.getInt("ko_marked"), shares.koMarked)
            assertEquals("ca $n ja_terms", case.getInt("ja_terms"), shares.jaTerms)
            assertEquals("ca $n ko_terms", case.getInt("ko_terms"), shares.koTerms)
        }
    }

    @Test
    fun aJapaneseNameIsReadByTheRulesAndEnglishAndVietnameseWordsAreNot() {
        assertEquals(listOf("“Ha-ru-tô-cun,”", "Gia-ma-tô!", "(Ki-âu-cô)", "Xa-cu-ra…"), said("“Haruto-kun,” Yamato! (Kyouko) Sakura…", "ja"))
        assertEquals(listOf("Kate", "và", "Mike", "Rose,", "Anne", "Emma", "Hoa", "Tôi", "a i", "a… a", "Level"), said("Kate và Mike Rose, Anne Emma Hoa Tôi AI Aaaa Level", "ja"))
        assertEquals(VieneuUnits.tokens("Haruto đến"), said("Haruto đến", null))
        assertEquals(listOf("Xeo-gion", "gặp", "Gi-hô"), said("Seo-yeon gặp Ji-ho", "ko"))
        assertEquals(listOf("Gin-đô-nô", "Giu-ki-tan", "Câu-ni", "hừm", "Goblin", "Elf"), said("Jin-dono Yuki-tan Kou-nii Hm Goblin Elf", "ja"))
    }

    @Test
    fun aLoneOSyllableOfANameIsMarkedSoTheNormaliserKeepsItAnO() {
        assertEquals(listOf("o_-xu-ki-xan,", "o_-ca-gia-ma,", "o_-ni-xa-ma"), said("Otsuki-san, Okayama, Onii-sama", "ja"))
        assertEquals(listOf("Ca-o_-ri,", "o_-cô-nô-mi-a-ki"), said("Kaori, okonomiyaki", "ja"))
        assertEquals("o_-xu-ki-xan", Names.loneSyllable("O-xu-ki-xan"))
        assertEquals("a-ri", Names.loneSyllable("A-ri"))
        assertEquals("ca-o_-ri", Names.loneSyllable("ca-o-ri"))
        assertEquals("o_", Names.loneSyllable("o"))
        assertNull(Names.loneSyllable(null))
    }

    @Test
    fun aNameGluedToAnOpeningBracketIsJudgedAlone() {
        assertEquals(listOf("nhìn", "Gi-ghen(trong", "Lupin", "ba),", "rồi"), said("nhìn Jigen(trong Lupin III), rồi", "ja"))
    }

    @Test
    fun theReadingTagIsEmptyWhenNothingChanges() {
        assertEquals("ja", VieneuUnits.readingTag("Haruto đến.", "ja"))
        assertEquals("", VieneuUnits.readingTag("Haruto đến.", null))
        assertEquals("", VieneuUnits.readingTag("Kate đến.", "ja"))
    }

    @Test
    fun theCacheKeyOnlyChangesForTextTheOriginChanges() {
        assertEquals(ClipCache.key("vieneu", "nano/Adam", "t"), ClipCache.key("vieneu", "nano/Adam", "t", ""))
        assertTrue(ClipCache.key("vieneu", "nano/Adam", "t", "ja") != ClipCache.key("vieneu", "nano/Adam", "t"))
        assertEquals("", ClipCache.reading("edge:vi-VN-X", "Haruto đến.", "ja"))
        assertEquals("ja", ClipCache.reading("vieneu:nano/Adam", "Haruto đến.", "ja"))
        assertEquals("", ClipCache.reading("vieneu:nano/Adam", "Kate đến.", "ja"))
    }

    @Test
    fun theBooksOriginIsGuessedOnceAndTheUsersChoiceWins() {
        val file = File.createTempFile("choices", ".json").also { it.deleteOnExit() }
        val choices = VoiceChoices(file)
        val names = "Haruto Yuki Sakura Kyouko Takeshi Hiroshi Akira Kenji Yamato Naoki Satoshi Ayaka"
        val text = (1..10).joinToString(" ") { names.split(' ').joinToString(" ") { name -> "$name nói." } }
        var calls = 0
        val sample = { calls++; sequenceOf(text) }
        assertEquals("ja", choices.originFor("b1", sample))
        assertEquals("ja", choices.originFor("b1", sample))
        assertEquals(1, calls)
        choices.setOriginOverride("b1", "none")
        assertEquals("", choices.originFor("b1", sample))
        choices.setOriginOverride("b1", "ko")
        assertEquals("ko", choices.originFor("b1", sample))
        choices.setOriginOverride("b1", null)
        assertEquals("ja", VoiceChoices(file).originFor("b1", sample))
        assertEquals(1, calls)
        assertEquals("", choices.originFor("b2") { sequenceOf("Hoa đi chợ.") })
        assertNull(Names.bookOrigin(emptySequence()))
    }
}
