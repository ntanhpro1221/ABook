package vn.abook.player.vieneu

import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class Tnfix173Test {
    @Test fun groupedJoinedUnitsAndClockBoundaries() {
        for ((text, expected) in listOf(
            "Nguồn 1.000V." to "Nguồn một nghìn vôn.",
            "Tệp 1,000 MB." to "Tệp một nghìn mê ga bai.",
            "Ổ 0.5GB." to "Ổ không phẩy năm ghi ga bai.",
            "Mức 15dB." to "Mức mười lăm đề xi ben.",
            "Chuông 12 AM." to "Chuông mười hai giờ đêm.",
            "Chuông 12 PM." to "Chuông mười hai giờ trưa."
        )) {
            val (shown, parts) = VieneuUnits.units(text, 256, directEnglish = true)
            assertEquals(VieneuUnits.tokens(text), shown)
            assertEquals(expected, parts.flatMap { it.pieces }.filter { it.isNotEmpty() }.joinToString(" "))
        }
    }

    @Test fun authoredClassRulesPreserveSourceAndMatchPython() {
        val cases = JSONArray(File("../../../tests/fixtures/readaloud/tnfix173/cases.json").readText(Charsets.UTF_8))
        for (index in 0 until cases.length()) {
            val row = cases.getJSONObject(index)
            val text = row.getString("text")
            val origin = if (row.has("origin")) row.getString("origin") else null
            val (shown, parts) = VieneuUnits.units(text, 256, origin, directEnglish = true)
            assertEquals(row.getString("id") + ": source", VieneuUnits.tokens(text), shown)
            assertEquals(row.getString("id"), row.getString("spoken"), parts.flatMap { it.pieces }.filter { it.isNotEmpty() }.joinToString(" "))
        }
    }
}
