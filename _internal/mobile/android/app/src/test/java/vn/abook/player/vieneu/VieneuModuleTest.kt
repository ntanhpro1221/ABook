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
import vn.abook.player.FakeTags
import vn.abook.player.MusicStore
import vn.abook.player.MusicStudentSetup
import vn.abook.player.PinnedFiles
import vn.abook.player.PinnedFiles.Packed
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.SharedRuntime
import vn.abook.player.readaloud.SupertonicModule
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.file.Files
import java.security.MessageDigest
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.zip.GZIPOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * The phone's "Giọng VieNeu" module with tiny stand-in files on a local server: nothing is fetched until a tap, the size shown is what this phone
 * lacks (shared parts once, "Gói nhạc"'s ONNX Runtime not at all), the dictionary comes out of its wheel, the self-benchmark runs after a
 * download and turns into a suggestion, a newer pin makes the module "outdated" and only that file is fetched, and each voice can be removed.
 * With "Giọng Supertonic" and "Gói nhạc": the runtime they need is downloaded once in any install order, and removing any of them keeps what
 * the modules still installed need - decided from what is on disk, with no record that could be lost.
 */
class VieneuModuleTest {
    private lateinit var server: ServerSocket
    private lateinit var root: File
    private val requests = CopyOnWriteArrayList<String>()
    private val benched = CopyOnWriteArrayList<String>()
    private val ranges = CopyOnWriteArrayList<String>()

    /** A file the server stops in the middle of: sends [first] bytes, tells the test ([reached]), waits for [gate], sends 1000 more and holds the
     *  connection (until [end]) - so a cancel lands while the module is part-way through that file. */
    private class Stall(val name: String, val first: Int) {
        val reached = CountDownLatch(1)
        val gate = CountDownLatch(1)
        val end = CountDownLatch(1)
    }

    @Volatile
    private var stall: Stall? = null
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
    private val clap = ByteArray(60_000) { (it % 227).toByte() }

    private val files get() = mapOf(
        "ort.gz" to ortGz, "g2p.gz" to g2pGz, "sea.whl" to wheel, "vieneu.whl" to voices, "turbo.bin" to turbo, "nano.bin" to nano,
        "supertonic.bin" to supertonic, "clap.bin" to clap,
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
        var range: String? = null
        while (true) {
            val line = input.readLine() ?: return
            if (line.isEmpty()) break
            if (line.startsWith("Range:", ignoreCase = true)) range = line.substringAfter(':').trim()
        }
        requests.add(name)
        range?.let { ranges.add(it) }
        val body = files[name]
        val out = client.getOutputStream()
        if (body == null) out.write("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
        else {
            val from = range?.removePrefix("bytes=")?.removeSuffix("-")?.toIntOrNull() ?: 0
            out.write("HTTP/1.1 ${if (range != null) "206 Partial Content" else "200 OK"}\r\nContent-Length: ${body.size - from}\r\nConnection: close\r\n\r\n".toByteArray())
            val held = stall?.takeIf { it.name == name && from == 0 }
            if (held == null) out.write(body, from, body.size - from)
            else {
                out.write(body, 0, held.first)
                out.flush()
                held.reached.countDown()
                held.gate.await(20, TimeUnit.SECONDS)
                out.write(body, held.first, 1000)
                out.flush()
                held.end.await(20, TimeUnit.SECONDS)
            }
        }
        out.flush()
    }

    @After
    fun tearDown() {
        stall?.let { it.gate.countDown(); it.end.countDown() }
        server.close()
        root.deleteRecursively()
    }

    /** Modules laid out under [files] as under the app's `files/` ([SharedRuntime.inFiles]). */
    private fun module(blocked: String = "", parts: Map<String, List<Part>> = groups, ramGb: Double = 7.6, files: File = root) = VieneuModule(
        File(files, VieneuModule.FOLDER), SharedRuntime.inFiles(files), "arm64-v8a", VoiceModule.Facts(8, ramGb),
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

    // ---- with "Giọng Supertonic" and "Gói nhạc": one runtime for all ------------------------------------------------------------------
    private val supertonicGroups get() = linkedMapOf(
        "ort" to groups.getValue("ort"), "g2p" to groups.getValue("g2p"),
        SupertonicModule.CHOICE to listOf(Part("model/onnx/vocoder.onnx", digest(supertonic), supertonic.size.toLong(), base + "supertonic.bin")),
    )

    private fun supertonic(files: File = root) = SupertonicModule(File(files, SupertonicModule.FOLDER), SharedRuntime.inFiles(files), "arm64-v8a",
        VoiceModule.Facts(8, 7.6), groups = supertonicGroups)

    /** "Gói nhạc" with a stand-in model and the same ONNX Runtime pin as the voices; [open] throwing = a package that cannot be opened (wiped). */
    private fun music(files: File = root, open: (File) -> ((File) -> JSONObject?) = { { null } }) = MusicStudentSetup(
        File(files, MusicStudentSetup.FOLDER), MusicStore(File(files, "mine"), FakeTags), open, SharedRuntime.inFiles(files), base,
        listOf(Part("clap.bin", digest(clap), clap.size.toLong())) + groups.getValue("ort"))

    private fun bytesOf(status: JSONObject) = status.getJSONArray("choices").getJSONObject(0).getLong("bytes")

    private val all = listOf("music", "vieneu", "supertonic")

    private fun <T> orders(items: List<T>): List<List<T>> =
        if (items.size <= 1) listOf(items) else items.flatMap { first -> orders(items - first).map { listOf(first) + it } }

    private fun install(name: String, files: File) {
        when (name) {
            "music" -> music(files).apply { start(); join() }
            "vieneu" -> module(files = files).apply { start(listOf("nano")); join() }
            else -> supertonic(files).apply { start(listOf(SupertonicModule.CHOICE)); join() }
        }
    }

    private fun installed(name: String, files: File): Boolean = when (name) {
        "music" -> music(files).complete()
        "vieneu" -> module(files = files).installed() != null
        else -> supertonic(files).installed() != null
    }

    /** Removing "Gói nhạc" = its package cannot be opened and is wiped (the phone has no other way to take it). */
    private fun remove(name: String, files: File) {
        when (name) {
            "music" -> assertFalse(music(files, open = { throw IllegalStateException("hỏng") }).attachIfPresent())
            "vieneu" -> module(files = files).remove("nano")
            else -> supertonic(files).remove(SupertonicModule.CHOICE)
        }
    }

    @Test
    fun everyInstallOrderFetchesTheRuntimeOnce() {
        for ((n, order) in orders(all).withIndex()) {
            val files = File(root, "order$n")
            requests.clear()
            order.forEach { install(it, files) }
            assertEquals("$order", 1, requests.count { it == "ort.gz" })
            assertEquals("$order", 1, requests.count { it == "g2p.gz" })
            assertTrue("$order", all.all { installed(it, files) })
            for (folder in listOf(MusicStudentSetup.FOLDER, VieneuModule.FOLDER, SupertonicModule.FOLDER)) {
                assertFalse("$order: no copy in $folder", File(files, "$folder/ort").exists() || File(files, "$folder/g2p").exists())
            }
        }
    }

    @Test
    fun theSizeShownIsOnlyWhatTheModuleItselfLacks() {
        install("vieneu", root)
        assertEquals(supertonicGroups.getValue(SupertonicModule.CHOICE).sumOf { it.wireSize }, bytesOf(supertonic().status()))
        assertEquals(clap.size.toLong(), music().status().getLong("total"))
        install("music", root)
        assertEquals(supertonic().folderFor("ort"), File(root, "runtime"))
        val fresh = File(root, "other").also { install("music", it) }
        assertEquals(wire("g2p", "voices", "nano"), choice(module(files = fresh).status(), "nano").getLong("bytes"))
    }

    @Test
    fun removingAnyModuleInAnyOrderKeepsWhatTheOthersStillNeed() {
        for ((n, order) in orders(all).withIndex()) {
            val files = File(root, "remove$n")
            all.forEach { install(it, files) }
            val left = all.toMutableList()
            for (name in order) {
                remove(name, files)
                left -= name
                assertFalse("$order: $name gone", installed(name, files))
                assertTrue("$order: $left still work after $name", left.all { installed(it, files) })
                assertEquals("$order after $name: ONNX Runtime", left.isNotEmpty(), File(files, "runtime/ort/libonnxruntime.so").isFile)
                assertEquals("$order after $name: sea-g2p", left.any { it != "music" }, File(files, "runtime/g2p/sea_g2p.bin").isFile)
            }
        }
    }

    @Test
    fun aModuleThatNothingRecordedIsStillKeptWorking() {
        // VieNeu's own files put in place by hand: no download ran, no claim, nothing written anywhere but its own folder
        val vieneu = File(root, VieneuModule.FOLDER)
        val own = listOf("voices", "nano").flatMap { groups.getValue(it) }
        val bytes = mapOf("voices" to voices, "nano" to nano)
        for (id in listOf("voices", "nano")) for (part in groups.getValue(id)) File(vieneu, part.name).apply { parentFile.mkdirs() }.writeBytes(bytes.getValue(id))
        PinnedFiles(vieneu, "", VoiceModule.STAMP).writeStamp(own.associate { it.name to it.sha256 })
        install("supertonic", root) // brings the runtime
        assertNotNull(module().installed())
        remove("supertonic", root)
        assertNotNull("VieNeu still reads", module().installed())
        assertEquals("nothing but the files and their stamp in the runtime folder", setOf("ort", "g2p", VoiceModule.STAMP),
            File(root, "runtime").list()!!.toSet())
        remove("vieneu", root)
        assertFalse(File(root, "runtime/ort").exists() || File(root, "runtime/g2p").exists())
    }

    @Test
    fun allTappedAtOnceFetchTheRuntimeOnce() {
        val vieneu = module()
        val supertonic = supertonic()
        val music = music()
        vieneu.start(listOf("nano"))
        supertonic.start(listOf(SupertonicModule.CHOICE))
        music.start()
        vieneu.join()
        supertonic.join()
        music.join()
        assertEquals(1, requests.count { it == "ort.gz" })
        assertEquals(1, requests.count { it == "g2p.gz" })
        assertTrue(all.all { installed(it, root) })
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

    @Test
    fun aCancelStopsTheDownloadKeepsThePartAndTheNextTapResumesWithRange() {
        val held = Stall("nano.bin", 30_000).also { stall = it }
        val module = module()
        assertFalse(module.status().getBoolean("cancelled"))
        assertTrue("the card may show Huỷ", module.status().getBoolean("cancellable"))
        module.cancel() // nothing is downloading: nothing happens
        assertFalse(module.status().getBoolean("cancelled"))
        module.start(listOf("nano"))
        assertTrue("the server holds nano.bin part-way", held.reached.await(20, TimeUnit.SECONDS))
        assertEquals("downloading", module.status().getString("state"))
        // wait until the phone has taken the first bytes in (the cancel is seen at the next read, not before the first)
        val partial0 = File(File(root, VieneuModule.FOLDER), "nano/nano.bin.part")
        val until = System.currentTimeMillis() + 20_000
        while (partial0.length() < 30_000 && System.currentTimeMillis() < until) Thread.sleep(10)
        module.cancel()
        held.gate.countDown()
        module.join()
        val status = module.status()
        assertEquals(status.toString(), "missing", status.getString("state"))
        assertTrue(status.getBoolean("cancelled"))
        assertEquals("", status.getString("error"))
        assertEquals(0, status.getLong("done"))
        val folder = File(root, VieneuModule.FOLDER)
        val partial = File(folder, "nano/nano.bin.part")
        assertEquals("what was sent stays for the next tap", 31_000L, partial.length())
        assertFalse(File(folder, "nano/nano.bin").exists())
        assertTrue("a cancelled download measures nothing", benched.isEmpty())
        // the next tap resumes where it stopped and clears the note
        stall = null
        held.end.countDown()
        ranges.clear()
        module.start(listOf("nano"))
        assertFalse("the note goes as soon as the download starts", module.status().getBoolean("cancelled"))
        module.join()
        assertEquals(module.status().toString(), "ready", module.status().getString("state"))
        assertEquals(listOf("bytes=31000-"), ranges.toList())
        assertEquals(nano.toList(), File(folder, "nano/nano.bin").readBytes().toList())
        assertFalse(partial.exists())
        assertFalse(module.status().getBoolean("cancelled"))
    }
}
