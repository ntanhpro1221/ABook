package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Giọng đã nhớ mà đã gỡ khỏi máy (gỡ VieNeu): lõi đọc bằng giọng mặc định như giao diện tự quay về, và vẫn nhớ lựa chọn của cuốn. */
class StaleVoiceTest {
    private val dir: File = Files.createTempDirectory("stale-voice").toFile()
    private val vieneu = "vieneu:nano/Adam"
    private var installed = true

    @Before
    fun setUp() {
        ReadAloud.choices = VoiceChoices(File(dir, "readaloud-voices.json")).also { it.remember("sach-a", vieneu) }
        ReadAloud.stillOffered = { id -> installed || !id.startsWith("vieneu:") }
        ReadAloud.setVoice(ReadAloud.DEFAULT_VOICE)
    }

    @After
    fun cleanUp() {
        ReadAloud.choices = null
        installed = true
        ReadAloud.stillOffered = { true }
        ReadAloud.setVoice(ReadAloud.DEFAULT_VOICE)
        dir.deleteRecursively()
    }

    @Test
    fun aBookKeepsItsInstalledModuleVoice() {
        ReadAloud.useVoiceOf("sach-a")
        assertEquals(vieneu, ReadAloud.voiceId)
    }

    @Test
    fun aRemovedModuleVoiceFallsBackToTheDefaultButIsStillRemembered() {
        installed = false
        ReadAloud.useVoiceOf("sach-a")
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
        assertEquals(vieneu, ReadAloud.choices!!.voiceFor("sach-a"))
        installed = true // tải lại: lần nạp kế cuốn về giọng cũ
        ReadAloud.useVoiceOf("sach-a")
        assertEquals(vieneu, ReadAloud.voiceId)
    }

    @Test
    fun settingARemovedVoiceUsesTheDefault() {
        installed = false
        ReadAloud.setVoice(vieneu)
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
    }

    @Test
    fun removingTheModuleWhileReadingSwitchesTheVoiceAtOnce() {
        ReadAloud.setVoice(vieneu)
        assertEquals(vieneu, ReadAloud.voiceId)
        installed = false
        ReadAloud.voicesChanged()
        assertEquals(ReadAloud.DEFAULT_VOICE, ReadAloud.voiceId)
    }
}
