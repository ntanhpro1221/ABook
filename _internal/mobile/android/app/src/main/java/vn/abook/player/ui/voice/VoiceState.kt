package vn.abook.player.ui.voice

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Một mô-đun giọng trên máy đang vẽ gì: trạng thái lõi (null = chưa hỏi xong), các lựa chọn bạn vừa bấm tải, và lỗi của lần bấm (không phải lỗi tải của lõi). */
@Immutable
data class ModuleUi(val status: ModuleStatus? = null, val pending: List<String> = emptyList(), val problem: String = "") {
    /** Trạng thái để vẽ: lần bấm tải vừa thất bại thì hiện như lỗi tải. */
    val shown: ModuleStatus?
        get() = status?.let { if (problem.isNotEmpty()) it.copy(state = ModuleState.Error, error = problem) else it }
}

@Immutable
data class KeysUi(val loaded: Boolean = false, val failed: Boolean = false, val providers: List<KeyProvider> = emptyList())

@Immutable
data class SampleFailure(val voice: String, val message: String)

/** Nghe thử: giọng đang phát, giọng đang lấy mẫu (chưa có tiếng), lỗi của giọng vừa bấm. */
@Immutable
data class SampleUi(val playing: String = "", val loading: String = "", val failed: SampleFailure? = null)

@Immutable
data class MusicUi(
    val loaded: Boolean = false,
    val failed: Boolean = false,
    val tracks: List<MusicTrack> = emptyList(),
    val importing: Boolean = false,
    val done: Int = 0,
    val total: Int = 0,
    /** Câu báo của lượt nhập vừa xong ("Đã thêm: 3 bài mới"), rỗng khi không có. */
    val summary: String = "",
    /** File không nhập được kèm lý do (một dòng mỗi file). */
    val problems: List<String> = emptyList(),
)

/** Dòng giá trị của các hàng dẫn tới màn con; null khi chưa đọc xong. */
@Immutable
data class VoiceSummary(val keys: String? = null, val music: String? = null)

/**
 * Trạng thái sống của Giọng đọc làm thêm. Màn chỉ vẽ các luồng ở đây và gọi hàm ở đây; mọi việc với lõi đi qua [VoiceSource]. Tiến độ tải là một luồng riêng
 * ([progress]) để thanh tiến độ đọc nó trong pha vẽ, không dựng lại hàng mỗi nhịp. `voicesChanged`: danh sách giọng cần đọc lại (giọng vừa tải / gỡ, khóa vừa dùng được).
 */
@Stable
class VoiceState(
    private val source: VoiceSource,
    private val scope: CoroutineScope,
    private val player: SamplePlayer,
    private val voicesChanged: () -> Unit = {},
    private val pollMs: Long = 700,
) {
    private val moduleFlow = MutableStateFlow(ModuleKind.entries.associateWith { ModuleUi() })
    private val progresses = ModuleKind.entries.associateWith { MutableStateFlow(0f) }
    private val keyFlow = MutableStateFlow(KeysUi())
    private val consentFlow = MutableStateFlow<Set<String>>(emptySet())
    private val sampleFlow = MutableStateFlow(SampleUi())
    private val musicFlow = MutableStateFlow(MusicUi())
    private val importFlow = MutableStateFlow(0f)
    private val watchers = HashMap<ModuleKind, Job>()
    private var turn = 0

    val modules: StateFlow<Map<ModuleKind, ModuleUi>> = moduleFlow
    val keys: StateFlow<KeysUi> = keyFlow
    val consents: StateFlow<Set<String>> = consentFlow
    val sample: StateFlow<SampleUi> = sampleFlow
    val music: StateFlow<MusicUi> = musicFlow

    /** Tiến độ 0..1 của việc tải một mô-đun; đọc trong pha vẽ. */
    fun progress(kind: ModuleKind): StateFlow<Float> = progresses.getValue(kind)

    /** Tiến độ 0..1 của lượt nhập nhạc; đọc trong pha vẽ. */
    val importProgress: StateFlow<Float> = importFlow

    val summary: StateFlow<VoiceSummary> = combine(keyFlow, musicFlow) { keys, music ->
        VoiceSummary(
            keys = if (keys.loaded) VoiceText.keySummary(keys.providers) else null,
            music = if (music.loaded) VoiceText.musicSummary(music.tracks.size) else null,
        )
    }.stateIn(scope, SharingStarted.Eagerly, VoiceSummary())

    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Result.failure(error)
    }

    private fun message(error: Throwable?, fallback: String) = error?.message?.takeIf { it.isNotBlank() } ?: fallback

    // ---- mở màn ----------------------------------------------------------------------------------------------------------------

    /** Mở màn Giọng đọc: đọc trạng thái hai mô-đun, các khóa, và những nhà cung cấp bạn đã đồng ý gửi chữ tới (nền, không chặn). */
    fun openVoice() {
        for (kind in ModuleKind.entries) scope.launch { refresh(kind) }
        loadKeys()
        loadConsents()
    }

    /** Những nhà cung cấp bạn đã đồng ý gửi chữ tới (màn Khóa cần biết trước khi hỏi lại đồng ý). */
    fun loadConsents() {
        scope.launch { attempt { source.consents() }.onSuccess { consentFlow.value = it } }
    }

    // ---- giọng tải về máy -------------------------------------------------------------------------------------------------

    private suspend fun refresh(kind: ModuleKind) {
        attempt { source.module(kind) }.onSuccess { apply(kind, it) }
    }

    private fun setModule(kind: ModuleKind, update: (ModuleUi) -> ModuleUi) = moduleFlow.update { it + (kind to update(it.getValue(kind))) }

    /**
     * Nhận trạng thái mới của lõi. Phần trăm không bao giờ lùi trong một lượt tải (một lần nối lại mà máy tải lại từ đầu file làm số nhảy lùi). Việc tải / đo vừa xong thì
     * danh sách giọng đọc lại (giọng mới hiện ngay) và mô-đun kia hỏi lại cỡ cần tải (hai mô-đun chung thư viện chạy model).
     */
    private fun apply(kind: ModuleKind, incoming: ModuleStatus) {
        val before = moduleFlow.value.getValue(kind).status
        val status = if (incoming.state == ModuleState.Downloading) incoming.copy(percent = maxOf(incoming.percent, before?.percent ?: 0)) else incoming
        progresses.getValue(kind).value = if (status.state == ModuleState.Downloading) status.percent / 100f else 0f
        setModule(kind) { it.copy(status = status, pending = if (status.state == ModuleState.Downloading || status.state == ModuleState.Error) it.pending else emptyList(), problem = "") }
        if (status.working) watch(kind)
        if (before?.working == true && !status.working) {
            voicesChanged()
            for (other in ModuleKind.entries.filter { it != kind }) scope.launch { refresh(other) }
        }
    }

    /** Hỏi lại mỗi nhịp khi mô-đun đang tải hay đang đo; xong thì thôi. Lỗi hỏi (hiếm) cũng thôi - lần mở màn sau hỏi lại. */
    private fun watch(kind: ModuleKind) {
        if (watchers[kind]?.isActive == true) return
        watchers[kind] = scope.launch {
            while (true) {
                delay(pollMs)
                val next = attempt { source.module(kind) }.getOrNull() ?: break
                apply(kind, next)
                if (!next.working) break
            }
        }
    }

    /** Tải các lựa chọn `ids` (null: cập nhật phần đã cũ). Thanh tiến độ và nút "Huỷ" nằm ở hàng bạn bấm. */
    fun download(kind: ModuleKind, ids: List<String>?) {
        setModule(kind) { it.copy(pending = ids.orEmpty(), problem = "") }
        scope.launch {
            val result = attempt { source.start(kind, ids) }
            result.onSuccess { apply(kind, it) }
            result.onFailure { error -> setModule(kind) { it.copy(problem = message(error, "Chưa tải được ${kind.title}")) } }
        }
    }

    /** "Thử lại" sau lỗi: tải lại đúng những gì bạn bấm. */
    fun retry(kind: ModuleKind) = download(kind, moduleFlow.value.getValue(kind).pending.ifEmpty { null })

    fun cancel(kind: ModuleKind) {
        scope.launch { attempt { source.cancel(kind) }.onSuccess { apply(kind, it) } }
    }

    fun measure(kind: ModuleKind) {
        scope.launch { attempt { source.measure(kind) }.onSuccess { apply(kind, it) } }
    }

    /** Gỡ một lựa chọn khỏi máy. Null = xong, khác null = câu lỗi. */
    suspend fun remove(kind: ModuleKind, choice: String): String? {
        val result = attempt { source.remove(kind, choice) }
        result.onSuccess { status ->
            apply(kind, status)
            voicesChanged()
            for (other in ModuleKind.entries.filter { it != kind }) refresh(other)
        }
        return result.exceptionOrNull()?.let { message(it, "Chưa gỡ được ${kind.title}") }
    }

    /**
     * Bấm nút của lời đề nghị: giọng Nano chưa có thì tải nó; còn lại đổi mọi cuốn đang dùng giọng chậm (và lựa chọn chung) sang giọng Nano đã có hay giọng trực tuyến mặc định.
     * Null = xong, khác null = câu lỗi.
     */
    suspend fun applySuggestion(kind: ModuleKind): String? {
        val suggestion = moduleFlow.value.getValue(kind).status?.suggestion ?: return null
        if (suggestion.switchTo == "nano" && !suggestion.installed) {
            download(ModuleKind.Vieneu, listOf("nano"))
            return null
        }
        val toPrefix = if (suggestion.switchTo == "nano") "vieneu:nano/" else ONLINE_VOICE
        val result = attempt { source.switchVoices(VoiceText.tierVoicePrefix(suggestion.tier), toPrefix, ONLINE_VOICE) }
        result.onSuccess { voicesChanged() }
        return result.exceptionOrNull()?.let { message(it, "Chưa đổi được giọng") }
    }

    // ---- đồng ý gửi chữ ---------------------------------------------------------------------------------------------------

    fun allowed(provider: String): Boolean = provider in consentFlow.value

    /** Bạn đồng ý gửi chữ cho nhà cung cấp này: lõi nhớ (đọc nối ở chương chữ đang chờ), màn thôi hỏi. */
    suspend fun allow(provider: String) {
        attempt { source.allow(provider) }.onSuccess { consentFlow.update { it + provider } }
    }

    // ---- khóa giọng trực tuyến --------------------------------------------------------------------------------------------

    fun loadKeys() {
        scope.launch {
            val result = attempt { source.providers() }
            result.onSuccess { list -> keyFlow.value = KeysUi(loaded = true, providers = list) }
            result.onFailure { keyFlow.update { it.copy(failed = true) } }
        }
    }

    private fun replace(provider: KeyProvider) = keyFlow.update { ui -> ui.copy(providers = ui.providers.map { if (it.id == provider.id) provider else it }) }

    /** "Lưu": chỉ cất khóa trên máy này, không gửi gì ra mạng. Null = xong, khác null = câu lỗi. */
    suspend fun saveKey(provider: KeyProvider, key: String, region: String): String? {
        if (key.isBlank() && !provider.hasKey) return "Dán khóa trước đã."
        val result = attempt { source.saveKey(provider.id, key.trim(), region.trim()) }
        result.onSuccess { replace(it) }
        return result.exceptionOrNull()?.let { message(it, "Chưa lưu được khóa") }
    }

    /**
     * "Kiểm tra": khóa vừa gõ (hay vùng vừa đổi) được lưu trước rồi mới gọi dịch vụ - như bản WebView. Dùng được thì danh sách giọng đọc lại để giọng của khóa hiện ngay;
     * `ok` false kèm câu nói được.
     */
    suspend fun checkKey(provider: KeyProvider, key: String, region: String): KeyResult {
        val changed = key.isNotBlank() || (provider.region && region.trim() != provider.regionValue)
        if (changed) saveKey(provider, key, region)?.let { return KeyResult(false, it) }
        val result = attempt { source.checkKey(provider.id) }
        result.onSuccess { checked ->
            checked.provider?.let(::replace)
            voicesChanged()
        }
        return result.getOrNull() ?: KeyResult(false, message(result.exceptionOrNull(), "Chưa kiểm tra được khóa"))
    }

    /** Xoá khóa khỏi máy này. Null = xong, khác null = câu lỗi. */
    suspend fun removeKey(provider: KeyProvider): String? {
        val result = attempt { source.removeKey(provider.id) }
        result.onSuccess {
            replace(it)
            voicesChanged()
        }
        return result.exceptionOrNull()?.let { message(it, "Chưa xoá được khóa") }
    }

    // ---- nghe thử ---------------------------------------------------------------------------------------------------------

    /**
     * Nghe thử một giọng: lấy mẫu rồi phát. Mỗi lần bấm là một lượt mới - mẫu của lượt cũ về muộn bị bỏ, không phát chồng lên giọng bấm sau, không tự phát sau khi bạn đã
     * bấm dừng. Giọng đang lấy mẫu hay đang phát mà bấm lại thì dừng.
     */
    fun play(voice: String) {
        val now = sampleFlow.value
        if (now.playing == voice || now.loading == voice) return stopSample()
        stopSample()
        val mine = turn
        sampleFlow.value = SampleUi(loading = voice)
        scope.launch {
            val result = attempt { source.sample(voice, VoiceText.SAMPLE) }
            if (turn != mine) return@launch
            val path = result.getOrNull()
            if (path == null) {
                sampleFlow.value = SampleUi(failed = SampleFailure(voice, message(result.exceptionOrNull(), "Chưa nghe thử được giọng này.")))
                return@launch
            }
            sampleFlow.value = SampleUi(playing = voice)
            player.play(
                path,
                onEnded = { if (turn == mine) sampleFlow.value = SampleUi() },
                onFailed = { if (turn == mine) sampleFlow.value = SampleUi(failed = SampleFailure(voice, "Chưa nghe thử được giọng này.")) },
            )
        }
    }

    fun stopSample() {
        turn++
        player.stop()
        sampleFlow.value = SampleUi()
    }

    // ---- Nhạc của tôi -----------------------------------------------------------------------------------------------------

    fun loadMusic() {
        scope.launch {
            val result = attempt { source.tracks() }
            result.onSuccess { list -> musicFlow.update { it.copy(loaded = true, failed = false, tracks = list) } }
            result.onFailure { musicFlow.update { it.copy(failed = true) } }
        }
    }

    /** Nhập các file bạn vừa chọn. Tiến độ (xong / tổng) hiện ngay trong hàng "Thêm nhạc của bạn"; xong thì một câu báo và file lỗi ở dòng riêng. */
    fun importMusic(uris: List<String>) {
        if (uris.isEmpty() || musicFlow.value.importing) return
        importFlow.value = 0f
        musicFlow.update { it.copy(importing = true, done = 0, total = uris.size, summary = "", problems = emptyList()) }
        scope.launch {
            val result = attempt {
                source.importMusic(uris) { done, total ->
                    importFlow.value = done.toFloat() / total
                    musicFlow.update { it.copy(done = done, total = total) }
                }
            }
            result.onSuccess { done ->
                musicFlow.update { it.copy(importing = false, loaded = true, tracks = done.tracks, summary = VoiceText.imported(done), problems = done.failed) }
            }
            result.onFailure { error ->
                musicFlow.update { it.copy(importing = false, problems = listOf(message(error, "Chưa thêm được nhạc"))) }
            }
        }
    }

    /** Xoá một bài khỏi kho. Null = xong, khác null = câu lỗi. */
    suspend fun removeTrack(link: String): String? {
        val result = attempt { source.removeTrack(link) }
        result.onSuccess { list -> musicFlow.update { it.copy(tracks = list) } }
        return result.exceptionOrNull()?.let { message(it, "Chưa xoá được bài này") }
    }

    companion object {
        /** Giọng trực tuyến mặc định của app (lõi: ReadAloud.DEFAULT_VOICE). */
        const val ONLINE_VOICE = "edge:vi-VN-HoaiMyNeural"
    }
}
