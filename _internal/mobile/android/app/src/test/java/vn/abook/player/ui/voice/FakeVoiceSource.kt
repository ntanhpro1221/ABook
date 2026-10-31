package vn.abook.player.ui.voice

import kotlinx.coroutines.CompletableDeferred

/**
 * Nguồn Giọng đọc giả: mô-đun, khoá, đồng ý và kho nhạc trong bộ nhớ; ghi lại mọi việc màn đã bảo lõi làm để test so lời gọi. Khoá chỉ ở dạng che (như lõi thật), và nguồn
 * này nhớ khoá đã nhận để test kiểm khoá có đi xuống lõi hay không. Việc dài có thể bị giữ bằng một cổng.
 */
class FakeVoiceSource : VoiceSource {
    val modules = ModuleKind.entries.associateWith { Fixtures.missing(it) }.toMutableMap()
    val started = ArrayList<Pair<ModuleKind, List<String>?>>()
    val cancels = ArrayList<ModuleKind>()
    val measures = ArrayList<ModuleKind>()
    val removed = ArrayList<Pair<ModuleKind, String>>()
    var startError: VoiceFailure? = null
    var removeError: VoiceFailure? = null
    val switched = ArrayList<Triple<String, String, String>>()
    var switchError: VoiceFailure? = null

    var keys = VoiceText.KEYED.map { (id, name) -> Fixtures.provider(id, name) }.toMutableList()
    val savedKeys = ArrayList<Triple<String, String, String>>()
    val checked = ArrayList<String>()
    var saveError: VoiceFailure? = null
    var checkResult: ((String) -> KeyResult)? = null
    val removedKeys = ArrayList<String>()
    var keysError: VoiceFailure? = null

    var allowed = mutableSetOf<String>()
    val sampled = ArrayList<Pair<String, String>>()
    var sampleError: VoiceFailure? = null
    var sampleGate: CompletableDeferred<Unit>? = null

    var tracks = emptyList<MusicTrack>()
    var tracksError: VoiceFailure? = null
    val imported = ArrayList<List<String>>()
    var importResult: ((List<String>) -> MusicImportResult)? = null
    var importGate: CompletableDeferred<Unit>? = null
    var importError: VoiceFailure? = null
    val removedTracks = ArrayList<String>()
    var trackRemoveError: VoiceFailure? = null

    override suspend fun module(kind: ModuleKind) = modules.getValue(kind)

    override suspend fun start(kind: ModuleKind, choices: List<String>?): ModuleStatus {
        startError?.let { throw it }
        started += kind to choices
        // Như lõi thật: lệnh tải xong trả về trạng thái "đang tải" (trừ khi test đã đặt sẵn một trạng thái đang tải).
        if (modules.getValue(kind).state != ModuleState.Downloading) modules[kind] = Fixtures.downloading(kind, 0)
        return modules.getValue(kind)
    }

    override suspend fun cancel(kind: ModuleKind): ModuleStatus {
        cancels += kind
        modules[kind] = Fixtures.missing(kind).copy(cancelled = true)
        return modules.getValue(kind)
    }

    override suspend fun measure(kind: ModuleKind): ModuleStatus {
        measures += kind
        return modules.getValue(kind)
    }

    override suspend fun remove(kind: ModuleKind, choice: String): ModuleStatus {
        removeError?.let { throw it }
        removed += kind to choice
        modules[kind] = Fixtures.missing(kind)
        return modules.getValue(kind)
    }

    override suspend fun switchVoices(fromPrefix: String, toPrefix: String, fallback: String) {
        switchError?.let { throw it }
        switched += Triple(fromPrefix, toPrefix, fallback)
    }

    override suspend fun providers(): List<KeyProvider> = keysError?.let { throw it } ?: keys

    override suspend fun saveKey(provider: String, key: String, region: String): KeyProvider {
        saveError?.let { throw it }
        savedKeys += Triple(provider, key, region)
        val before = keys.first { it.id == provider }
        val after = before.copy(hasKey = key.isNotBlank() || before.hasKey, masked = if (key.isNotBlank()) "••••" + key.takeLast(4) else before.masked, regionValue = region, valid = false)
        keys = keys.map { if (it.id == provider) after else it }.toMutableList()
        return after
    }

    override suspend fun removeKey(provider: String): KeyProvider {
        removedKeys += provider
        val after = keys.first { it.id == provider }.copy(hasKey = false, masked = "", valid = false, voices = 0, regionValue = "")
        keys = keys.map { if (it.id == provider) after else it }.toMutableList()
        return after
    }

    override suspend fun checkKey(provider: String): KeyResult {
        checked += provider
        val result = checkResult?.invoke(provider) ?: KeyResult(true, "Dùng được · 4 giọng tiếng Việt")
        val after = keys.first { it.id == provider }.copy(valid = result.ok, voices = if (result.ok) 4 else 0)
        keys = keys.map { if (it.id == provider) after else it }.toMutableList()
        return result.copy(provider = after)
    }

    override suspend fun consents(): Set<String> = allowed.toSet()

    override suspend fun allow(provider: String) {
        allowed += provider
    }

    override suspend fun sample(voice: String, text: String): String {
        sampled += voice to text
        sampleGate?.await()
        sampleError?.let { throw it }
        return "/cache/$voice.mp3"
    }

    override suspend fun tracks(): List<MusicTrack> = tracksError?.let { throw it } ?: tracks

    override suspend fun importMusic(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImportResult {
        imported += uris
        for (index in uris.indices) progress(index + 1, uris.size)
        importGate?.await()
        importError?.let { throw it }
        val result = importResult?.invoke(uris) ?: MusicImportResult(tracks + uris.map { Fixtures.track(it) }, uris.size, 0, emptyList())
        tracks = result.tracks
        return result
    }

    override suspend fun removeTrack(link: String): List<MusicTrack> {
        trackRemoveError?.let { throw it }
        removedTracks += link
        tracks = tracks.filterNot { it.link == link }
        return tracks
    }
}

/** Máy phát giả: ghi lại đường file được bảo phát, không bao giờ ra loa. Test gọi [finish] / [fail] để giả lúc phát hết / hỏng. */
class FakeSamplePlayer : SamplePlayer {
    val played = ArrayList<String>()
    var stops = 0
    private var ended: (() -> Unit)? = null
    private var failed: (() -> Unit)? = null

    override fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit) {
        played += path
        ended = onEnded
        failed = onFailed
    }

    override fun stop() {
        stops++
        ended = null
        failed = null
    }

    fun finish() = ended?.invoke()
    fun fail() = failed?.invoke()
}

/** Dữ liệu mẫu: cùng hình với lõi (VoiceModule.status, OnlineKeys.public, MusicStore.entries). */
object Fixtures {
    private fun choices(kind: ModuleKind, installed: Set<String> = emptySet(), leftovers: Set<String> = emptySet()): List<ModuleChoice> = when (kind) {
        ModuleKind.Vieneu -> listOf(
            ModuleChoice("turbo", "Giọng VieNeu", "Giọng nữ, đọc truyện tự nhiên", 198_000_000, "turbo" in installed, true, "turbo" in installed || "turbo" in leftovers),
            ModuleChoice("nano", "Giọng VieNeu Nano", "Nhẹ hơn, hợp máy yếu", 52_000_000, "nano" in installed, false, "nano" in installed || "nano" in leftovers),
        )
        ModuleKind.Supertonic -> listOf(
            ModuleChoice("supertonic", "Giọng Supertonic", "Nhiều giọng, nhẹ máy", 263_000_000, "supertonic" in installed, true, "supertonic" in installed || "supertonic" in leftovers),
            ModuleChoice("supertonic_fast", "Bản nhanh hơn", "Đọc nhanh hơn trên máy yếu", 48_000_000, "supertonic_fast" in installed, false, "supertonic_fast" in installed || "supertonic_fast" in leftovers),
        )
    }

    private fun status(
        kind: ModuleKind, state: ModuleState, percent: Int = 0, total: Long = 0, error: String = "", installed: Set<String> = emptySet(), leftovers: Set<String> = emptySet(),
        bench: Map<String, ModuleBench> = emptyMap(), suggestion: ModuleSuggestion? = null, outdated: Long = 0, benchmarking: Boolean = false, metered: Boolean = false, reason: String = "",
    ) = ModuleStatus(state, percent, total, error, reason, choices(kind, installed, leftovers), outdated, bench, benchmarking, suggestion, "turbo", 0.8, metered, false)

    fun missing(kind: ModuleKind, metered: Boolean = false) = status(kind, ModuleState.Missing, metered = metered)
    fun downloading(kind: ModuleKind, percent: Int) = status(kind, ModuleState.Downloading, percent, 198_000_000)
    fun failed(kind: ModuleKind) = status(kind, ModuleState.Error, error = "Mất mạng giữa chừng. Tải lại sẽ làm tiếp từ chỗ dừng.", leftovers = setOf(choices(kind).first().id))
    fun ready(kind: ModuleKind, bench: Map<String, ModuleBench> = emptyMap(), suggestion: ModuleSuggestion? = null) =
        status(kind, ModuleState.Ready, installed = setOf(choices(kind).first().id), bench = bench, suggestion = suggestion)
    fun outdated(kind: ModuleKind) = status(kind, ModuleState.Outdated, installed = setOf(choices(kind).first().id), outdated = 12_000_000)
    fun unsupported(kind: ModuleKind) = status(kind, ModuleState.Unsupported, reason = "thiếu bộ nhớ trống")
    fun leftover(kind: ModuleKind) = status(kind, ModuleState.Missing, leftovers = setOf(choices(kind).first().id))
    fun benchmarking(kind: ModuleKind) = status(kind, ModuleState.Ready, installed = setOf(choices(kind).first().id), benchmarking = true)

    fun provider(id: String, name: String, hasKey: Boolean = false, valid: Boolean = false, region: String = "") = KeyProvider(
        id, name, if (id == "azure") "Miễn phí 500.000 ký tự mỗi tháng" else "Miễn phí có hạn mức",
        id == "azure", hasKey, if (hasKey) "••••WXYZ" else "", region, valid, if (valid) 4 else 0,
    )

    fun track(name: String, bytes: Long = 4_200_000, creator: String = "Bạn", duration: Double = 187.0, analysed: Boolean = true) =
        MusicTrack("local:" + name.hashCode().toUInt().toString(16), name, creator, duration, bytes, analysed)
}
