package vn.abook.player.readaloud

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.file.Files

class MachineVoicePickTest {
    @Test fun settingsAndPlaybackAgreeOnTheMeasuredDefaultAndKeepExplicitVoices() {
        val edge = vn.abook.player.ui.data.VoiceOption("edge:default", "Edge", "edge", true, "female")
        val local = vn.abook.player.ui.data.VoiceOption("supertonic:F1", "F1", "supertonic", false, "female", true)
        val unmeasured = local.copy(pick = null)
        val groups = vn.abook.player.ui.data.Voices.group(listOf(edge, local))
        assertEquals(local.id, vn.abook.player.ui.data.Voices.resolve(groups, ""))
        assertEquals(edge.id, vn.abook.player.ui.data.Voices.resolve(groups, edge.id))
        assertEquals(edge.id, vn.abook.player.ui.data.Voices.resolve(vn.abook.player.ui.data.Voices.group(listOf(edge, unmeasured)), ""))
        assertEquals(edge.id, vn.abook.player.ui.data.Voices.resolve(groups, "missing"))
    }
    private fun row(id: String, rtf: Double = 0.3, cer: Double? = 0.03, mos: Double? = 3.0, error: String = "") =
        EngineNumbers(id, "$id:voice", "m1", rtf, 500, 100, cer, mos, error)

    @Test fun selectionUsesTheSameGatesAndTiesAsDesktop() {
        assertEquals("supertonic", MachineVoicePick.choose(listOf(row("vieneu", mos = 2.8), row("supertonic", mos = 3.2))))
        assertEquals("good", MachineVoicePick.choose(listOf(row("bad", error = "failed", mos = 5.0), row("good"))))
        assertEquals("good", MachineVoicePick.choose(listOf(row("bad", cer = 0.16, mos = 5.0), row("good"))))
        assertEquals("good", MachineVoicePick.choose(listOf(row("bad", rtf = 0.8, mos = 5.0), row("good"))))
        assertEquals("clear", MachineVoicePick.choose(listOf(row("natural", cer = 0.05, mos = 3.05), row("clear", cer = 0.02))))
        assertEquals("fast", MachineVoicePick.choose(listOf(row("slow", rtf = 0.5), row("fast", rtf = 0.2))))
        assertEquals("a", MachineVoicePick.choose(listOf(row("b"), row("a"))))
        assertEquals("fast", MachineVoicePick.choose(listOf(row("slow", rtf = 0.5, cer = null, mos = null), row("fast", rtf = 0.2, cer = null, mos = null))))
        assertNull(MachineVoicePick.choose(listOf(row("bad", rtf = 2.0))))
        assertEquals("good", MachineVoicePick.choose(listOf(row("bad", rtf = Double.NaN), row("good"))))
    }

    @Test fun storeMeasuresAllModelsPreservesOverrideAndInvalidatesChangedMachinesOrModels() {
        val root = Files.createTempDirectory("voice-pick").toFile()
        try {
            val file = File(root, "pick.json")
            var modelMark = "m1"
            val seen = mutableListOf<String>()
            val engine = object : LocalEngine {
                override val id = "test"
                override val voices = listOf(VoiceInfo("test:a", "A", "test", false, false))
                override val capabilities = setOf("offline", "vi-VN")
                override val resourceNeeds = mapOf("device" to "cpu")
                override val mark get() = modelMark
                override fun synthesize(text: String, out: File): Clip {
                    seen.add(text)
                    return Clip(out, 1000, emptyList(), "test:a")
                }
                override fun forget() { seen.add("forget") }
            }
            var now = 0L
            fun picker(machine: String = "phone") = MachineVoicePick(file, machine, { listOf(engine) }, { 500L * 1024 * 1024 }, { now += 100_000_000; now })
            val pick = picker()
            assertNull(pick.status().chosen)
            pick.setOverride("test")
            pick.measure()
            assertEquals("test", pick.status().chosen)
            assertEquals("test", pick.status().auto)
            assertEquals("test", picker().status().override)
            assertEquals(MachineVoicePick.SENTENCES, seen.filter { it != "forget" && it != "Xin chào." })
            assertEquals(2, seen.count { it == "forget" })
            assertEquals(500L, pick.status().engines.single().ramMb)
            assertNull(pick.status().engines.single().cer)
            assertNull(pick.status().engines.single().natural)
            pick.setOverride("")
            assertTrue(picker("another phone").status().engines.isEmpty())
            modelMark = "m2"
            assertTrue(pick.status().engines.isEmpty())
            assertNull(pick.status().chosen)
            assertTrue(runCatching { pick.setOverride("missing") }.isFailure)
        } finally { root.deleteRecursively() }
    }

    @Test fun failingSynthesisDoesNotStopOtherEnginesAndIsExcluded() {
        val root = Files.createTempDirectory("voice-pick-fail").toFile()
        try {
            val engine = object : LocalEngine {
                override val id = "broken"
                override val voices = listOf(VoiceInfo("broken:a", "A", "broken", false, false))
                override val capabilities = emptySet<String>()
                override val resourceNeeds = emptyMap<String, String>()
                override val mark = "m1"
                override fun synthesize(text: String, out: File): Clip = error("model hỏng")
                override fun forget() = Unit
            }
            val pick = MachineVoicePick(File(root, "pick.json"), "phone", { listOf(engine) }, { 0L })
            pick.measure()
            assertEquals("error", pick.status().engines.single().verdict)
            assertEquals("", pick.status().chosen)
            assertNull(pick.status().auto)
        } finally { root.deleteRecursively() }
    }
}
