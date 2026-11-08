package vn.abook.player.readaloud

import vn.abook.player.S

import org.json.JSONObject
import vn.abook.player.Store
import java.io.File

/** The same neutral set and rule as readaloud/engine_pick.py. No model or runtime downloads here. */
interface LocalEngine {
    val id: String
    val voices: List<VoiceInfo>
    val capabilities: Set<String>
    val resourceNeeds: Map<String, String>
    val mark: String
    fun synthesize(text: String, out: File): Clip
    fun forget()
}

data class EngineNumbers(
    val engine: String, val voice: String, val mark: String,
    val rtf: Double? = null, val ramMb: Long? = null, val loadMs: Long? = null,
    val cer: Double? = null, val natural: Double? = null, val error: String = "",
) {
    val verdict: String get() = when {
        error.isNotEmpty() || rtf == null || !rtf.isFinite() || rtf < 0 ||
            listOfNotNull(cer, natural).any { !it.isFinite() || it < 0 } -> "error"
        cer != null && cer > MachineVoicePick.CER_GATE -> "unclear"
        rtf >= MachineVoicePick.LIVE_RTF -> "slow"
        else -> ""
    }
}

data class EnginePickStatus(
    val engines: List<EngineNumbers> = emptyList(), val installed: List<String> = emptyList(),
    val auto: String? = null, val override: String = "", val chosen: String? = null,
    val measuring: Boolean = false, val error: String = "",
)

class MachineVoicePick(
    private val file: File, private val machine: String, private val engines: () -> List<LocalEngine>,
    private val rss: () -> Long, private val clock: () -> Long = System::nanoTime,
) {
    private val lock = Any()
    @Volatile private var measuring = false
    @Volatile private var problem = ""

    private fun read(): JSONObject = runCatching { JSONObject(file.readText(Charsets.UTF_8)) }.getOrDefault(JSONObject())

    fun status(): EnginePickStatus = synchronized(lock) {
        val data = read()
        val installed = engines()
        val rows = data.optJSONObject("engines")?.takeIf { data.optString("machine") == machine }
        val measured = installed.mapNotNull { engine ->
            rows?.optJSONObject(engine.id)?.takeIf { it.optString("mark") == engine.mark && it.optString("voice") == engine.voices.firstOrNull()?.id }?.let {
                EngineNumbers(engine.id, it.optString("voice"), engine.mark,
                    if (it.isNull("rtf")) null else it.optDouble("rtf"),
                    if (it.isNull("ramMb")) null else it.optLong("ramMb"),
                    if (it.isNull("loadMs")) null else it.optLong("loadMs"), error = it.optString("error"))
            }
        }
        val auto = choose(measured)
        val override = data.optString("override").takeIf { id -> installed.any { it.id == id } }.orEmpty()
        EnginePickStatus(measured, installed.map { it.id }, auto, override,
            override.ifEmpty { auto ?: if (measured.isNotEmpty()) "" else null }, measuring, problem)
    }

    fun setOverride(engine: String) = synchronized(lock) {
        require(engine.isEmpty() || engines().any { it.id == engine }) { S.s_giong_nay_chua_tai_tren_may_c3c42007 }
        val data = read().put("override", engine)
        Store.writeAtomic(file, data.toString())
    }

    /** Called on an IO thread. Sequential engines, background priority; no phone ASR/UTMOS is bundled. */
    fun measure() {
        synchronized(lock) { if (measuring) return; measuring = true; problem = "" }
        try {
            val rows = JSONObject()
            for (engine in engines()) {
                val row = JSONObject().put("voice", engine.voices.first().id).put("mark", engine.mark)
                try {
                    engine.forget()
                    val peak = java.util.concurrent.atomic.AtomicLong(rss())
                    val running = java.util.concurrent.atomic.AtomicBoolean(true)
                    val sampler = Thread {
                        while (running.get()) { peak.accumulateAndGet(rss(), ::maxOf); Thread.sleep(20) }
                    }.apply { isDaemon = true; start() }
                    val out = File.createTempFile("voice-pick-", ".wav", file.parentFile)
                    try {
                        val began = clock()
                        engine.synthesize(S.s_xin_chao_0dcb19e7, out)
                        row.put("loadMs", (clock() - began) / 1_000_000)
                        var work = 0L
                        var audio = 0L
                        for (sentence in SENTENCES) {
                            val start = clock()
                            val clip = engine.synthesize(sentence, out)
                            work += clock() - start
                            audio += clip.durationMs
                        }
                        check(audio > 0) { S.s_may_doc_khong_ra_tieng_7f1ebda2 }
                        row.put("rtf", work / (audio * 1_000_000.0))
                    } finally {
                        running.set(false); sampler.join()
                        peak.accumulateAndGet(rss(), ::maxOf)
                        row.put("ramMb", peak.get() / (1024 * 1024))
                        out.delete()
                    }
                } catch (error: Exception) {
                    row.put("error", error.message ?: S.s_thu_khong_duoc_d17d8afe)
                } finally { engine.forget() }
                rows.put(engine.id, row)
            }
            synchronized(lock) {
                val data = read().put("machine", machine).put("engines", rows).put("at", System.currentTimeMillis())
                Store.writeAtomic(file, data.toString())
            }
        } catch (error: Exception) { problem = error.message ?: S.s_thu_khong_duoc_d17d8afe }
        finally { measuring = false }
    }

    companion object {
        const val LIVE_RTF = 0.8
        const val CER_GATE = 0.15
        const val NATURAL_TIE = 0.1
        val SENTENCES = listOf(
            S.s_buoi_sang_hom_ay_troi_trong_xanh_va_gio_th_3c7ef60b,
            S.s_co_be_mo_cua_so_lang_le_nhin_xuong_con_duo_f7a6d29c,
            S.s_anh_ay_im_lang_mot_luc_lau_roi_moi_cham_ra_5b6f8f27,
            S.s_chung_toi_di_bo_doc_bo_song_cho_toi_khi_ma_e5b1a748,
        )
        fun engineOf(voice: String) = if ('/' in voice) voice.substringBefore('/') else voice.substringBefore(':')
        fun name(engine: String) = when (engine) {
            "vieneu:turbo" -> S.s_giong_vieneu_371ad9fb
            "vieneu:nano" -> S.s_giong_vieneu_nano_dc5fdeb6
            "supertonic" -> S.s_giong_supertonic_9922ded4
            else -> engine
        }
        fun choose(rows: List<EngineNumbers>): String? {
            var fit = rows.filter { it.verdict.isEmpty() }
            val best = fit.mapNotNull { it.natural }.maxOrNull()
            if (best != null) fit = fit.filter { it.natural != null && best - it.natural < NATURAL_TIE }
            return fit.minWithOrNull(compareBy<EngineNumbers> { it.cer ?: Double.POSITIVE_INFINITY }.thenBy { it.rtf }.thenBy { it.engine })?.engine
        }
    }
}
