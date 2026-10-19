package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/** Giọng mặc định khi chưa chọn: cùng danh sách và cùng các ca với ui/src/listen/readAloudVoice.test.ts (tests/fixtures/default_voice/cases.json). */
class NarratorVoiceTest {
    private val shared = JSONObject(File("../../../tests/fixtures/default_voice/cases.json").readText(Charsets.UTF_8))

    @Test
    fun theListIsTheSameAsTheInterfaces() {
        val preferred = shared.getJSONObject("preferred")
        val fromFixture = preferred.keys().asSequence().associateWith { tier ->
            preferred.getJSONArray(tier).let { list -> (0 until list.length()).map { list.getString(it) } }
        }
        assertEquals(fromFixture, NarratorVoice.PREFERRED)
    }

    @Test
    fun everySharedCaseGivesTheSameAnswer() {
        val cases = shared.getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val item = cases.getJSONObject(index)
            val voices = item.getJSONArray("voices").let { list ->
                (0 until list.length()).map { list.getJSONArray(it).let { pair -> pair.getString(0) to pair.getString(1) } }
            }
            val gender = if (item.isNull("gender")) null else item.getString("gender")
            val expected = if (item.isNull("expect")) null else item.getString("expect")
            assertEquals(item.getString("name"), expected, NarratorVoice.pick(voices, gender))
        }
    }
}
