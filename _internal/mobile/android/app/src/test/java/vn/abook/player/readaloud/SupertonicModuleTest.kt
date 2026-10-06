package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.PinnedFiles
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.vieneu.SharedRuntime
import vn.abook.player.vieneu.VieneuModule
import vn.abook.player.vieneu.VoiceModule
import java.io.File
import java.nio.file.Files

/**
 * The phone's "Giọng Supertonic" module (the download itself is VoiceModule's, tested through VieneuModuleTest, with both voices): the same pins
 * as the desktop for the model, the very ONNX Runtime / sea-g2p files of "Giọng VieNeu", kept once for both ([SharedRuntime]) or used where
 * "Gói nhạc" has them, and not counted; one choice, ticked, not "Khuyên dùng"; slower than listening -> an online voice is offered; removing it
 * never takes what another voice still uses.
 */
class SupertonicModuleTest {
    private val root: File = Files.createTempDirectory("abook-supertonic").toFile()
    private val music = File(root, "music/student")
    private val shared = File(root, "runtime")
    private val runtime = SharedRuntime(shared, listOf(music))

    private fun part(name: String, size: Int) = ByteArray(size) { (it * 7 + name.length).toByte() }.let { bytes ->
        Part(name, PinnedFiles.sha256Of(bytes), bytes.size.toLong(), "http://127.0.0.1:9/$name", blocking = name.endsWith(".so")) to bytes
    }

    private val files = mapOf(
        "ort" to listOf(part("ort/libonnxruntime.so", 4000), part("ort/libonnxruntime4j_jni.so", 300)),
        "g2p" to listOf(part("g2p/libabook_sea_g2p.so", 2000), part("g2p/sea_g2p.bin", 5000)),
        "supertonic" to listOf(part("model/onnx/vocoder.onnx", 3000), part("model/voice_styles/F1.json", 100)),
    )
    private val groups = files.mapValues { (_, list) -> list.map { it.first } }
    private val rtf = mutableListOf(1.9)

    private fun module() = SupertonicModule(File(root, "supertonic"), runtime, "arm64-v8a", VoiceModule.Facts(8, 7.6),
        benchmark = { VoiceModule.Benchmark(rtf.last(), 5000, 1000, 6.0) }, groups = groups)

    /** Put part [id]'s files in [folder] (as a module that downloaded them would). */
    private fun place(folder: File, id: String) {
        for ((part, bytes) in files.getValue(id)) File(folder, part.name).apply { parentFile.mkdirs() }.writeBytes(bytes)
        val pinned = PinnedFiles(folder, "", VoiceModule.STAMP)
        pinned.writeStamp(pinned.readStamp() + files.getValue(id).associate { it.first.name to it.first.sha256 })
    }

    private fun wire(vararg ids: String) = ids.flatMap { groups.getValue(it) }.sumOf { it.wireSize }

    private fun choice(status: JSONObject) = status.getJSONArray("choices").getJSONObject(0)

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    @Test
    fun theModelIsPinnedLikeTheDesktopAndNothingIsHereBeforeATap() {
        assertEquals(18, SupertonicModule.FILES.size)
        assertTrue(SupertonicModule.FILES.all { it.remote.startsWith("https://huggingface.co/Supertone/supertonic-3/resolve/") && it.name.startsWith("model/") })
        val status = module().status()
        assertEquals("missing", status.getString("state"))
        assertEquals("supertonic", status.getString("recommended"))
        assertFalse(choice(status).getBoolean("recommended"))
        assertTrue(choice(status).getBoolean("default"))
        assertEquals(wire("ort", "g2p", "supertonic"), choice(status).getLong("bytes"))
        assertNull(module().installed())
    }

    @Test
    fun theSharedRuntimeAndTheMusicPackagesAreUsedWhereTheyAreAndNotCounted() {
        place(music, "ort")
        place(shared, "g2p")
        val module = module()
        val status = module.status()
        assertEquals(wire("supertonic"), choice(status).getLong("bytes"))
        val parts = status.getJSONArray("parts")
        assertTrue((0 until parts.length()).map { parts.getJSONObject(it) }.filter { it.getString("id") != "supertonic" }.all { it.getBoolean("external") })
        place(File(root, "supertonic"), "supertonic")
        val installed = module.installed()
        assertNotNull(installed)
        assertEquals(music, installed!!.ortFolder)
        assertEquals(File(shared, "g2p/sea_g2p.bin"), installed.g2p!!.second)
        assertEquals(File(root, "supertonic/model"), installed.model)
        assertEquals("ready", module.status().getString("state"))
    }

    @Test
    fun withoutTheTextReaderTheVoiceStillReadsTheTextAsWritten() {
        place(shared, "ort")
        place(File(root, "supertonic"), "supertonic")
        val installed = module().installed()
        assertNotNull(installed)
        assertNull(installed!!.g2p)
        assertEquals(shared, installed.ortFolder)
    }

    @Test
    fun aSlowPhoneIsOfferedAnOnlineVoiceAndAFastOneNothing() {
        listOf("ort", "g2p").forEach { place(shared, it) }
        place(File(root, "supertonic"), "supertonic")
        val module = module()
        module.measureAgain()
        module.join()
        val slow = module.status()
        assertEquals(1.9, slow.getJSONObject("benchmark").getJSONObject("supertonic").getDouble("rtf"), 0.0)
        assertEquals("online", slow.getJSONObject("suggestion").getString("switchTo"))
        assertEquals(1.9, module.rtf("supertonic:F1")!!, 0.0)
        assertNull(module.rtf("vieneu:nano/Adam"))
        rtf.add(0.4)
        module.measureAgain()
        module.join()
        assertTrue(module.status().isNull("suggestion"))
    }

    /** The same line as "Giọng VieNeu" (VieneuModuleTest): at SLOW_RTF this phone cannot read live and the card points to "Làm trước". */
    @Test
    fun tooSlowToReadLiveIsTheSameLineAsVieneu() {
        listOf("ort", "g2p").forEach { place(shared, it) }
        place(File(root, "supertonic"), "supertonic")
        val module = module()
        for ((value, slow) in listOf(VoiceModule.SLOW_RTF to true, VoiceModule.SLOW_RTF - 0.01 to false, 1.9 to true)) {
            rtf.add(value)
            module.measureAgain()
            module.join()
            val status = module.status()
            assertEquals(VoiceModule.SLOW_RTF, status.getDouble("slowRtf"), 0.0)
            assertEquals("rtf $value", slow, !status.isNull("suggestion"))
        }
    }

    @Test
    fun removingItKeepsWhatAnotherVoiceUses() {
        place(music, "ort")
        place(shared, "g2p")
        runtime.use("vieneu", listOf("g2p"))
        place(File(root, "supertonic"), "supertonic")
        val module = module()
        module.remove("supertonic")
        assertNull(module.installed())
        assertFalse(File(root, "supertonic").exists())
        assertTrue(File(music, "ort/libonnxruntime.so").isFile)
        assertTrue("VieNeu still uses it", File(shared, "g2p/sea_g2p.bin").isFile)
        assertEquals("missing", module.status().getString("state"))
    }

    @Test
    fun theTextReaderPartIsVieneusPinnedFiles() {
        fun pins(parts: List<Part>) = parts.filter { it.name.startsWith("g2p/") || it.name.startsWith("ort/") }.map { listOf(it.name, it.sha256, it.size, it.remote) }.toSet()
        val supertonic = SupertonicModule(File(root, "supertonic"), runtime, "arm64-v8a", VoiceModule.Facts(8, 7.6))
        val vieneu = VieneuModule(File(root, "vieneu"), runtime, "arm64-v8a", VoiceModule.Facts(8, 7.6))
        assertEquals(4, pins(supertonic.parts(listOf("supertonic"))).size)
        assertEquals(pins(vieneu.parts(listOf("nano"))), pins(supertonic.parts(listOf("supertonic"))))
    }
}
