package vn.abook.player.vieneu

import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.PinnedFiles
import vn.abook.player.PinnedFiles.Packed
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.Store
import java.io.File
import java.io.IOException

/**
 * "Giọng VieNeu" on the phone (docs/LISTEN_ANYTHING.md section 3): the same voices the desktop module (`abook/webui/vieneu_module.py`) offers,
 * downloaded only when the listener taps, never shipped in the APK. The same pinned upstream files as the desktop (Hugging Face commits, the
 * PyPI wheels of sea-g2p and vieneu 3.8.1, SHA-256 + size each), plus what only the phone needs: ONNX Runtime's native libraries (shared with
 * "Gói nhạc": when that is on the phone it is used and not counted) and sea-g2p built as a JNI library (scripts/prepare_sea_g2p_android.py).
 *
 * Choices: Nano ("Khuyên dùng" on phones: measured 03-10 neither tier keeps up live on a mid-range phone, Nano is lighter) and Turbo (only
 * recommended once a self-benchmark says this phone is fast enough). After a download the phone measures itself for a few seconds
 * ([benchmark]); a voice slower than [SLOW_RTF] is offered "Làm trước" (prepare ahead) or a switch - never switched silently.
 * Sizes shown are what THIS phone still lacks. Each choice can be removed again.
 */
class VieneuModule(
    private val dir: File,
    /** "Gói nhạc"'s folder: its `ort/` libraries are used when present (same pinned version), so they are not downloaded twice. */
    private val sharedOrt: File?,
    abi: String?,
    private val facts: Facts,
    /** Measure a tier just downloaded ([VieneuVoices.benchmark]); null in tests that do not measure. */
    private val benchmark: ((String) -> Benchmark)? = null,
    /** Drop loaded engines before files are replaced or removed. */
    private val forget: () -> Unit = {},
    private val metered: () -> Boolean = { false },
    groups: Map<String, List<Part>>? = null,
    /** Why this phone cannot have the module ("" = it can); null = decided from the ABI and the pins. */
    blocked: String? = null,
) {
    class Facts(val cores: Int, val ramGb: Double)

    class Benchmark(val rtf: Double, val firstAudioMs: Long, val loadMs: Long, val audioSeconds: Double) {
        fun json(): JSONObject = JSONObject().put("rtf", rtf).put("firstAudioMs", firstAudioMs).put("loadMs", loadMs).put("audioSeconds", audioSeconds)
    }

    private val pinned = PinnedFiles(dir, "", STAMP)
    private val g2pLib = abi?.let { G2P_LIBRARIES[it] }
    /** Part id -> its files (paths inside [dir]). "ort" is empty when this ABI has no ONNX Runtime build. */
    private val groups: Map<String, List<Part>> = groups ?: linkedMapOf(
        "ort" to vn.abook.player.OrtRuntime.parts(abi).map { Part(it.name, it.sha256, it.size, MUSIC_BASE + it.remote, it.packed, true, "Thư viện chạy model") },
        "g2p" to listOfNotNull(g2pLib, DICTIONARY),
        "voices" to listOf(VOICES),
        "turbo" to TURBO_FILES,
        "nano" to NANO_FILES,
    )
    private val unsupported: String = blocked ?: when {
        abi == null || g2pLib == null || this.groups["ort"].isNullOrEmpty() -> "điện thoại này chưa chạy được giọng VieNeu (kiến trúc máy chưa hỗ trợ)"
        G2P_REVISION.isEmpty() -> "bản giọng VieNeu cho điện thoại chưa được đăng"
        else -> ""
    }

    private val lock = Any()
    private var downloading = false
    private var benchmarking = false
    private var error = ""
    private var finished = 0L
    private var current = 0L
    private var total = 0L
    private var worker: Thread? = null
    private val benchFile = File(dir, BENCH)

    /** ONNX Runtime is already in "Gói nhạc"'s folder (same pinned files): use it there, do not count or download it again. */
    private fun ortShared(): Boolean = sharedOrt != null && groups.getValue("ort").let { parts ->
        parts.isNotEmpty() && parts.all { part -> File(sharedOrt, part.name).let { it.isFile && it.length() == part.size } }
    }

    /** Folder holding `ort/` for [vn.abook.player.OrtRuntime.load]. */
    fun ortFolder(): File = if (ortShared()) sharedOrt!! else dir

    // ---- what is here -----------------------------------------------------------------------------------------------------------
    private fun partState(id: String, stamp: Map<String, String>): String {
        if (id == "ort" && ortShared()) return "current"
        val files = groups.getValue(id)
        if (files.isEmpty() || !files.all { pinned.present(it) }) return "missing"
        return if (files.all { pinned.isCurrent(it, stamp) }) "current" else "outdated"
    }

    private fun states(): Map<String, String> {
        val stamp = pinned.readStamp()
        return groups.keys.associateWith { partState(it, stamp) }
    }

    private fun bytes(id: String, states: Map<String, String>): Long =
        if (states[id] == "current") 0L else groups.getValue(id).filter { !pinned.isCurrent(it) }.sumOf { it.wireSize }

    private fun have(states: Map<String, String>) = CHOICES.filter { choice -> NEEDS.getValue(choice).all { states[it] != "missing" } }

    /** Parts (each once) that [choices] still lack or have in an older version. */
    private fun lacking(choices: List<String>, states: Map<String, String>): List<String> =
        choices.flatMap { NEEDS.getValue(it) }.distinct().filter { states[it] != "current" }

    /** Every file [choices] use (shared ones once), as pinned by this app. */
    fun parts(choices: List<String>): List<Part> = choices.flatMap { NEEDS.getValue(it) }.distinct().flatMap { groups.getValue(it) }

    /** Where the parts are, for [VieneuVoices]; null when no voice is usable yet (an older version stays usable until updated). */
    fun installed(): VieneuInstalled? {
        val states = states()
        val tiers = have(states)
        if (tiers.isEmpty() || g2pLib == null) return null
        // runtime libraries must match the APK's code (ONNX Runtime's Java API, the JNI functions): an old one waits for the update
        val stamp = pinned.readStamp()
        val used = tiers.flatMap { NEEDS.getValue(it) }.distinct().filter { !(it == "ort" && ortShared()) }
        if (used.flatMap { groups.getValue(it) }.any { it.blocking && !pinned.isCurrent(it, stamp) }) return null
        return VieneuInstalled(pinned.file(g2pLib), pinned.file(DICTIONARY), pinned.file(VOICES),
            if ("turbo" in tiers) File(dir, "turbo") to File(dir, "turbo") else null, if ("nano" in tiers) File(dir, "nano") else null)
    }

    // ---- benchmark --------------------------------------------------------------------------------------------------------------
    private fun readBench(): JSONObject = try {
        JSONObject(benchFile.readText(Charsets.UTF_8))
    } catch (_: Exception) {
        JSONObject()
    }

    /** Self-measured speed of a VieNeu voice ("vieneu:nano/...") on this phone, for "Làm trước" estimates; null when not measured. */
    fun rtf(voiceId: String): Double? {
        if (!voiceId.startsWith("vieneu:")) return null
        val tier = voiceId.removePrefix("vieneu:").substringBefore('/')
        return readBench().optJSONObject(tier)?.optDouble("rtf")?.takeIf { !it.isNaN() }
    }

    /** Before any measurement Nano; Turbo once a measurement says this phone keeps up with it (or Nano runs well under the limit). */
    fun recommended(bench: JSONObject = readBench()): String {
        val turbo = bench.optJSONObject("turbo")?.optDouble("rtf") ?: Double.NaN
        val nano = bench.optJSONObject("nano")?.optDouble("rtf") ?: Double.NaN
        return if ((!turbo.isNaN() && turbo < SLOW_RTF) || (turbo.isNaN() && !nano.isNaN() && nano < TURBO_HEADROOM_RTF)) "turbo" else "nano"
    }

    // ---- status -----------------------------------------------------------------------------------------------------------------
    /** For the "Giọng VieNeu" card (same shape as the desktop's `vieneu_module.status`, ui/src/listen/vieneuModule.ts). */
    fun status(): JSONObject = synchronized(lock) {
        val states = states()
        val tiers = have(states)
        val behind = lacking(tiers, states).filter { states[it] == "outdated" }
        val bench = readBench()
        val best = recommended(bench)
        val state = when {
            downloading -> "downloading"
            error.isNotEmpty() -> "error"
            tiers.isNotEmpty() -> if (behind.isNotEmpty()) "outdated" else "ready"
            unsupported.isNotEmpty() -> "unsupported"
            else -> "missing"
        }
        val choices = JSONArray()
        for (choice in CHOICES) {
            val (label, detail) = CHOICE_TEXT.getValue(choice)
            choices.put(JSONObject().put("id", choice).put("label", label).put("detail", detail).put("needs", JSONArray(NEEDS.getValue(choice)))
                .put("bytes", lacking(listOf(choice), states).sumOf { bytes(it, states) }).put("installed", choice in tiers)
                .put("recommended", choice == best).put("default", choice == best).put("removable", choice in tiers))
        }
        val parts = JSONArray()
        for (id in groups.keys) {
            parts.put(JSONObject().put("id", id).put("label", PART_LABEL.getValue(id)).put("bytes", groups.getValue(id).sumOf { it.wireSize })
                .put("state", states.getValue(id)).put("external", id == "ort" && ortShared()))
        }
        val shownBench = JSONObject()
        for (tier in tiers) bench.optJSONObject(tier)?.let { shownBench.put(tier, it) }
        JSONObject().put("state", state).put("done", if (downloading) finished + current else 0).put("total", if (downloading) total else 0)
            .put("error", error).put("supported", unsupported.isEmpty()).put("reason", unsupported).put("choices", choices).put("parts", parts)
            .put("outdatedParts", JSONArray(behind.map { PART_LABEL.getValue(it) })).put("outdatedBytes", behind.sumOf { bytes(it, states) })
            .put("benchmark", shownBench).put("benchmarking", benchmarking)
            .put("suggestion", if (benchmarking) JSONObject.NULL else suggestion(bench, tiers) ?: JSONObject.NULL)
            .put("device", JSONObject().put("cores", facts.cores).put("ramGb", facts.ramGb).put("gpu", "").put("runs", "cpu"))
            .put("recommended", best).put("slowRtf", SLOW_RTF).put("metered", runCatching { metered() }.getOrDefault(false)).put("removable", true)
    }

    /** A downloaded voice slower than listening -> what to offer (the listener decides): Turbo -> Nano when Nano keeps up, else an online voice. */
    private fun suggestion(bench: JSONObject, tiers: List<String>): JSONObject? {
        val slow = tiers.filter { (bench.optJSONObject(it)?.optDouble("rtf") ?: 0.0) >= SLOW_RTF }
        if (slow.isEmpty()) return null
        val tier = if ("turbo" in slow) "turbo" else slow[0]
        val rtf = bench.getJSONObject(tier).getDouble("rtf")
        return if (tier == "turbo" && "nano" !in slow) JSONObject().put("tier", tier).put("rtf", rtf).put("switchTo", "nano").put("installed", "nano" in tiers)
        else JSONObject().put("tier", tier).put("rtf", rtf).put("switchTo", "online").put("installed", true)
    }

    // ---- download / remove / measure -------------------------------------------------------------------------------------------
    /** Download what [choices] lack (null: update the outdated parts of what is installed), on a background thread. */
    fun start(choices: List<String>?) {
        synchronized(lock) {
            if (downloading || benchmarking) return
            val unknown = choices?.firstOrNull { it !in CHOICES }
            require(unknown == null) { "Không có lựa chọn $unknown" }
            val states = states()
            val wanted = choices ?: have(states)
            val needed = lacking(wanted, states)
            error = ""
            if (needed.isEmpty()) return
            if (unsupported.isNotEmpty()) {
                error = unsupported.replaceFirstChar { it.uppercase() } + "."
                return
            }
            downloading = true
            finished = 0
            current = 0
            total = needed.sumOf { bytes(it, states) }
            val files = needed.flatMap { id -> groups.getValue(id) }
            worker = Thread({ run(files, needed) }, "abook-vieneu-module").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
                start()
            }
        }
    }

    private fun run(files: List<Part>, needed: List<String>) {
        try {
            forget() // a loaded engine must not read files being replaced
            pinned.download(files, object : PinnedFiles.Progress {
                override fun current(bytes: Long) = synchronized(lock) { current = bytes }
                override fun done(part: Part) = synchronized(lock) {
                    finished += part.wireSize
                    current = 0
                }
            })
            forget()
            synchronized(lock) {
                downloading = false
                error = ""
                benchmarking = true
            }
            val installedTiers = have(states())
            measure(TIERS.filter { tier -> tier in installedTiers && NEEDS.getValue(tier).any { it in needed } })
        } catch (failure: Exception) {
            synchronized(lock) { error = describe(failure) }
        } finally {
            synchronized(lock) { downloading = false }
        }
    }

    private fun describe(failure: Exception): String = when (failure) {
        is PinnedFiles.ChecksumError -> "Giọng VieNeu tải về bị hỏng (không khớp mã kiểm) - bấm Thử lại để tải lại."
        is IOException -> "Không tải được giọng VieNeu (${failure.message ?: "mất kết nối"}). Bấm Thử lại - phần đã tải được giữ."
        else -> "Không tải được giọng VieNeu (${failure.message ?: failure.javaClass.simpleName})."
    }

    /** Measure [tiers] (a few seconds each; the caller has set `benchmarking`); a failed measurement never spoils the download. */
    private fun measure(tiers: List<String>) {
        try {
            val run = benchmark ?: return
            if (tiers.isEmpty() || installed() == null) return
            val results = readBench()
            for (tier in tiers) {
                try {
                    results.put(tier, run(tier).json())
                } catch (_: Throwable) { // UnsatisfiedLinkError, OutOfMemoryError: say nothing about the speed rather than crash
                    results.remove(tier)
                }
            }
            dir.mkdirs()
            Store.writeAtomic(benchFile, results.toString())
        } finally {
            synchronized(lock) { benchmarking = false }
        }
    }

    /** "Thử lại tốc độ": measure every installed tier again, on a background thread. */
    fun measureAgain() {
        synchronized(lock) {
            if (downloading || benchmarking) return
            val tiers = have(states())
            if (tiers.isEmpty()) return
            benchmarking = true
            worker = Thread({ measure(tiers) }, "abook-vieneu-bench").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
                start()
            }
        }
    }

    /** Remove one voice ([choice]); the shared parts (text reader, voice list, own ONNX Runtime) go with the last one. */
    fun remove(choice: String) {
        require(choice in CHOICES) { "Không có lựa chọn $choice" }
        synchronized(lock) {
            if (downloading || benchmarking) return
            forget()
            val others = have(states()).filter { it != choice }
            val keep = others.flatMap { NEEDS.getValue(it) }.toSet()
            val drop = NEEDS.getValue(choice).filter { it !in keep }
            pinned.remove(drop.flatMap { groups.getValue(it) })
            drop.forEach { id -> if (id != "ort") File(dir, id).deleteRecursively() }
            if (others.isEmpty()) File(dir, "ort").deleteRecursively()
            val bench = readBench().apply { remove(choice) }
            if (bench.length() == 0) benchFile.delete() else Store.writeAtomic(benchFile, bench.toString())
            error = ""
        }
    }

    /** Wait for the download / measurement thread (tests). */
    fun join(millis: Long = 60_000) {
        worker?.join(millis)
    }

    companion object {
        const val STAMP = "module.json"
        private const val BENCH = "benchmark.json"
        /** At or above this a voice cannot be listened to live (desktop vieneu_module.SLOW_RTF). */
        const val SLOW_RTF = 0.8
        /** Nano this much faster than listening -> Turbo (about as fast on a phone, measured 03-10) is worth recommending. */
        const val TURBO_HEADROOM_RTF = 0.6
        val TIERS = listOf("turbo", "nano")
        val CHOICES = listOf("nano", "turbo")
        val NEEDS = mapOf("turbo" to listOf("ort", "g2p", "voices", "turbo"), "nano" to listOf("ort", "g2p", "voices", "nano"))
        val CHOICE_TEXT = mapOf(
            "nano" to ("Giọng VieNeu Nano" to "11 giọng, âm thanh 24 kHz - nhẹ hơn, hợp với điện thoại"),
            "turbo" to ("Giọng VieNeu" to "25 giọng, âm thanh 48 kHz - hay nhất, cần điện thoại mạnh"),
        )
        val PART_LABEL = mapOf("ort" to "Thư viện chạy model", "g2p" to "Bộ đọc chữ tiếng Việt", "voices" to "Danh sách giọng",
            "turbo" to "Giọng VieNeu", "nano" to "Giọng VieNeu Nano")

        // Pins: the same upstream files as abook/webui/vieneu_module.py (tests/test_vieneu_android.py compares the two tables).
        private const val TURBO_BASE = "https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/resolve/61b85e3d937fbbacb387714180e8182823512523/onnx_int8/"
        private const val CODEC_BASE = "https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX/resolve/ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae/"
        private const val NANO_BASE = "https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Nano/resolve/aba295eb96a6fa6003ebe417cc1f2802a7adc1dc/"
        private const val MUSIC_BASE = vn.abook.player.MusicStudentSetup.BASE

        /** Commit of NGDtuanh/abook-music-student that holds `sea-g2p/0.9.1/` (scripts/prepare_sea_g2p_android.py). Empty = not uploaded yet. */
        const val G2P_REVISION = ""
        private const val G2P_BASE = "https://huggingface.co/NGDtuanh/abook-music-student/resolve/$G2P_REVISION/sea-g2p/0.9.1/"

        private fun g2pLib(abi: String, sha256: String, size: Long, packedSha256: String, packedSize: Long) =
            Part("g2p/libabook_sea_g2p.so", sha256, size, "$G2P_BASE$abi/libabook_sea_g2p.so.gz", Packed(packedSha256, packedSize), true, "Bộ đọc chữ tiếng Việt")

        // As scripts/prepare_sea_g2p_android.py prints them (SHA-256 + size of the library and of its gzip on the server).
        val G2P_LIBRARIES = mapOf(
            "arm64-v8a" to g2pLib("arm64-v8a", "eabbce7c25af8738897469924c2272c50aee60334b88255622f9d864bf00a427", 3_946_648, "216499f2a02d6c55438e27319fab02ebb89c488638e92e032f0e724b1321572f", 1_723_307),
            "armeabi-v7a" to g2pLib("armeabi-v7a", "677710c9f5e7a91d3c1f009599ef6994c5d6ac90a8c0872b612cf4357bb52f4b", 3_136_944, "ac3d66c0fb3f70044e1a84c5869fa43bdc3fe6d05ccd43c4335c9be178618f5f", 1_523_185),
            "x86_64" to g2pLib("x86_64", "9746d66971f1c18ec7b815424bf4ac5313b914f52dc5eae36a1410970ee540c9", 4_888_872, "bfa27c2831dcc3caf042be1ec121c6bc7c3e035a66ee3b96ac99921d21f3a6a2", 1_799_203),
        )

        /** The 63 MB dictionary, taken out of the very wheel the desktop downloads (vieneu_module.G2P). */
        val DICTIONARY = Part("g2p/sea_g2p.bin", "4346e690d0711ebc5231e7a42c5c88aaf6e40377e894b4617c018fd81c6f4096", 62_829_820,
            "https://files.pythonhosted.org/packages/98/2d/4553efd8f340f332eb5976118e441b09ec95cf60d27fd1ad04240d885905/sea_g2p-0.9.1-cp310-abi3-win_amd64.whl",
            Packed("b6d7c09afb83750abe61735ad2e60f5c20b4cdfac30b1b9b1904de9f64f10c32", 27_531_798, "sea_g2p/sea_g2p.bin"), label = "Bộ đọc chữ tiếng Việt")

        /** The vieneu 3.8.1 wheel (vieneu_module.VOICES), kept whole: the two voice lists are read out of it. */
        val VOICES = Part("voices/vieneu-3.8.1-py3-none-any.whl", "bf24f88ec95f96459756d897b04a118e923536d36bcfcdccd13ba6f8f7d580ba", 2_642_947,
            "https://files.pythonhosted.org/packages/35/03/83c6564f834b90b9fe200c4381a8d8fc506c0697233b1a5b2c3d06d9899f/vieneu-3.8.1-py3-none-any.whl",
            label = "Danh sách giọng")
        val VOICE_MEMBERS = mapOf("turbo" to "vieneu/assets/voices_v3_turbo.json", "nano" to "vieneu/assets/voices_v3_nano.json")

        private fun file(folder: String, base: String, name: String, sha256: String, size: Long, label: String) =
            Part("$folder/$name", sha256, size, base + name, label = label)

        val TURBO_FILES = listOf(
            file("turbo", TURBO_BASE, "config.json", "a9f8d9c4b4736448ab355d1a98cfe48f5e39aecf2916c37b0806c228612e9a2d", 2_152, "Giọng VieNeu"),
            file("turbo", TURBO_BASE, "tokenizer.json", "6cc6bcbe380b8c37bd9f2514e37c5dfa3e00e122c6e3125dae5c4afe48e39158", 22_320, "Giọng VieNeu"),
            file("turbo", TURBO_BASE, "vieneu_prefill.onnx", "c6a80dabf67c820de798f8deb7d4e0f37d81b5d76e33fbe20ab5a67f2d371f4e", 1_090_823, "Giọng VieNeu"),
            file("turbo", TURBO_BASE, "vieneu_decode_step.onnx", "2c5b30bd8ccb751c58d651f44c074df10c4113efd08719adaa8e3dec6a6ce2ca", 1_062_040, "Giọng VieNeu"),
            file("turbo", TURBO_BASE, "vieneu_acoustic_cached.onnx", "f631e3387c788c3d8b9a5ac5df94952af5bc4c4d1049ff8a751e76a246fff2d4", 7_207_223, "Giọng VieNeu"),
            file("turbo", TURBO_BASE, "vieneu_backbone_shared.data", "bb683925f7c8d826fadca4f8a0252ae4d5fc5b7837c14f6857e18f4c6666588d", 103_891_968, "Giọng VieNeu"),
            file("turbo", TURBO_BASE, "vieneu_v3_heads.npz", "fb22484baa424bbb775133a6e5f0d00d6299b2b256fbe3312a864b85b9aed01e", 52_219_622, "Giọng VieNeu"),
            file("turbo", CODEC_BASE, "moss_audio_tokenizer_decode_full.onnx", "0fbbafe3fd4afa2a019af5c5ced204af6e2d1db044fa40f021525d2aee95b4ac", 681_902, "Giọng VieNeu"),
            file("turbo", CODEC_BASE, "moss_audio_tokenizer_decode_shared.data", "e69d52e0f4e84ca27850557ee54face46632d3a5a16c89bd246c7c408466dcad", 44_198_912, "Giọng VieNeu"),
        )
        val NANO_FILES = listOf(
            file("nano", NANO_BASE, "config.json", "3762f1716fd8d7a1451ddf2e051c03b0a341e8adda4f1dbd0db0ae9777514e56", 2_927, "Giọng VieNeu Nano"),
            file("nano", NANO_BASE, "constants.npz", "7c011938effe41687a9af85107a31a040dfcf0fb3d0f048ec10f4fb65c1a8829", 53_448, "Giọng VieNeu Nano"),
            file("nano", NANO_BASE, "text_encoder.onnx", "204f02cccae1f16ccb2d3840f05721a37fe250b82cbd456337a0ccb49615e4bf", 26_519_943, "Giọng VieNeu Nano"),
            file("nano", NANO_BASE, "duration_predictor.onnx", "20fd7fa60006d0a48ee82e0451b3f920d2052588c083c756cce669f3947c0a68", 727_809, "Giọng VieNeu Nano"),
            file("nano", NANO_BASE, "vector_estimator.onnx", "c6c1d4398ca35d3ad1bd3f0459413d1b975d09e7f2f3a2b4493a7b92bbf6ce93", 155_132_418, "Giọng VieNeu Nano"),
            file("nano", NANO_BASE, "codec_decoder.onnx", "b0ab15e7828a39d53679e25b1ba4ba415a61311307202a6323130b9e1cc3029d", 99_319_941, "Giọng VieNeu Nano"),
        )
    }
}
