package vn.abook.player.vieneu

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.PinnedFiles.Packed
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.readaloud.SupertonicModule
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.file.Files
import java.security.MessageDigest
import java.util.concurrent.CopyOnWriteArrayList
import java.util.zip.GZIPOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * The phone's "Giọng VieNeu" module with tiny stand-in files on a local server: nothing is fetched until a tap, the size shown is what this phone
 * lacks (shared parts once, "Gói nhạc"'s ONNX Runtime not at all), the dictionary comes out of its wheel, the self-benchmark runs after a
 * download and turns into a suggestion, a newer pin makes the module "outdated" and only that file is fetched, and each voice can be removed.
 * With "Giọng Supertonic": the runtime both need is downloaded once whichever comes first, and removing one never breaks the other.
 */
class VieneuModuleTest {
    private lateinit var server: ServerSocket
    private lateinit var root: File
    private val requests = CopyOnWriteArrayList<String>()
    private val benched = CopyOnWriteArrayList<String>()
    private var rtf = mapOf("turbo" to 1.75, "nano" to 1.84)

    private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private val ortLib = ByteArray(40_000) { (it * 13).toByte() }
    private val ortGz = ByteArrayOutputStream().also { sink -> GZIPOutputStream(sink).use { it.write(ortLib) } }.toByteArray()
    private val g2pLib = ByteArray(30_000) { (it * 7 + 1).toByte() }
    private val g2pGz = ByteArrayOutputStream().also { sink -> GZIPOutputStream(sink).use { it.write(g2pLib) } }.toByteArray()
    private val dictionary = ByteArray(120_000) { (it / 3).toByte() }
    private val wheel = ByteArrayOutputStream().also { sink ->
        ZipOutputStream(sink).use { zip ->
            zip.putNextEntry(ZipEntry("sea_g2p/__init__.py")); zip.write("x".toByteArray())
            zip.putNextEntry(ZipEntry("sea_g2p/sea_g2p.bin")); zip.write(dictionary)
        }
    }.toByteArray()
    private val voices = "voices".repeat(1000).toByteArray()
    private val turbo = ByteArray(90_000) { (it % 251).toByte() }
    private var nano = ByteArray(70_000) { (it % 241).toByte() }
    private val supertonic = ByteArray(50_000) { (it % 233).toByte() }

    private val files get() = mapOf(
        "ort.gz" to ortGz, "g2p.gz" to g2pGz, "sea.whl" to wheel, "vieneu.whl" to voices, "turbo.bin" to turbo, "nano.bin" to nano,
        "supertonic.bin" to supertonic,
    )

    private val base get() = "http://127.0.0.1:${server.localPort}/"

    private val groups get() = linkedMapOf(
        "ort" to listOf(Part("ort/libonnxruntime.so", digest(ortLib), ortLib.size.toLong(), base + "ort.gz", Packed(digest(ortGz), ortGz.size.toLong()), true)),
        "g2p" to listOf(
            Part("g2p/libabook_sea_g2p.so", digest(g2pLib), g2pLib.size.toLong(), base + "g2p.gz", Packed(digest(g2pGz), g2pGz.size.toLong()), true),
            Part("g2p/sea_g2p.bin", digest(dictionary), dictionary.size.toLong(), base + "sea.whl", Packed(digest(wheel), wheel.size.toLong(), "sea_g2p/sea_g2p.bin")),
        ),
        "voices" to listOf(Part("voices/vieneu-3.8.3-py3-none-any.whl", digest(voices), voices.size.toLong(), base + "vieneu.whl")),
        "turbo" to listOf(Part("turbo/turbo.bin", digest(turbo), turbo.size.toLong(), base + "turbo.bin")),
        "nano" to listOf(Part("nano/nano.bin", digest(nano), nano.size.toLong(), base + "nano.bin")),
    )

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-vieneu").toFile()
        server = ServerSocket(0, 5, InetAddress.getByName("127.0.0.1"))
        Thread {
            while (!server.isClosed) {
                val client = try {
                    server.accept()
                } catch (_: Exception) {
                    break
                }
                Thread { client.use { serve(it) } }.start()
            }
        }.apply { isDaemon = true }.start()
    }

    private fun serve(client: Socket) {
        val input = client.getInputStream().bufferedReader(Charsets.ISO_8859_1)
        val name = (input.readLine() ?: return).split(' ')[1].removePrefix("/")
        while (true) if ((input.readLine() ?: return).isEmpty()) break
        requests.add(name)
        val body = files[name]
        val out = client.getOutputStream()
        if (body == null) out.write("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
        else {
            out.write("HTTP/1.1 200 OK\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray())
            out.write(body)
        }
        out.flush()
    }

    @After
    fun tearDown() {
        server.close()
        root.deleteRecursively()
    }

    private fun runtime(music: File? = null) = SharedRuntime(File(root, "runtime"), listOfNotNull(music))

    private fun module(music: File? = null, blocked: String = "", parts: Map<String, List<Part>> = groups, ramGb: Double = 7.6) = VieneuModule(
        File(root, "vieneu"), runtime(music), "arm64-v8a", VoiceModule.Facts(8, ramGb),
        benchmark = { tier -> benched.add(tier); VoiceModule.Benchmark(rtf.getValue(tier), 6000, 2000, 5.0) },
        groups = parts, blocked = blocked,
    )

    private fun choice(status: JSONObject, id: String): JSONObject =
        (0 until status.getJSONArray("choices").length()).map { status.getJSONArray("choices").getJSONObject(it) }.first { it.getString("id") == id }

    private fun wire(vararg ids: String) = ids.flatMap { groups.getValue(it) }.sumOf { it.wireSize }

    @Test
    fun nothingIsFetchedBeforeATapAndNanoIsWhatAPhoneIsOffered() {
        val status = module().status()
        assertEquals("missing", status.getString("state"))
        assertEquals("nano", status.getString("recommended"))
        assertTrue(choice(status, "nano").getBoolean("recommended") && choice(status, "nano").getBoolean("default"))
        assertFalse(choice(status, "turbo").getBoolean("default"))
        assertEquals(wire("ort", "g2p", "voices", "nano"), choice(status, "nano").getLong("bytes"))
        assertEquals(wire("ort", "g2p", "voices", "turbo"), choice(status, "turbo").getLong("bytes"))
        assertTrue(requests.isEmpty())
        assertNull(module().installed())
    }

    @Test
    fun aTapDownloadsNanoMeasuresItAndSuggestsMakingAheadWhenItIsSlow() {
        val module = module()
        module.start(listOf("nano"))
        module.join()
        val status = module.status()
        assertEquals(status.toString(), "ready", status.getString("state"))
        assertEquals(setOf("ort.gz", "g2p.gz", "sea.whl", "vieneu.whl", "nano.bin"), requests.toSet())
        val installed = module.installed()
        assertNotNull(installed)
        assertNull(installed!!.turbo)
        assertEquals(digest(dictionary), digest(installed.dictionary.readBytes()))
        assertFalse("the wheel is not kept", File(root, "runtime/g2p/sea_g2p.bin.zip").exists())
        assertEquals("the runtime is kept for every voice", File(root, "runtime"), module.ortFolder())
        assertEquals(listOf("nano"), benched)
        assertEquals(1.84, status.getJSONObject("benchmark").getJSONObject("nano").getDouble("rtf"), 0.0)
        assertEquals("online", status.getJSONObject("suggestion").getString("switchTo"))
        assertEquals(1.84, module.rtf("vieneu:nano/Adam")!!, 0.0)
        assertNull(module.rtf("edge:vi-VN-HoaiMyNeural"))
        // Turbo now only lacks its own files: the shared parts are counted once
        assertEquals(wire("turbo"), choice(status, "turbo").getLong("bytes"))
        assertTrue(choice(status, "nano").getBoolean("installed"))
    }

    /** At [VoiceModule.SLOW_RTF] a voice cannot be read live (the card points to "Làm trước"), just under it it can - the line Supertonic shares. */
    @Test
    fun theSlowLineIsSlowRtfForEveryVoice() {
        val module = module()
        rtf = mapOf("turbo" to VoiceModule.SLOW_RTF, "nano" to VoiceModule.SLOW_RTF)
        module.start(listOf("nano"))
        module.join()
        assertEquals("online", module.status().getJSONObject("suggestion").getString("switchTo"))
        rtf = mapOf("turbo" to VoiceModule.SLOW_RTF - 0.01, "nano" to VoiceModule.SLOW_RTF - 0.01)
        module.measureAgain()
        module.join()
        assertTrue(module.status().isNull("suggestion"))
    }

    @Test
    fun aFastPhoneIsToldTurboIsWorthIt() {
        rtf = mapOf("turbo" to 0.5, "nano" to 0.4)
        val module = module()
        module.start(listOf("nano"))
        module.join()
        assertEquals("nano fast enough -> turbo recommended", "turbo", module.status().getString("recommended"))
        assertTrue(module.status().isNull("suggestion"))
    }

    @Test
    fun aFastPhoneWithLittleMemoryIsStillToldNanoAndWhy() {
        rtf = mapOf("turbo" to 0.5, "nano" to 0.4)
        val module = module(ramGb = 3.6)
        module.start(listOf("nano"))
        module.join()
        val status = module.status()
        assertEquals("nano", status.getString("recommended"))
        assertTrue(choice(status, "turbo").getString("detail").contains("4 GB RAM"))
        assertFalse(choice(status, "nano").getString("detail").contains("RAM"))
    }

    @Test
    fun theMusicPackagesOnnxRuntimeIsUsedAndNotCounted() {
        val shared = File(root, "music/student").also { File(it, "ort").mkdirs() }
        File(shared, "ort/libonnxruntime.so").writeBytes(ortLib)
        val module = module(shared)
        val status = module.status()
        assertEquals(wire("g2p", "voices", "nano"), choice(status, "nano").getLong("bytes"))
        module.start(listOf("nano"))
        module.join()
        assertFalse(requests.contains("ort.gz"))
        assertEquals(shared, module.ortFolder())
        assertNotNull(module.installed())
    }

    @Test
    fun aNewerPinMakesTheModuleOutdatedAndOnlyThatFileIsFetched() {
        module().apply { start(listOf("nano")); join() }
        requests.clear()
        nano = ByteArray(70_000) { (it % 239).toByte() }
        val newer = module()
        val status = newer.status()
        assertEquals("outdated", status.getString("state"))
        assertEquals(wire("nano"), status.getLong("outdatedBytes"))
        assertNotNull("the older voice keeps working until the update", newer.installed())
        newer.start(null)
        newer.join()
        assertEquals(listOf("nano.bin"), requests.toList())
        assertEquals("ready", newer.status().getString("state"))
    }

    @Test
    fun removingOneVoiceKeepsWhatTheOtherNeedsAndTheLastTakesEverything() {
        val module = module()
        module.start(listOf("nano", "turbo"))
        module.join()
        assertEquals(setOf("nano", "turbo"), benched.toSet())
        module.remove("nano")
        val after = module.installed()
        assertNotNull(after)
        assertNull(after!!.nano)
        assertTrue(after.dictionary.isFile)
        assertFalse(File(root, "vieneu/nano").exists())
        module.remove("turbo")
        assertNull(module.installed())
        assertEquals("missing", module.status().getString("state"))
        assertFalse(File(root, "vieneu").exists())
        assertFalse("no other voice uses the runtime", File(root, "runtime/g2p").exists() || File(root, "runtime/ort").exists())
    }

    // ---- with "Giọng Supertonic": one runtime for both ----------------------------------------------------------------------------
    private val supertonicGroups get() = linkedMapOf(
        "ort" to groups.getValue("ort"), "g2p" to groups.getValue("g2p"),
        SupertonicModule.CHOICE to listOf(Part("model/onnx/vocoder.onnx", digest(supertonic), supertonic.size.toLong(), base + "supertonic.bin")),
    )

    private fun supertonic(music: File? = null) = SupertonicModule(File(root, "supertonic"), runtime(music), "arm64-v8a", VoiceModule.Facts(8, 7.6),
        groups = supertonicGroups)

    private fun bytesOf(status: JSONObject) = status.getJSONArray("choices").getJSONObject(0).getLong("bytes")

    @Test
    fun vieneuFirstThenSupertonicDownloadsOnlyItsModel() {
        module().apply { start(listOf("nano")); join() }
        requests.clear()
        val second = supertonic()
        assertEquals(supertonicGroups.getValue(SupertonicModule.CHOICE).sumOf { it.wireSize }, bytesOf(second.status()))
        second.start(listOf(SupertonicModule.CHOICE))
        second.join()
        assertEquals(listOf("supertonic.bin"), requests.toList())
        val installed = second.installed()
        assertNotNull(installed)
        assertEquals(File(root, "runtime"), installed!!.ortFolder)
        assertEquals(File(root, "runtime/g2p/sea_g2p.bin"), installed.g2p!!.second)
        assertFalse(File(root, "supertonic/ort").exists() || File(root, "vieneu/ort").exists())
    }

    @Test
    fun supertonicFirstThenVieneuDownloadsOnlyItsVoices() {
        supertonic().apply { start(listOf(SupertonicModule.CHOICE)); join() }
        requests.clear()
        val second = module()
        assertEquals(wire("voices", "nano"), choice(second.status(), "nano").getLong("bytes"))
        second.start(listOf("nano"))
        second.join()
        assertEquals(setOf("vieneu.whl", "nano.bin"), requests.toSet())
        assertNotNull(second.installed())
        assertEquals(File(root, "runtime"), second.ortFolder())
    }

    @Test
    fun bothTappedAtOnceFetchTheRuntimeOnce() {
        val first = module()
        val second = supertonic()
        first.start(listOf("nano"))
        second.start(listOf(SupertonicModule.CHOICE))
        first.join()
        second.join()
        assertEquals(1, requests.count { it == "ort.gz" })
        assertEquals(1, requests.count { it == "g2p.gz" })
        assertNotNull(first.installed())
        assertNotNull(second.installed())
    }

    @Test
    fun removingOneVoiceKeepsTheOtherWorkingAndTheLastTakesTheRuntime() {
        val vieneu = module()
        val supertonic = supertonic()
        vieneu.apply { start(listOf("nano")); join() }
        supertonic.apply { start(listOf(SupertonicModule.CHOICE)); join() }
        vieneu.remove("nano")
        assertNull(vieneu.installed())
        assertFalse(File(root, "vieneu").exists())
        assertNotNull("Supertonic still reads", supertonic.installed())
        assertEquals("ready", supertonic.status().getString("state"))
        assertTrue(File(root, "runtime/ort/libonnxruntime.so").isFile && File(root, "runtime/g2p/sea_g2p.bin").isFile)
        // and the other way round: VieNeu back, Supertonic removed
        requests.clear()
        vieneu.apply { start(listOf("nano")); join() }
        assertFalse("the runtime was kept", requests.contains("ort.gz") || requests.contains("g2p.gz"))
        supertonic.remove(SupertonicModule.CHOICE)
        assertFalse(File(root, "supertonic").exists())
        assertNotNull("VieNeu still reads", vieneu.installed())
        vieneu.remove("nano")
        assertFalse("no voice left -> no runtime left", File(root, "runtime/ort").exists() || File(root, "runtime/g2p").exists())
        assertFalse(File(root, "runtime/${SharedRuntime.USERS}").exists())
    }

    @Test
    fun aRuntimeCopyInTheVoicesOwnFolderIsDroppedOnceTheSharedOneIsHere() {
        File(root, "vieneu/ort").mkdirs()
        File(root, "vieneu/ort/libonnxruntime.so").writeBytes(ortLib)
        File(root, "vieneu/g2p").mkdirs()
        File(root, "vieneu/g2p/sea_g2p.bin").writeBytes(dictionary)
        val module = module()
        module.start(listOf("nano"))
        module.join()
        assertNotNull(module.installed())
        assertFalse(File(root, "vieneu/ort").exists() || File(root, "vieneu/g2p").exists())
        assertTrue(File(root, "runtime/ort/libonnxruntime.so").isFile)
    }

    @Test
    fun theMusicPackagesOnnxRuntimeServesBothVoicesAndIsNeverRemoved() {
        val music = File(root, "music/student").also { File(it, "ort").mkdirs() }
        File(music, "ort/libonnxruntime.so").writeBytes(ortLib)
        val vieneu = module(music)
        val supertonic = supertonic(music)
        vieneu.apply { start(listOf("nano")); join() }
        supertonic.apply { start(listOf(SupertonicModule.CHOICE)); join() }
        assertFalse(requests.contains("ort.gz"))
        assertEquals(music, supertonic.installed()!!.ortFolder)
        supertonic.remove(SupertonicModule.CHOICE)
        vieneu.remove("nano")
        assertTrue(File(music, "ort/libonnxruntime.so").isFile)
    }

    @Test
    fun aPhoneThatCannotRunItSaysWhyAndDownloadsNothing() {
        val module = module(blocked = "điện thoại này chưa chạy được giọng VieNeu (kiến trúc máy chưa hỗ trợ)")
        assertEquals("unsupported", module.status().getString("state"))
        assertFalse(module.status().getBoolean("supported"))
        module.start(listOf("nano"))
        module.join()
        assertTrue(requests.isEmpty())
        assertEquals("error", module.status().getString("state"))
    }

    @Test
    fun aMissingFileOnTheServerIsAReadableErrorAndTheNextTapRetries() {
        val parts = LinkedHashMap(groups).apply { put("nano", listOf(Part("nano/nano.bin", digest(nano), nano.size.toLong(), base + "gone.bin"))) }
        val module = module(parts = parts)
        module.start(listOf("nano"))
        module.join()
        val status = module.status()
        assertEquals("error", status.getString("state"))
        assertTrue(status.getString("error"), status.getString("error").startsWith("Không tải được giọng VieNeu"))
        assertTrue("finished parts are kept", File(root, "runtime/g2p/sea_g2p.bin").isFile)
    }
}
