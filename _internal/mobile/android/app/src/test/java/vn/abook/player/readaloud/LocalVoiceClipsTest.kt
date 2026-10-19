package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.PinnedFiles
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.SharedRuntime
import vn.abook.player.vieneu.NumpyRandomState
import vn.abook.player.vieneu.VieneuModule
import vn.abook.player.vieneu.VieneuNano
import vn.abook.player.vieneu.VieneuPreset
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuTier
import vn.abook.player.vieneu.VieneuUnits
import vn.abook.player.vieneu.VoiceModule
import java.io.File
import java.nio.file.Files
import java.util.concurrent.CancellationException

/**
 * Voices that run on the phone (VieNeu, Supertonic), the four faults of review a63 (desktop: tests/test_uxfix70_local_voices.py):
 * the model mark in the clip key, the size still to download on the module card, "Tốc độ giọng trên máy" changed while listening, and a read
 * nobody needs any more stopping between chunks and steps.
 */
class LocalVoiceClipsTest {
    private val root: File = Files.createTempDirectory("abook-local-voices").toFile()

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    // ---- 1. model mark in the clip key ---------------------------------------------------------------------------------------------
    private fun put(cache: ClipCache, voice: String, text: String, durationMs: Long = 1000) {
        val tmp = cache.temp("wav")
        tmp.writeBytes(ByteArray(100) { 1 })
        cache.put(voice, text, tmp, "wav", durationMs, listOf(Span(0, durationMs)))
    }

    @Test
    fun anUpdatedModelOrScheduleMissesTheOldClipsOfLocalVoicesOnly() {
        var mark = "aaaa1111"
        val asked = ArrayList<Pair<String, String>>()
        val cache = ClipCache(File(root, "cache"), markOf = { voice, tier -> asked.add(voice to tier); mark })
        put(cache, "supertonic:F1#q", "Trời mưa.")
        put(cache, "vieneu:nano/Adam", "Trời mưa.")
        put(cache, "edge:vi-VN-HoaiMyNeural", "Trời mưa.")
        assertNotNull(cache.get("supertonic:F1#q", "Trời mưa."))
        assertEquals(listOf("supertonic:F1" to "", "vieneu:nano/Adam" to ""), asked.distinct())
        mark = "bbbb2222" // new pins (model update) or a new schedule (steps)
        assertNull("Supertonic reads it again", cache.get("supertonic:F1#q", "Trời mưa."))
        assertNull("VieNeu reads it again", cache.get("vieneu:nano/Adam", "Trời mưa."))
        assertNotNull("Edge keeps its key", cache.get("edge:vi-VN-HoaiMyNeural", "Trời mưa."))
        assertTrue(asked.none { it.first.startsWith("edge:") })
    }

    private fun part(name: String, size: Int, seed: Int = 0) = ByteArray(size) { (it * 7 + name.length + seed).toByte() }.let { bytes ->
        Part(name, PinnedFiles.sha256Of(bytes), bytes.size.toLong(), "http://127.0.0.1:9/$name", blocking = name.endsWith(".so")) to bytes
    }

    private val files = mapOf(
        "ort" to listOf(part("ort/libonnxruntime.so", 400), part("ort/libonnxruntime4j_jni.so", 30)),
        "g2p" to listOf(part("g2p/libabook_sea_g2p.so", 200), part("g2p/sea_g2p.bin", 500)),
        SupertonicModule.CHOICE to listOf(part("model/onnx/vocoder.onnx", 3000), part("model/voice_styles/F1.json", 100)),
        SupertonicModule.FAST_CHOICE to listOf(part(SupertonicText.FAST_ESTIMATOR, 2000)),
    )
    private val groups = files.mapValues { (_, list) -> list.map { it.first } }
    private val runtime = SharedRuntime.inFiles(root)
    private val shared = File(root, "runtime")
    private val folder = File(root, SupertonicModule.FOLDER)

    private fun supertonic() = SupertonicModule(folder, runtime, "arm64-v8a", VoiceModule.Facts(8, 7.6), groups = groups)

    /** Put part [id]'s files in [dir] as a download would; [pin] overrides the stamp (an older version on the phone). */
    private fun place(dir: File, id: String, pin: ((Part) -> String)? = null) {
        for ((part, bytes) in files.getValue(id)) File(dir, part.name).apply { parentFile.mkdirs() }.writeBytes(bytes)
        val pinned = PinnedFiles(dir, "", VoiceModule.STAMP)
        pinned.writeStamp(pinned.readStamp() + files.getValue(id).associate { it.first.name to (pin?.invoke(it.first) ?: it.first.sha256) })
    }

    @Test
    fun theMarkComesFromTheDownloadedPinsAndTheSchedule() {
        listOf("ort", "g2p").forEach { place(shared, it) }
        place(folder, SupertonicModule.CHOICE)
        place(folder, SupertonicModule.FAST_CHOICE)
        val module = supertonic()
        val quality = module.mark(false)
        assertTrue(quality.matches(Regex("[0-9a-f]{8}")))
        assertEquals("computed once, same answer", quality, module.mark(false))
        assertNotEquals("the fast tier reads with its own estimator and steps", quality, module.mark(true))
        // a phone holding another version of the model has another mark (a fresh module reads the stamp again)
        place(folder, SupertonicModule.CHOICE) { "0".repeat(64) }
        assertNotEquals(quality, supertonic().mark(false))
        // removing a part forgets the computed marks
        val before = module.mark(true)
        module.remove(SupertonicModule.FAST_CHOICE)
        assertNotEquals(before, module.mark(true))
    }

    @Test
    fun vieneuMarksTheTierModelAndNanosSchedule() {
        val nano = listOf(part("nano/vector_estimator.onnx", 300))
        val turbo = listOf(part("turbo/backbone.onnx", 300))
        val voices = listOf(part("voices.whl", 50))
        val vieneuGroups = mapOf("ort" to emptyList(), "g2p" to emptyList(), "voices" to voices.map { it.first }, "turbo" to turbo.map { it.first }, "nano" to nano.map { it.first })
        val module = VieneuModule(File(root, "vieneu"), runtime, "arm64-v8a", VoiceModule.Facts(8, 7.6), groups = vieneuGroups)
        val nanoMark = module.mark("vieneu:nano/Adam")
        assertEquals(nanoMark, module.mark("vieneu:nano/Binh"))
        assertNotEquals(nanoMark, module.mark("vieneu:turbo/Adam"))
        assertEquals(module.mark(listOf("voices", "nano"), "nano:${VieneuNano.STEPS}:${VieneuNano.CFG}:${VieneuNano.CFG_LAST}"), nanoMark)
        assertNotEquals("the schedule is part of the mark", module.mark(listOf("voices", "nano"), "nano:8:3.0:true"), nanoMark)
    }

    // ---- 2. the size still to download -------------------------------------------------------------------------------------------
    @Test
    fun theCardShowsWhatIsStillToDownloadAlsoAfterCancel() {
        listOf("ort", "g2p").forEach { place(shared, it) }
        val module = supertonic()
        fun choice(id: String) = module.status().getJSONArray("choices").let { all -> (0 until all.length()).map { all.getJSONObject(it) } }.firstOrNull { it.getString("id") == id }
        fun partBytes(id: String) = module.status().getJSONArray("parts").let { all -> (0 until all.length()).map { all.getJSONObject(it) } }.first { it.getString("id") == id }.getLong("bytes")
        assertEquals(3100L, choice(SupertonicModule.CHOICE)!!.getLong("bytes"))
        // Huỷ after 1200 bytes of the vocoder: the .part stays and the next tap resumes it
        File(folder, "model/onnx/vocoder.onnx.part").apply { parentFile.mkdirs() }.writeBytes(ByteArray(1200))
        assertEquals(1900L, choice(SupertonicModule.CHOICE)!!.getLong("bytes"))
        assertEquals(1900L, partBytes(SupertonicModule.CHOICE))
        // the fast tier: its own bytes only, its .part counted too
        File(folder, "${SupertonicText.FAST_ESTIMATOR}.part").apply { parentFile.mkdirs() }.writeBytes(ByteArray(500))
        assertEquals(1500L, module.speedFastBytes())
        // installed, then a newer pin for one file: "Cập nhật" shows that file, less its .part
        File(folder, "model/onnx/vocoder.onnx.part").delete()
        place(folder, SupertonicModule.CHOICE) { if (it.name.endsWith("vocoder.onnx")) "0".repeat(64) else it.sha256 }
        val outdated = module.status()
        assertEquals("outdated", outdated.getString("state"))
        assertEquals(3000L, outdated.getLong("outdatedBytes"))
        File(folder, "model/onnx/vocoder.onnx.part").writeBytes(ByteArray(1000))
        assertEquals(2000L, module.status().getLong("outdatedBytes"))
        // a current part shows its whole size
        assertEquals(430L, partBytes("ort"))
    }

    @Test
    fun aPartLeftCountsOnlyWhatIsMissingAndNeverBelowZero() {
        val (part, bytes) = part("model/x.onnx", 1000)
        val pinned = PinnedFiles(File(root, "p"), "", VoiceModule.STAMP)
        assertEquals(1000L, pinned.left(part))
        File(root, "p/model").mkdirs()
        File(root, "p/model/x.onnx.part").writeBytes(ByteArray(400))
        assertEquals(600L, pinned.left(part))
        File(root, "p/model/x.onnx.part").writeBytes(ByteArray(1400)) // larger than pinned: downloaded again from the start
        assertEquals(1000L, pinned.left(part))
        File(root, "p/model/x.onnx").writeBytes(bytes)
        pinned.writeStamp(mapOf(part.name to part.sha256))
        assertEquals(0L, pinned.left(part))
    }

    // ---- 3. "Tốc độ giọng trên máy" changed while listening ------------------------------------------------------------------------
    @Test
    fun theFastTierTakesAQualityClipFirstAndQualityTakesOnlyQuality() {
        var live = "fast5"
        val cache = ClipCache(File(root, "cache"), tierOf = { live }, markOf = { _, tier -> if (tier.isEmpty()) "q0000000" else "f0000000" })
        put(cache, "supertonic:F1#q", "Đoạn một.", 1111)
        put(cache, "supertonic:F1#fast5", "Đoạn hai.", 2222)
        put(cache, "supertonic:F1#q", "Đoạn ba.", 3333)
        put(cache, "supertonic:F1#fast5", "Đoạn ba.", 4444)
        // listening at the fast tier: a quality clip made before the switch plays, its own clips too, quality first when both are there
        assertEquals(1111L, cache.get("supertonic:F1", "Đoạn một.")!!.durationMs)
        assertEquals(2222L, cache.get("supertonic:F1", "Đoạn hai.")!!.durationMs)
        assertEquals(3333L, cache.get("supertonic:F1#fast5", "Đoạn ba.")!!.durationMs)
        assertTrue(cache.contains("supertonic:F1", "Đoạn một."))
        assertEquals(1111L, cache.durationMs("supertonic:F1", "Đoạn một."))
        assertEquals("supertonic:F1", cache.get("supertonic:F1", "Đoạn một.")!!.voice)
        // listening at the quality tier, and every export: quality only
        live = ""
        assertNull(cache.get("supertonic:F1", "Đoạn hai."))
        assertNull(cache.get("supertonic:F1#q", "Đoạn hai."))
        assertTrue(!cache.contains("supertonic:F1#q", "Đoạn hai."))
        assertNull(cache.durationMs("supertonic:F1#q", "Đoạn hai."))
        assertEquals(3333L, cache.get("supertonic:F1#q", "Đoạn ba.")!!.durationMs)
    }

    // ---- 4. a read nobody needs stops between chunks and steps ---------------------------------------------------------------------
    private val long = (1..40).joinToString(" ") { "Câu thứ $it của đoạn văn rất dài này, người nghe đã nhảy đi nơi khác." }

    private class SlowEngine(private val cancel: ClipCancel?, private val cancelAfter: Int, private val stepMs: Long = 0) : SupertonicSynth {
        override val sampleRate = 44_100
        var calls = 0
        override fun infer(text: String, name: String, random: NumpyRandomState, speed: Double): FloatArray {
            calls++
            if (calls == cancelAfter) cancel?.cancel()
            if (stepMs > 0) Thread.sleep(stepMs)
            return FloatArray(4410) { 0.1f }
        }
    }

    @Test
    fun aCancelledSupertonicReadStopsAtTheNextChunk() {
        val cancel = ClipCancel()
        val engine = SlowEngine(cancel, cancelAfter = 2)
        val result = ClipRetry.run(online = false, delaysMs = LongArray(0), sleep = { false }, cancel = cancel) {
            SupertonicSpeaker(null) { it.joinToString(" ") }.speak(engine, "F1", long)
            throw AssertionError("not reached")
        }
        assertTrue(result.exceptionOrNull() is CancellationException)
        assertEquals(2, engine.calls)
        assertTrue(VieneuUnits.units(long, SupertonicText.MAX_CHARS).second.size > 5)
        // outside a cancellable read nothing changes (self-benchmark, tests)
        assertEquals(VieneuUnits.units(long, SupertonicText.MAX_CHARS).second.size, SlowEngine(null, 0).also {
            SupertonicSpeaker(null) { pieces -> pieces.joinToString(" ") }.speak(it, "F1", long)
        }.calls)
    }

    private class CountingTier(private val cancel: ClipCancel) : VieneuTier {
        override val rate = 24_000
        var calls = 0
        override fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray {
            calls++
            cancel.cancel()
            return FloatArray(2400) { 0.1f }
        }
        override fun close() = Unit
    }

    @Test
    fun aCancelledVieneuReadStopsAtTheNextChunk() {
        val cancel = ClipCancel()
        val tier = CountingTier(cancel)
        val preset = VieneuPreset("Adam", "male", FloatArray(192), null, FloatArray(50 * 256))
        val result = ClipRetry.run(online = false, delaysMs = LongArray(0), sleep = { false }, cancel = cancel) {
            VieneuSpeaker { it.joinToString(" ") }.speak("nano", tier, "Adam", preset, long)
            throw AssertionError("not reached")
        }
        assertTrue(result.exceptionOrNull() is CancellationException)
        assertEquals(1, tier.calls)
    }

    /** Huỷ an export (or jump away) during a long paragraph read on the phone: the reader is free within 0.5 s and nothing goes in the cache. */
    @Test
    fun cancellingALongLocalReadFreesTheReaderQuicklyAndCachesNothing() {
        val cache = ClipCache(File(root, "cache"))
        val cancel = ClipCancel()
        val engine = SlowEngine(null, 0, stepMs = 50)
        val voice = object : Voice {
            override val id = "supertonic:F1"
            override val extension = "wav"
            override fun synthesize(text: String, out: File): Clip {
                val spoken = SupertonicSpeaker(null) { it.joinToString(" ") }.speak(engine, "F1", text)
                out.writeBytes(ByteArray(spoken.samples.size))
                return Clip(out, spoken.durationMs, spoken.words, id)
            }
        }
        val reader = ClipReader(cache, voiceFor = { voice }, fallback = { null })
        val text = long.take(1000)
        assertEquals(1000, text.length)
        Thread { Thread.sleep(150); cancel.cancel() }.start()
        val began = System.nanoTime()
        val result = ClipRetry.run(online = false, delaysMs = LongArray(0), sleep = { false }, cancel = cancel) { reader.readExactly(text, "supertonic:F1#q") }
        val seconds = (System.nanoTime() - began) / 1e9
        assertTrue(result.exceptionOrNull() is CancellationException)
        assertTrue("stopped after $seconds s", seconds < 0.5)
        assertTrue(engine.calls < VieneuUnits.units(text, SupertonicText.MAX_CHARS).second.size)
        assertNull(cache.get("supertonic:F1#q", text))
        assertTrue(File(root, "cache").listFiles()!!.none { it.isFile })
    }
}
