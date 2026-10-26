package vn.abook.player.ui.devices

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentHashMap

/** Màn "Nối máy tính": mọi thứ màn cần vẽ. Đổi hiếm (không đổi theo từng nhịp tải) - tiến độ từng cuốn ở [DevicesState.progress]. */
@Immutable
data class PairUi(
    val loaded: Boolean = false,
    val refreshing: Boolean = false,
    val link: Link = Link(),
    val devices: List<Paired> = emptyList(),
    val sections: List<BookSection> = emptyList(),
    val form: PairForm = PairForm(),
    val found: List<Found> = emptyList(),
    val scanning: Boolean = false,
    val bluetooth: Bluetooth = Bluetooth.Off,
    val attempt: Attempt = Attempt.Idle,
    /** Đã có máy tính chính mà người dùng mở khung ghép thêm một thiết bị nữa. */
    val adding: Boolean = false,
    val downloading: Set<String> = emptySet(),
    val failed: Map<String, String> = emptyMap(),
    val studio: Map<String, StudioComputer> = emptyMap(),
) {
    val paired: Boolean get() = link.paired
    val method: PairMethod get() = when {
        form.manual -> PairMethod.Address
        bluetooth !is Bluetooth.Off -> PairMethod.Bluetooth
        else -> PairMethod.Wifi
    }
    val wifiChoices: List<Found> get() = found.withoutPaired(devices)
    val bluetoothChoices: List<Found>
        get() = (bluetooth as? Bluetooth.Devices)?.list.orEmpty().filter { paired || it.kind == DeviceKind.Computer || it.abook }.withoutPaired(devices)
    val showForm: Boolean get() = loaded && (!link.paired || adding)

    /** Máy tìm thấy để chọn: Wi-Fi rồi Bluetooth, bỏ những máy đã ghép. */
    val choices: List<Found>
        get() {
            val bluetooth = (bluetooth as? Bluetooth.Devices)?.list.orEmpty().filter { paired || it.kind == DeviceKind.Computer || it.abook }
            return (found + bluetooth).withoutPaired(devices)
        }
}

@Immutable
data class ShareUi(val loaded: Boolean = false, val share: Share = Share(), val busy: Boolean = false, val problem: String = "")

@Immutable
data class StorageUi(val loaded: Boolean = false, val storage: Storage = Storage())

/** Dòng giá trị của ba hàng ở trang nhóm Thiết bị và tên máy này; null khi chưa đọc xong. */
@Immutable
data class Summary(val link: Link? = null, val share: Share? = null, val storage: Storage? = null) {
    val deviceName: String get() = link?.deviceName.orEmpty()
    val pair: String? get() = link?.let { if (it.paired) "Đã nối ${it.shownName}" else "Chưa nối" }
    val sharing: String?
        get() = share?.let { if (it.running) (if (it.devices.isEmpty()) "Đang bật" else "Đang bật · ${it.devices.size} máy") else "Đang tắt" }
    val storageLine: String? get() = storage?.line
}

/**
 * Trạng thái sống của ba màn Thiết bị. Màn chỉ vẽ [pair] / [share] / [storage] và gọi hàm ở đây; mọi việc với lõi đi qua [DevicesSource]. Tiến độ tải từng cuốn
 * là một luồng riêng ([progress]) để màn đọc nó trong pha vẽ, không dựng lại mỗi nhịp. `changed`: Thư viện cần đọc lại (sách nghe thẳng mới, sách vừa tải xong).
 */
@Stable
class DevicesState(
    private val source: DevicesSource,
    private val scope: CoroutineScope,
    private val links: DeviceLinks = DeviceLinks(),
    private val changed: suspend () -> Unit = {},
    private val pollMs: Long = 2000,
) {
    private val pairFlow = MutableStateFlow(PairUi())
    private val shareFlow = MutableStateFlow(ShareUi())
    private val storageFlow = MutableStateFlow(StorageUi())
    private val progresses = ConcurrentHashMap<String, MutableStateFlow<Float>>()
    private var reloadJob: Job? = null
    private var pollJob: Job? = null
    private var streaming = false
    private var prefilled = false

    val pair: StateFlow<PairUi> = pairFlow
    val share: StateFlow<ShareUi> = shareFlow
    val storage: StateFlow<StorageUi> = storageFlow
    val summary: StateFlow<Summary> = combine(pairFlow, shareFlow, storageFlow) { pair, share, storage ->
        Summary(pair.link.takeIf { pair.loaded }, share.share.takeIf { share.loaded }, storage.storage.takeIf { storage.loaded })
    }.stateIn(scope, SharingStarted.Eagerly, Summary())

    init {
        scope.launch { source.downloadEvents().collect(::onDownload) }
        scope.launch { source.shareChanges().collect { loadShare() } }
    }

    /** Tiến độ 0..1 của một cuốn đang tải; đọc trong pha vẽ. */
    fun progress(id: String): StateFlow<Float> = writable(id)

    private fun writable(id: String) = progresses.getOrPut(id) { MutableStateFlow(0f) }

    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Result.failure(error)
    }

    private fun message(error: Throwable?) = error?.message?.takeIf { it.isNotBlank() } ?: "Chưa làm được"

    // ---- trang nhóm ----------------------------------------------------------------------------------------------------

    /** Mở trang nhóm Thiết bị: đọc ba dòng giá trị (nền, không chặn). */
    fun loadSummary() {
        scope.launch {
            coroutineScope {
                launch { attempt { source.link() }.onSuccess { link -> pairFlow.update { it.copy(link = link, loaded = true) } } }
                launch { loadShare() }
                launch { loadStorage() }
            }
        }
    }

    /** Đổi tên điện thoại này (máy kia thấy nó bằng tên ấy). Null = xong, khác null = câu lỗi. */
    suspend fun rename(name: String): String? {
        val result = attempt { source.setDeviceName(name) }
        result.onSuccess { clean -> pairFlow.update { it.copy(link = it.link.copy(deviceName = clean)) } }
        return result.exceptionOrNull()?.let { message(it) }
    }

    // ---- Nối máy tính --------------------------------------------------------------------------------------------------

    /** Vào màn: đọc máy tính chính, thiết bị ghép thêm và sách của chúng; chưa ghép gì thì tìm máy trong Wi-Fi luôn. */
    fun openPair() {
        reloadJob?.cancel()
        reloadJob = scope.launch {
            val link = attempt { source.link() }.getOrNull() ?: return@launch
            pairFlow.update { it.copy(link = link, loaded = true) }
            if (!link.paired) {
                // Máy tính ghép lần trước: ghép lại sau khi nó bỏ ghép không phải gõ lại địa chỉ.
                if (!prefilled && link.lastAddress.isNotEmpty()) pairFlow.update { it.copy(form = it.form.copy(address = link.lastAddress, manual = true)) }
                prefilled = true
                scan()
            }
            reload()
        }
    }

    /** Làm mới: hỏi lại máy tính chính và các thiết bị ghép thêm (nút "Thử lại" và mục "Làm mới"). */
    fun refresh() {
        reloadJob?.cancel()
        reloadJob = scope.launch { reload() }
    }

    private suspend fun reload() {
        val link = attempt { source.link() }.getOrNull() ?: return
        pairFlow.update { state ->
            // Máy tính chính hiện ngay, chưa rõ trạng thái - các dòng đã biết giữ nguyên (không nháy).
            val shown = if (link.paired && state.devices.none { it.main }) listOf(mainDevice(link, Reach.Checking)) + state.devices.filterNot { it.main } else state.devices
            state.copy(link = link, loaded = true, refreshing = true, devices = if (link.paired) shown else shown.filterNot { it.main })
        }
        val (remote, peers) = coroutineScope {
            val remote = async { if (link.paired) attempt { source.remote() } else null }
            val peers = async { attempt { source.peers() } }
            remote.await() to peers.await()
        }
        val fresh = if (link.paired) attempt { source.link() }.getOrDefault(link) else link
        val main = if (link.paired) mainDevice(fresh, reachOf(remote?.exceptionOrNull())) else null
        val peerList = peers.getOrDefault(emptyList())
        val sections = buildList {
            val books = remote?.getOrNull()?.books.orEmpty()
            if (main != null && books.isNotEmpty()) add(BookSection(null, main.name, books))
            for (peer in peerList) if (peer.device.reach == Reach.Ok && peer.books.isNotEmpty()) add(BookSection(peer.device.key, peer.device.name, peer.books))
        }
        pairFlow.update { it.copy(link = fresh, refreshing = false, devices = listOfNotNull(main) + peerList.map { peer -> peer.device }, sections = sections) }
        if (main?.reach == Reach.Ok || peerList.any { it.device.reach == Reach.Ok }) syncStreamed()
    }

    private fun mainDevice(link: Link, reach: Reach) =
        Paired(MAIN_KEY, link.shownName, DeviceKind.Computer, link.via, link.fingerprint, reach, host = link.host)

    private fun reachOf(error: Throwable?): Reach = when {
        error == null -> Reach.Ok
        error is DeviceFailure && error.unpaired -> Reach.Unpaired
        error is DeviceFailure && error.changed -> Reach.Changed(message(error))
        else -> Reach.Offline(message(error), (error as? DeviceFailure)?.technical)
    }

    /** Gom sách nghe thẳng của các máy đã ghép vào Thư viện rồi bảo Thư viện đọc lại; một lượt một lúc. */
    fun syncStreamed() {
        if (streaming) return
        streaming = true
        scope.launch {
            try {
                attempt { source.streamable() }
                attempt { changed() }
            } finally {
                streaming = false
            }
        }
    }

    fun scan() {
        if (pairFlow.value.scanning) return
        pairFlow.update { it.copy(scanning = true) }
        scope.launch {
            val found = attempt { source.discover() }.getOrDefault(emptyList())
            pairFlow.update { it.copy(found = found, scanning = false) }
            val now = pairFlow.value
            val choices = now.wifiChoices
            if (now.method == PairMethod.Wifi && choices.size == 1 && now.form.picked == null) pick(choices.first())
        }
    }

    /** Tìm máy đã ghép Bluetooth với điện thoại. Chưa có quyền "Thiết bị ở gần" thì Android hỏi trước. */
    fun findBluetooth() {
        scope.launch {
            pairFlow.update { it.copy(bluetooth = Bluetooth.Listing, form = it.form.copy(manual = false, picked = null), attempt = Attempt.Idle) }
            if (!source.nearbyAllowed()) {
                links.askNearby { granted ->
                    if (granted) findBluetooth() else pairFlow.update { it.copy(bluetooth = Bluetooth.Denied) }
                }
                return@launch
            }
            attempt { source.bluetoothDevices() }
                .onSuccess { list -> pairFlow.update { it.copy(bluetooth = Bluetooth.Devices(list)) } }
                .onFailure { error -> pairFlow.update { it.copy(bluetooth = Bluetooth.Failed(message(error))) } }
            val now = pairFlow.value
            val choices = now.bluetoothChoices
            if (now.method == PairMethod.Bluetooth && choices.size == 1 && now.form.picked == null) pick(choices.first())
        }
    }

    /** Quay lại từ Cài đặt Android mà quyền đã bật: tìm máy luôn, không bắt bấm lại. */
    fun recheckBluetooth() {
        if (pairFlow.value.bluetooth !is Bluetooth.Denied) return
        scope.launch { if (source.nearbyAllowed()) findBluetooth() }
    }

    fun openAppSettings() = links.openAppSettings()

    /** Đổi cách nối: Wi-Fi (tự tìm), Bluetooth (máy đã ghép), hay gõ địa chỉ. */
    fun setMethod(method: PairMethod) {
        when (method) {
            PairMethod.Wifi -> {
                pairFlow.update { it.copy(form = it.form.copy(manual = false, picked = null), bluetooth = Bluetooth.Off, attempt = Attempt.Idle) }
                scan()
            }
            PairMethod.Bluetooth -> findBluetooth()
            PairMethod.Address -> pairFlow.update { it.copy(form = it.form.copy(manual = true, picked = null), bluetooth = Bluetooth.Off, attempt = Attempt.Idle) }
        }
    }

    fun pick(found: Found) = pairFlow.update { it.copy(form = it.form.copy(picked = if (it.form.picked == found.address) null else found.address, manual = false), attempt = Attempt.Idle) }

    fun setAddress(text: String) = pairFlow.update { it.copy(form = it.form.copy(address = text), attempt = Attempt.Idle) }

    fun setCode(text: String) = pairFlow.update { it.copy(form = it.form.copy(code = text.filter(Char::isDigit).take(6)), attempt = Attempt.Idle) }

    /** Mở / đóng khung ghép thêm một thiết bị khi đã có máy tính chính. */
    fun setAdding(on: Boolean) {
        pairFlow.update { it.copy(adding = on, form = if (on) it.form else PairForm(), attempt = Attempt.Idle) }
        if (on && pairFlow.value.found.isEmpty()) scan()
    }

    fun connect() {
        val state = pairFlow.value
        val form = state.form
        val raw = form.target
        if (!form.ready || raw == null || state.attempt is Attempt.Working) return
        val address = if (raw.startsWith("bt:")) raw else normalizeAddress(raw)
        if (address == null) {
            pairFlow.update { it.copy(attempt = Attempt.Failed("Địa chỉ chưa đúng - ví dụ 192.168.1.20:47630")) }
            return
        }
        val name = state.choices.firstOrNull { it.address == raw }?.shown ?: address.substringBeforeLast(':')
        pairFlow.update { it.copy(attempt = Attempt.Working(name)) }
        scope.launch {
            attempt { source.pair(address, form.digits, extra = state.paired) }
                .onSuccess {
                    pairFlow.update { it.copy(form = PairForm(), attempt = Attempt.Idle, adding = false, found = emptyList(), bluetooth = Bluetooth.Off) }
                    reload()
                }
                .onFailure { error -> pairFlow.update { it.copy(attempt = Attempt.Failed(message(error), (error as? DeviceFailure)?.technical)) } }
        }
    }

    // ---- một thiết bị đã ghép ------------------------------------------------------------------------------------------

    /** Mở bảng của một máy tính: hỏi xem Studio của nó còn mở được không. */
    fun loadStudio() {
        scope.launch {
            attempt { source.studio() }.onSuccess { list -> pairFlow.update { it.copy(studio = list.associateBy { c -> c.key }) } }
        }
    }

    /** Mở Studio của máy tính `key` ở trình xem riêng. Null = đã mở, khác null = câu lỗi. */
    suspend fun openStudio(key: String): String? {
        val result = attempt { source.studioTarget(key) }
        result.onSuccess { (computer, path) -> links.openStudio(computer, path) }
        return result.exceptionOrNull()?.let { message(it) }
    }

    /** Bỏ ghép máy tính chính. Null = xong. */
    suspend fun unpairMain(): String? {
        val result = attempt { source.unpair() }
        if (result.isFailure) return message(result.exceptionOrNull())
        pairFlow.update { it.copy(devices = it.devices.filterNot { device -> device.main }, sections = it.sections.filterNot { s -> s.source == null }) }
        reloadJob?.cancel()
        reloadJob = scope.launch { reload() }
        syncStreamed()
        return null
    }

    /** Hỏi trước khi bỏ ghép một thiết bị ghép thêm: cái sẽ mất. Null khi không đọc được (cứ cho bỏ - lõi từ chối nếu còn sửa chưa gửi). */
    suspend fun unsent(key: String): Unsent? = attempt { source.unsent(key) }.getOrNull()

    /** Bỏ ghép thiết bị `key`. Null = xong, khác null = câu lỗi (thiết bị vẫn ghép). */
    suspend fun forget(key: String, choice: ForgetChoice): String? {
        val result = attempt { source.forget(key, choice) }
        if (result.isFailure) return message(result.exceptionOrNull())
        pairFlow.update { it.copy(devices = it.devices.filterNot { device -> device.key == key }, sections = it.sections.filterNot { s -> s.source == key }) }
        syncStreamed()
        return null
    }

    /** "Ghép lại" một máy đã bỏ ghép điện thoại này: mở khung ghép với sẵn địa chỉ của nó, chỉ còn nhập mã mới. */
    fun repair(device: Paired) {
        scope.launch {
            if (device.main) {
                attempt { source.unpair() }
                reload()
                val last = pairFlow.value.link.lastAddress
                pairFlow.update { it.copy(form = PairForm(address = last, manual = last.isNotEmpty()), attempt = Attempt.Idle) }
                scan()
            } else {
                val address = attempt { source.peerAddress(device.key) }.getOrNull().orEmpty()
                pairFlow.update { it.copy(adding = true, form = PairForm(address = address, manual = address.isNotEmpty()), attempt = Attempt.Idle) }
                scan()
            }
        }
    }

    // ---- tải sách ------------------------------------------------------------------------------------------------------

    fun download(book: RemoteBook) {
        writable(book.id).value = 0f
        pairFlow.update { it.copy(downloading = it.downloading + book.id, failed = it.failed - book.id) }
        scope.launch {
            attempt { source.download(book) }.onFailure { error ->
                pairFlow.update { it.copy(downloading = it.downloading - book.id, failed = it.failed + (book.id to message(error))) }
            }
        }
    }

    fun cancelDownload(id: String) {
        scope.launch { attempt { source.cancelDownload(id) } }
    }

    private suspend fun onDownload(event: DownloadEvent) {
        writable(event.id).value = event.fraction
        val running = event.running
        pairFlow.update { state ->
            val failed = when {
                event.error != null -> state.failed + (event.id to event.error)
                event.finished || event.cancelled -> state.failed - event.id
                else -> state.failed
            }
            if ((event.id in state.downloading) == running && failed == state.failed) state
            else state.copy(downloading = if (running) state.downloading + event.id else state.downloading - event.id, failed = failed)
        }
        if (event.finished) {
            attempt { changed() }
            if (pairFlow.value.loaded) reload()
            if (storageFlow.value.loaded) loadStorage()
        }
    }

    // ---- Chia sẻ thư viện ----------------------------------------------------------------------------------------------

    fun openShare() {
        scope.launch { loadShare() }
    }

    private suspend fun loadShare() {
        attempt { source.share() }.onSuccess(::setShare)
    }

    private fun setShare(share: Share) {
        shareFlow.update { it.copy(loaded = true, share = share, busy = false) }
        pollCode(share)
    }

    /** Đang hiện mã ghép: hỏi lại mỗi vài giây để thấy máy mới vào danh sách hay mã hết hạn. */
    private fun pollCode(share: Share) {
        pollJob?.cancel()
        if (share.code == null) return
        pollJob = scope.launch {
            while (isActive) {
                delay(pollMs)
                val next = attempt { source.share() }.getOrNull() ?: continue
                shareFlow.update { it.copy(share = next) }
                if (next.code == null) break
            }
        }
    }

    /** Công tắc: bật thì xin quyền thông báo trước (Android 13+; từ chối vẫn chạy), tắt thì tắt luôn. */
    fun setSharing(on: Boolean) {
        if (shareFlow.value.busy) return
        shareFlow.update { it.copy(busy = true, problem = "") }
        if (on) links.askNotifications { change { source.setShare(true) } } else change { source.setShare(false) }
    }

    fun newCode() = change { source.startCode() }

    fun cancelCode() = change { source.cancelCode() }

    fun revoke(id: String) = change { source.revoke(id) }

    private fun change(block: suspend () -> Share) {
        shareFlow.update { it.copy(busy = true, problem = "") }
        scope.launch {
            attempt { block() }
                .onSuccess(::setShare)
                .onFailure { error -> shareFlow.update { it.copy(busy = false, problem = message(error)) } }
        }
    }

    // ---- Dung lượng ----------------------------------------------------------------------------------------------------

    fun openStorage() {
        scope.launch { loadStorage() }
    }

    private suspend fun loadStorage() {
        attempt { source.storage() }.onSuccess { storage -> storageFlow.value = StorageUi(true, storage) }
    }

    /** Xoá khỏi máy (cùng lõi và lời xác nhận với menu "Xoá khỏi máy" ở trang sách). Null = đã xoá, khác null = câu lỗi. */
    suspend fun delete(id: String): String? {
        val result = attempt { source.delete(id) }
        val error = result.exceptionOrNull()?.let { message(it) } ?: result.getOrNull()
        if (error == null) {
            storageFlow.update { ui -> ui.copy(storage = ui.storage.copy(entries = ui.storage.entries.filterNot { it.id == id })) }
            loadStorage()
        }
        return error
    }

    /** Lúc mở app: lượt tải còn giữ từ lần trước, chia sẻ đã bật từ lần trước. */
    fun restore() {
        scope.launch { attempt { source.restore() } }
    }
}
