package vn.abook.player.ui.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Phần thuần của hộp hỏi đồng ý và khối lỗi giọng (OnlineConsent.kt): cùng lời, cùng luật với listen/onlineConsent.ts, readAloudVoice.ts, vieneuModule.ts. */
class OnlineConsentTest {
    private val hoaiMy = ConsentVoice("edge:vi-VN-HoaiMyNeural", "Hoài My (Edge)", "edge", true, "female")
    private val namMinh = ConsentVoice("edge:vi-VN-NamMinhNeural", "Nam Minh (Edge)", "edge", true, "male")
    private val azure = ConsentVoice("azure:an", "An (Azure)", "azure", true, "female")
    private val nano = ConsentVoice("vieneu:nano/aihan", "Ái Hân (VieNeu)", "vieneu", false, "female")
    private val nanoMale = ConsentVoice("vieneu:nano/adam", "Adam (VieNeu)", "vieneu", false, "male")
    private val device = ConsentVoice("device:vi", "Giọng tiếng Việt", "device", false)

    // ---- chọn giọng và quyết định hỏi ----

    @Test
    fun `the book reads with the voice it remembered, else the default, else the first`() {
        val all = listOf(namMinh, hoaiMy, nano)
        assertEquals(nano, OnlineConsent.resolve(all, nano.id))
        assertEquals("giọng đã nhớ không còn: giọng mặc định của app", hoaiMy, OnlineConsent.resolve(all, "vieneu:gone"))
        assertEquals("không có cả giọng mặc định: giọng đầu tiên", namMinh, OnlineConsent.resolve(listOf(namMinh, nano), "vieneu:gone"))
        assertNull(OnlineConsent.resolve(emptyList(), "x"))
    }

    @Test
    fun `only an online voice whose provider is not agreed yet needs the question`() {
        assertTrue(OnlineConsent.needsPrompt(hoaiMy, emptySet()))
        assertFalse("đã đồng ý với Microsoft", OnlineConsent.needsPrompt(hoaiMy, setOf("edge")))
        assertTrue("đồng ý với Microsoft không phải đồng ý với Azure", OnlineConsent.needsPrompt(azure, setOf("edge")))
        assertFalse("giọng chạy trên máy không gửi chữ đi", OnlineConsent.needsPrompt(nano, emptySet()))
        assertFalse(OnlineConsent.needsPrompt(device, emptySet()))
        assertFalse(OnlineConsent.needsPrompt(null, emptySet()))
    }

    // ---- lời ----

    @Test
    fun `the choose step says where the text goes only as far as the list needs`() {
        val local = "Giọng của máy đọc ngay trên máy này, không gửi chữ đi đâu."
        val ask = VoiceText.consent(hoaiMy.name, hoaiMy.provider)
        assertEquals("chỉ giọng chạy trên máy", local, OnlineConsent.chooseText(listOf(nano, device), hoaiMy))
        assertEquals("có cả hai", "$local $ask", OnlineConsent.chooseText(listOf(hoaiMy, nano), hoaiMy))
        assertEquals("chỉ giọng trực tuyến", ask, OnlineConsent.chooseText(listOf(hoaiMy, namMinh), hoaiMy))
        assertEquals("Giọng Hoài My là giọng Edge: chữ của đoạn đang đọc được gửi tới máy chủ Microsoft để đọc.", ask)
    }

    @Test
    fun `a keyed provider says the key and the possible charge`() {
        assertEquals(
            "Giọng An dùng khoá Azure Speech của bạn: chữ của đoạn đang đọc được gửi tới Azure Speech để đọc, và dịch vụ có thể tính tiền vào tài khoản của bạn.",
            VoiceText.consent(azure.name, azure.provider),
        )
    }

    @Test
    fun `each row says where the voice reads and which one is being asked`() {
        assertEquals("trực tuyến · đang chọn", OnlineConsent.tag(hoaiMy, hoaiMy.id))
        assertEquals("trực tuyến", OnlineConsent.tag(namMinh, hoaiMy.id))
        assertEquals("của máy", OnlineConsent.tag(nano, hoaiMy.id))
        assertEquals("Nghe thử giọng Hoài My", OnlineConsent.sampleLabel(false, hoaiMy.name))
        assertEquals("Dừng giọng Hoài My", OnlineConsent.sampleLabel(true, hoaiMy.name))
    }

    // ---- chương kế ----

    @Test
    fun `next and previous aim at the chapter the core will go to`() {
        val ids = listOf(10, 11, 12)
        assertEquals(12, OnlineConsent.stepTarget(ids, 11, 1, 0))
        assertNull("hết cuốn", OnlineConsent.stepTarget(ids, 12, 1, 0))
        assertEquals(10, OnlineConsent.stepTarget(ids, 11, -1, 2_000))
        assertEquals("quá 5 giây: về đầu chính chương này", 11, OnlineConsent.stepTarget(ids, 11, -1, 6_000))
        assertNull("chương đầu, chưa quá 5 giây", OnlineConsent.stepTarget(ids, 10, -1, 0))
        assertNull(OnlineConsent.stepTarget(ids, null, 1, 0))
        assertNull(OnlineConsent.stepTarget(ids, 99, 1, 0))
    }

    // ---- giọng đang chọn không đọc được ----

    @Test
    fun `the core's two stuck sentences are recognised, other errors are not`() {
        assertTrue(VoiceStuck.isStuck("Không có mạng - giọng đang chọn cần mạng."))
        assertTrue(VoiceStuck.isStuck("Giọng đang chọn đang không dùng được."))
        assertTrue(VoiceStuck.isStuck("Giọng Hoài My đang không dùng được."))
        assertFalse(VoiceStuck.isStuck("Giọng  đang không dùng được."))
        assertFalse(VoiceStuck.isStuck("Không phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại."))
        assertFalse(VoiceStuck.isStuck(""))
    }

    @Test
    fun `the short sentence names the voice instead of saying the chosen one`() {
        assertEquals("Không có mạng - giọng Hoài My cần mạng.", VoiceStuck.shown("Không có mạng - giọng đang chọn cần mạng.", "Hoài My (Edge)"))
        assertEquals("Giọng Hoài My đang không dùng được.", VoiceStuck.shown("Giọng đang chọn đang không dùng được.", "Hoài My (Edge)"))
        assertEquals("tên chưa biết: giữ lời của lõi", "Không có mạng - giọng đang chọn cần mạng.", VoiceStuck.shown("Không có mạng - giọng đang chọn cần mạng.", null))
        assertEquals("lỗi khác không đổi", "Mất kết nối - đang thử lại…", VoiceStuck.shown("Mất kết nối - đang thử lại…", "Hoài My"))
    }

    @Test
    fun `the offline voice offered is a downloaded one, the same gender when it can`() {
        val all = listOf(hoaiMy, device, nanoMale, nano)
        assertEquals("cùng giới với giọng đang chọn", nano, VoiceStuck.localVoiceFor(all, hoaiMy))
        assertEquals(nanoMale, VoiceStuck.localVoiceFor(all, namMinh))
        assertEquals("không biết giọng đang chọn: giọng đầu tiên", nanoMale, VoiceStuck.localVoiceFor(all, null))
        assertNull("giọng của máy đã tự đỡ, không kể", VoiceStuck.localVoiceFor(listOf(hoaiMy, device), hoaiMy))
        assertNull(VoiceStuck.localVoiceFor(listOf(hoaiMy), hoaiMy))
    }

    @Test
    fun `the voice caption is a person's name, never the engine`() {
        assertEquals("Ái Hân", VoiceStuck.caption(nano))
        assertEquals("Giọng đọc của máy", VoiceStuck.caption(device))
        assertEquals("Giọng đọc của máy", VoiceStuck.caption(null))
    }

    // ---- tải giọng VieNeu trong khối lỗi ----

    private fun status(vararg installed: String, ticked: Set<String> = setOf("turbo"), recommended: String = "turbo") =
        Fixtures.missing(ModuleKind.Vieneu).let { base ->
            base.copy(
                recommended = recommended,
                choices = base.choices.map { it.copy(installed = it.id in installed, ticked = it.id in ticked) },
            )
        }

    @Test
    fun `the offer is the one recommended voice, the ticked bundle is the extra button`() {
        val offer = OfflineOffer.of(status())
        assertEquals(listOf("turbo"), offer.light)
        assertEquals(listOf("turbo"), offer.full)
        assertEquals(listOf("turbo"), offer.missing)
        val weak = OfflineOffer.of(status(ticked = setOf("turbo", "nano"), recommended = "nano"))
        assertEquals("máy yếu được khuyên giọng nhẹ", listOf("nano"), weak.light)
        assertEquals(listOf("turbo", "nano"), weak.full)
        assertEquals(listOf("nano"), weak.missing)
    }

    @Test
    fun `what is already on the phone is not offered again`() {
        val offer = OfflineOffer.of(status("turbo", ticked = setOf("turbo", "nano")))
        assertEquals(listOf("nano"), offer.full)
        assertEquals("giọng nhẹ nhất đã có: không còn nút chính", emptyList<String>(), offer.light)
        assertEquals(listOf("nano"), offer.missing)
    }

    @Test
    fun `sizes add up per choice and the button says it`() {
        val base = status()
        assertEquals(198_000_000L, OfflineOffer.bytes(base, listOf("turbo")))
        assertEquals(250_000_000L, OfflineOffer.bytes(base, listOf("turbo", "nano")))
        assertEquals(0L, OfflineOffer.bytes(base, emptyList()))
        assertEquals("Tải giọng VieNeu (189 MB)", OfflineOffer.label("Tải giọng VieNeu", false, 198_000_000))
        assertEquals("Tải giọng VieNeu", OfflineOffer.label("Tải giọng VieNeu", false, 0))
        assertEquals("sau lỗi chỉ còn Thử lại", "Thử lại", OfflineOffer.label("Tải giọng VieNeu", true, 198_000_000))
        assertEquals("Gói đầy đủ (238 MB)", OfflineOffer.fullLabel(250_000_000))
    }
}
