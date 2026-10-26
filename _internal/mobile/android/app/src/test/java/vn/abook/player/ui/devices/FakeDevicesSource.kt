package vn.abook.player.ui.devices

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow

/** Nguồn Thiết bị giả: kho trong bộ nhớ, ghi lại mọi việc màn đã bảo lõi làm để test so lời gọi. Việc dài có thể bị giữ bằng một cổng. */
class FakeDevicesSource : DevicesSource {
    var link = Link()
    var found = emptyList<Found>()
    var nearby = true
    var bluetooth = emptyList<Found>()
    var bluetoothError: DeviceFailure? = null

    val pairs = ArrayList<Triple<String, String, Boolean>>()
    var pairError: DeviceFailure? = null
    var pairGate: CompletableDeferred<Unit>? = null
    var pairedName = "Máy bàn"
    var unpairs = 0

    var remote: RemoteLibrary? = null
    var remoteError: DeviceFailure? = null
    var peers = emptyList<PeerLibrary>()
    var peerAddresses = emptyMap<String, String>()
    var unsent = Unsent()
    val forgets = ArrayList<Pair<String, ForgetChoice>>()
    var forgetError: DeviceFailure? = null
    var streamables = 0

    val downloads = ArrayList<String>()
    var downloadError: DeviceFailure? = null
    val cancels = ArrayList<String>()
    val events = MutableSharedFlow<DownloadEvent>(extraBufferCapacity = 64)

    var studio = emptyList<StudioComputer>()
    var target = "may" to "/studio"
    var targetError: DeviceFailure? = null

    var share = Share()
    var shareError: DeviceFailure? = null
    val shareEvents = MutableSharedFlow<Unit>(extraBufferCapacity = 8)
    var deviceName = ""
    var storage = Storage()
    val deleted = ArrayList<String>()
    var deleteError: String? = null
    var restores = 0

    override suspend fun link() = link
    override suspend fun discover() = found
    override suspend fun nearbyAllowed() = nearby

    override suspend fun bluetoothDevices(): List<Found> = bluetoothError?.let { throw it } ?: bluetooth

    override suspend fun pair(address: String, code: String, extra: Boolean): String {
        pairs += Triple(address, code, extra)
        pairGate?.await()
        pairError?.let { throw it }
        if (!extra) link = Link(paired = true, name = pairedName, host = address.substringBeforeLast(':'), via = address, deviceName = link.deviceName)
        return pairedName
    }

    override suspend fun unpair() {
        unpairs++
        link = Link(paired = false, deviceName = link.deviceName, lastAddress = link.host)
    }

    override suspend fun remote(): RemoteLibrary = remoteError?.let { throw it } ?: remote ?: throw DeviceFailure("Chưa nối được máy kia.")
    override suspend fun peers() = peers
    override suspend fun peerAddress(key: String) = peerAddresses[key]
    override suspend fun unsent(key: String) = unsent

    override suspend fun forget(key: String, choice: ForgetChoice) {
        forgetError?.let { throw it }
        forgets += key to choice
        peers = peers.filterNot { it.device.key == key }
    }

    override suspend fun streamable() {
        streamables++
    }

    override suspend fun download(book: RemoteBook) {
        downloadError?.let { throw it }
        downloads += book.id
    }

    override suspend fun cancelDownload(id: String) {
        cancels += id
    }

    override fun downloadEvents(): Flow<DownloadEvent> = events
    override suspend fun studio() = studio
    override suspend fun studioTarget(key: String): Pair<String, String> = targetError?.let { throw it } ?: target

    override suspend fun share(): Share = share

    override suspend fun setShare(on: Boolean): Share {
        shareError?.let { throw it }
        share = share.copy(running = on, code = if (on) share.code else null)
        return share
    }

    override suspend fun startCode(): Share {
        share = share.copy(running = true, code = Code("482915", 1_700_000_000.0 + 600))
        return share
    }

    override suspend fun cancelCode(): Share {
        share = share.copy(code = null)
        return share
    }

    override suspend fun revoke(id: String): Share {
        share = share.copy(devices = share.devices.filterNot { it.id == id })
        return share
    }

    override fun shareChanges(): Flow<Unit> = shareEvents

    override suspend fun setDeviceName(name: String): String {
        deviceName = name
        return name
    }

    override suspend fun storage() = storage

    override suspend fun delete(id: String): String? {
        deleted += id
        if (deleteError == null) storage = storage.copy(entries = storage.entries.filterNot { it.id == id })
        return deleteError
    }

    override suspend fun restore() {
        restores++
    }
}
