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

    private val files get() = mapOf(
        "ort.gz" to ortGz, "g2p.gz" to g2pGz, "sea.whl" to wheel, "vieneu.whl" to voices, "turbo.bin" to turbo, "nano.bin" to nano,
    )

    private val base get() = "http://127.0.0.1:${server.localPort}/"

    private val groups get() = linkedMapOf(
        "ort" to listOf(Part("ort/libonnxruntime.so", digest(ortLib), ortLib.size.toLong(), base + "ort.gz", Packed(digest(ortGz), ortGz.size.toLong()), true)),
        "g2p" to listOf(
            Part("g2p/libabook_sea_g2p.so", digest(g2pLib), g2pLib.size.toLong(), base + "g2p.gz", Packed(digest(g2pGz), g2pGz.size.toLong()), true),
            Part("g2p/sea_g2p.bin", digest(dictionary), dictionary.size.toLong(), base + "sea.whl", Packed(digest(wheel), wheel.size.toLong(), "sea_g2p/sea_g2p.bin")),
        ),
        "voices" to listOf(Part("voices/vieneu-3.8.1-py3-none-any.whl", digest(voices), voices.size.toLong(), base + "vieneu.whl")),
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

    private fun module(shared: File? = null, blocked: String = "", parts: Map<String, List<Part>> = groups, ramGb: Double = 7.6) = VieneuModule(
        File(root, "vieneu"), shared, "arm64-v8a", VieneuModule.Facts(8, ramGb),
        benchmark = { tier -> benched.add(tier); VieneuModule.Benchmark(rtf.getValue(tier), 6000, 2000, 5.0) },
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
        assertFalse("the wheel is not kept", File(root, "vieneu/g2p/sea_g2p.bin.zip").exists())
        assertEquals(listOf("nano"), benched)
        assertEquals(1.84, status.getJSONObject("benchmark").getJSONObject("nano").getDouble("rtf"), 0.0)
        assertEquals("online", status.getJSONObject("suggestion").getString("switchTo"))
        assertEquals(1.84, module.rtf("vieneu:nano/Adam")!!, 0.0)
        assertNull(module.rtf("edge:vi-VN-HoaiMyNeural"))
        // Turbo now only lacks its own files: the shared parts are counted once
        assertEquals(wire("turbo"), choice(status, "turbo").getLong("bytes"))
        assertTrue(choice(status, "nano").getBoolean("installed"))
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
        assertFalse(File(root, "vieneu/g2p/sea_g2p.bin").exists())
        assertFalse(File(root, "vieneu/ort").exists())
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
        assertTrue("finished parts are kept", File(root, "vieneu/g2p/sea_g2p.bin").isFile)
    }
}
