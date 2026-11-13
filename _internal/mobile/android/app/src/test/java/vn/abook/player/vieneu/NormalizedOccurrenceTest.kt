package vn.abook.player.vieneu

import java.io.File
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.readaloud.BookReadings

/** Authored sentences share only text/counts with Python; no sentence IPA fixture. */
class NormalizedOccurrenceTest {
    private fun reader(): SeaG2p {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB") ?: "../../sea_g2p_jni/target/release/abook_sea_g2p.dll")
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT") ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        G2pTestInputs.requireOrSkip("Native frontend files required", library.isFile && dictionary.isFile)
        return SeaG2p(library.absoluteFile, dictionary.absoluteFile)
    }

    @Test fun readerKeepsOnlyAdjudicatedOccurrencesAfterNumbersExpand() {
        val cases = JSONArray(File("../../../tests/fixtures/readaloud/normalized_occurrences.json").readText(Charsets.UTF_8))
        val vi = mapOf("ben" to "bˈɛn", "can" to "kˈaːn", "an" to "ˈaːn", "ten" to "t̪ˈɛn")
        reader().use { g2p ->
            for (i in 0 until cases.length()) {
                val row = cases.getJSONObject(i)
                val names = row.getJSONArray("names").let { a -> (0 until a.length()).map(a::getString).toSet() }
                val rulings = PhonemePolicy.Rulings(names = names)
                val origin = if (row.has("origin")) row.getString("origin") else null
                val (shown, units) = VieneuUnits.units(row.getString("text"), 256, origin, BookReadings(emptyMap(), rulings), directEnglish = true)
                if (row.getString("id").startsWith("tag-")) org.junit.Assert.assertTrue(units.any { u -> u.pieces.any { "<en>C P U</en>" in it } })
                val phones = units.flatMap { g2p.phonemize(it.pieces, it.text(shown), rulings).split(Regex("\\s+")) }.map { it.trimEnd('.', ',', '!', '?') }
                assertEquals(row.getString("id"), row.getInt("count"), phones.count { it == vi.getValue(row.getString("word")) })
                if (row.has("english")) {
                    val english = g2p.g2p("<en>${row.getString("english")}</en>").trim()
                    assertEquals(row.getString("id"), 1, phones.count { it == english })
                }
            }
        }
    }

    @Test fun normalizedFragmentsConsumeEachOccurrenceOnce() {
        reader().use { g2p ->
            val rulings = PhonemePolicy.Rulings(names = setOf("can"))
            val fragments = listOf("Can đi 12 km.", "<en>I can do it</en>,", "Can đi 12 km.")
            for (cue in listOf("", "[chuckle]", "<|emotion_1|>")) {
                val spoken = "Can đi 12 km. $cue <en>I can do it</en>, Can đi 12 km."
                val cursor = intArrayOf(0)
                for ((i, fragment) in fragments.withIndex()) {
                    val given = g2p.normalize(fragment, false)
                    val raw = g2p.g2p(given)
                    val phones = PhonemePolicy.restoreGeneratedSyllables(spoken, given, raw, g2p::g2p, rulings = rulings,
                        cursor = cursor, normalize = { g2p.normalize(it, false) })
                    if (i == 1) assertEquals(raw, phones)
                    else assertEquals("kˈaːn", phones.split(Regex("\\s+"))[0])
                }
            }
        }
    }

    @Test fun changedNormalizerContextIsRejected() {
        val raw = "bˈen rest rest rest."
        assertEquals(raw, PhonemePolicy.restoreGeneratedSyllables("Ben đi 12 km.", "ben đi 12 km.", raw, { if (it == "bén") "bˈɛnɜ" else "bˈen" },
            rulings = PhonemePolicy.Rulings(names = setOf("ben")),
            normalize = { if (it == "Ben đi 12 km.") "ben đi xa" else it.lowercase() }))
    }
}
