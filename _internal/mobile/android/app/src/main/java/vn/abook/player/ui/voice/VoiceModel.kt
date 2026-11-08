package vn.abook.player.ui.voice

import vn.abook.player.S

import vn.abook.player.ui.data.dotJoined
import vn.abook.player.formatSize

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import java.util.Locale

/*
 * Mô hình và lời của các việc Giọng đọc làm thêm: giọng tải về máy (VieNeu, Supertonic), khoá giọng trực tuyến, nghe thử, đồng ý gửi chữ, Nhạc của tôi. Cùng hình JSON
 * với lõi (VoiceModule.status, OnlineKeys.public, MusicStore.entries).
 * Hàm thuần, không Android: thử trên JVM.
 */

/** Màn con của nhóm Giọng đọc (cấp hai, cũng là cấp cuối: Cài đặt -> Giọng đọc -> màn này). Bảng trượt là lớp nổi, không phải cấp ba. */
enum class VoicePage { Keys, Music }

/** Hai mô-đun giọng chạy trên máy, tải khi bạn bấm. `invite`: lời mời dưới tên khi chưa tải - cùng lời thẻ giọng bên web (vieneuModule.ts `invite`). */
enum class ModuleKind(val key: String, val title: String, val invite: String) {
    Vieneu("vieneu", S.s_giong_vieneu_371ad9fb, S.s_giong_hay_doc_ngay_tren_may_khong_can_mang_69bed8de),
    Supertonic("supertonic", S.s_giong_supertonic_9922ded4, S.s_muoi_giong_nam_nu_nhe_may_khong_can_mang_c_4e018b39),
}

enum class ModuleState { Missing, Downloading, Ready, Outdated, Error, Unsupported }

@Immutable
data class ModuleChoice(
    val id: String,
    val label: String,
    val detail: String,
    /** Byte máy này còn thiếu cho riêng lựa chọn này. */
    val bytes: Long,
    val installed: Boolean,
    val recommended: Boolean,
    /** Gỡ được (đã cài, hay còn phần tải dở). */
    val removable: Boolean,
    /** Mô-đun đánh dấu sẵn lựa chọn này cho máy (gói mặc định của Cài đặt). */
    val ticked: Boolean = false,
)

@Immutable
data class ModuleBench(val rtf: Double, val firstAudioMs: Long)

/** Lời đề nghị đổi giọng khi giọng vừa tải đọc chậm hơn tốc độ nghe: người nghe quyết, máy không tự đổi. */
@Immutable
data class ModuleSuggestion(val tier: String, val rtf: Double, val switchTo: String, val installed: Boolean)

/**
 * Trạng thái một mô-đun giọng. `percent` đã tính sẵn (số byte chạy theo nhịp riêng - [VoiceState.progress]), nên màn chỉ dựng lại khi số phần trăm hay trạng thái đổi.
 */
@Immutable
data class ModuleStatus(
    val state: ModuleState,
    val percent: Int,
    val total: Long,
    val error: String,
    val reason: String,
    val choices: List<ModuleChoice>,
    val outdatedBytes: Long,
    val benchmark: Map<String, ModuleBench>,
    val benchmarking: Boolean,
    val suggestion: ModuleSuggestion?,
    val recommended: String,
    val slowRtf: Double,
    val metered: Boolean,
    val cancelled: Boolean,
) {
    val working: Boolean get() = state == ModuleState.Downloading || benchmarking
    val installedAny: Boolean get() = choices.any { it.installed }

    fun choice(id: String): ModuleChoice? = choices.firstOrNull { it.id == id }
}

object ModuleJson {
    fun status(json: JSONObject): ModuleStatus {
        val state = when (json.optString("state")) {
            "downloading" -> ModuleState.Downloading
            "ready" -> ModuleState.Ready
            "outdated" -> ModuleState.Outdated
            "error" -> ModuleState.Error
            "unsupported" -> ModuleState.Unsupported
            else -> ModuleState.Missing
        }
        val total = json.optLong("total")
        val done = json.optLong("done")
        val rows = json.optJSONArray("choices")
        val choices = (0 until (rows?.length() ?: 0)).mapNotNull { rows?.optJSONObject(it) }.map { row ->
            ModuleChoice(
                row.optString("id"), row.optString("label"), row.optString("detail"), row.optLong("bytes"), row.optBoolean("installed"),
                row.optBoolean("recommended"), row.optBoolean("removable"), row.optBoolean("default"),
            )
        }
        val bench = json.optJSONObject("benchmark")
        val results = LinkedHashMap<String, ModuleBench>()
        bench?.keys()?.forEach { tier -> bench.optJSONObject(tier)?.let { results[tier] = ModuleBench(it.optDouble("rtf"), it.optLong("firstAudioMs")) } }
        val suggestion = json.optJSONObject("suggestion")?.let {
            ModuleSuggestion(it.optString("tier"), it.optDouble("rtf"), it.optString("switchTo"), it.optBoolean("installed"))
        }
        return ModuleStatus(
            state, if (total > 0) minOf(100L, done * 100 / total).toInt() else 0, total, json.optString("error"), json.optString("reason"), choices,
            json.optLong("outdatedBytes"), results, json.optBoolean("benchmarking"), suggestion, json.optString("recommended"),
            json.optDouble("slowRtf", 0.8), json.optBoolean("metered"), json.optBoolean("cancelled"),
        )
    }
}

/** Lỗi đã dịch cho người nghe (lõi ném, nguồn gói lại). */
class VoiceFailure(message: String) : Exception(message)

// ---- khoá giọng trực tuyến ----------------------------------------------------------------------------------------------------

/** Một nhà cung cấp giọng dùng khoá của bạn, như lõi mô tả ([vn.abook.player.readaloud.KeyedProvider.describe]): khoá chỉ ở dạng che. */
@Immutable
data class KeyProvider(
    val id: String,
    val name: String,
    /** Hạn mức miễn phí nhà cung cấp cho ("Miễn phí 500.000 ký tự mỗi tháng"). */
    val free: String,
    /** Cần nhập vùng (Azure). */
    val region: Boolean,
    val hasKey: Boolean,
    /** "••••abcd": đủ để nhận ra khoá nào, không bao giờ là khoá thật. */
    val masked: String,
    val regionValue: String,
    val valid: Boolean,
    val voices: Int,
    val timings: String = "estimated",
)

/** Kết quả "Kiểm tra" một khoá: câu nói được cho người nghe. */
@Immutable
data class KeyResult(val ok: Boolean, val text: String, val provider: KeyProvider? = null)

object KeyJson {
    fun provider(json: JSONObject): KeyProvider {
        val limits = json.optJSONObject("limits")
        return KeyProvider(
            json.optString("id"), json.optString("name"), limits?.optString("free").orEmpty(), limits?.optBoolean("region") == true,
            json.optBoolean("hasKey"), json.optString("masked"), json.optString("region"), json.optBoolean("valid"), json.optInt("voices"), limits?.optString("timings", "estimated") ?: "estimated",
        )
    }

    /** `checkOnlineKey`: {ok, reason?, message?, voices?, provider}. */
    fun check(json: JSONObject): KeyResult {
        val provider = json.optJSONObject("provider")?.let(::provider)
        return if (json.optBoolean("ok")) {
            KeyResult(true, S.s_dung_duoc_0_giong_tieng_viet_8d3747da(if (json.has("voices")) json.optInt("voices") else provider?.voices ?: 0), provider)
        } else {
            KeyResult(false, json.optString("message").ifBlank { S.s_khoa_chua_dung_duoc_2ae17f08 }, provider)
        }
    }
}

// ---- Nhạc của tôi ---------------------------------------------------------------------------------------------------------------

@Immutable
data class MusicTrack(val link: String, val title: String, val creator: String, val duration: Double, val bytes: Long, val analysed: Boolean)

/** Kết quả một lượt nhập: bài mới, bài đã có từ trước, file không nhập được kèm lý do. */
@Immutable
data class MusicImportResult(val tracks: List<MusicTrack>, val added: Int, val existing: Int, val failed: List<String>)

object MusicJson {
    fun tracks(rows: org.json.JSONArray?): List<MusicTrack> = (0 until (rows?.length() ?: 0)).mapNotNull { rows?.optJSONObject(it) }.map { row ->
        MusicTrack(row.optString("link"), row.optString("title"), row.optString("creator"), row.optDouble("duration", 0.0), row.optLong("bytes"), row.optBoolean("analysed"))
    }

    /** Lời đáp của lượt nhập (`my_music_import`). */
    fun imported(json: JSONObject): MusicImportResult {
        val failed = json.optJSONArray("failed")
        return MusicImportResult(
            tracks(json.optJSONArray("tracks")), json.optJSONArray("added")?.length() ?: 0, json.optJSONArray("existing")?.length() ?: 0,
            (0 until (failed?.length() ?: 0)).map { failed!!.optString(it) },
        )
    }
}

// ---- lời --------------------------------------------------------------------------------------------------------------------------

/** Việc một hàng giọng trên máy đang mời / cho làm. */
sealed interface ModuleAction {
    /** "Tải 198 MB" (hay "Dùng" khi các phần đã có sẵn). */
    data class Download(val label: String) : ModuleAction
    data object Cancel : ModuleAction
    data object Retry : ModuleAction

    /** Đã có (hay còn phần tải dở): chạm mở bảng việc của nó. */
    data object Manage : ModuleAction

    /** Chờ tới lượt (mô-đun đang tải một lựa chọn khác) hay máy không dùng được. */
    data object None : ModuleAction
}

/** Một hàng giọng trên máy, đã nói bằng lời: tên, dòng phụ (đỏ khi là lỗi), việc ở cuối hàng; `progress` = đang tải ngay hàng này (thanh tiến độ dưới hàng). */
@Immutable
data class ModuleRow(
    val id: String,
    val title: String,
    val hint: String,
    val problem: Boolean,
    val action: ModuleAction,
    val progress: Boolean,
)

object VoiceText {
    fun gender(value: String): String? = when (value.lowercase()) { "male", "nam" -> S.s_nam_22dd59c8; "female", S.s_nu_316c30fd -> S.s_nu_e15bc11c; else -> null }
    fun onlineNotice(provider: String): String? = when {
        provider == "edge" -> S.s_giong_edge_gui_chu_cua_sach_toi_may_chu_mi_7aefebec
        provider in KEYED -> S.s_giong_0_gui_chu_cua_sach_toi_1_bang_khoa_c_3149e832(KEYED[provider], KEYED[provider])
        else -> null
    }
    fun advice(vieneu: ModuleStatus?, supertonic: ModuleStatus?): String? {
        if (vieneu == null || supertonic == null || vieneu.installedAny || supertonic.installedAny) return null
        if (vieneu.state == ModuleState.Unsupported) return null
        val name = tierName(if (vieneu.recommended == "nano") "nano" else "turbo").replaceFirstChar { it.lowercase() }
        return S.s_nen_dung_0_chi_can_tai_mot_bo_giong_46fb0d74(name)
    }
    private fun seconds(value: Double): String = String.format(Locale.ROOT, "%.1f", value).replace('.', ',')

    /** Tên một tầng giọng (vieneuModule.ts `tierName`). */
    fun tierName(tier: String): String = when (tier) {
        "turbo" -> S.s_giong_vieneu_371ad9fb
        "nano" -> S.s_giong_vieneu_nano_dc5fdeb6
        else -> S.s_giong_supertonic_9922ded4
    }

    /** Tên một lựa chọn trên hàng: cùng tên lõi đặt, trừ bản nhanh hơn của Supertonic (đứng riêng trong danh sách phẳng nên phải nói của giọng nào). */
    fun choiceTitle(choice: ModuleChoice): String = if (choice.id == "supertonic_fast") S.s_supertonic_nhanh_hon_3717c32e else choice.label

    /** Đầu mã giọng của một tầng ("vieneu:nano/", "supertonic:") - để đổi mọi cuốn đang dùng tầng ấy sang giọng khác. */
    fun tierVoicePrefix(tier: String): String = if (tier == "supertonic") "supertonic:" else "vieneu:$tier/"

    /** Câu nhắc trước khi tải bằng dữ liệu di động (null khi không cần nhắc). */
    fun metered(status: ModuleStatus, bytes: Long): String? =
        if (status.metered && bytes > 0) S.s_dien_thoai_dang_dung_du_lieu_di_dong_tai_0_8aee54f4(formatSize(bytes)) else null

    /** Câu nói kết quả tự đo, theo điều người nghe cần biết (vieneuModule.ts `benchmarkLabel`). */
    fun benchmark(tier: String, result: ModuleBench, slow: Double): String {
        val name = tierName(tier)
        if (result.rtf >= slow) {
            val hour = maxOf(1, Math.round(result.rtf * 60).toInt())
            return S.s_0_may_nay_khong_kip_doc_truc_tiep_1_giay_c_953404bf(name, seconds(result.rtf), hour)
        }
        val speed = if (result.rtf > 0) 1 / result.rtf else 0.0
        return S.s_0_doc_truc_tiep_duoc_may_nay_doc_nhanh_gap_b0ef506b(name, seconds(speed), seconds(result.firstAudioMs / 1000.0))
    }

    /** Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút (vieneuModule.ts `suggestionText`). */
    fun suggestion(suggestion: ModuleSuggestion): Pair<String, String> {
        val lead = S.s_0_doc_cham_tren_may_nay_1_giay_cho_moi_gia_10e817a5(tierName(suggestion.tier), seconds(suggestion.rtf))
        if (suggestion.switchTo == "nano") {
            return if (suggestion.installed) S.s_0_giong_vieneu_nano_nhe_hon_da_co_san_fef4245f(lead) to S.s_dung_giong_vieneu_nano_b84996dd
            else S.s_0_giong_vieneu_nano_nhe_hon_hop_may_nay_05bccaca(lead) to S.s_tai_giong_vieneu_nano_e24acf37
        }
        return S.s_0_giong_truc_tuyen_nhe_may_can_mang_be7ce311(lead) to S.s_dung_giong_truc_tuyen_a5bae2dc
    }

    /** Lời hỏi trước khi gỡ một giọng khỏi máy: điện thoại không biết cuốn nào dùng nó, nên một câu ngắn (vieneuModule.ts `removeAsk(null)`). */
    const val REMOVE_ASK = S.s_giong_se_khong_con_tren_may_nay_cho_toi_kh_cb683781

    /** Dòng phụ của hàng khi mô-đun không dùng được trên máy này. */
    fun unsupported(status: ModuleStatus): String =
        if (status.reason.isNotEmpty()) S.s_may_nay_chua_dung_duoc_0_aaad0a2a(status.reason) else S.s_may_nay_chua_dung_duoc_faf04aee

    const val CANCELLED = S.s_da_huy_lan_tai_sau_lam_tiep_tu_cho_dung_a3bd5f77
    /** Nhãn của lựa chọn nên tải - cùng chữ với nhãn "Khuyên dùng" của thẻ giọng bên web (VieneuModuleCard.tsx). */
    private const val RECOMMENDED = S.s_khuyen_dung_b1d3dec8

    /**
     * Mỗi lựa chọn của mô-đun một hàng. `pending`: các lựa chọn bạn vừa bấm tải (mô-đun tải theo cả gói, nhưng thanh tiến độ và nút "Huỷ" nằm ở hàng bạn bấm; không rõ thì
     * hàng chưa có đầu tiên). Hàng đã có: dòng phụ nói tốc độ máy đo được; hàng chưa có: nói cỡ cần tải ở nút cuối hàng.
     */
    fun rows(status: ModuleStatus, pending: List<String>): List<ModuleRow> {
        // Máy không dùng được và chưa có gì: một hàng nói lý do, không lặp cho từng lựa chọn.
        if (status.state == ModuleState.Unsupported && status.choices.none { it.installed }) return status.choices.take(1).map { row(status, it, false) }
        val missing = status.choices.filter { !it.installed }
        val mine = pending.filter { id -> missing.any { it.id == id } }.ifEmpty { missing.take(1).map { it.id } }
        return status.choices.map { choice -> row(status, choice, choice.id in mine) }
    }

    private fun row(status: ModuleStatus, choice: ModuleChoice, mine: Boolean): ModuleRow {
        val title = choiceTitle(choice)
        if (status.state == ModuleState.Unsupported && !choice.installed) return ModuleRow(choice.id, title, unsupported(status), true, ModuleAction.None, false)
        if (choice.installed) return installed(status, choice, title)
        val lead = if (choice.recommended) "$RECOMMENDED · " else ""
        return when {
            status.state == ModuleState.Downloading && mine ->
                ModuleRow(choice.id, title, S.s_dang_tai_0_1_0d39c288(formatSize(status.total), status.percent), false, ModuleAction.Cancel, true)
            status.state == ModuleState.Downloading -> ModuleRow(choice.id, title, lead + choice.detail, false, ModuleAction.None, false)
            status.state == ModuleState.Error && mine -> ModuleRow(choice.id, title, status.error, true, ModuleAction.Retry, false)
            else -> {
                val cancelled = if (status.cancelled && mine) "$CANCELLED " else ""
                ModuleRow(choice.id, title, cancelled + lead + (if (choice.bytes == 0L) S.s_da_co_san_90ac4add else choice.detail), false, ModuleAction.Download(if (choice.bytes > 0) S.s_tai_0_3463a4d8(formatSize(choice.bytes)) else S.s_dung_7927ca4e), false)
            }
        }
    }

    private fun installed(status: ModuleStatus, choice: ModuleChoice, title: String): ModuleRow {
        val tier = status.benchmark[choice.id]
        val hint = when {
            status.benchmarking -> S.s_dang_thu_giong_vua_tai_vai_giay_34a21087
            status.state == ModuleState.Outdated -> S.s_co_ban_moi_0_f447f64f(formatSize(status.outdatedBytes))
            tier != null && tier.rtf >= status.slowRtf -> S.s_cham_hon_toc_do_nghe_dung_lam_truoc_a40aebf4
            tier != null && tier.rtf > 0 -> S.s_doc_truc_tiep_duoc_nhanh_gap_0_lan_762949dd(seconds(1 / tier.rtf))
            else -> S.s_da_co_7610f1dd
        }
        return ModuleRow(choice.id, title, hint, false, ModuleAction.Manage, false)
    }

    /** Hàng chưa có mà còn phần tải dở (đã huỷ giữa chừng): chạm mở bảng có "Xoá phần đã tải". */
    fun hasLeftovers(choice: ModuleChoice): Boolean = !choice.installed && choice.removable

    // ---- đồng ý gửi chữ -----------------------------------------------------------------------------------------------------------

    /** Tên nhà cung cấp giọng dùng khoá của bạn (readAloudVoice.ts `KEYED_PROVIDERS`). */
    val KEYED = linkedMapOf("azure" to S.s_azure_speech_8bd84d93, "google" to S.s_google_cloud_69bd2211, "fpt" to "FPT.AI", "viettel" to S.s_viettel_ai_9094e708)

    private val COMPANIES = mapOf("edge" to S.s_microsoft_c7bac469)

    /** Giọng của nơi này gửi chữ ra ngoài máy (Edge, hay nhà cung cấp dùng khoá của bạn): phải được bạn đồng ý trước lần đầu. */
    fun isOnline(provider: String): Boolean = provider in COMPANIES || provider in KEYED

    /** Tên giọng như người nghe gọi: "Hoài My (Edge)" -> "Hoài My". */
    fun spokenName(name: String): String = name.replace(Regex("""\s*\([^)]*\)\s*$"""), "").trim().ifEmpty { name }

    /** Chữ đi tới đâu khi đọc bằng giọng trực tuyến của nhà cung cấp này (onlineConsent.ts `onlineDestination`). */
    fun destination(provider: String): String = KEYED[provider] ?: COMPANIES[provider]?.let { S.s_may_chu_0_085d6415(it) } ?: S.s_dich_vu_ngoai_0bb5b472

    /** Lời hỏi trước lần đầu đọc bằng giọng trực tuyến (onlineConsent.ts `onlinePromptText`). */
    fun consent(voiceName: String, provider: String): String {
        val name = spokenName(voiceName)
        val where = destination(provider)
        if (provider in KEYED) return S.s_giong_0_dung_khoa_1_cua_ban_chu_cua_doan_d_005b3ec4(name, where, where)
        return if (provider in COMPANIES) {
            S.s_giong_0_la_giong_1_chu_cua_doan_dang_doc_d_48efa5c3(name, if (provider == "edge") S.s_edge_0f82fe72 else S.s_truc_tuyen_ada49667, where)
        } else {
            S.s_giong_0_la_giong_truc_tuyen_chu_cua_doan_d_eee4aa0e(name, where)
        }
    }

    /** Câu đọc thử (readAloudVoice.ts `SAMPLE_TEXT`): ngắn, có dấu câu để nghe cả chỗ ngắt. */
    const val SAMPLE = S.s_xin_chao_toi_se_doc_sach_cho_ban_nghe_ban_885b35e2

    // ---- khoá ---------------------------------------------------------------------------------------------------------------------

    /** Dòng phụ của một nhà cung cấp: chưa có khoá thì hạn mức miễn phí; có rồi thì khoá che + kết quả lần kiểm tra. */
    fun keyHint(provider: KeyProvider): String = keyStatus(provider)?.let { "${provider.masked} · $it" } ?: provider.free

    /** Kết quả lần kiểm tra khoá - cùng chữ với nhãn trạng thái của thẻ khoá bên web (VoiceSettings.tsx KeyCard); chưa có khoá thì null. */
    fun keyStatus(provider: KeyProvider): String? = when {
        !provider.hasKey -> null
        provider.valid -> S.s_dung_duoc_0_giong_ddbd60b5(provider.voices)
        else -> S.s_chua_dung_duoc_c68b3845
    }

    /** Dòng tóm tắt của hàng "Khoá giọng trực tuyến": tên các nhà cung cấp đã có khoá, hay "Chưa có khoá". */
    fun keySummary(providers: List<KeyProvider>): String =
        providers.filter { it.hasKey }.map { it.name }.dotJoined().ifEmpty { S.s_chua_co_khoa_fce87985 }

    /** Lấy khoá ở đâu - nói theo những gì bạn thấy trên trang của nhà cung cấp (VoiceSettings.tsx `KEY_HELP`). */
    fun keyHelp(provider: String): String = when (provider) {
        "azure" -> S.s_azure_tao_speech_f0_mien_phi_keys_and_endp_13c271d5
        "google" -> S.s_google_cloud_bat_cloud_text_to_speech_api_6c11e0dc
        "fpt" -> S.s_tren_console_fpt_ai_dang_nhap_mo_muc_text_4010b0be
        "viettel" -> S.s_tren_viettelai_vn_dang_nhap_mo_tai_khoan_t_0f2b04ac
        else -> ""
    }

    // ---- Nhạc của tôi -------------------------------------------------------------------------------------------------------------

    /** Dòng phụ của một bài: nghệ sĩ · độ dài. */
    fun trackLine(track: MusicTrack): String {
        val whole = track.duration.toLong().coerceAtLeast(0)
        val clock = if (track.duration > 0) String.format(Locale.ROOT, "%d:%02d", whole / 60, whole % 60) else ""
        return listOf(track.creator, clock).dotJoined()
    }

    fun musicSummary(count: Int): String = if (count == 0) S.s_chua_co_bai_nao_c1c708be else S.s_0_bai_1e392237(count)

    /** Câu báo sau khi nhập (studio/musicLocal.ts `importSummary`): bao nhiêu bài vào, bao nhiêu đã có, file nào không nhập được thì ở dòng riêng. */
    fun imported(result: MusicImportResult): String {
        val parts = ArrayList<String>()
        if (result.added > 0) parts += S.s_0_bai_moi_0344fbff(result.added)
        if (result.existing > 0) parts += S.s_0_bai_da_co_tu_truoc_37a68de3(result.existing)
        return if (parts.isEmpty()) "" else S.s_da_them_0_2918e530(parts.joinToString(", "))
    }
}
