package vn.abook.player.vieneu

import android.app.ActivityManager
import android.content.Context
import org.json.JSONObject
import vn.abook.player.AndroidMusicStudent
import vn.abook.player.OrtRuntime
import vn.abook.player.readaloud.Clip
import vn.abook.player.readaloud.Voice
import vn.abook.player.readaloud.VoiceException
import vn.abook.player.readaloud.VoiceInfo
import java.io.File
import java.util.zip.ZipFile

/**
 * The VieNeu voices of this phone for "Nghe ngay" (provider "vieneu", offline): the module ([VieneuModule], `files/vieneu`), the voice lists,
 * and the engines, loaded on first use and kept for the process - one tier at a time (an engine holds hundreds of MB while it runs).
 * Synthesis is serialised: one paragraph at a time, on the caller's (background) thread.
 */
object VieneuVoices {
    const val PREFIX = "vieneu"
    /** The paragraph the self-benchmark reads (same as the desktop's `vieneu.BENCH_TEXT`). */
    const val BENCH_TEXT = "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa. Trời hôm nay đẹp quá."

    private var context: Context? = null
    private var module: VieneuModule? = null
    private var presetsOf: Pair<String, Map<String, List<VieneuPreset>>>? = null
    private var engine: Pair<String, VieneuTier>? = null

    @Synchronized
    fun module(appContext: Context): VieneuModule = module ?: run {
        val ctx = appContext.applicationContext
        context = ctx
        VieneuModule(File(ctx.filesDir, "vieneu"), File(ctx.filesDir, "music/student"), OrtRuntime.deviceAbi(), facts(ctx),
            benchmark = ::benchmark, forget = ::forget, metered = { AndroidMusicStudent.metered(ctx) }).also { module = it }
    }

    /** Cores and memory of this phone, for a voice module's "Khuyên dùng" and its card. */
    fun facts(ctx: Context): VoiceModule.Facts {
        val memory = ActivityManager.MemoryInfo().also { (ctx.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(it) }
        return VoiceModule.Facts(Runtime.getRuntime().availableProcessors(), Math.round(memory.totalMem / 1e8) / 10.0)
    }

    /** Drop the loaded engine and voice lists (the module is about to replace or remove files). The text reader stays mapped. */
    @Synchronized
    fun forget() {
        engine?.second?.let { runCatching { it.close() } }
        engine = null
        presetsOf = null
    }

    @Synchronized
    private fun presets(installed: VieneuInstalled): Map<String, List<VieneuPreset>> {
        val key = installed.voices.absolutePath + installed.voices.lastModified() + (installed.turbo != null) + (installed.nano != null)
        presetsOf?.takeIf { it.first == key }?.let { return it.second }
        val found = ZipFile(installed.voices).use { wheel ->
            VieneuPresets.TIERS.filter { (it == "turbo" && installed.turbo != null) || (it == "nano" && installed.nano != null) }.associateWith { tier ->
                val entry = wheel.getEntry(VieneuModule.VOICE_MEMBERS.getValue(tier)) ?: throw IllegalStateException("thiếu danh sách giọng $tier")
                VieneuPresets.read(JSONObject(wheel.getInputStream(entry).use { String(it.readBytes(), Charsets.UTF_8) }))
            }
        }
        presetsOf = key to found
        return found
    }

    /** Voices for the list ("Adam (VieNeu Nano)"); empty when the module is not on this phone. Never loads an engine. */
    fun voices(appContext: Context): List<VoiceInfo> {
        val installed = module(appContext).installed() ?: return emptyList()
        return runCatching {
            presets(installed).flatMap { (tier, list) ->
                list.map { VoiceInfo("$PREFIX:$tier/${it.name}", "${it.name} (${VieneuPresets.LABEL.getValue(tier)})", PREFIX, false, false, it.gender) }
            }
        }.getOrDefault(emptyList())
    }

    fun voice(appContext: Context, id: String): Voice {
        module(appContext)
        return VieneuVoice(id)
    }

    private class Ready(val tier: String, val engine: VieneuTier, val g2p: SeaG2p, val preset: VieneuPreset)

    @Synchronized
    private fun ready(tier: String, name: String?): Ready {
        val ctx = context ?: throw VoiceException("Chưa khởi động", reason = "voice")
        val owner = module(ctx)
        val installed = owner.installed() ?: throw VoiceException("Giọng VieNeu chưa tải trên điện thoại này - tải trong Cài đặt → Giọng đọc.", reason = "voice")
        val list = presets(installed)[tier] ?: throw VoiceException("Giọng VieNeu này chưa tải trên điện thoại này.", reason = "voice")
        val preset = (if (name == null) list.firstOrNull() else list.firstOrNull { it.name == name }) ?: throw VoiceException("Không có giọng VieNeu này.", reason = "voice")
        try {
            OrtRuntime.load(owner.ortFolder())
            val reader = SeaG2p.shared(installed.g2pLibrary, installed.dictionary)
            val loaded = engine?.takeIf { it.first == tier }?.second ?: run {
                forget()
                val cores = Runtime.getRuntime().availableProcessors()
                // measured 03-10 on a Helio P95: Turbo's per-frame graphs are fastest on 2 threads (the big cores), its codec on all; Nano on 4
                val made: VieneuTier = if (tier == "turbo") {
                    val dir = installed.turbo!!.first
                    TurboTier(VieneuTurbo(dir, installed.turbo.second, 2, 2, minOf(cores, 8)), ByteBpe(File(dir, "tokenizer.json")))
                } else {
                    NanoTier(VieneuNano(installed.nano!!, minOf(cores, 4)))
                }
                engine = tier to made
                made
            }
            return Ready(tier, loaded, reader, preset)
        } catch (failure: Throwable) {
            if (failure is VoiceException) throw failure
            throw VoiceException("Giọng VieNeu chưa sẵn sàng (${failure.message ?: failure.javaClass.simpleName}) - hãy tải lại Giọng VieNeu trong Cài đặt.", cause = failure, reason = "voice")
        }
    }

    /** One paragraph -> [out] (16-bit WAV at the tier's rate) + words. */
    @Synchronized
    fun synthesize(id: String, text: String, out: File, origin: String? = null): Clip {
        val (tier, name) = id.removePrefix("$PREFIX:").let { it.substringBefore('/') to it.substringAfter('/', "") }
        val ready = ready(tier, name)
        val spoken = try {
            VieneuSpeaker(ready.g2p::phonemize).speak(tier, ready.engine, ready.preset.name, ready.preset, text, origin)
        } catch (failure: OutOfMemoryError) {
            forget()
            throw VoiceException("Điện thoại không đủ bộ nhớ cho giọng VieNeu lúc này.", cause = failure, reason = "voice")
        }
        if (spoken.samples.isEmpty()) throw VoiceException("Đoạn này không có chữ nào đọc được.", reason = "empty")
        VieneuAudio.writeWav(spoken.samples, spoken.rate, out)
        return Clip(out, spoken.durationMs, spoken.words, id)
    }

    /**
     * Self-benchmark after a download (desktop `VieneuProvider.benchmark`): load the engine, read "Xin chào." once (ONNX Runtime's first run is
     * much slower; not counted), then [BENCH_TEXT] with the tier's first voice. RTF = seconds of work per second of audio (under 1 keeps up).
     */
    fun benchmark(tier: String): VoiceModule.Benchmark = synchronized(this) {
        val began = System.nanoTime()
        val ready = ready(tier, null)
        val speaker = VieneuSpeaker(ready.g2p::phonemize)
        speaker.speak(tier, ready.engine, ready.preset.name, ready.preset, "Xin chào.")
        val loaded = System.nanoTime()
        val spoken = speaker.speak(tier, ready.engine, ready.preset.name, ready.preset, BENCH_TEXT)
        VoiceModule.Benchmark.of(began, loaded, System.nanoTime(), spoken.samples.size, spoken.rate)
    }
}

/** A VieNeu voice ("vieneu:nano/Adam"): offline, WAV clips, words spread by syllables. */
class VieneuVoice(override val id: String) : Voice {
    override val extension = "wav"
    override fun synthesize(text: String, out: File): Clip = VieneuVoices.synthesize(id, text, out)
    override fun synthesize(text: String, out: File, origin: String?): Clip = VieneuVoices.synthesize(id, text, out, origin)
}
