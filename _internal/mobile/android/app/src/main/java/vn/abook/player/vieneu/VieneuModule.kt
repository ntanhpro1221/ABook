package vn.abook.player.vieneu

import org.json.JSONObject
import vn.abook.player.PinnedFiles.Packed
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.SharedRuntime
import java.io.File

/**
 * "Giọng VieNeu" on the phone (docs/LISTEN_ANYTHING.md section 3): the same voices the desktop module (`abook/webui/vieneu_module.py`) offers,
 * downloaded only when the listener taps, never shipped in the APK. The same pinned upstream files as the desktop (Hugging Face commits, the
 * PyPI wheels of sea-g2p and vieneu 3.8.3, SHA-256 + size each), plus what only the phone needs: ONNX Runtime's native libraries and sea-g2p
 * built as a JNI library (scripts/prepare_sea_g2p_android.py) - both kept once for "Gói nhạc" and every voice ([SharedRuntime]), so whichever
 * comes first, the others do not download them again.
 *
 * Choices: Nano ("Khuyên dùng" on phones: measured 03-10 neither tier keeps up live on a mid-range phone, Nano is lighter) and Turbo (only
 * recommended once a self-benchmark says this phone is fast enough). After a download the phone measures itself for a few seconds
 * ([VoiceModule.Benchmark]); a voice slower than [VoiceModule.SLOW_RTF] is offered "Làm trước" (prepare ahead) or a switch - never switched
 * silently. Sizes shown are what THIS phone still lacks. Each choice can be removed again. Download, measuring and removal: [VoiceModule].
 */
class VieneuModule(
    dir: File,
    /** ONNX Runtime and sea-g2p, shared with "Gói nhạc" and the other voices. */
    runtime: SharedRuntime,
    abi: String?,
    facts: VoiceModule.Facts,
    /** Measure a tier just downloaded ([VieneuVoices.benchmark]); null in tests that do not measure. */
    benchmark: ((String) -> VoiceModule.Benchmark)? = null,
    /** Drop loaded engines before files are replaced or removed. */
    forget: () -> Unit = {},
    metered: () -> Boolean = { false },
    groups: Map<String, List<Part>>? = null,
    /** Why this phone cannot have the module ("" = it can); null = decided from the ABI and the pins. */
    blocked: String? = null,
) : VoiceModule(dir, runtime, groups ?: defaultGroups(abi), facts, benchmark, forget, metered) {
    private val g2pLib = abi?.let { G2P_LIBRARIES[it] }
    override val name = "giọng VieNeu"
    override val key = "vieneu"
    override val choices = CHOICES
    override val tiers = TIERS
    override fun needs(choice: String) = NEEDS.getValue(choice)
    override fun partLabel(id: String) = PART_LABEL.getValue(id)
    override val unsupported: String = blocked ?: when {
        abi == null || g2pLib == null || this.groups["ort"].isNullOrEmpty() -> "điện thoại này chưa chạy được giọng VieNeu (kiến trúc máy chưa hỗ trợ)"
        G2P_REVISION.isEmpty() -> "bản giọng VieNeu cho điện thoại chưa được đăng"
        else -> ""
    }

    /** Folder holding `ort/` for [vn.abook.player.OrtRuntime.load]. */
    fun ortFolder(): File = folderFor("ort")

    override fun choiceText(choice: String): Pair<String, String> {
        val (label, text) = CHOICE_TEXT.getValue(choice)
        // Turbo trên máy ít RAM: vẫn tải được (người dùng quyết), nhưng nói trước vì sao Nano hợp hơn.
        val detail = if (choice == "turbo" && facts.ramGb < TURBO_MIN_RAM_GB)
            "$text. Máy này có khoảng ${"%.0f".format(java.util.Locale.ROOT, facts.ramGb)} GB RAM, mà giọng này cần khoảng 1,3 GB khi đọc nên Android dễ tắt nó - Giọng VieNeu Nano hợp hơn"
        else text
        return label to detail
    }

    /** Where the parts are, for [VieneuVoices]; null when no voice is usable yet (an older version stays usable until updated). */
    fun installed(): VieneuInstalled? {
        val tiers = have(states())
        if (tiers.isEmpty() || g2pLib == null) return null
        if (runtimeBehind(tiers.flatMap { needs(it) }.distinct())) return null // an old runtime library waits for the update
        val g2p = folderFor("g2p")
        return VieneuInstalled(File(g2p, g2pLib.name), File(g2p, DICTIONARY.name), pinned.file(VOICES),
            if ("turbo" in tiers) File(dir, "turbo") to File(dir, "turbo") else null, if ("nano" in tiers) File(dir, "nano") else null)
    }

    override fun measurable() = installed() != null

    /** Self-measured speed of a VieNeu voice ("vieneu:nano/...") on this phone, for "Làm trước" estimates; null when not measured. */
    fun rtf(voiceId: String): Double? {
        if (!voiceId.startsWith("vieneu:")) return null
        return tierRtf(voiceId.removePrefix("vieneu:").substringBefore('/'))
    }

    /** Before any measurement Nano; Turbo once a measurement says this phone keeps up with it (or Nano runs well under the limit) - and only with
     *  enough memory for it ([TURBO_MIN_RAM_GB]). */
    override fun recommended(bench: JSONObject): String {
        if (facts.ramGb < TURBO_MIN_RAM_GB) return "nano"
        val turbo = bench.optJSONObject("turbo")?.optDouble("rtf") ?: Double.NaN
        val nano = bench.optJSONObject("nano")?.optDouble("rtf") ?: Double.NaN
        return if ((!turbo.isNaN() && turbo < SLOW_RTF) || (turbo.isNaN() && !nano.isNaN() && nano < TURBO_HEADROOM_RTF)) "turbo" else "nano"
    }

    /** A downloaded voice slower than listening -> what to offer (the listener decides): Turbo -> Nano when Nano keeps up, else an online voice. */
    override fun suggestion(bench: JSONObject, tiers: List<String>): JSONObject? {
        val slow = tiers.filter { slowRtf(bench, it) != null }
        if (slow.isEmpty()) return null
        val tier = if ("turbo" in slow) "turbo" else slow[0]
        val rtf = slowRtf(bench, tier)!!
        return if (tier == "turbo" && "nano" !in slow) JSONObject().put("tier", tier).put("rtf", rtf).put("switchTo", "nano").put("installed", "nano" in tiers)
        else JSONObject().put("tier", tier).put("rtf", rtf).put("switchTo", "online").put("installed", true)
    }

    companion object {
        /** The parts of the module for [abi] as pinned by this app. */
        private fun defaultGroups(abi: String?): Map<String, List<Part>> = linkedMapOf(
            "ort" to SharedRuntime.ortParts(abi),
            "g2p" to listOfNotNull(abi?.let { G2P_LIBRARIES[it] }, DICTIONARY),
            "voices" to listOf(VOICES),
            "turbo" to TURBO_FILES,
            "nano" to NANO_FILES,
        )

        /** Its own folder in the app's files. */
        const val FOLDER = "vieneu"

        /** Nano this much faster than listening -> Turbo (about as fast on a phone, measured 03-10) is worth recommending. */
        const val TURBO_HEADROOM_RTF = 0.6
        /** Turbo peaks at about 1.25-1.3 GB while reading (PSS, OPPO A93 and the emulator 03-10); under a 6 GB phone (Android reports ~5.5) it is
         *  likely to be killed in the background, so it is not recommended there. */
        const val TURBO_MIN_RAM_GB = 5.5
        val TIERS = listOf("turbo", "nano")
        val CHOICES = listOf("nano", "turbo")
        val NEEDS = mapOf("turbo" to listOf("ort", "g2p", "voices", "turbo"), "nano" to listOf("ort", "g2p", "voices", "nano"))
        val CHOICE_TEXT = mapOf(
            "nano" to ("Giọng VieNeu Nano" to "11 giọng, âm thanh 24 kHz - lúc đọc tốn ít bộ nhớ hơn, hợp điện thoại yếu; file tải nặng hơn Giọng VieNeu"),
            "turbo" to ("Giọng VieNeu" to "25 giọng, âm thanh 48 kHz - hay nhất, cần điện thoại mạnh"),
        )
        val PART_LABEL = mapOf("ort" to "Thư viện chạy model", "g2p" to "Bộ đọc chữ tiếng Việt", "voices" to "Danh sách giọng",
            "turbo" to "Giọng VieNeu", "nano" to "Giọng VieNeu Nano")

        // Pins: the same upstream files as abook/webui/vieneu_module.py (tests/test_vieneu_android.py compares the two tables).
        private const val TURBO_BASE = "https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/resolve/61b85e3d937fbbacb387714180e8182823512523/onnx_int8/"
        private const val CODEC_BASE = "https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX/resolve/ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae/"
        private const val NANO_BASE = "https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Nano/resolve/aba295eb96a6fa6003ebe417cc1f2802a7adc1dc/"

        /** Commit of NGDtuanh/abook-music-student that holds `sea-g2p/0.9.1/` (scripts/prepare_sea_g2p_android.py). Empty = not uploaded yet. */
        const val G2P_REVISION = "a8446407cc4f4775b0f0029da63a24756ebc966f"
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
            "https://files.pythonhosted.org/packages/73/57/58916050fe1218c106f89d4fa3b8f18f4ef5d264e6ec5906020f2f1dfcf2/sea_g2p-0.10.0-cp310-abi3-win_amd64.whl",
            Packed("118d471796ff4fafe5cdcf1f75431a63e76ec5c0e7786cb7b3ff876d6d5292ea", 27_530_792, "sea_g2p/sea_g2p.bin"), label = "Bộ đọc chữ tiếng Việt")

        /** The vieneu 3.8.3 wheel (vieneu_module.VOICES), kept whole: the two voice lists are read out of it. */
        val VOICES = Part("voices/vieneu-3.8.3-py3-none-any.whl", "7388d166e65746f5bb075bf8094d324f8131a82393680b712260d6f2f983ef06", 2_643_059,
            "https://files.pythonhosted.org/packages/fc/9c/e7b624412b8a734d6b1cd8ca6209f88a309464b05393c40f2e316ec90885/vieneu-3.8.3-py3-none-any.whl",
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
