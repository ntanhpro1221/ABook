package vn.abook.player.readaloud

import java.io.File
import java.nio.file.Files
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Test

class BookTimingVoiceTest {
    private val oldChoices = ReadAloud.choices
    private val oldOffered = ReadAloud.stillOffered
    private val oldLocal = ReadAloud.localVoice
    private val oldVoice = ReadAloud.voiceId

    @After fun restore() {
        ReadAloud.choices = oldChoices
        ReadAloud.stillOffered = oldOffered
        ReadAloud.localVoice = oldLocal
        ReadAloud::class.java.getDeclaredField("voiceId").apply { isAccessible = true }.set(null, oldVoice)
    }

    @Test fun timingUsesTheRequestedBookAndProfileWithoutChangingPlaybackVoice() {
        val file = File(Files.createTempDirectory("book-timing-voice").toFile(), "voices.json")
        val choices = VoiceChoices(file)
        ReadAloud.choices = choices
        ReadAloud.stillOffered = { true }
        choices.remember("a", "device:a", "ra")
        choices.remember("b", "device:b", "rb")
        choices.remember("b", "device:c", "rc")
        ReadAloud.useVoiceOf("a", "ra")
        assertEquals("device:b", ReadAloud.voiceForBook("b", "rb"))
        assertEquals("device:c", ReadAloud.voiceForBook("b", "rc"))
        assertEquals("device:a", ReadAloud.voiceId)
        ReadAloud.useVoiceOf("b", "rb")
        assertEquals(ReadAloud.voiceForBook("b", "rb"), ReadAloud.voiceId)
        ReadAloud.stillOffered = { it != "device:b" }
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceForBook("b", "rb"))
    }
}
