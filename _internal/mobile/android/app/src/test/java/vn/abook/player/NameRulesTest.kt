package vn.abook.player

import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Phép kiểm tên và cách đọc người nghe gõ (NameRules, soát a89 T1) so với bản Python (webui/name_rules.py) qua bộ ví dụ dùng chung
 * tests/fixtures/book_edits/name_rules.json: [{fn, input, others?, allowEmpty?, out | error}].
 */
class NameRulesTest {
    @Test
    fun every_shared_case_gives_what_python_gave() {
        val cases = BookEditsFixtures.json("name_rules.json") as JSONArray
        assertTrue(cases.length() >= 20)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val input = case.getString("input")
            val others = case.optJSONArray("others")?.let { list -> (0 until list.length()).map { list.getString(it) } } ?: emptyList()
            val run = {
                when (case.getString("fn")) {
                    "tidy" -> NameRules.tidy(input)
                    "person" -> NameRules.person(input, others, case.optBoolean("allowEmpty", false))
                    "surface" -> NameRules.surface(input)
                    "spoken" -> NameRules.spoken(input)
                    else -> fail("fn lạ: $case").let { "" }
                }
            }
            if (case.has("error")) {
                val message = try {
                    run()
                    fail("ca $index phải bị từ chối: $case")
                    ""
                } catch (problem: NameRules.Problem) {
                    problem.message
                }
                assertEquals("ca $index", case.getString("error"), message)
            } else {
                assertEquals("ca $index", case.getString("out"), run())
            }
        }
    }
}
