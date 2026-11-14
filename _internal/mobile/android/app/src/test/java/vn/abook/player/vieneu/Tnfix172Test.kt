package vn.abook.player.vieneu

import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class Tnfix172Test {
    @Test fun sharedAuthoredRulesAndCounterexamples() {
        val cases = JSONArray(File("../../../tests/fixtures/readaloud/tnfix172/cases.json").readText(Charsets.UTF_8))
        for (index in 0 until cases.length()) {
            val row = cases.getJSONObject(index)
            val text = row.getString("text")
            val origin = if (row.has("origin")) row.getString("origin") else null
            val (shown, parts) = VieneuUnits.units(text, 256, origin, directEnglish = true)
            assertEquals(row.getString("id") + ": source", VieneuUnits.tokens(text), shown)
            val said = parts.flatMap { it.pieces }.filter { it.isNotEmpty() }.joinToString(" ")
            assertEquals(row.getString("id"), row.getString("spoken"), said)
        }
    }
}
