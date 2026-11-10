package vn.abook.player.readaloud

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

/** Loanwords with a settled Vietnamese reading, every voice: the same cases as tests/test_loanwords.py. */
class LoanwordsTest {
    @Test
    fun sharedLoanwordCasesMatchDesktop() {
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/loanwords/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val text = case.getString("text")
            val origin = if (case.isNull("origin")) null else case.getString("origin")
            val toks = VieneuUnits.tokens(text)
            assertEquals(text, case.getString("direct"), VieneuUnits.spokenTokens(toks, origin, directEnglish = true).joinToString(" "))
            assertEquals(text, case.getString("plain"), VieneuUnits.spokenTokens(toks, origin).joinToString(" "))
            assertEquals(text, case.getString("direct"), VieneuUnits.units(text, 256, origin, directEnglish = true).second.flatMap { it.pieces }.joinToString(" "))
        }
    }

    @Test
    fun theTableIsTheSharedPolicyFile() {
        val policy = JSONObject(File("../../../abook/readaloud/english_policy.json").readText(Charsets.UTF_8)).getJSONObject("loanwords")
        assertEquals(policy.keys().asSequence().associateWith(policy::getString), Names.LOANWORDS)
    }
}
