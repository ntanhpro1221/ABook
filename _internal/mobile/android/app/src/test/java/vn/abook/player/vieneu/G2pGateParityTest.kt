package vn.abook.player.vieneu

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import vn.abook.player.readaloud.JapanesePolicy
import vn.abook.player.readaloud.BookReadings
import java.io.File

/** Exact desktop/phone contract. Build JNI with prepare_sea_g2p_android.py first.
 * ABOOK_REQUIRE_G2P_PARITY=1 makes absent native inputs an error in CI.
 * Private calibration input/output and reports stay outside the checkout:
 * sentence phones can reveal their original sentence.
 */
class G2pGateParityTest {
    private fun strings(array: JSONArray) = (0 until array.length()).map(array::getString)
    private fun map(obj: JSONObject) = obj.keys().asSequence().associateWith(obj::getString)

    private fun compare(fixture: File, expectedCount: Int, suffix: String) {
        val library = File(System.getenv("ABOOK_SEA_G2P_LIB")
            ?: "../../sea_g2p_jni/target/release/" + System.mapLibraryName("abook_sea_g2p"))
        val dictionary = File(System.getenv("ABOOK_SEA_G2P_DICT")
            ?: "../../../runtime/.venv/Lib/site-packages/sea_g2p/sea_g2p.bin")
        val present = library.isFile && dictionary.isFile
        if (System.getenv("ABOOK_REQUIRE_G2P_PARITY") == "1") assertTrue("Host JNI library and dictionary required", present)
        assumeTrue("Build host JNI and supply ABOOK_SEA_G2P_LIB/DICT", present)
        val data = JSONObject(fixture.readText(Charsets.UTF_8))
        val cases = data.getJSONArray("cases")
        assertEquals(expectedCount, cases.length())
        val results = JSONArray()
        val counts = sortedMapOf<String, IntArray>()
        SeaG2p(library.absoluteFile, dictionary.absoluteFile).use { g2p ->
            for (i in 0 until cases.length()) {
                val row = cases.getJSONObject(i)
                val cls = row.getString("class")
                val origin = if (row.isNull("origin")) null else row.getString("origin")
                val text = row.getString("text")
                val bookReadings = if (row.getBoolean("book_names"))
                    JapanesePolicy.bookNameReadings(emptySequence(), listOf(text), origin) else emptyMap()
                val readings = bookReadings + map(row.getJSONObject("readings"))
                val given = row.getJSONObject("rulings")
                val rulings = PhonemePolicy.Rulings(
                    names = strings(given.getJSONArray("names")).toSet(),
                    foreign = strings(given.getJSONArray("foreign")).toSet())
                val (shown, units) = VieneuUnits.units(text, 256, origin, BookReadings(readings, rulings), directEnglish = true)
                val actualUnits = units.map { g2p.phonemize(it.pieces, it.text(shown), rulings) }
                val actual = actualUnits.joinToString(" ")
                val wantUnits = row.getJSONArray("units")
                val piecesMatch = units.size == wantUnits.length() && units.indices.all {
                    units[it].pieces == strings(wantUnits.getJSONObject(it).getJSONArray("pieces"))
                }
                // Unit boundaries and exact phones are the contract. Equivalent
                // spellings before normalization (e.g. lower case) may differ.
                val expectedUnits = (0 until wantUnits.length()).map { wantUnits.getJSONObject(it).getString("phonemes") }
                val same = actual == row.getString("phonemes") && actualUnits == expectedUnits
                val count = counts.getOrPut(cls) { intArrayOf(0, 0, 0) }
                count[0]++
                if (!same) count[1]++
                if (!piecesMatch) count[2]++
                val spellingDiffs = JSONArray()
                if (!piecesMatch) {
                    val wantWords = (0 until wantUnits.length())
                        .flatMap { strings(wantUnits.getJSONObject(it).getJSONArray("pieces")) }
                        .flatMap { it.split(Regex("\\s+")) }
                    val gotWords = units.flatMap { it.pieces }.flatMap { it.split(Regex("\\s+")) }
                    // Isolated changed words only: never expose a private sentence.
                    if (wantWords.size == gotWords.size) {
                        wantWords.indices.filter { wantWords[it] != gotWords[it] }.forEach {
                            spellingDiffs.put(JSONObject().put("desktop", wantWords[it]).put("phone", gotWords[it]))
                        }
                    }
                }
                results.put(JSONObject().put("id", row.getString("id")).put("class", cls).put("match", same)
                    .put("spelling_differences", spellingDiffs)
                    .put("pieces_match", piecesMatch).put("desktop", row.getString("phonemes")).put("phone", actual))
            }
        }
        val summary = JSONObject()
        counts.forEach { (cls, c) ->
            summary.put(cls, JSONObject().put("n", c[0]).put("mismatches", c[1]).put("spelling_differences", c[2]))
        }
        System.getenv("ABOOK_G2P_PARITY_REPORT")?.let { path ->
            if (suffix == "calibration") assertTrue("Private parity report must stay outside public checkout",
                !File(path).canonicalFile.toPath().startsWith(File("../../../..").canonicalFile.toPath()))
            File("$path.$suffix.json").writeText(JSONObject().put("classes", summary).put("results", results).toString(2), Charsets.UTF_8)
        }
        println("Exact G2P parity ($suffix): $summary")
        assertEquals("Exact phoneme mismatches by class: $summary", 0, counts.values.sumOf { it[1] })
    }

    @Test fun allPublicTokensMatchDesktopExactly() = compare(File("../../../tests/data/g2pgate/desktop_parity.json"),
        JSONArray(File("../../../tests/data/g2pgate/tokens.json").readText(Charsets.UTF_8)).length(), "tokens")

    @Test fun allMarkedStretchesMatchDesktopExactly() = compare(File("../../../tests/data/g2pgate/stretches_parity.json"), 115, "stretches")

    @Test fun authoredNormalizedOccurrencesMatchDesktopExactly() {
        val path = System.getenv("ABOOK_G2P_OCCURRENCE_FIXTURE")
        G2pTestInputs.requireOrSkip("Generate authored occurrence parity outside the repository", path != null && File(path).isFile)
        val rows = JSONArray(File("../../../tests/fixtures/readaloud/normalized_occurrences/cases.json").readText(Charsets.UTF_8))
        compare(File(path!!), rows.length(), "occurrences")
    }

    @Test fun all442PrivateCalibrationRowsMatchDesktopExactly() {
        val path = System.getenv("ABOOK_G2P_CALIBRATION_FIXTURE")
        assumeTrue("Private calibration fixture is optional; generate outside repository", path != null)
        assertTrue("Private calibration fixture must stay outside public checkout",
            !File(path!!).canonicalFile.toPath().startsWith(File("../../../..").canonicalFile.toPath()))
        compare(File(path!!), 442, "calibration")
    }
}
