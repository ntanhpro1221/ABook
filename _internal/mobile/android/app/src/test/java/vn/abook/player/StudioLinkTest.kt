package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Studio của máy tính đã ghép mở trên điện thoại: chọn máy, so bản, báo máy chỉ cho nghe. */
class StudioLinkTest {
    private val peers = JSONObject()
        .put("b2", JSONObject().put("name", "Máy phòng khách").put("kind", "computer").put("token", "ma-b2"))
        .put("a1", JSONObject().put("name", "Điện thoại của Lan").put("kind", "phone").put("token", "ma-a1"))
        .put("c3", JSONObject().put("name", "Laptop chưa trả lời").put("token", "ma-c3"))

    @Test
    fun onlyComputersHaveAStudioAndTheMainComputerComesFirst() {
        val computers = StudioLink.computers(true, "NGDtuanh-Lecoo", peers)
        assertEquals(listOf(StudioLink.Computer(StudioLink.MAIN, "NGDtuanh-Lecoo"), StudioLink.Computer("b2", "Máy phòng khách")), computers)
        assertEquals(listOf(StudioLink.Computer("b2", "Máy phòng khách")), StudioLink.computers(false, "", peers))
        assertEquals(emptyList<StudioLink.Computer>(), StudioLink.computers(false, "", JSONObject()))
        assertTrue(StudioLink.known("b2", false, peers))
        assertFalse("điện thoại khác không có Studio", StudioLink.known("a1", true, peers))
        assertFalse("máy tính chính đã bỏ ghép", StudioLink.known(StudioLink.MAIN, false, peers))
    }

    @Test
    fun differentVersionsAreRefusedButASourceBuildIsNot() {
        assertTrue(StudioLink.mismatched("0.4.50", "0.4.51"))
        assertFalse(StudioLink.mismatched("0.4.51", "0.4.51"))
        assertFalse(StudioLink.mismatched("", "0.4.51"))
        assertFalse(StudioLink.mismatched("dev", "0.4.51"))
    }

    @Test
    fun theWaitingLineNamesTheComputer() {
        assertEquals("Máy NGDtuanh-Lecoo không trả lời - đang chờ nối lại", StudioLink.silentLine("NGDtuanh-Lecoo"))
        assertEquals("Máy phòng khách không trả lời - đang chờ nối lại", StudioLink.silentLine("máy phòng khách"))
    }

    @Test
    fun theComputerSaysWhenThisPhoneMayOnlyListen() {
        assertTrue(StudioLink.listenOnly("""{"version":"0.4.58","remote":true,"listenOnly":true,"machine":"NGD-PC"}"""))
        assertFalse(StudioLink.listenOnly("""{"version":"0.4.58","remote":true,"listenOnly":false}"""))
        assertFalse("máy cũ chưa có cờ này", StudioLink.listenOnly("""{"version":"0.4.50"}"""))
        assertFalse("không đọc được thì nút vẫn mở", StudioLink.listenOnly("không phải json"))
    }
}
