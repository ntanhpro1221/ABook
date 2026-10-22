package vn.abook.player.readaloud

import android.os.Handler
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.BookEditsFixtures
import vn.abook.player.FakeExo
import vn.abook.player.Playback
import vn.abook.player.Store
import java.io.File
import java.nio.file.Files

/**
 * Soát a79 lỗi 1-3: chữ không rời máy trước khi người nghe đồng ý với đúng nhà cung cấp ấy. Các đường không qua hộp hỏi của giao diện (Android Auto, widget,
 * nút tai nghe, đổi giọng giữa chương, giọng cũ bị gỡ) phải dừng ở đầu đoạn, không gọi mạng.
 */
class ConsentHoldTest {
    private val exo = FakeExo()
    private val notices = mutableListOf<String>()
    private val listener: (String) -> Unit = { notices += it }
    private val dir: File = Files.createTempDirectory("consent-hold").toFile()

    private fun field(owner: Class<*>, name: String) = owner.getDeclaredField(name).also { it.isAccessible = true }
    private fun held() = field(ReadAloud::class.java, "held").get(ReadAloud) as Boolean
    private fun inFlight() = field(ReadAloud::class.java, "inFlight").get(ReadAloud) as Boolean

    @Before fun setup() {
        Handler.reset()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, BookEditsFixtures.tempDir("consent-hold"))
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        Playback.player = exo.player
        field(Playback::class.java, "bookId").set(Playback, "consent-book")
        field(Playback::class.java, "chapters").set(Playback, listOf(Playback.Chapter(1, "Một", "", 0.0, text = "texts/1.txt"), Playback.Chapter(2, "Hai", "", 0.0, text = "texts/2.txt")))
        for (name in listOf("1", "2")) Store.file("consent-book", "texts/$name.txt").apply { parentFile.mkdirs() }.writeText("Đoạn một.\n\nĐoạn hai.\n", Charsets.UTF_8)
        ReadAloud.choices = VoiceChoices(File(dir, "readaloud-voices.json"))
        ReadAloud.stillOffered = { true }
        field(ReadAloud::class.java, "voiceId").set(ReadAloud, ReadAloud.DEFAULT_VOICE)
        ReadAloud.addNoticeListener(listener)
    }

    @After fun cleanup() {
        ReadAloud.removeNoticeListener(listener)
        ReadAloud.stop()
        field(ReadAloud::class.java, "waiting").set(ReadAloud, null)
        field(ReadAloud::class.java, "failure").set(ReadAloud, null)
        field(ReadAloud::class.java, "voiceId").set(ReadAloud, ReadAloud.DEFAULT_VOICE)
        ReadAloud.choices = null
        ReadAloud.stillOffered = { true }
        field(Playback::class.java, "bookId").set(Playback, "")
        field(Playback::class.java, "chapters").set(Playback, emptyList<Playback.Chapter>())
        Playback.player = null
        Handler.reset()
        dir.deleteRecursively()
    }

    private fun becomeActive(voice: String, play: Boolean) {
        field(ReadAloud::class.java, "active").set(ReadAloud, true)
        field(ReadAloud::class.java, "voiceId").set(ReadAloud, voice)
        field(ReadAloud::class.java, "waiting").set(ReadAloud, ReadAloud.Target(0, 0, 0, -1, play))
        // Không có gì để đưa vào hàng đợi: bài thử chỉ xem lõi có chịu gọi mạng hay không.
        field(ReadAloud::class.java, "failure").set(ReadAloud, "đứng yên")
    }

    @Test fun onlyEdgeConsentOpensTheEdgeFallbackOfAKeyedVoice() {
        assertNull("chưa đồng ý gì", ReadAloud.edgeFallback())
        ReadAloud.allowOnline(listOf("azure", "fpt", "google"))
        assertNull("đồng ý cho dịch vụ khác không thay được đồng ý cho Microsoft", ReadAloud.edgeFallback())
        ReadAloud.allowOnline(listOf("azure", "edge"))
        assertEquals("edge:vi-VN-HoaiMyNeural", ReadAloud.edgeFallback()!!.id)
    }

    @Test fun startingATextChapterWithAnUnapprovedOnlineVoiceHoldsAndSendsNothing() {
        ReadAloud.startAt(0, 0, play = true) // Android Auto / widget / nút tai nghe
        assertTrue("dừng chờ đồng ý", held())
        assertFalse(ReadAloud.wantsPlay())
        assertFalse("ExoPlayer không được bật", exo.playWhenReady)
        assertFalse("không gọi mạng", inFlight())
        Handler.advance(0)
        assertEquals(listOf(ReadAloud.CONSENT_NOTICE), notices)
    }

    @Test fun pressingPlayWhileHeldWithoutConsentStillSendsNothing() {
        ReadAloud.startAt(0, 0, play = true)
        field(ReadAloud::class.java, "active").set(ReadAloud, true)
        assertTrue("đã xử lý, không để Playback phát tiếp", ReadAloud.onPlay())
        assertTrue(held())
        assertFalse(ReadAloud.wantsPlay())
        assertFalse(inFlight())
    }

    @Test fun anApprovedProviderDoesNotHold() {
        ReadAloud.allowOnline(listOf("edge"))
        ReadAloud.startAt(0, 0, play = false)
        assertFalse(held())
        // Đồng ý cho Edge không phải đồng ý cho Google.
        field(ReadAloud::class.java, "voiceId").set(ReadAloud, "google:vi-VN-Wavenet-A")
        ReadAloud.startAt(0, 0, play = false)
        assertTrue(held())
    }

    @Test fun aLocalVoiceNeverNeedsConsent() {
        field(ReadAloud::class.java, "voiceId").set(ReadAloud, "device:vi")
        ReadAloud.startAt(0, 0, play = false)
        assertFalse(held())
    }

    @Test fun switchingToAnUnapprovedOnlineVoiceMidListeningKeepsTheOldVoice() {
        becomeActive("device:vi", play = true)
        ReadAloud.setVoice("edge:vi-VN-NamMinhNeural")
        assertEquals("device:vi", ReadAloud.voiceId)
        Handler.advance(0)
        assertEquals(listOf(ReadAloud.CONSENT_NOTICE), notices)
        ReadAloud.allowOnline(listOf("edge"))
        ReadAloud.setVoice("edge:vi-VN-NamMinhNeural")
        assertEquals("edge:vi-VN-NamMinhNeural", ReadAloud.voiceId)
    }

    @Test fun aRemovedVoiceFallingBackToAnUnapprovedOnlineOneStopsInsteadOfSending() {
        becomeActive("vieneu:turbo/Adam", play = true)
        ReadAloud.stillOffered = { id -> !id.startsWith("vieneu:") }
        exo.playWhenReady = true
        ReadAloud.voicesChanged()
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
        assertTrue(held())
        assertFalse(exo.playWhenReady)
        assertFalse(inFlight())
        Handler.advance(0)
        assertEquals(listOf(ReadAloud.CONSENT_NOTICE), notices)
    }

    @Test fun prepareAheadRefusesAnOnlineVoiceThatIsNotApproved() {
        assertNotNull("chưa đồng ý: làm trước sẽ gửi cả loạt chương đi", PrepareAhead.refusal("edge:vi-VN-HoaiMyNeural"))
        assertNull("giọng chạy trên máy không gửi gì", PrepareAhead.refusal("vieneu:turbo/Adam"))
        assertNull(PrepareAhead.refusal("device:vi"))
        ReadAloud.allowOnline(listOf("edge"))
        assertNull(PrepareAhead.refusal("edge:vi-VN-HoaiMyNeural"))
        assertNotNull("đồng ý cho Microsoft không phải cho Google", PrepareAhead.refusal("google:vi-VN-Wavenet-A"))
    }

    @Test fun sleepTimerAtTheEndOfATextChapterWaitsAtTheStartOfTheNextChapter() {
        // Soát a79 lỗi 13: như máy tính (player.tsx), hẹn "hết chương" xong thì đứng ở 0:00 của chương kế, không phải cuối chương vừa nghe.
        ReadAloud.allowOnline(listOf("edge"))
        field(ReadAloud::class.java, "active").set(ReadAloud, true)
        exo.item = androidx.media3.common.MediaItem.Builder().setMediaId("1").build() // ExoPlayer đang đứng ở chương một
        assertEquals(1, Playback.currentChapter?.id)
        ReadAloud.parkAtNextChapter(0) // handleEnded gọi nó sau SleepTimer.onPausedAtChapterEnd
        assertEquals("chương kế", 2, Playback.currentChapter?.id)
        assertEquals("ở đầu chương", 0L, Playback.positionMs)
        assertTrue("chưa ai bấm phát: dừng, chưa gọi mạng", held() && !inFlight() && !ReadAloud.wantsPlay())
        // Chương cuối thì ở lại (bấm Phát thì EndPlan nghe lại từ đầu).
        ReadAloud.parkAtNextChapter(1)
        assertEquals(2, Playback.currentChapter?.id)
    }
}
