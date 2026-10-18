package vn.abook.player.readaloud

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.Store
import vn.abook.player.vieneu.VoiceModule
import java.io.File

/**
 * "Tốc độ giọng trên máy" on the phone, the desktop's `abook/webui/voice_speed.py` (same rules, same status shape, ui/src/listen/voiceSpeed.ts): the
 * Supertonic voices and VieNeu Nano have two tiers for "Nghe ngay" - "Chất lượng cao nhất" and "Nhanh hơn" (the app's smaller int8 vector estimator,
 * fewer steps: [SupertonicText.FAST_ESTIMATOR], [vn.abook.player.vieneu.VieneuModule.NANO_FAST]). One choice per phone: [AUTO] (default) follows the
 * self-benchmark of the quality tier ([VoiceModule.SLOW_RTF]); an explicit choice is always kept; "Tự động" only moves between the two tiers of the
 * same voice, never to another voice.
 *
 * The tier applies to live listening only. A clip's tier is part of its cache key (the desktop's tier tag "fast<steps>" after the reading tags, nothing
 * for the quality tier - so keys match the desktop's), resolved by [ClipCache]: a plain voice id means "the live tier now", `<id>#q` the quality tier
 * (every export: [quality]) and `<id>#fast<n>` the fast one. The fast file is downloaded only when the fast tier is wanted (the module card offers
 * "Bản nhanh hơn" with its size); until then live listening reads the quality tier.
 */
object VoiceSpeed {
    const val FILE = "voice-speed.json"
    const val AUTO = "auto"
    const val QUALITY = "quality"
    const val FAST = "fast"
    val CHOICES = listOf(AUTO, QUALITY, FAST)
    /** Tier tag of an explicit quality id (`supertonic:F1#q`): no tag in the cache key. */
    const val QUALITY_TAG = "q"
    private const val SEPARATOR = '#'
    /** How long a live tier decision is kept (the cache asks it for every paragraph of a chapter). */
    private const val MEMO_MS = 3_000L

    /** A voice with two tiers, as its module knows it (SupertonicModule: the ten Supertonic voices, VieneuModule: Nano). */
    interface Family {
        /** "supertonic" / "nano". */
        val speedId: String
        /** "Giọng Supertonic" / "Giọng VieNeu Nano". */
        val speedName: String
        /** Module key for the card that downloads the fast file: "supertonic" / "vieneu". */
        val speedModule: String
        /** That card's choice for the fast file. */
        val fastChoice: String
        val fastSteps: Int
        /** The quality tier is on this phone. */
        fun speedInstalled(): Boolean
        /** Self-measured RTF of the quality tier (the measurement after a download measures it); null = not measured. */
        fun speedRtf(): Double?
        fun speedFastReady(): Boolean
        fun speedFastBytes(): Long
    }

    @Volatile
    private var file: File? = null
    @Volatile
    private var families: () -> List<Family> = { emptyList() }
    private val memo = HashMap<String, Pair<String, Long>>()

    /** Where the choice is kept and the families of this phone (ReadAloud: the two modules). */
    @Synchronized
    fun configure(file: File?, families: () -> List<Family> = this.families) {
        this.file = file
        this.families = families
        memo.clear()
    }

    /** This app's setup (the module factories and [ReadAloud] call it; the first one wins): the choice next to the app's files, the two modules. */
    fun setup(ctx: Context) {
        if (file != null) return
        val app = ctx.applicationContext
        configure(File(app.filesDir, FILE)) { listOf(SupertonicVoices.module(app), vn.abook.player.vieneu.VieneuVoices.module(app)) }
    }

    /** A module changed its files or its measurement: decide again. */
    @Synchronized
    fun changed() = memo.clear()

    fun choice(): String {
        val path = file ?: return AUTO
        val value = runCatching { JSONObject(path.readText(Charsets.UTF_8)).optString("choice") }.getOrNull()
        return if (value in CHOICES) value!! else AUTO
    }

    @Synchronized
    fun setChoice(value: String) {
        require(value in CHOICES) { "Không có lựa chọn $value" }
        val path = file ?: throw IllegalStateException("Cài đặt tốc độ giọng chưa được cấu hình")
        path.parentFile?.mkdirs()
        Store.writeAtomic(path, JSONObject().put("version", 1).put("choice", value).toString())
        memo.clear()
    }

    /** The tier choice [chosen] wants for a voice measured at [rtf] (quality tier; null = not measured -> quality). */
    fun decide(chosen: String, rtf: Double?): String = when (chosen) {
        QUALITY, FAST -> chosen
        else -> if (rtf != null && rtf >= VoiceModule.SLOW_RTF) FAST else QUALITY
    }

    /** "supertonic" / "nano" for a voice with two tiers, "" for any other. */
    fun family(voiceId: String): String = when {
        voiceId.startsWith("${SupertonicVoices.PREFIX}:") -> "supertonic"
        voiceId.startsWith("vieneu:nano/") -> "nano"
        else -> ""
    }

    /** (voice id, tier tag) of a possibly tiered id; ids of other voices are never split. */
    fun split(voiceId: String): Pair<String, String> {
        val at = voiceId.lastIndexOf(SEPARATOR)
        if (at < 0 || (!voiceId.startsWith("${SupertonicVoices.PREFIX}:") && !voiceId.startsWith("vieneu:"))) return voiceId to ""
        return voiceId.substring(0, at) to voiceId.substring(at + 1)
    }

    /** The id an export reads with: the quality tier, whatever the live choice ("" tag for voices without tiers). */
    fun quality(voiceId: String): String = if (family(split(voiceId).first).isEmpty()) voiceId else "${split(voiceId).first}$SEPARATOR$QUALITY_TAG"

    /** Explicit id of [voiceId] read at tier tag [tag] ("" = quality). */
    fun explicit(voiceId: String, tag: String): String = if (family(voiceId).isEmpty()) voiceId else "$voiceId$SEPARATOR${tag.ifEmpty { QUALITY_TAG }}"

    /** Whether a tag means the fast tier ("fast5", "fast10"). */
    fun isFast(tag: String) = tag.startsWith(FAST) && tag.length > FAST.length

    /** Whether the current choice wants the fast tier for a voice measured at [rtf] (its card then offers the fast file). */
    fun wantsFast(rtf: Double?): Boolean = decide(choice(), rtf) == FAST

    /** Tier tag of a live clip by [voiceId] in the cache key: "fast<steps>" when reading the fast tier (wanted and downloaded), else "". */
    fun liveTag(voiceId: String): String {
        val name = family(voiceId)
        if (name.isEmpty()) return ""
        val now = System.currentTimeMillis()
        synchronized(this) { memo[name]?.takeIf { now - it.second < MEMO_MS }?.let { return it.first } }
        val found = runCatching { families().firstOrNull { it.speedId == name } }.getOrNull()
        val tag = if (found == null || decide(choice(), found.speedRtf()) != FAST || !found.speedFastReady()) "" else "$FAST${found.fastSteps}"
        synchronized(this) { memo[name] = tag to now }
        return tag
    }

    /** For the settings row: the choice + each two-tier voice on this phone: wanted tier, tier read now, measurement, bytes of the fast file still lacking. */
    fun status(): JSONObject {
        val chosen = choice()
        val voices = JSONArray()
        for (found in runCatching { families() }.getOrDefault(emptyList())) {
            if (!found.speedInstalled()) continue
            val rtf = found.speedRtf()
            val tier = decide(chosen, rtf)
            val ready = found.speedFastReady()
            voices.put(JSONObject().put("id", found.speedId).put("name", found.speedName).put("module", found.speedModule).put("fastChoice", found.fastChoice)
                .put("rtf", rtf ?: JSONObject.NULL).put("tier", tier).put("using", if (tier == FAST && ready) FAST else QUALITY)
                .put("fastBytes", if (ready) 0L else found.speedFastBytes()))
        }
        return JSONObject().put("choice", chosen).put("voices", voices)
    }
}
