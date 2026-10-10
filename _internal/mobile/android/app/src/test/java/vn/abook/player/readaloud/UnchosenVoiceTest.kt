package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * Người nghe CHƯA chọn giọng: lõi đọc bằng giọng VieNeu đầu danh sách nếu điện thoại đã tải mô-đun (chữ không rời máy), không thì giọng mặc định -
 * đúng luật `resolveVoice` của giao diện (listen/readAloudVoice.ts) và của máy tính. Giọng đã chọn thì không đổi.
 */
class UnchosenVoiceTest {
    private val dir: File = Files.createTempDirectory("unchosen-voice").toFile()
    private val vieneu = "vieneu:turbo/Adam"
    private var installed: List<String> = listOf(vieneu, "vieneu:turbo/Mai")

    @Before
    fun setUp() {
        ReadAloud.choices = VoiceChoices(File(dir, "readaloud-voices.json"))
        ReadAloud.localVoice = { installed.firstOrNull() }
        ReadAloud.stillOffered = { id -> id in installed || !id.startsWith("vieneu:") }
        ReadAloud.setVoice(ReadAloud.DEFAULT_VOICE)
    }

    @After
    fun cleanUp() {
        ReadAloud.choices = null
        ReadAloud.localVoice = { null }
        ReadAloud.stillOffered = { true }
        ReadAloud.setVoice(ReadAloud.DEFAULT_VOICE)
        dir.deleteRecursively()
    }

    @Test
    fun aBookWithNoChosenVoiceUsesTheFirstLocalVoiceWhenThePhoneHasOne() {
        ReadAloud.useVoiceOf("sach-moi")
        assertEquals(vieneu, ReadAloud.voiceId)
    }

    @Test
    fun withoutALocalVoiceTheDefaultStaysTheOnlineOne() {
        installed = emptyList()
        ReadAloud.useVoiceOf("sach-moi")
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
    }

    @Test
    fun aChosenVoiceIsNeverReplacedByTheLocalDefault() {
        ReadAloud.choices!!.remember("sach-a", "edge:vi-VN-NamMinhNeural")
        ReadAloud.useVoiceOf("sach-a")
        assertEquals("edge:vi-VN-NamMinhNeural", ReadAloud.voiceId)
    }

    @Test
    fun aChosenLocalVoiceThatWasRemovedFallsBackToTheDefaultNotToAnotherLocalVoice() {
        ReadAloud.choices!!.remember("sach-a", "vieneu:turbo/Thien")
        ReadAloud.useVoiceOf("sach-a")
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
    }

    @Test
    fun removingTheFirstLocalVoiceMovesAnUnchosenBookToTheNextOne() {
        ReadAloud.useVoiceOf("sach-moi")
        assertEquals(vieneu, ReadAloud.voiceId)
        installed = listOf("vieneu:turbo/Mai")
        ReadAloud.voicesChanged()
        assertEquals("vieneu:turbo/Mai", ReadAloud.voiceId)
        installed = emptyList()
        ReadAloud.voicesChanged()
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
    }
}
