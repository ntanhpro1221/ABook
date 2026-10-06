package vn.abook.player.vieneu

import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.PinnedFiles
import vn.abook.player.PinnedFiles.Part
import vn.abook.player.SharedRuntime
import vn.abook.player.Store
import java.io.File
import java.io.IOException

/**
 * The frame of a voice the listener downloads on a tap (the phone's `voice_module.ModuleCore`), shared by "Giọng VieNeu" ([VieneuModule]) and
 * "Giọng Supertonic" ([vn.abook.player.readaloud.SupertonicModule]): pinned parts in [dir] (SHA-256 + size each, a newer pin makes a part
 * "outdated" and only it is fetched again), the runtime parts ([SharedRuntime.PARTS]) kept once in [runtime] for "Gói nhạc" and every voice and
 * not counted again, sizes shown = what this phone still lacks, the download on a background thread with progress, a self-benchmark of a few
 * seconds after it, removal of each choice. Same status shape as the desktop (ui/src/listen/vieneuModule.ts). The subclass gives the parts, choices and words.
 */
abstract class VoiceModule(
    protected val dir: File,
    /** Where the runtime parts ([SharedRuntime.PARTS]) are, for every module. */
    private val runtime: SharedRuntime,
    /** Part id -> its files (paths inside [dir], or inside [runtime]'s folder for a runtime part). */
    protected val groups: Map<String, List<Part>>,
    protected val facts: Facts,
    /** Measure a tier just downloaded; null in tests that do not measure. */
    private val benchmark: ((String) -> Benchmark)?,
    /** Drop loaded engines before files are replaced or removed. */
    private val forget: () -> Unit,
    private val metered: () -> Boolean,
) {
    class Facts(val cores: Int, val ramGb: Double)

    class Benchmark(val rtf: Double, val firstAudioMs: Long, val loadMs: Long, val audioSeconds: Double) {
        fun json(): JSONObject = JSONObject().put("rtf", rtf).put("firstAudioMs", firstAudioMs).put("loadMs", loadMs).put("audioSeconds", audioSeconds)

        companion object {
            /** From the clock of a self-benchmark: [began] -> engine loaded + warmed at [loaded] -> paragraph of [samples] at [rate] done at [done] (ns). */
            fun of(began: Long, loaded: Long, done: Long, samples: Int, rate: Int): Benchmark {
                val seconds = samples.toDouble() / rate
                return Benchmark(Math.round((done - loaded) / 1e9 / seconds * 1000) / 1000.0, (done - loaded) / 1_000_000, (loaded - began) / 1_000_000,
                    Math.round(seconds * 100) / 100.0)
            }
        }
    }

    /** "giọng VieNeu": the module in the middle of a sentence (error messages). */
    protected abstract val name: String
    /** "vieneu": thread names, and this module's claim on [runtime] while it downloads. */
    protected abstract val key: String
    /** Choices in the order the card shows them, and the tiers measured after a download (in measuring order). */
    abstract val choices: List<String>
    protected abstract val tiers: List<String>
    abstract fun needs(choice: String): List<String>
    protected abstract fun partLabel(id: String): String
    /** (label, detail) of a choice for this phone. */
    protected abstract fun choiceText(choice: String): Pair<String, String>
    /** Why this phone cannot have the module ("" = it can). */
    protected abstract val unsupported: String
    /** The choice "Khuyên dùng" for this phone given the self-benchmarks [bench]. */
    abstract fun recommended(bench: JSONObject = readBench()): String
    /** A downloaded voice slower than listening -> what to offer (the listener decides), null when none is slow. */
    protected abstract fun suggestion(bench: JSONObject, tiers: List<String>): JSONObject?
    /** (recommended, ticked at first) of a choice. */
    protected open fun marks(choice: String, best: String): Pair<Boolean, Boolean> = (choice == best) to (choice == best)
    /** Whether part [id] is one of the runtime parts kept in [runtime] for every module. */
    private fun common(id: String) = id in SharedRuntime.PARTS

    /** Where part [id]'s files are kept (and downloaded to). */
    private fun store(id: String): PinnedFiles = if (common(id)) runtime.pinned else pinned

    protected val pinned = PinnedFiles(dir, "", STAMP)
    private val lock = Any()
    private var downloading = false
    private var benchmarking = false
    private var error = ""
    private var finished = 0L
    private var current = 0L
    private var total = 0L
    private var worker: Thread? = null
    private val benchFile = File(dir, BENCH)

    /** Folder whose `<part path>` files are used for part [id]: [runtime]'s for a runtime part, else this module's. */
    fun folderFor(id: String): File = if (common(id)) runtime.dir else dir

    // ---- what is here -----------------------------------------------------------------------------------------------------------
    private fun partState(id: String, stamps: Map<PinnedFiles, Map<String, String>>): String {
        val files = groups.getValue(id)
        val store = store(id)
        if (files.isEmpty() || !files.all { store.present(it) }) return "missing"
        return if (files.all { store.isCurrent(it, stamps.getValue(store)) }) "current" else "outdated"
    }

    protected fun states(): Map<String, String> {
        val stamps = listOf(pinned, runtime.pinned).associateWith { it.readStamp() }
        return groups.keys.associateWith { partState(it, stamps) }
    }

    private fun bytes(id: String, states: Map<String, String>): Long =
        if (states[id] == "current") 0L else groups.getValue(id).filter { !store(id).isCurrent(it) }.sumOf { it.wireSize }

    /** Choices whose parts are all on this phone (an older version counts). */
    protected fun have(states: Map<String, String>) = choices.filter { choice -> needs(choice).all { states[it] != "missing" } }

    /** Parts (each once) that [wanted] still lack or have in an older version. */
    private fun lacking(wanted: List<String>, states: Map<String, String>): List<String> =
        wanted.flatMap { needs(it) }.distinct().filter { states[it] != "current" }

    /** Every file [wanted] use (shared ones once), as pinned by this app. */
    fun parts(wanted: List<String>): List<Part> = wanted.flatMap { needs(it) }.distinct().flatMap { groups.getValue(it) }

    /** Runtime libraries ([Part.blocking]) must match the APK's code (ONNX Runtime's Java API, JNI functions): true when one of the parts [used]
     *  (the copies this module or [runtime] keeps) is older than this app's pin - the voice then waits for the update. */
    protected fun runtimeBehind(used: List<String>): Boolean =
        used.any { id -> groups.getValue(id).any { it.blocking && !store(id).isCurrent(it) } }

    // ---- benchmark --------------------------------------------------------------------------------------------------------------
    protected fun readBench(): JSONObject = try {
        JSONObject(benchFile.readText(Charsets.UTF_8))
    } catch (_: Exception) {
        JSONObject()
    }

    /** Self-measured RTF of [tier] on this phone; null when not measured. */
    protected fun tierRtf(tier: String): Double? = readBench().optJSONObject(tier)?.optDouble("rtf")?.takeIf { !it.isNaN() }

    /** The RTF of [tier] in [bench] when this phone cannot read it live (at or above [SLOW_RTF]: the card then says so and points to "Làm trước",
     *  ui/src/listen/vieneuModule.ts), else null - the one rule of every voice module. */
    protected fun slowRtf(bench: JSONObject, tier: String): Double? = bench.optJSONObject(tier)?.optDouble("rtf")?.takeIf { !it.isNaN() && it >= SLOW_RTF }

    // ---- status -----------------------------------------------------------------------------------------------------------------
    /** For the module's card (same shape as the desktop's status, ui/src/listen/vieneuModule.ts). */
    fun status(): JSONObject = synchronized(lock) {
        val states = states()
        val installedTiers = have(states)
        val behind = lacking(installedTiers, states).filter { states[it] == "outdated" }
        val bench = readBench()
        val best = recommended(bench)
        val state = when {
            downloading -> "downloading"
            error.isNotEmpty() -> "error"
            installedTiers.isNotEmpty() -> if (behind.isNotEmpty()) "outdated" else "ready"
            unsupported.isNotEmpty() -> "unsupported"
            else -> "missing"
        }
        val shown = JSONArray()
        for (choice in choices) {
            val (label, detail) = choiceText(choice)
            val (recommended, ticked) = marks(choice, best)
            shown.put(JSONObject().put("id", choice).put("label", label).put("detail", detail).put("needs", JSONArray(needs(choice)))
                .put("bytes", lacking(listOf(choice), states).sumOf { bytes(it, states) }).put("installed", choice in installedTiers)
                .put("recommended", recommended).put("default", ticked).put("removable", choice in installedTiers))
        }
        val parts = JSONArray()
        for (id in groups.keys) {
            parts.put(JSONObject().put("id", id).put("label", partLabel(id)).put("bytes", groups.getValue(id).sumOf { it.wireSize })
                .put("state", states.getValue(id)).put("external", common(id)))
        }
        val shownBench = JSONObject()
        for (tier in installedTiers) bench.optJSONObject(tier)?.let { shownBench.put(tier, it) }
        JSONObject().put("state", state).put("done", if (downloading) finished + current else 0).put("total", if (downloading) total else 0)
            .put("error", error).put("supported", unsupported.isEmpty()).put("reason", unsupported).put("choices", shown).put("parts", parts)
            .put("outdatedParts", JSONArray(behind.map { partLabel(it) })).put("outdatedBytes", behind.sumOf { bytes(it, states) })
            .put("benchmark", shownBench).put("benchmarking", benchmarking)
            .put("suggestion", if (benchmarking) JSONObject.NULL else suggestion(bench, installedTiers) ?: JSONObject.NULL)
            .put("device", JSONObject().put("cores", facts.cores).put("ramGb", facts.ramGb).put("gpu", "").put("runs", "cpu"))
            .put("recommended", best).put("slowRtf", SLOW_RTF).put("metered", runCatching { metered() }.getOrDefault(false)).put("removable", true)
    }

    // ---- download / remove / measure -------------------------------------------------------------------------------------------
    /** Download what [wanted] lack (null: update the outdated parts of what is installed), on a background thread. */
    fun start(wanted: List<String>?) {
        synchronized(lock) {
            if (downloading || benchmarking) return
            val unknown = wanted?.firstOrNull { it !in choices }
            require(unknown == null) { "Không có lựa chọn $unknown" }
            val states = states()
            val needed = lacking(wanted ?: have(states), states)
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
            // claimed for the download: another module removed meanwhile must not take runtime files this one is about to use
            runtime.claim(key, (wanted ?: have(states)).flatMap { needs(it) }.filter(::common))
            worker = Thread({ run(needed) }, "abook-$key-module").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
                start()
            }
        }
    }

    private fun run(needed: List<String>) {
        try {
            forget() // a loaded engine must not read files being replaced
            val progress = object : PinnedFiles.Progress {
                override fun current(bytes: Long) = synchronized(lock) { current = bytes }
                override fun done(part: Part) = synchronized(lock) {
                    finished += part.wireSize
                    current = 0
                }
            }
            val (common, own) = needed.partition(::common)
            // another module may be fetching the same runtime files: one at a time, the second then finds them current
            if (common.isNotEmpty()) synchronized(runtime.fetching) { runtime.pinned.download(common.flatMap { groups.getValue(it) }, progress) }
            // a copy in this module's own folder (where versions before the shared folder put it) is never read again
            common.flatMap { groups.getValue(it) }.map { it.name.substringBefore('/') }.distinct().forEach { File(dir, it).deleteRecursively() }
            pinned.download(own.flatMap { groups.getValue(it) }, progress)
            forget()
            synchronized(lock) {
                downloading = false
                error = ""
                benchmarking = true
            }
            val installedTiers = have(states())
            measure(tiers.filter { tier -> tier in installedTiers && needs(tier).any { it in needed } })
        } catch (failure: Exception) {
            synchronized(lock) { error = describe(failure) }
        } finally {
            runtime.done(key) // from here this module's own files on disk say what it needs
            synchronized(lock) { downloading = false }
        }
    }

    private fun describe(failure: Exception): String {
        val title = name.replaceFirstChar { it.uppercase() }
        return when (failure) {
            is PinnedFiles.ChecksumError -> "$title tải về bị hỏng (không khớp mã kiểm) - bấm Thử lại để tải lại."
            is IOException -> "Không tải được $name (${failure.message ?: "mất kết nối"}). Bấm Thử lại - phần đã tải được giữ."
            else -> "Không tải được $name (${failure.message ?: failure.javaClass.simpleName})."
        }
    }

    /** Whether a just-downloaded voice can be measured at all (the voice's files are usable). */
    protected abstract fun measurable(): Boolean

    /** Measure [measured] (a few seconds each; the caller has set `benchmarking`); a failed measurement never spoils the download. */
    private fun measure(measured: List<String>) {
        try {
            val run = benchmark ?: return
            if (measured.isEmpty() || !measurable()) return
            val results = readBench()
            for (tier in measured) {
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
            val installedTiers = have(states())
            if (installedTiers.isEmpty()) return
            benchmarking = true
            worker = Thread({ measure(tiers.filter { it in installedTiers }) }, "abook-$key-bench").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
                start()
            }
        }
    }

    /** Remove one choice; parts another installed choice still needs stay, the last one takes this module's folder. A runtime part goes only when
     *  no installed module needs it any more ([SharedRuntime.release], decided from what is on disk after this module's own files are gone). */
    fun remove(choice: String) {
        require(choice in choices) { "Không có lựa chọn $choice" }
        synchronized(lock) {
            if (downloading || benchmarking) return
            forget()
            val others = have(states()).filter { it != choice }
            val keep = others.flatMap { needs(it) }.toSet()
            val (common, own) = needs(choice).filter { it !in keep }.partition(::common)
            if (others.isEmpty()) {
                dir.deleteRecursively()
            } else {
                val files = own.flatMap { groups.getValue(it) }
                pinned.remove(files)
                files.map { it.name.substringBefore('/') }.distinct().forEach { File(dir, it).deleteRecursively() }
                val bench = readBench().apply { remove(choice) }
                if (bench.length() == 0) benchFile.delete() else Store.writeAtomic(benchFile, bench.toString())
            }
            runtime.release(common.associateWith { groups.getValue(it) })
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
    }
}
