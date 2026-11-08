package vn.abook.player.readaloud

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class JapaneseDeliveryTest {
    @Test fun sharedDeliveryPreservesPhonesAndWordBoundaries() {
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/japanese_delivery/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val c = cases.getJSONObject(index)
            val words = c.getJSONArray("words")
            val marked = JapaneseDelivery.mark(c.getString("text"), (0 until words.length()).map { words.getString(it) }.toSet())
            assertEquals(c.getString("text"), c.getString("marked"), marked)
            val calls = c.getJSONObject("calls")
            val phones = JapaneseDelivery.phonemes(marked, true) { text, final -> calls.getString(text + "|" + if (final) "1" else "0") }
            assertEquals(c.getString("text"), c.getString("phonemes"), phones)
        }
    }

    @Test fun automaticGroupingKeepsAnExplicitDifferentReading() {
        val groups = JapaneseDelivery.groups(listOf("Nopami", "Nakanori"), "ja")
        assertEquals("<en>Nô‿pa‿mi</en> <en>Na‿ca‿nô‿ri</en>", JapaneseDelivery.mark("Nô-pa-mi Na-ca-nô-ri", groups))
        assertEquals("cách-đọc-riêng", JapaneseDelivery.mark("cách-đọc-riêng", groups))
        assertTrue(JapaneseDelivery.groups(listOf("Nopami"), "ko").isEmpty())
        assertTrue(JapaneseDelivery.groups(listOf("Nopami"), "ja", mapOf("Nopami" to "Nô pa mi")).isEmpty())
    }

    @Test fun contextSensitiveConversionKeepsWholeStream() {
        assertEquals("whole sentence.", JapaneseDelivery.phonemes("Tên <en>Nô‿pa‿mi</en>.", true) { _, final ->
            if (final) "whole sentence." else "different fragment"
        })
    }
}
