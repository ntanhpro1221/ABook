package vn.abook.player.ui.devices

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.BookDownloads
import vn.abook.player.BluetoothLink
import vn.abook.player.Devices
import vn.abook.player.EditsSync
import vn.abook.player.NetErrors
import vn.abook.player.PeerAddresses
import vn.abook.player.Peers
import vn.abook.player.Pin
import vn.abook.player.RemoteBooks
import vn.abook.player.ShareService
import vn.abook.player.Store
import vn.abook.player.SyncLink
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.listenerFlow

/**
 * Nguồn thật của ba màn Thiết bị: gọi thẳng các lõi ([Devices], [RemoteBooks], [Peers], [BookDownloads], [ShareService], [Store]) - cùng những hàm mà
 * `LibraryPlugin` chuyển tiếp cho bản WebView, không qua cầu Capacitor. Xoá khỏi máy đi qua `library` ([BookSource.delete]): đúng lõi và đúng đường
 * làm mới Thư viện của menu "Xoá khỏi máy" ở trang sách.
 */
class DevicesRepo(private val context: Context, private val library: vn.abook.player.ui.data.LibraryRepo) : DevicesSource {
    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) {
        Store.init(context)
        block()
    }

    /** Lỗi của lõi thành lời cho người nghe (lỗi mạng đã dịch, máy kia bỏ ghép, chứng chỉ đổi). */
    private fun failure(error: Exception, fallback: String): DeviceFailure {
        if (error is DeviceFailure) return error
        val (message, technical) = BookDownloads.describe(error, fallback)
        return DeviceFailure(message, technical, unpaired = NetErrors.unpaired(error), changed = error is Pin.ChangedException)
    }

    private inline fun <T> guard(fallback: String, block: () -> T): T = try {
        block()
    } catch (error: Exception) {
        throw failure(error, fallback)
    }

    override suspend fun link(): Link = io { DevicesJson.link(Devices.connection(context)) }

    override suspend fun discover(): List<Found> = io {
        val found = Devices.discover(context)
        (0 until found.length()).map { DevicesJson.found(found.getJSONObject(it)) }
    }

    override suspend fun nearbyAllowed(): Boolean = BluetoothLink.permitted(context)

    override suspend fun bluetoothDevices(): List<Found> = io {
        guard("Chưa dùng được Bluetooth") {
            val devices = Devices.bluetoothDevices(context)
            (0 until devices.length()).map { DevicesJson.bluetooth(devices.getJSONObject(it)) }
        }
    }

    override suspend fun pair(address: String, code: String, extra: Boolean): String = io {
        guard("Chưa kết nối được") {
            val digits = code.filter(Char::isDigit)
            if (address.startsWith("bt:")) {
                val device = address.removePrefix("bt:")
                if (extra) Peers.pairBluetooth(context, device, digits).optString("name") else Devices.pairBluetooth(context, device, digits)
            } else {
                val (host, port) = PeerAddresses.split(address)
                if (extra) Peers.pair(context, host, port, digits).optString("name") else Devices.pair(context, host, port, digits)
            }
        }
    }

    override suspend fun unpair() = io { Devices.unpair(context) }

    override suspend fun remote(): RemoteLibrary = io {
        guard("Chưa nối được máy kia.") {
            val reply = RemoteBooks.library(context)
            RemoteLibrary(reply.optString("name"), DevicesJson.books(reply.getJSONArray("books"))).also { RemoteBooks.reached(context) }
        }
    }

    override suspend fun peers(): List<PeerLibrary> = io {
        val all = Peers.libraries(context)
        (0 until all.length()).map { index ->
            val entry = all.getJSONObject(index)
            DevicesJson.peer(entry.put("kind", Peers.kindOf(context, entry.getString("key"))))
        }
    }

    override suspend fun peerAddress(key: String): String? = io {
        val peer = Peers.all(context).optJSONObject(key) ?: return@io null
        val host = peer.optString("host")
        if (host.startsWith("bt:")) host else PeerAddresses.endpoint(host, peer.optInt("port", DEFAULT_PORT))
    }

    override suspend fun unsent(key: String): Unsent = io {
        val unsent = Peers.unsent(key)
        val cache = Peers.cached(key)
        DevicesJson.unsent(unsent.books.map { UnsentBook(it.title, it.changes) }, unsent.changes, Peers.kindOf(context, key) == "computer", cache.books, cache.bytes, cache.places)
    }

    override suspend fun forget(key: String, choice: ForgetChoice) = io {
        guard("Chưa bỏ ghép được") {
            if (choice == ForgetChoice.Send) Peers.sendUnsent(key) { EditsSync.pushNow(context, it) }
            Peers.forget(context, key, discard = choice == ForgetChoice.Discard)
        }
    }

    override suspend fun streamable() {
        val rows = io { RemoteBooks.streamable(context) }
        library.acceptRemote(rows)
    }

    override suspend fun download(book: RemoteBook) = io {
        guard("Chưa tải được") {
            val manifest = Store.streamManifest(book.id)
            val source = book.source ?: manifest?.optString("source")?.takeIf { it.isNotEmpty() }
            val remoteId = book.remoteId ?: manifest?.optString("remoteId")?.takeIf { it.isNotEmpty() }
            BookDownloads.start(context, book.id, source, remoteId)
        }
    }

    override suspend fun cancelDownload(id: String) = io { BookDownloads.cancel(context, id) }

    override fun downloadEvents(): Flow<DownloadEvent> = listenerFlow { send -> BookDownloads.listen { event -> send(download(event)) } }

    private fun download(event: JSONObject): DownloadEvent {
        val total = event.optLong("total")
        val fraction = if (total > 0) event.optLong("done").toFloat() / total else event.optInt("files").toFloat() / maxOf(1, event.optInt("filesTotal", 1))
        return DownloadEvent(
            event.optString("bookId"), fraction.coerceIn(0f, 1f), event.optBoolean("finished"), event.optBoolean("cancelled"),
            event.optString("error").takeIf { it.isNotEmpty() }, event.optString("technical").takeIf { it.isNotEmpty() },
        )
    }

    override suspend fun studio(): List<StudioComputer> = io {
        val computers = Devices.studioComputers(context)
        (0 until computers.length()).map { computers.getJSONObject(it) }.map { StudioComputer(it.optString("key"), it.optString("name"), it.optBoolean("listenOnly")) }
    }

    override suspend fun studioTarget(key: String): Pair<String, String> = io { guard("Chưa mở được Studio") { Devices.studioTarget(context, null, key) } }

    override suspend fun share(): Share = io { DevicesJson.share(Devices.shareView(context)) }

    override suspend fun setShare(on: Boolean): Share = io { guard("Chưa làm được") { DevicesJson.share(Devices.setShare(context, on)) } }

    override suspend fun startCode(): Share = io { guard("Chưa làm được") { DevicesJson.share(Devices.sharePair(context)) } }

    override suspend fun cancelCode(): Share = io { DevicesJson.share(Devices.shareCancelPairing(context)) }

    override suspend fun revoke(id: String): Share = io { DevicesJson.share(Devices.shareRevoke(context, id)) }

    override fun shareChanges(): Flow<Unit> = listenerFlow { send ->
        val stopShare = ShareService.watch { send(Unit) }
        val stopPairing = vn.abook.player.LibraryServer.watchPairing { send(Unit) }
        val stop: () -> Unit = { stopShare(); stopPairing() }
        stop
    }

    override suspend fun setDeviceName(name: String): String = io { Devices.setDeviceName(context, name) }

    override suspend fun storage(): Storage = io { DevicesJson.storage(Devices.storage(), { Store.rawManifest(it) != null }, { SyncLink.holderName(context, it) }).let { storage -> storage.copy(entries = storage.entries.filterNot { library.isHidden(it.id) }) } }

    override suspend fun delete(id: String, title: String, partial: Boolean): String? = library.removeFromPhone(id, title, partial)

    override suspend fun restore() = io {
        runCatching { BookDownloads.restore(context) }
        if (SyncLink.prefs(context).getBoolean(Devices.SHARE_KEY, false)) runCatching { ShareService.enable(context) }
        Unit
    }
}
