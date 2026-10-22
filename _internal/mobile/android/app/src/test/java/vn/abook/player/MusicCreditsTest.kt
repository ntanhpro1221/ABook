package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Ghi công nhạc nền trong file xuất: cùng chữ với máy tính (tests/test_export_music_credits.py) - các chuỗi mong đợi lấy từ `music_export.credit_text`. */
class MusicCreditsTest {
    private val by = JSONObject().put("title", "Bài A").put("creator", "Kevin").put("license", "by")
        .put("licenseUrl", "https://creativecommons.org/licenses/by/4.0/")
        .put("attribution", "\"Bài A\" Kevin (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License")
    private val cc0 = JSONObject().put("title", "The Hope").put("creator", "").put("license", "cc0")
        .put("licenseUrl", "https://creativecommons.org/publicdomain/zero/1.0/")
        .put("attribution", "\"The Hope\" by  licensed CC0: https://opengameart.org/content/the-hope")

    @Test
    fun aCreditLineKeepsTheCatalogAttributionButNeverPrintsAnEmptyBy() {
        assertEquals(by.getString("attribution"), MusicCredits.line(by))
        assertEquals("“The Hope”, giấy phép CC0 1.0, https://creativecommons.org/publicdomain/zero/1.0/", MusicCredits.line(cc0))
        assertEquals("“Của tôi” - Tôi", MusicCredits.line(JSONObject().put("title", "Của tôi").put("creator", "Tôi").put("source", "local")))
        assertEquals("“X”, giấy phép CC BY-SA, https://l", MusicCredits.line(JSONObject().put("title", "X").put("license", "by-sa").put("landing", "https://l")))
        assertEquals("", MusicCredits.line(JSONObject()))
        assertEquals("null trong JSON là rỗng, không phải chữ null", "“X”", MusicCredits.line(JSONObject().put("title", "X").put("creator", JSONObject.NULL)))
    }

    @Test
    fun theModifiedNoteIsOnlyForMusicThatAsksForCredit() {
        val both = MusicCredits.text(listOf(by, cc0, by))
        assertEquals(
            "Nhạc nền:\n${by.getString("attribution")}\n“The Hope”, giấy phép CC0 1.0, https://creativecommons.org/publicdomain/zero/1.0/\n${MusicCredits.MODIFIED_NOTE}\n",
            both,
        )
        assertEquals("Nhạc nền:\n“The Hope”, giấy phép CC0 1.0, https://creativecommons.org/publicdomain/zero/1.0/\n", MusicCredits.text(listOf(cc0)))
        assertEquals("", MusicCredits.text(listOf(JSONObject())))
        assertFalse(MusicCredits.needsCredit(cc0) || MusicCredits.needsCredit(JSONObject().put("license", "by").put("source", "local")))
        assertTrue(MusicCredits.needsCredit(by))
    }

    @Test
    fun licenseNamesMatchTheDesktop() {
        assertEquals("CC BY-NC", MusicCredits.licenseLabel("by-nc", ""))
        assertEquals("CC0", MusicCredits.licenseLabel("CC0", ""))
        assertEquals("odd", MusicCredits.licenseLabel("odd", ""))
        assertEquals("CC BY-SA 3.0", MusicCredits.licenseLabel("by", "https://creativecommons.org/licenses/by-sa/3.0/"))
    }
}
