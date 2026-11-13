package vn.abook.player.vieneu

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.readaloud.BookReadings
import vn.abook.player.readaloud.JapanesePolicy

/**
 * Real names where the name-sound table and the split Japanese-name road meet (tests/fixtures/readaloud/real_names/cases.json, the file
 * tests/test_real_names.py reads): the phone says the same string as the desktop and Studio and hands the model the same phonemes.
 */
class RealNamesTest {
    private class Case(val text: String, val said: String, val phonemes: String, val tag: String)

    private class Book(val origin: String?, val shared: JSONObject, val proven: Map<String, String>, val cases: List<Case>) {
        val texts get() = cases.map { it.text }
        /** What [vn.abook.player.readaloud.ReadAloud.readingsOf] holds: [names] the book proves, under Studio's `sharedWords` (no listener reading). */
        fun readings(names: Map<String, String> = proven): Map<String, String> = BookReadings.over(names, BookReadings.of(emptyMap(), shared))
    }

    private val fixture = JSONObject(File("../../../tests/fixtures/readaloud/real_names/cases.json").readText(Charsets.UTF_8))
    private val roster = listOf("Dan", "Ji-eun", "Hyun Woo", "Heizaemon", "Yuki")
    private val books = fixture.getJSONArray("books").let { all ->
        (0 until all.length()).map { i ->
            val book = all.getJSONObject(i)
            val proven = book.getJSONObject("proven")
            val cases = book.getJSONArray("cases")
            Book(if (book.isNull("origin")) null else book.getString("origin"), book.getJSONObject("sharedWords"),
                proven.keys().asSequence().associateWith(proven::getString),
                (0 until cases.length()).map { j -> cases.getJSONObject(j).let { Case(it.getString("text"), it.getString("said"), it.getString("phonemes"), it.getString("tag")) } })
        }
    }

    private fun unitOf(case: Case, book: Book, readings: Map<String, String> = book.readings()): Pair<List<String>, VieneuUnits.Unit> {
        val (tokens, units) = VieneuUnits.units(case.text, VieneuSpeaker.MAX_CHARS.getValue("turbo"), book.origin, readings, directEnglish = true)
        assertEquals(case.text, 1, units.size)
        assertEquals(case.text, 0 to tokens.lastIndex, units[0].first to units[0].last)
        return tokens to units[0]
    }

    @Test fun theFixtureIsTheOneRosterInThreeBooks() {
        assertEquals(roster.toSet(), fixture.getJSONObject("roster").keys().asSequence().toSet())
        assertEquals(listOf("ja", "ko", null), books.map { it.origin })
        for (book in books) {
            val shown = book.texts.joinToString(" ")
            for (word in listOf("Ji-eun", "Hyun Woo", "Heizaemon", "Dan", "pin", "veo", "boa", "K", "APP")) assertTrue("${book.origin} $word", word in shown)
        }
        assertTrue(books[0].texts.joinToString(" ").let { "YUKI" in it && "HYUN WOO" in it })
    }

    @Test fun theBookProvesTheSameNamesAndKeepsStudiosRulings() {
        for (book in books) {
            assertEquals(book.origin, book.proven, JapanesePolicy.bookNameReadings(book.texts.asSequence(), roster, book.origin))
            val readings = book.readings()
            // the Western name spelled like a Vietnamese syllable is Studio's ruling: it must survive the proven names laid under it
            assertEquals(book.origin, setOf("dan"), (readings as BookReadings).rulings?.foreign)
            val names = book.shared.getJSONObject("readings")
            assertEquals(book.origin, book.proven + names.keys().asSequence().associateWith(names::getString), readings.toMap())
        }
        assertEquals(mapOf("HYUN" to "Hi-un", "WOO" to "Woo", "YUKI" to "Giu-ki"), books[0].proven)
    }

    @Test fun thePhoneSaysTheSameStringAndKeysTheSameReading() {
        for (book in books) for (case in book.cases) {
            val (tokens, unit) = unitOf(case, book)
            assertEquals(case.text, case.said, unit.pieces.joinToString(" "))
            assertEquals(case.text, case.said, VieneuUnits.spokenTokens(tokens, book.origin, book.readings(), directEnglish = true).filter { it.isNotEmpty() }.joinToString(" "))
            assertEquals(case.text, case.tag, VieneuUnits.readingTag(case.text, book.origin, directEnglish = true))
            assertTrue(case.tag, case.tag.endsWith("jp-fallback6"))
        }
    }

    /** The phone has no roster: it proves names from the text alone ([vn.abook.player.readaloud.VoiceChoices.nameReadingsFor]) and still says every case the same. */
    @Test fun thePhonesOwnProvenNamesSayTheSame() {
        for (book in books) {
            val own = JapanesePolicy.bookNameReadings(book.texts.asSequence(), origin = book.origin)
            assertEquals(book.origin, book.proven - "WOO", own)
            for (case in book.cases) assertEquals(case.text, case.said, unitOf(case, book, book.readings(own)).second.pieces.joinToString(" "))
        }
    }

    @Test fun eachNameAndWordIsSaidItsOwnWay() {
        for (book in books) {
            val said = book.cases.associate { it.text to it.said }
            assertEquals("Gi-ưn gật đầu.", said["Ji-eun gật đầu."])
            assertEquals("Hi-un U nhìn Gi-ưn rồi cười.", said["Hyun Woo nhìn Ji-eun rồi cười."])
            assertEquals("Chờ đã, Hây-da-e-môn!", said["Chờ đã, Heizaemon!"])
            assertEquals("Rồi Dan cười.", said["Rồi Dan cười."])
            assertEquals("Nước trong veo, Giu-ki thả con boa xuống rồi thay pin.", said["Nước trong veo, Yuki thả con boa xuống rồi thay pin."])
            assertEquals("Gi-ưn tải app hạng K về máy.", said["Ji-eun tải APP hạng K về máy."])
        }
        val shouted = books[0].cases.associate { it.text to it.said }
        assertEquals("Giu-ki! Hây-da-e-môn gọi lớn.", shouted["YUKI! Heizaemon gọi lớn."])
        assertEquals("“Hi-un U! Gi-ưn đâu rồi?”", shouted["“HYUN WOO! Ji-eun đâu rồi?”"])
        assertEquals("Rồi Dan, Hây-da-e-môn và Giu-ki mở app hạng K xem cục pin.", shouted["Rồi Dan, Heizaemon và YUKI mở APP hạng K xem cục pin."])
    }

    @Test fun theNativeFrontendHandsTheModelTheSamePhonemes() {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB") ?: "../../sea_g2p_jni/target/release/abook_sea_g2p.dll")
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT") ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        G2pTestInputs.requireOrSkip("Native frontend files required", library.isFile && dictionary.isFile)
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { reader ->
            for (book in books) {
                val rulings = (book.readings() as BookReadings).rulings
                for (case in book.cases) {
                    val (tokens, unit) = unitOf(case, book)
                    val phonemes = reader.phonemize(unit.pieces, unit.text(tokens), rulings)
                    assertEquals(case.text, case.phonemes, phonemes)
                    // one phonetic word per spoken syllable: no name is joined into one word, none loses a syllable
                    val words = phonemes.split(" ")
                    assertEquals(case.text, case.said.replace("-", " ").split(" ").size, words.size)
                    assertTrue(phonemes, words.all { word -> word.count { it == 'ˈ' || it == 'ˌ' } == 1 })
                }
                // Dan is /ɗ/ by the book's rulings only: without them sea-g2p reads the Vietnamese syllable "dan"
                val dan = book.cases.first { it.text == "Rồi Dan cười." }
                val (tokens, unit) = unitOf(dan, book)
                assertEquals("ɹˈo2j ɗˈaːn kˈyə2j.", dan.phonemes)
                assertEquals("ɹˈo2j zˈaːn kˈyə2j.", reader.phonemize(unit.pieces, unit.text(tokens), null))
            }
            // K is the letter "ca"; APP the English word; pin / veo / boa Vietnamese level syllables
            assertEquals("hˈaː6ŋ kˈaː vˈe2 mˈaɜj.", reader.phonemize(listOf("hạng K về máy.")))
            assertEquals(reader.phonemize(listOf("hạng ca về máy.")), reader.phonemize(listOf("hạng K về máy.")))
            val mixed = books[0].cases.first { it.text.startsWith("Rồi Dan, Heizaemon và YUKI") }.phonemes
            assertEquals("ɹˈo2j ɗˈaːn, hˈəɪ zˈaː ˈɛ mˈon vˌaː2 zˈu kˈi mˈəː4 ˈæp hˈaː6ŋ kˈaː sˈɛm kˈu6c pˈin.", mixed)
        }
    }
}
