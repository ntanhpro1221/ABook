package vn.abook.player.ui.voice

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import java.util.Locale

/*
 * Mô hình và lời của các việc Giọng đọc làm thêm: giọng tải về máy (VieNeu, Supertonic), khoá giọng trực tuyến, nghe thử, đồng ý gửi chữ, Nhạc của tôi. Cùng hình JSON
 * với lõi (VoiceModule.status, OnlineKeys.public, MusicStore.entries) và cùng lời với bản WebView (listen/vieneuModule.ts, onlineConsent.ts, studio/musicLocal.ts).
 * Hàm thuần, không Android: thử trên JVM.
 */

/** Màn con của nhóm Giọng đọc (cấp hai, cũng là cấp cuối: Cài đặt -> Giọng đọc -> màn này). Bảng trượt là lớp nổi, không phải cấp ba. */
enum class VoicePage { Keys, Music }

/** Hai mô-đun giọng chạy trên máy, tải khi bạn bấm. `invite`: lời mời dưới tên khi chưa tải - cùng lời thẻ giọng bên web (vieneuModule.ts `invite`). */
enum class ModuleKind(val key: String, val title: String, val invite: String) {
    Vieneu("vieneu", "Giọng VieNeu", "Giọng hay, đọc ngay trên máy, không cần mạng. Chữ của sách không rời máy."),
    Supertonic("supertonic", "Giọng Supertonic", "Mười giọng nam nữ, nhẹ máy, không cần mạng. Chữ của sách không rời máy."),
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
)

/** Kết quả "Kiểm tra" một khoá: câu nói được cho người nghe. */
@Immutable
data class KeyResult(val ok: Boolean, val text: String, val provider: KeyProvider? = null)

object KeyJson {
    fun provider(json: JSONObject): KeyProvider {
        val limits = json.optJSONObject("limits")
        return KeyProvider(
            json.optString("id"), json.optString("name"), limits?.optString("free").orEmpty(), limits?.optBoolean("region") == true,
            json.optBoolean("hasKey"), json.optString("masked"), json.optString("region"), json.optBoolean("valid"), json.optInt("voices"),
        )
    }

    /** `checkOnlineKey`: {ok, reason?, message?, voices?, provider}. */
    fun check(json: JSONObject): KeyResult {
        val provider = json.optJSONObject("provider")?.let(::provider)
        return if (json.optBoolean("ok")) {
            KeyResult(true, "Dùng được · ${if (json.has("voices")) json.optInt("voices") else provider?.voices ?: 0} giọng tiếng Việt", provider)
        } else {
            KeyResult(false, json.optString("message").ifBlank { "Khoá chưa dùng được." }, provider)
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
    /** Cỡ file cho người nghe, MỘT hệ thập phân (studio/musicLocal.ts `formatSize`): "850 MB", "1,2 GB"; dưới 10 MB một chữ số thập phân. */
    fun size(bytes: Long): String {
        if (bytes >= 1_000_000_000) return String.format(Locale.ROOT, "%.2f", bytes / 1e9).replace('.', ',') + " GB"
        val megabytes = bytes / 1e6
        if (megabytes < 1) return "${maxOf(1L, Math.round(bytes / 1e3))} KB"
        return if (megabytes < 10) String.format(Locale.ROOT, "%.1f", megabytes).replace('.', ',') + " MB" else "${Math.round(megabytes)} MB"
    }

    private fun seconds(value: Double): String = String.format(Locale.ROOT, "%.1f", value).replace('.', ',')

    /** Tên một tầng giọng (vieneuModule.ts `tierName`). */
    fun tierName(tier: String): String = when (tier) {
        "turbo" -> "Giọng VieNeu"
        "nano" -> "Giọng VieNeu Nano"
        else -> "Giọng Supertonic"
    }

    /** Tên một lựa chọn trên hàng: cùng tên lõi đặt, trừ bản nhanh hơn của Supertonic (đứng riêng trong danh sách phẳng nên phải nói của giọng nào). */
    fun choiceTitle(choice: ModuleChoice): String = if (choice.id == "supertonic_fast") "Supertonic nhanh hơn" else choice.label

    /** Đầu mã giọng của một tầng ("vieneu:nano/", "supertonic:") - để đổi mọi cuốn đang dùng tầng ấy sang giọng khác. */
    fun tierVoicePrefix(tier: String): String = if (tier == "supertonic") "supertonic:" else "vieneu:$tier/"

    /** Câu nhắc trước khi tải bằng dữ liệu di động (null khi không cần nhắc). */
    fun metered(status: ModuleStatus, bytes: Long): String? =
        if (status.metered && bytes > 0) "Điện thoại đang dùng dữ liệu di động - tải ${size(bytes)} có thể tốn tiền mạng. Nên chờ có Wi-Fi." else null

    /** Câu nói kết quả tự đo, theo điều người nghe cần biết (vieneuModule.ts `benchmarkLabel`). */
    fun benchmark(tier: String, result: ModuleBench, slow: Double): String {
        val name = tierName(tier)
        if (result.rtf >= slow) {
            val hour = maxOf(1, Math.round(result.rtf * 60).toInt())
            return "$name: máy này không kịp đọc trực tiếp (${seconds(result.rtf)} giây cho mỗi giây nghe). Dùng “Làm trước”: mỗi giờ nghe cần khoảng $hour phút."
        }
        val speed = if (result.rtf > 0) 1 / result.rtf else 0.0
        return "$name: đọc trực tiếp được - máy này đọc nhanh gấp ${seconds(speed)} lần tốc độ nghe; đoạn đầu chương có tiếng sau khoảng ${seconds(result.firstAudioMs / 1000.0)} giây."
    }

    /** Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút (vieneuModule.ts `suggestionText`). */
    fun suggestion(suggestion: ModuleSuggestion): Pair<String, String> {
        val lead = "${tierName(suggestion.tier)} đọc chậm trên máy này (${seconds(suggestion.rtf)} giây cho mỗi giây nghe). Giữ giọng này thì dùng “Làm trước”."
        if (suggestion.switchTo == "nano") {
            return if (suggestion.installed) "$lead Giọng VieNeu Nano nhẹ hơn, đã có sẵn." to "Dùng giọng VieNeu Nano"
            else "$lead Giọng VieNeu Nano nhẹ hơn, hợp máy này." to "Tải giọng VieNeu Nano"
        }
        return "$lead Giọng trực tuyến nhẹ máy (cần mạng)." to "Dùng giọng trực tuyến"
    }

    /** Lời hỏi trước khi gỡ một giọng khỏi máy: điện thoại không biết cuốn nào dùng nó, nên một câu ngắn (vieneuModule.ts `removeAsk(null)`). */
    const val REMOVE_ASK = "Giọng sẽ không còn trên máy này cho tới khi bạn tải lại."

    /** Dòng phụ của hàng khi mô-đun không dùng được trên máy này. */
    fun unsupported(status: ModuleStatus): String =
        if (status.reason.isNotEmpty()) "Máy này chưa dùng được: ${status.reason}." else "Máy này chưa dùng được."

    const val CANCELLED = "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng."
    /** Nhãn của lựa chọn nên tải - cùng chữ với nhãn "Khuyên dùng" của thẻ giọng bên web (VieneuModuleCard.tsx). */
    private const val RECOMMENDED = "Khuyên dùng"

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
                ModuleRow(choice.id, title, "Đang tải ${size(status.total)} · ${status.percent}%", false, ModuleAction.Cancel, true)
            status.state == ModuleState.Downloading -> ModuleRow(choice.id, title, lead + choice.detail, false, ModuleAction.None, false)
            status.state == ModuleState.Error && mine -> ModuleRow(choice.id, title, status.error, true, ModuleAction.Retry, false)
            else -> {
                val cancelled = if (status.cancelled && mine) "$CANCELLED " else ""
                ModuleRow(choice.id, title, cancelled + lead + choice.detail, false, ModuleAction.Download(if (choice.bytes > 0) "Tải (${size(choice.bytes)})" else "Dùng"), false)
            }
        }
    }

    private fun installed(status: ModuleStatus, choice: ModuleChoice, title: String): ModuleRow {
        val tier = status.benchmark[choice.id]
        val hint = when {
            status.benchmarking -> "Đang thử giọng vừa tải, vài giây"
            status.state == ModuleState.Outdated -> "Có bản mới · ${size(status.outdatedBytes)}"
            tier != null && tier.rtf >= status.slowRtf -> "Chậm hơn tốc độ nghe · dùng “Làm trước”"
            tier != null && tier.rtf > 0 -> "Đọc trực tiếp được · nhanh gấp ${seconds(1 / tier.rtf)} lần"
            else -> "Đã có trên máy"
        }
        return ModuleRow(choice.id, title, hint, false, ModuleAction.Manage, false)
    }

    /** Hàng chưa có mà còn phần tải dở (đã huỷ giữa chừng): chạm mở bảng có "Xoá phần đã tải". */
    fun hasLeftovers(choice: ModuleChoice): Boolean = !choice.installed && choice.removable

    // ---- đồng ý gửi chữ -----------------------------------------------------------------------------------------------------------

    /** Tên nhà cung cấp giọng dùng khoá của bạn (readAloudVoice.ts `KEYED_PROVIDERS`). */
    val KEYED = linkedMapOf("azure" to "Azure Speech", "google" to "Google Cloud", "fpt" to "FPT.AI", "viettel" to "Viettel AI")

    private val COMPANIES = mapOf("edge" to "Microsoft")

    /** Giọng của nơi này gửi chữ ra ngoài máy (Edge, hay nhà cung cấp dùng khoá của bạn): phải được bạn đồng ý trước lần đầu. */
    fun isOnline(provider: String): Boolean = provider in COMPANIES || provider in KEYED

    /** Tên giọng như người nghe gọi: "Hoài My (Edge)" -> "Hoài My". */
    fun spokenName(name: String): String = name.replace(Regex("""\s*\([^)]*\)\s*$"""), "").trim().ifEmpty { name }

    /** Chữ đi tới đâu khi đọc bằng giọng trực tuyến của nhà cung cấp này (onlineConsent.ts `onlineDestination`). */
    fun destination(provider: String): String = KEYED[provider] ?: COMPANIES[provider]?.let { "máy chủ $it" } ?: "dịch vụ ngoài"

    /** Lời hỏi trước lần đầu đọc bằng giọng trực tuyến (onlineConsent.ts `onlinePromptText`). */
    fun consent(voiceName: String, provider: String): String {
        val name = spokenName(voiceName)
        val where = destination(provider)
        if (provider in KEYED) return "Giọng $name dùng khoá $where của bạn: chữ của đoạn đang đọc được gửi tới $where để đọc, và dịch vụ có thể tính tiền vào tài khoản của bạn."
        return if (provider in COMPANIES) {
            "Giọng $name là giọng ${if (provider == "edge") "Edge" else "trực tuyến"}: chữ của đoạn đang đọc được gửi tới $where để đọc."
        } else {
            "Giọng $name là giọng trực tuyến: chữ của đoạn đang đọc được gửi tới $where để đọc."
        }
    }

    /** Câu đọc thử (readAloudVoice.ts `SAMPLE_TEXT`): ngắn, có dấu câu để nghe cả chỗ ngắt. */
    const val SAMPLE = "Xin chào, tôi sẽ đọc sách cho bạn nghe. Bạn thấy giọng này thế nào?"

    // ---- khoá ---------------------------------------------------------------------------------------------------------------------

    /** Dòng phụ của một nhà cung cấp: chưa có khoá thì hạn mức miễn phí; có rồi thì khoá che + kết quả lần kiểm tra. */
    fun keyHint(provider: KeyProvider): String = keyStatus(provider)?.let { "${provider.masked} · $it" } ?: provider.free

    /** Kết quả lần kiểm tra khoá - cùng chữ với nhãn trạng thái của thẻ khoá bên web (VoiceSettings.tsx KeyCard); chưa có khoá thì null. */
    fun keyStatus(provider: KeyProvider): String? = when {
        !provider.hasKey -> null
        provider.valid -> "Dùng được · ${provider.voices} giọng"
        else -> "Chưa dùng được"
    }

    /** Dòng tóm tắt của hàng "Khoá giọng trực tuyến": tên các nhà cung cấp đã có khoá, hay "Chưa có khoá". */
    fun keySummary(providers: List<KeyProvider>): String =
        providers.filter { it.hasKey }.joinToString(" · ") { it.name }.ifEmpty { "Chưa có khoá" }

    /** Lấy khoá ở đâu - nói theo những gì bạn thấy trên trang của nhà cung cấp (VoiceSettings.tsx `KEY_HELP`). */
    fun keyHelp(provider: String): String = when (provider) {
        "azure" -> "Azure: tạo Speech (F0 miễn phí) › Keys and Endpoint. Chép Key 1 và Location/Region (ví dụ southeastasia)."
        "google" -> "Google Cloud: bật Cloud Text-to-Speech API. Vào APIs & Services › Credentials › Create credentials › API key."
        "fpt" -> "Trên console.fpt.ai: đăng nhập, mở mục “Text to Speech” (Chuyển văn bản thành giọng nói), chép “API key” (khoá API)."
        "viettel" -> "Trên viettelai.vn: đăng nhập, mở Tài khoản › Token, chép token."
        else -> ""
    }

    // ---- Nhạc của tôi -------------------------------------------------------------------------------------------------------------

    /** Dòng phụ của một bài: nghệ sĩ · độ dài. */
    fun trackLine(track: MusicTrack): String {
        val whole = track.duration.toLong().coerceAtLeast(0)
        val clock = if (track.duration > 0) String.format(Locale.ROOT, "%d:%02d", whole / 60, whole % 60) else ""
        return listOf(track.creator, clock).filter { it.isNotEmpty() }.joinToString(" · ")
    }

    fun musicSummary(count: Int): String = if (count == 0) "Chưa có bài nào" else "$count bài"

    /** Câu báo sau khi nhập (studio/musicLocal.ts `importSummary`): bao nhiêu bài vào, bao nhiêu đã có, file nào không nhập được thì ở dòng riêng. */
    fun imported(result: MusicImportResult): String {
        val parts = ArrayList<String>()
        if (result.added > 0) parts += "${result.added} bài mới"
        if (result.existing > 0) parts += "${result.existing} bài đã có từ trước"
        return if (parts.isEmpty()) "" else "Đã thêm: ${parts.joinToString(", ")}"
    }
}
