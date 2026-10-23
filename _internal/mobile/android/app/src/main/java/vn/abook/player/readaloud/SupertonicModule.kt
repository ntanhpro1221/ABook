package vn.abook.player.readaloud

import org.json.JSONObject
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.SharedRuntime
import vn.abook.player.vieneu.VieneuModule
import vn.abook.player.vieneu.VoiceModule
import java.io.File

/** Where the "Giọng Supertonic" module's files are on this phone ([SupertonicModule.installed]). [g2p] (library, dictionary) is null when sea-g2p is
 *  not here: the voice then reads the text as written, like the desktop without sea-g2p. */
class SupertonicInstalled(val model: File, val ortFolder: File, val g2p: Pair<File, File>?)

/**
 * "Giọng Supertonic" on the phone: the ten Supertonic 3 voices the desktop module (`abook/webui/supertonic_module.py`) offers, downloaded only when
 * the listener taps, never shipped in the APK - the same pinned files (Hugging Face `Supertone/supertonic-3` at one commit, SHA-256 + size each;
 * tests/test_supertonic_android.py compares the two tables). Parts: ONNX Runtime's libraries and sea-g2p (numbers, dates, times read as words),
 * kept once for "Gói nhạc" and every voice ([SharedRuntime]: one of those downloaded first -> already here and not counted), and the model
 * itself. After a download the phone measures itself for a few seconds; slower than listening -> the card points to "Làm trước" or an online
 * voice (never a silent switch). Removing it takes its model, and the shared runtime only when no installed module needs it.
 *
 * The vector estimator is the app's int8 "top30" one and the vocoder the app's int8 one (both replace upstream fp32, desktop the same). "Bản nhanh hơn" ([FAST_CHOICE]: the "fast" int8
 * estimator in `fast/`) is the fast tier of "Tốc độ giọng trên máy" ([VoiceSpeed]): offered only when that setting wants it (or already here), never
 * measured (the measurement is of the quality tier), removed with the voice.
 */
class SupertonicModule(
    dir: File,
    /** ONNX Runtime and sea-g2p, shared with "Gói nhạc" and the other voices. */
    runtime: SharedRuntime,
    abi: String?,
    facts: VoiceModule.Facts,
    benchmark: ((String) -> VoiceModule.Benchmark)? = null,
    forget: () -> Unit = {},
    metered: () -> Boolean = { false },
    groups: Map<String, List<Part>>? = null,
    blocked: String? = null,
) : VoiceModule(dir, runtime, groups ?: defaultGroups(abi), facts, benchmark, forget, metered), VoiceSpeed.Family {
    override val name = "giọng Supertonic"
    override val key = "supertonic"
    /** "Bản nhanh hơn" only where its part is pinned (tests give their own parts). */
    override val choices = if (FAST_CHOICE in this.groups) listOf(CHOICE, FAST_CHOICE) else listOf(CHOICE)
    override val tiers = listOf(CHOICE)
    override fun needs(choice: String) = if (choice == FAST_CHOICE) NEEDS + FAST_CHOICE else NEEDS
    override fun partLabel(id: String) = PART_LABEL.getValue(id)
    override fun choiceText(choice: String) = if (choice == FAST_CHOICE) FAST_LABEL to FAST_DETAIL else LABEL to DETAIL
    override fun offered(choice: String, installed: List<String>) =
        choice != FAST_CHOICE || choice in installed || (CHOICE in installed && VoiceSpeed.wantsFast(speedRtf()))
    override fun requires(choice: String) = if (choice == FAST_CHOICE) listOf(CHOICE) else emptyList()
    override val unsupported: String = blocked ?: if (abi == null || this.groups["ort"].isNullOrEmpty())
        "điện thoại này chưa chạy được giọng Supertonic (kiến trúc máy chưa hỗ trợ)" else ""

    /** The desktop's card: one choice, not "Khuyên dùng" but ticked. */
    override fun marks(choice: String, best: String) = false to true

    override fun recommended(bench: JSONObject) = CHOICE

    /** Slower than listening on this phone -> "Làm trước", or an online voice (desktop `supertonic_module.suggestion`). */
    override fun suggestion(bench: JSONObject, tiers: List<String>): JSONObject? {
        if (CHOICE !in tiers) return null
        val rtf = slowRtf(bench, CHOICE) ?: return null
        return JSONObject().put("tier", CHOICE).put("rtf", rtf).put("switchTo", "online").put("installed", true)
    }

    /** Where the files are; null when the voice cannot read yet (model or ONNX Runtime missing, or an older runtime library waiting for the
     *  update). sea-g2p is used when it is here. */
    fun installed(): SupertonicInstalled? {
        val states = states()
        if (states[CHOICE] == "missing" || states["ort"] == "missing") return null
        if (runtimeBehind(NEEDS.filter { states[it] != "missing" })) return null
        val g2p = if (states["g2p"] == "missing") null else folderFor("g2p").let { folder ->
            val (library, dictionary) = groups.getValue("g2p").let { it.first() to it.last() }
            File(folder, library.name) to File(folder, dictionary.name)
        }
        return SupertonicInstalled(File(dir, MODEL), folderFor("ort"), g2p)
    }

    override fun measurable() = installed() != null

    /** Self-measured speed of a Supertonic voice on this phone; null when not measured / another voice. */
    fun rtf(voiceId: String): Double? = if (voiceId.startsWith("${SupertonicVoices.PREFIX}:")) tierRtf(CHOICE) else null

    /** The fast tier's vector estimator; null while it is not downloaded (or the voice itself cannot read). */
    fun fastEstimator(): File? =
        if (FAST_CHOICE in choices && installed() != null && states()[FAST_CHOICE] != "missing") File(dir, SupertonicText.FAST_ESTIMATOR) else null

    // ---- "Tốc độ giọng trên máy" ([VoiceSpeed]) ------------------------------------------------------------------------------------------
    override val speedId = "supertonic"
    override val speedName = LABEL
    override val speedModule = key
    override val fastChoice = FAST_CHOICE
    override val fastSteps = SupertonicText.FAST_STEPS
    override fun speedInstalled() = installed() != null
    override fun speedRtf() = tierRtf(CHOICE)
    override fun speedFastReady() = fastEstimator() != null
    override fun speedFastBytes() = if (FAST_CHOICE in groups) left(FAST_CHOICE, states()) else 0L

    /** Model mark of the tier the clip is read at, for the clip cache key (desktop `supertonic_module.model_mark`): the fast tier reads with the
     *  base model and its own estimator at [SupertonicText.FAST_STEPS], the quality tier with the base model at [SupertonicText.STEPS]. */
    fun mark(fast: Boolean): String =
        if (fast) mark(listOf(CHOICE, FAST_CHOICE), "fast:${SupertonicText.FAST_STEPS}:open${SupertonicText.OPENING_CUT}") else mark(listOf(CHOICE), "quality:${SupertonicText.STEPS}:open${SupertonicText.OPENING_CUT}")

    companion object {
        const val CHOICE = "supertonic"
        /** "Bản nhanh hơn" (desktop supertonic_module.FAST_CHOICE). */
        const val FAST_CHOICE = "supertonic_fast"
        /** Its own folder in the app's files. */
        const val FOLDER = "supertonic"
        val NEEDS = listOf("ort", "g2p", CHOICE)
        private const val MODEL = "model"
        private const val LABEL = "Giọng Supertonic"
        private const val DETAIL = "10 giọng nam nữ, 44 kHz; tự đổi số và ngày giờ thành chữ."
        private const val FAST_LABEL = "Bản nhanh hơn"
        private const val FAST_DETAIL = "Tạo giọng nhanh hơn, tiếng kém chút; xuất sách vẫn dùng bản tốt nhất."
        val PART_LABEL = mapOf("ort" to "Bộ chạy giọng", "g2p" to "Bộ đọc tiếng Việt", CHOICE to "Giọng Supertonic", FAST_CHOICE to FAST_LABEL)

        private fun defaultGroups(abi: String?): Map<String, List<Part>> = linkedMapOf(
            "ort" to SharedRuntime.ortParts(abi),
            "g2p" to if (abi == null || VieneuModule.G2P_LIBRARIES[abi] == null) emptyList() else listOf(VieneuModule.G2P_LIBRARIES.getValue(abi), VieneuModule.DICTIONARY),
            CHOICE to FILES,
            FAST_CHOICE to FAST_FILES,
        )

        // Pins: the same files as abook/webui/supertonic_module.py (SOURCE_REPO at SOURCE_REVISION, FILES).
        private const val BASE = "https://huggingface.co/Supertone/supertonic-3/resolve/724fb5abbf5502583fb520898d45929e62f02c0b/"

        private fun file(name: String, sha256: String, size: Long) = Part("$MODEL/$name", sha256, size, BASE + name, label = "Giọng Supertonic")
        /** A file the app made itself ([VoiceModule.APP_MODELS], desktop the same pins): [path] on the phone, [source] in that repo. */
        private fun appFile(path: String, source: String, sha256: String, size: Long, label: String) =
            Part(path, sha256, size, VoiceModule.APP_MODELS + source, label = label)

        val FILES = listOf(
            file("onnx/duration_predictor.onnx", "c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db", 3_700_147),
            file("onnx/text_encoder.onnx", "c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff", 36_416_150),
            appFile("$MODEL/onnx/vector_estimator.onnx", "supertonic3-int8/top30/vector_estimator.onnx", "30ca11e17f99f2ccb33b7d8ec7cc51df9c86c7f2df3ede6a2107b5f505d526f0", 115_904_311, "Giọng Supertonic"),
            appFile("$MODEL/onnx/vocoder.onnx", "supertonic3-int8/vocoder/vocoder.onnx", "a81b861b87697404ae897b0824801691ecaac59f6801b70c6b55b9432aa46059", 45_162_003, "Giọng Supertonic"),
            file("onnx/tts.json", "42078d3aef1cd43ab43021f3c54f47d2d75ceb4e75f627f118890128b06a0d09", 8_253),
            file("onnx/unicode_indexer.json", "9bf7346e43883a81f8645c81224f786d43c5b57f3641f6e7671a7d6c493cb24f", 277_676),
            file("config.json", "4099082b107a9d4029849ac76b89eca65e03732660969c2babe5bf308c7357f2", 174),
            file("LICENSE", "0d944a9110fed9a9602d60e0423a272903e7bd21ab060490774efc77c2275e9f", 15_007),
            file("voice_styles/F1.json", "bbdec6ee00231c2c742ad05483df5334cab3b52fda3ba38e6a07059c4563dbc2", 292_046),
            file("voice_styles/F2.json", "7c722c6a72707b1a77f035d67f0d1351ba187738e06f7683e8c72b1df3477fc6", 292_423),
            file("voice_styles/F3.json", "12f6ef2573baa2defa1128069cb59f203e3ab67c92af77b42df8a0e3a2f7c6ab", 290_794),
            file("voice_styles/F4.json", "c2fa764c1225a76dfc3e2c73e8aa4f70d9ee48793860eb34c295fff01c2e032b", 291_808),
            file("voice_styles/F5.json", "45966e73316415626cf41a7d1c6f3b4c70dbc1ba2bee5c1978ef0ce33244fc8d", 291_479),
            file("voice_styles/M1.json", "e35604687f5d23694b8e91593a93eec0e4eca6c0b02bb8ed69139ab2ea6b0a5b", 291_748),
            file("voice_styles/M2.json", "b76cbf62bac707c710cf0ae5aba5e31eea1a6339a9734bfae33ab98499534a50", 292_055),
            file("voice_styles/M3.json", "ea1ac35ccb91b0d7ecad533a2fbd0eec10c91513d8951e3b25fbba99954e159b", 290_198),
            file("voice_styles/M4.json", "ca8eefad4fcd989c9379032ff3e50738adc547eeb5e221b82593a6d7b3bac303", 291_522),
            file("voice_styles/M5.json", "dd22b92740314321f8ae11c5e87f8dd60d060f15dd3a632b5adf77f471f77af2", 291_469),
        )
        /** Its own top folder (`fast/`), so removing it never touches the model. */
        val FAST_FILES = listOf(
            appFile(SupertonicText.FAST_ESTIMATOR, "supertonic3-int8/fast/vector_estimator.onnx", "e30ab5a4457219a8e402b52ad0ba28fab2fa658ed0027b78c298cfed25c08272", 81_526_521, FAST_LABEL),
        )
    }
}
