package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/** Tự lùi khi nghe lại: cùng các ca với ui/src/listen/sleep.test.ts (tests/fixtures/auto_rewind/cases.json). */
class AutoRewindTest {
    @Test
    fun everySharedCaseGivesTheSameAnswer() {
        val cases = JSONObject(File("../../../tests/fixtures/auto_rewind/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONArray(index)
            assertEquals("tạm dừng ${case.getLong(0)} ms", case.getDouble(1), AutoRewind.seconds(case.getLong(0)), 0.0)
        }
    }
}
