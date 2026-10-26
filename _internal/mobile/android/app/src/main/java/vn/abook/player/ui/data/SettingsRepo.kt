package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Một giọng "Nghe ngay" của máy ([vn.abook.player.readaloud.ReadAloud.voices]). */
@Immutable
data class VoiceOption(val id: String, val name: String, val provider: String, val isDefault: Boolean)

/** Một nhóm giọng theo nơi đọc (Edge, khoá của bạn, VieNeu, Supertonic, giọng của máy) - cùng thứ tự `VOICE_GROUPS` của bản WebView. */
@Immutable
data class VoiceGroup(val provider: String, val title: String, val detail: String, val voices: List<VoiceOption>)

/** Danh sách giọng của màn Giọng đọc. `chosen`: mã giọng đang dùng làm mặc định (đã đối chiếu với danh sách: giọng đã gỡ thì về giọng mặc định). */
@Immutable
sealed interface VoiceList {
    @Immutable
    data object Loading : VoiceList

    @Immutable
    data object Failed : VoiceList

    @Immutable
    data class Ready(val groups: List<VoiceGroup>, val chosen: String) : VoiceList {
        val chosenVoice: VoiceOption? get() = groups.firstNotNullOfOrNull { group -> group.voices.firstOrNull { it.id == chosen } }
    }
}

/** "Tốc độ đọc" của giọng trên máy ([vn.abook.player.readaloud.VoiceSpeed]): lựa chọn của cả máy + một dòng cho mỗi giọng hai bậc đã tải. */
@Immutable
data class VoiceSpeedState(val choice: VoiceSpeedChoice, val lines: List<String>)

enum class VoiceSpeedChoice(override val key: String, override val label: String, val description: String) : Choice {
    Auto("auto", "Tự động", "Máy kịp thì đọc bản hay nhất."),
    Quality("quality", "Chất lượng cao nhất", "Luôn đọc bản hay nhất; máy chậm có thể phải chờ."),
    Fast("fast", "Nhanh hơn", "Nhanh hơn, tiếng kém hơn chút - hợp máy yếu.");

    /** Câu dưới hàng chọn (cùng `voiceSpeedDescription` của bản WebView). */
    val sentence: String get() = "$description Chỉ áp cho giọng Supertonic; sách xuất ra luôn dùng bản hay nhất."
}

/** Một mục của danh sách thành phần bên thứ ba (docs/THIRD_PARTY.md); `bullet`: gạch đầu dòng hay đoạn văn. */
@Immutable
data class ThirdPartyItem(val text: String, val bullet: Boolean)

@Immutable
data class ThirdPartySection(val title: String, val items: List<ThirdPartyItem>)

/**
 * Phần lõi mà Cài đặt cần - tách ra để thử bằng lõi giả (lõi thật: [AndroidSettingsCore]). Mọi hàm chạy ở luồng nền (đọc / ghi đĩa, hỏi bộ đọc của máy).
 */
interface SettingsCore {
    /** Tuỳ chọn đã nhớ ở kho native, dạng `ListenPrefs.stored()` + `autoMusic`. */
    fun load(): JSONObject

    /** Áp và nhớ các trường đổi (dạng `PlayerPlugin.configure` nhận, kèm `settingsStamp`). */
    fun save(changes: JSONObject)

    /** Giọng của máy (có thể chờ vài giây: hỏi bộ đọc của hệ điều hành). */
    fun voices(): List<VoiceOption>

    /** Giọng mặc định đã chọn ("" = chưa chọn). */
    fun defaultVoice(): String
    fun chooseDefaultVoice(id: String)

    /** `VoiceSpeed.status()`: {choice, voices: [{name, tier, using, rtf, fastBytes}]}. */
    fun voiceSpeed(): JSONObject
    fun setVoiceSpeed(choice: String): JSONObject

    /** Bản đọc đã làm của cả máy (byte), và dọn hết (trả cỡ còn lại). */
    fun cacheBytes(): Long
    fun clearCache(): Long

    /** ABook được hiện thông báo (Android 13+ cần quyền; máy cũ luôn được). */
    fun notificationsAllowed(): Boolean

    /** Đuôi nhật ký của app (đã che khoá / mã / IP như bản gửi đi). */
    fun logLines(): List<String>
    fun clearLogs()

    /** docs/THIRD_PARTY.md (Markdown); "" khi bản dựng không gói nó. */
    fun thirdParty(): String

    /** Phiên bản đang cài ("0.4.146"). */
    val version: String
}

/**
 * Kho dữ liệu Cài đặt cho giao diện native (NATIVE_PHONE_UI.md §2): [state] bất biến, đổi NGAY khi người dùng chọn (màn không chờ đĩa), còn việc ghi
 * xuống lõi xếp hàng trên MỘT coroutine nền theo đúng thứ tự chạm. Ghi qua cùng cửa với bản WebView ([vn.abook.player.ListenPrefs.apply], cùng khoá, cùng giá trị)
 * kèm dấu giờ mới: lần mở bản WebView sau thấy bản native mới hơn thì lấy nó (`syncSettings`).
 */
class SettingsRepo(private val core: SettingsCore, private val scope: CoroutineScope, private val io: CoroutineDispatcher) {
    private val flow = MutableStateFlow(AppSettings.Default)
    val state: StateFlow<AppSettings> get() = flow

    private val loadedFlow = MutableStateFlow(false)

    /** Đã đọc kho (giao diện sáng / tối đúng từ khung đầu: màn chờ giữ tới lúc này). */
    val loaded: StateFlow<Boolean> get() = loadedFlow

    private val voiceFlow = MutableStateFlow<VoiceList>(VoiceList.Loading)
    val voices: StateFlow<VoiceList> get() = voiceFlow

    private val speedFlow = MutableStateFlow<VoiceSpeedState?>(null)
    val speed: StateFlow<VoiceSpeedState?> get() = speedFlow

    private val cacheFlow = MutableStateFlow<Long?>(null)

    /** Cỡ bản đọc đã làm; null = chưa đo. */
    val cache: StateFlow<Long?> get() = cacheFlow

    private val notifyFlow = MutableStateFlow(true)
    val notificationsAllowed: StateFlow<Boolean> get() = notifyFlow

    private val writes = Channel<() -> Unit>(Channel.UNLIMITED)

    init {
        scope.launch(io) {
            for (write in writes) runCatching(write)
        }
    }

    val version: String get() = core.version

    /** Đọc kho một lần (luồng nền). Đọc lỗi = mặc định, vẫn báo đã nạp: không giữ màn chờ. */
    suspend fun load() {
        val stored = withContext(io) { runCatching { AppSettings.from(core.load()) }.getOrDefault(AppSettings.Default) }
        if (!loadedFlow.value) flow.value = stored
        loadedFlow.value = true
    }

    /** Đổi tuỳ chọn: màn thấy ngay; ghi xuống lõi sau, theo thứ tự. Không đổi gì thì thôi. */
    fun change(update: (AppSettings) -> AppSettings) {
        val before = flow.value
        val after = update(before)
        val changes = after.changesFrom(before)
        if (changes.length() == 0) return
        val stamp = maxOf(System.currentTimeMillis(), before.stamp + 1)
        flow.value = after.copy(stamp = stamp)
        changes.put("settingsStamp", stamp)
        writes.trySend { core.save(changes) }
    }

    fun loadVoices() {
        scope.launch {
            voiceFlow.value = withContext(io) {
                runCatching { VoiceList.Ready(Voices.group(core.voices()), "").let { it.copy(chosen = Voices.resolve(it.groups, core.defaultVoice())) } }
                    .getOrDefault(VoiceList.Failed)
            }
        }
    }

    /** Chọn giọng mặc định (cuốn chưa chọn giọng riêng đọc bằng giọng này từ lần nạp kế). */
    fun chooseVoice(id: String) {
        val now = voiceFlow.value as? VoiceList.Ready ?: return
        if (now.chosen == id) return
        voiceFlow.value = now.copy(chosen = id)
        writes.trySend { core.chooseDefaultVoice(id) }
    }

    fun loadSpeed() {
        scope.launch { speedFlow.value = withContext(io) { runCatching { VoiceSpeedText.state(core.voiceSpeed()) }.getOrNull() } }
    }

    fun chooseSpeed(choice: VoiceSpeedChoice) {
        val now = speedFlow.value ?: return
        if (now.choice == choice) return
        speedFlow.value = now.copy(choice = choice)
        scope.launch { withContext(io) { runCatching { VoiceSpeedText.state(core.setVoiceSpeed(choice.key)) }.getOrNull() }?.let { speedFlow.value = it } }
    }

    fun loadCache() {
        scope.launch { cacheFlow.value = withContext(io) { runCatching { core.cacheBytes() }.getOrNull() } }
    }

    fun clearCache() {
        scope.launch { cacheFlow.value = withContext(io) { runCatching { core.clearCache() }.getOrNull() } }
    }

    /** Hỏi lại quyền thông báo (mở màn, quay lại từ Cài đặt Android). */
    fun checkNotifications() {
        scope.launch { notifyFlow.value = withContext(io) { runCatching { core.notificationsAllowed() }.getOrDefault(true) } }
    }

    suspend fun logLines(): List<String> = withContext(io) { runCatching { core.logLines() }.getOrDefault(emptyList()) }

    fun clearLogs() {
        writes.trySend { core.clearLogs() }
    }

    suspend fun thirdParty(): List<ThirdPartySection> = withContext(io) { ThirdParty.parse(runCatching { core.thirdParty() }.getOrDefault("")) }
}

/** Nhóm giọng như bản WebView (listen/voiceGroups.ts, readAloudVoice.ts `resolveVoice`). Hàm thuần. */
object Voices {
    private val KEYED = listOf("azure" to "Azure Speech", "google" to "Google Cloud", "fpt" to "FPT.AI", "viettel" to "Viettel AI")
    private val GROUPS: List<Triple<String, String, String>> =
        listOf(Triple("edge", "Edge", "trực tuyến, miễn phí")) +
            KEYED.map { (provider, name) -> Triple(provider, name, "dùng khoá của bạn") } +
            listOf(
                Triple("vieneu", "VieNeu", "trên máy này, không cần mạng"),
                Triple("supertonic", "Supertonic", "trên máy này, không cần mạng"),
                Triple("device", "Giọng của máy", "không cần mạng"),
            )
    private val SUFFIX = Regex("""^(.*\S)\s+\(([^()]+)\)$""")

    fun group(voices: List<VoiceOption>): List<VoiceGroup> {
        val known = GROUPS.map { it.first }.toSet()
        val groups = GROUPS.map { (provider, title, detail) -> VoiceGroup(provider, title, detail, voices.filter { it.provider == provider }.map { shorten(it, title) }) }
        val other = voices.filter { it.provider !in known }
        return (if (other.isEmpty()) groups else groups + VoiceGroup("other", "Khác", "", other)).filter { it.voices.isNotEmpty() }
    }

    /** "Hoài My (Edge)" trong nhóm Edge -> "Hoài My": tên nhóm đã nói nơi đọc. Đuôi khác (tên mô-đun, vùng) giữ nguyên. */
    private fun shorten(voice: VoiceOption, title: String): VoiceOption {
        val match = SUFFIX.matchEntire(voice.name) ?: return voice
        return if (match.groupValues[2].equals(title, ignoreCase = true)) voice.copy(name = match.groupValues[1]) else voice
    }

    /** Giọng đang dùng: giọng đã chọn nếu máy còn nó, không thì giọng mặc định của lõi, không nữa thì giọng đầu. */
    fun resolve(groups: List<VoiceGroup>, chosen: String): String {
        val all = groups.flatMap { it.voices }
        return (all.firstOrNull { it.id == chosen } ?: all.firstOrNull { it.isDefault } ?: all.firstOrNull())?.id.orEmpty()
    }
}

/** Lời của "Tốc độ đọc" (listen/voiceSpeed.ts). Hàm thuần. */
object VoiceSpeedText {
    private fun tierLabel(tier: String) = if (tier == "fast") "Nhanh hơn" else "Chất lượng cao nhất"

    fun state(status: JSONObject): VoiceSpeedState {
        val choice = VoiceSpeedChoice.entries.firstOrNull { it.key == status.optString("choice") } ?: VoiceSpeedChoice.Auto
        val voices = status.optJSONArray("voices")
        val lines = (0 until (voices?.length() ?: 0)).mapNotNull { voices?.optJSONObject(it) }.map { line(it, choice) }
        return VoiceSpeedState(choice, lines)
    }

    /** Dòng của một giọng: đang dùng bậc nào và vì sao; muốn bản nhanh hơn mà chưa tải thì nói cỡ cần tải. */
    fun line(voice: JSONObject, choice: VoiceSpeedChoice): String {
        val name = voice.optString("name")
        val tier = voice.optString("tier")
        val using = voice.optString("using")
        if (tier == "fast" && using != "fast") {
            return "$name - Đang dùng: ${tierLabel("quality")}. Bản nhanh hơn cần tải thêm ${Fmt.size(voice.optLong("fastBytes"))}."
        }
        val why = when {
            choice != VoiceSpeedChoice.Auto -> "bạn đã chọn"
            voice.isNull("rtf") -> "chưa đo được tốc độ máy này"
            tier == "fast" -> "máy này đọc chậm hơn tốc độ nghe"
            else -> "máy này đọc kịp tốc độ nghe"
        }
        return "$name - Đang dùng: ${tierLabel(using)} ($why)."
    }
}

/** docs/THIRD_PARTY.md -> các mục (shared/thirdParty.ts `parseThirdParty`): mục theo `##`, mục cho người bảo trì bỏ đi. Hàm thuần. */
object ThirdParty {
    const val MAINTAINER_SECTION = "Ghi chú cho người bảo trì"

    fun parse(markdown: String): List<ThirdPartySection> {
        val titles = arrayListOf("")
        val sections = arrayListOf(ArrayList<ThirdPartyItem>())
        var open: StringBuilder? = null
        var openBullet = false
        fun close() {
            open?.let { sections.last() += ThirdPartyItem(it.toString(), openBullet) }
            open = null
        }
        for (raw in markdown.replace("\r", "").split("\n")) {
            val line = raw.trim()
            when {
                line.isEmpty() -> close()
                line.startsWith("# ") -> Unit
                line.startsWith("## ") -> {
                    close()
                    titles += line.removePrefix("## ").trim()
                    sections += ArrayList<ThirdPartyItem>()
                }
                else -> {
                    val bullet = line.startsWith("- ") || line.startsWith("* ")
                    val current = open
                    if (bullet || current == null) {
                        close()
                        open = StringBuilder(if (bullet) line.substring(2) else line)
                        openBullet = bullet
                    } else {
                        current.append(' ').append(line)
                    }
                }
            }
        }
        close()
        return titles.indices.map { ThirdPartySection(titles[it], sections[it]) }
            .filter { it.items.isNotEmpty() && it.title != MAINTAINER_SECTION }
    }

    /** Chữ đậm `**...**` và mã `` `...` `` của Markdown trên màn chỉ là chữ thường: bỏ dấu. */
    fun plain(text: String): String = text.replace(Regex("""\*\*([^*]+)\*\*"""), "$1").replace(Regex("""`([^`]+)`"""), "$1")
}
