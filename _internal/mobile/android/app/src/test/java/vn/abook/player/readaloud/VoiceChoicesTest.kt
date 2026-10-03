package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Giọng "Nghe ngay" nhớ trong lõi theo từng cuốn: còn nguyên sau khi app khởi động lại (widget / xe hơi phát tiếp đúng giọng). */
class VoiceChoicesTest {
    private val dir: File = Files.createTempDirectory("voice-choices").toFile()
    private val file = File(dir, "readaloud-voices.json")

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    @Test
    fun nothingChosenMeansTheDefaultVoice() {
        assertEquals("", VoiceChoices(file).voiceFor("sach-a"))
    }

    @Test
    fun eachBookKeepsItsOwnVoiceAndTheLastChoiceIsTheDefaultForOthers() {
        val choices = VoiceChoices(file)
        choices.remember("sach-a", "device:vi-vn-x-gft")
        choices.remember("sach-b", "edge:vi-VN-NamMinhNeural")
        assertEquals("device:vi-vn-x-gft", choices.voiceFor("sach-a"))
        assertEquals("edge:vi-VN-NamMinhNeural", choices.voiceFor("sach-b"))
        assertEquals("edge:vi-VN-NamMinhNeural", choices.voiceFor("sach-moi"))
    }

    @Test
    fun choicesSurviveARestart() {
        VoiceChoices(file).remember("sach-a", "device:vi-vn-x-gft")
        VoiceChoices(file).remember("sach-b", "edge:vi-VN-HoaiMyNeural")
        val reopened = VoiceChoices(file)
        assertEquals("device:vi-vn-x-gft", reopened.voiceFor("sach-a"))
        assertEquals("edge:vi-VN-HoaiMyNeural", reopened.voiceFor("sach-b"))
    }

    @Test
    fun anEmptyChoiceDoesNotForgetAnEarlierOne() {
        val choices = VoiceChoices(file)
        choices.remember("sach-a", "device:vi-vn-x-gft")
        choices.remember("sach-a", "")
        assertEquals("device:vi-vn-x-gft", VoiceChoices(file).voiceFor("sach-a"))
    }

    @Test
    fun aBrokenFileIsLikeNoChoice() {
        file.writeText("{không phải json", Charsets.UTF_8)
        val choices = VoiceChoices(file)
        assertEquals("", choices.voiceFor("sach-a"))
        choices.remember("sach-a", "device:vi-vn-x-gft")
        assertEquals("device:vi-vn-x-gft", VoiceChoices(file).voiceFor("sach-a"))
    }
}
