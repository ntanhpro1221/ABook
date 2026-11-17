package vn.abook.player.ui.data

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.ui.studio.StudioCastJson
import java.io.File

/**
 * Một đầu ra thật của máy chủ (tests/fixtures/cast_contract/cast.json, sinh từ avatars.cast bởi tests/test_cast_contract_fixture.py) vào
 * phần nghe (Cast.parse - cast.json trong gói) và Studio (StudioCastJson - GET /cast): đúng chữ expected.json ghi. Web
 * (castContract.dom.test.tsx) và Qt (tst_cast.qml test_serverCastContract) đọc cùng hai file.
 */
class CastContractTest {
    private val folder = File("../../../tests/fixtures/cast_contract")
    private val cast = File(folder, "cast.json").readText()
    private val expected = JSONObject(File(folder, "expected.json").readText())

    private fun expectedRows(): List<List<String>> {
        val rows = expected.getJSONArray("narratorRows")
        return (0 until rows.length()).map { index ->
            rows.getJSONObject(index).let { listOf(it.getString("voice"), it.getString("preset"), it.getString("scope"), it.getString("line")) }
        }
    }

    private fun shown(rows: List<NarratorLine>) = rows.map { listOf(it.voice, it.preset, it.scope, Cast.narratorRowCount(it).replace(' ', ' ')) }

    private fun expectedGenders(): Map<String, String> {
        val genders = expected.getJSONObject("genders")
        return genders.keys().asSequence().associateWith { genders.getString(it) }
    }

    @Test
    fun `the listening side shows the server's cast as every client does`() {
        val view = Cast.parse(cast)!!
        assertEquals(expectedRows(), shown(Cast.narratorRows(view.narrator)))
        assertEquals(expectedGenders(), (view.characters + view.extras).associate { it.displayName to Cast.genderText(it) })
    }

    @Test
    fun `Studio reads the same server output into the same narrator rows`() {
        val studio = StudioCastJson.cast(JSONObject(cast))
        val narrator = studio.narrator
        assertEquals(expectedRows(), shown(Cast.narratorRows(narrator.voice, narrator.chapterVoices, narrator.exceptChapters, narrator.voiceLines, narrator.voiceSeconds)))
    }
}
