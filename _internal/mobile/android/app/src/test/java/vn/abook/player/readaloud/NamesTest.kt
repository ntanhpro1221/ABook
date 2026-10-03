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
        assertTrue(cases.length() >= 13)
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val array = case.getJSONArray("texts")
            val texts = (0 until array.length()).map { array.getString(it) }
            val sample = if (case.has("sample")) case.getInt("sample") else Names.SAMPLE_CHAPTERS
            val (counts, suffixed) = Names.scanNames(texts.asSequence().take(sample))
            val shares = Names.originShares(counts, suffixed)
            val want = if (case.isNull("origin")) null else case.getString("origin")
            assertEquals("ca $n", want, Names.bookOrigin(texts.asSequence(), sample))
            assertEquals("ca $n total", case.getInt("total"), shares.total)
            assertEquals("ca $n names", case.getInt("names"), shares.names)
            assertEquals("ca $n ja_names", case.getInt("ja_names"), shares.jaNames)
            assertEquals("ca $n ko_names", case.getInt("ko_names"), shares.koNames)
            assertEquals("ca $n honorific", case.getInt("honorific"), shares.honorific)
            assertEquals("ca $n honorific_names", case.getInt("honorific_names"), shares.honorificNames)
        }
    }

    @Test
    fun aJapaneseNameIsReadByTheRulesAndEnglishAndVietnameseWordsAreNot() {
        assertEquals(listOf("“Ha-ru-tô-cun,”", "Gia-ma-tô!", "(Ki-âu-cô)", "Xa-cu-ra…"), said("“Haruto-kun,” Yamato! (Kyouko) Sakura…", "ja"))
        assertEquals(listOf("Kate", "và", "Mike", "Rose,", "Anne", "Emma", "Hoa", "Tôi", "AI", "Aaaa", "Level"), said("Kate và Mike Rose, Anne Emma Hoa Tôi AI Aaaa Level", "ja"))
        assertEquals(VieneuUnits.tokens("Haruto đến"), said("Haruto đến", null))
        assertEquals(listOf("Xeo Gie-on", "gặp", "Gi Hô"), said("Seo-yeon gặp Ji-ho", "ko"))
        assertEquals(listOf("Gin-đô-nô", "Giu-ki-tan", "Câu-ni", "Hm", "Goblin", "Elf"), said("Jin-dono Yuki-tan Kou-nii Hm Goblin Elf", "ja"))
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
