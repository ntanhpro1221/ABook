package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * "Tốc độ giọng trên máy" (VoiceSpeed.kt, desktop voice_speed.py): "Tự động" follows the quality tier's self-benchmark, an explicit choice always
 * wins, the choice survives a restart; a clip's tier is in its cache key the way the desktop writes it, and an export (`#q`) never meets a fast clip.
 */
class VoiceSpeedTest {
    private val root: File = Files.createTempDirectory("abook-voice-speed").toFile()

    /** A two-tier voice with a measurement and a fast file that may or may not be here. */
    private class Fake(override val speedId: String, var rtf: Double?, var ready: Boolean, override val fastSteps: Int) : VoiceSpeed.Family {
        override val speedName = "Giọng $speedId"
        override val speedModule = speedId
        override val fastChoice = "${speedId}_fast"
        override fun speedInstalled() = true
        override fun speedRtf() = rtf
        override fun speedFastReady() = ready
        override fun speedFastBytes() = if (ready) 0L else 81_526_521L
    }

    private val supertonic = Fake("supertonic", 1.21, true, 5)

    private fun configure() = VoiceSpeed.configure(File(root, VoiceSpeed.FILE)) { listOf(supertonic) }

    @After
    fun tearDown() {
        VoiceSpeed.configure(null) { emptyList() }
        root.deleteRecursively()
    }

    @Test
    fun autoKeepsTheBestTierWhenThePhoneKeepsUpAndAnExplicitChoiceAlwaysWins() {
        assertEquals(VoiceSpeed.QUALITY, VoiceSpeed.decide(VoiceSpeed.AUTO, 0.79))
        assertEquals(VoiceSpeed.FAST, VoiceSpeed.decide(VoiceSpeed.AUTO, 0.8))
        assertEquals("not measured yet: the best tier", VoiceSpeed.QUALITY, VoiceSpeed.decide(VoiceSpeed.AUTO, null))
        assertEquals(VoiceSpeed.QUALITY, VoiceSpeed.decide(VoiceSpeed.QUALITY, 2.5))
        assertEquals(VoiceSpeed.FAST, VoiceSpeed.decide(VoiceSpeed.FAST, 0.1))
    }

    @Test
    fun theChoiceIsKeptAndAnUnknownOneIsRefused() {
        configure()
        assertEquals(VoiceSpeed.AUTO, VoiceSpeed.choice())
        VoiceSpeed.setChoice(VoiceSpeed.FAST)
        assertEquals(VoiceSpeed.FAST, VoiceSpeed.choice())
        VoiceSpeed.configure(File(root, VoiceSpeed.FILE)) { listOf(supertonic) } // the app again
        assertEquals(VoiceSpeed.FAST, VoiceSpeed.choice())
        assertTrue(runCatching { VoiceSpeed.setChoice("turbo") }.isFailure)
        File(root, VoiceSpeed.FILE).writeBytes("{".toByteArray())
        assertEquals("a broken file is \"Tự động\"", VoiceSpeed.AUTO, VoiceSpeed.choice())
    }

    @Test
    fun liveListeningReadsTheTierTheChoiceWantsOnlyWhenItsFileIsHere() {
        configure()
        assertEquals("1.21 >= 0.8: auto goes fast", "fast5", VoiceSpeed.liveTag("supertonic:F1"))
        assertEquals("VieNeu Nano has one tier, however slow", "", VoiceSpeed.liveTag("vieneu:nano/Adam"))
        assertEquals("Turbo has one tier", "", VoiceSpeed.liveTag("vieneu:turbo/Adam"))
        assertEquals("", VoiceSpeed.liveTag("edge:vi-VN-HoaiMyNeural"))
        VoiceSpeed.setChoice(VoiceSpeed.FAST)
        assertEquals("fast5", VoiceSpeed.liveTag("supertonic:F1"))
        assertEquals("an explicit \"Nhanh hơn\" still leaves Nano alone", "", VoiceSpeed.liveTag("vieneu:nano/Adam"))
        supertonic.ready = false
        VoiceSpeed.changed()
        assertEquals("not downloaded: still the best tier", "", VoiceSpeed.liveTag("supertonic:F1"))
        val status = VoiceSpeed.status()
        assertEquals(VoiceSpeed.FAST, status.getString("choice"))
        assertEquals("only Supertonic has a row", 1, status.getJSONArray("voices").length())
        val row = status.getJSONArray("voices").getJSONObject(0)
        assertEquals("supertonic", row.getString("id"))
        assertEquals(VoiceSpeed.FAST, row.getString("tier"))
        assertEquals(VoiceSpeed.QUALITY, row.getString("using"))
        assertEquals(81_526_521L, row.getLong("fastBytes"))
        VoiceSpeed.setChoice(VoiceSpeed.QUALITY)
        assertEquals("never switched away from an explicit choice", "", VoiceSpeed.liveTag("supertonic:F1"))
    }

    @Test
    fun aTierIdSplitsOnlyForTwoTierVoices() {
        assertEquals("supertonic:F1" to "fast5", VoiceSpeed.split("supertonic:F1#fast5"))
        assertEquals("VieNeu ids are never split or tagged", "vieneu:nano/Adam", VoiceSpeed.quality("vieneu:nano/Adam"))
        assertEquals("vieneu:nano/Adam#x" to "", VoiceSpeed.split("vieneu:nano/Adam#x"))
        assertEquals("", VoiceSpeed.family("vieneu:nano/Adam"))
        assertEquals("edge:vi-VN-X", VoiceSpeed.quality("edge:vi-VN-X"))
        assertEquals("device:a#b" to "", VoiceSpeed.split("device:a#b"))
    }

    @Test
    fun theTierIsTheLastMarkOfTheKeyLikeTheDesktopAndAnExportNeverMeetsAFastClip() {
        configure()
        val cache = ClipCache(File(root, "clips"), tierOf = VoiceSpeed::liveTag)
        val text = "Chiếc thuyền nhỏ trôi chậm giữa dòng sông."
        fun put(voice: String) = cache.temp("wav").let { tmp ->
            tmp.writeBytes(ByteArray(64) { 1 })
            cache.put(voice, text, tmp, "wav", 1000, emptyList())
        }
        assertEquals("live", "supertonic:F1#fast5", cache.resolve("supertonic:F1"))
        assertEquals("export", "supertonic:F1#q", cache.resolve(VoiceSpeed.quality("supertonic:F1")))
        assertEquals("edge:vi-VN-X", cache.resolve("edge:vi-VN-X"))
        val live = put(cache.resolve("supertonic:F1"))
        assertEquals("a clip carries the plain voice id", "supertonic:F1", live.voice)
        assertEquals("the desktop's key: tier tag after the reading tags", "${ClipCache.key("supertonic", "F1", text, "fast5")}.wav", live.file.name)
        assertTrue(cache.contains("supertonic:F1", text))
        assertTrue("an export reads the best tier", !cache.contains(VoiceSpeed.quality("supertonic:F1"), text))
        val best = put(VoiceSpeed.quality("supertonic:F1"))
        assertEquals("the best tier keeps the key it always had", "${ClipCache.key("supertonic", "F1", text)}.wav", best.file.name)
        assertNotEquals(live.file, best.file)
        VoiceSpeed.setChoice(VoiceSpeed.QUALITY)
        assertEquals("choosing the best tier: live listening finds the best clip", best.file, cache.get("supertonic:F1", text)!!.file)
        // Nano: the reading marks of a VieNeu clip (its lift mark) and no tier tag, whatever the choice
        VoiceSpeed.setChoice(VoiceSpeed.FAST)
        val nanoClip = put(cache.resolve("vieneu:nano/Adam"))
        val marks = ClipCache.reading("vieneu:nano/Adam", text, null)
        assertEquals("${ClipCache.key("vieneu", "nano/Adam", text, marks)}.wav", nanoClip.file.name)
    }
}
