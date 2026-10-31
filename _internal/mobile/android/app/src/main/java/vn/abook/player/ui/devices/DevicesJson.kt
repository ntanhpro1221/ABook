package vn.abook.player.ui.devices

import org.json.JSONArray
import org.json.JSONObject

/**
 * Đọc JSON của các lõi (`Devices`, `RemoteBooks`, `Peers`) thành mô hình của màn. Hình JSON do lõi trả.
 */
internal object DevicesJson {
    private fun JSONArray?.objects(): List<JSONObject> = if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

    private fun kind(value: String) = if (value == "phone") DeviceKind.Phone else DeviceKind.Computer

    fun link(json: JSONObject) = Link(
        paired = json.optBoolean("paired"), name = json.optString("name"), host = json.optString("host"), via = json.optString("connectedVia"),
        fingerprint = json.optString("fingerprint"), deviceName = json.optString("deviceName"), lastAddress = json.optString("lastAddress"),
    )

    /** Máy tìm thấy trong Wi-Fi: {host, port, name, kind}. */
    fun found(json: JSONObject) = Found("${json.getString("host")}:${json.optInt("port", DEFAULT_PORT)}", json.optString("name"), kind(json.optString("kind")))

    /** Máy đã ghép Bluetooth: {address, name, kind, abook}. */
    fun bluetooth(json: JSONObject) = Found("bt:${json.getString("address")}", json.optString("name"), kind(json.optString("kind")), bluetooth = true, abook = json.optBoolean("abook"))

    fun book(json: JSONObject): RemoteBook {
        val downloaded = json.optBoolean("downloaded")
        val available = json.optInt("chaptersAvailable")
        fun changed(remote: String, local: String) = downloaded && json.optString(remote).isNotEmpty() && json.optString(remote) != json.optString(local)
        return RemoteBook(
            id = json.getString("id"), source = json.optString("source").takeIf { it.isNotEmpty() }, remoteId = json.optString("remoteId").takeIf { it.isNotEmpty() },
            title = json.optString("title"), chaptersAvailable = available, chaptersTotal = json.optInt("chaptersTotal"),
            duration = json.optDouble("duration", 0.0).takeIf { it.isFinite() } ?: 0.0, bytes = json.optLong("bytes"), producing = json.optBoolean("producing"),
            downloaded = downloaded, newChapters = if (downloaded) (available - json.optInt("localChapters")).coerceAtLeast(0) else 0,
            newAudio = changed("audioVersion", "localAudioVersion"), newMeta = changed("metaVersion", "localMetaVersion"), newWords = changed("wordsVersion", "localWordsVersion"),
            newCover = downloaded && (json.optJSONObject("cover")?.optLong("version") ?: 0L) != json.optLong("localCoverVersion"),
        )
    }

    fun books(array: JSONArray?): List<RemoteBook> = array.objects().map(::book)

    fun share(json: JSONObject): Share {
        val pairing = json.optJSONObject("pairing")
        val bluetooth = json.optJSONObject("bluetooth")
        return Share(
            running = json.optBoolean("running"), name = json.optString("name"), port = json.optInt("port"),
            addresses = (0 until (json.optJSONArray("addresses")?.length() ?: 0)).map { json.getJSONArray("addresses").getString(it) },
            code = pairing?.let { Code(it.optString("code"), it.optDouble("expiresAt", 0.0)) }, blocked = json.optBoolean("blocked"),
            devices = json.optJSONArray("devices").objects().map { Sharer(it.optString("id"), it.optString("name"), it.optDouble("lastSeen", 0.0)) },
            error = json.optString("error"), bluetooth = bluetooth?.optString("status").orEmpty(), bluetoothConnections = bluetooth?.optInt("connections") ?: 0,
            fingerprint = json.optString("fingerprint"), backgroundAllowed = json.optBoolean("backgroundAllowed", true),
        )
    }

    /** `isBook(mã)`: thư mục là cuốn đã tải xong (bản gói sách nằm trên máy); không thì là phần tải dở / gói nghe thẳng, `holder(mã)` = tên máy giữ cuốn ấy. */
    fun storage(json: JSONObject, isBook: (String) -> Boolean, holder: (String) -> String = { "" }): Storage = Storage(
        bytes = json.optLong("bytes"), free = json.optLong("free"),
        entries = json.optJSONArray("books").objects().map {
            val id = it.getString("id")
            Stored(id, it.optString("title").ifBlank { "Sách tải dở" }, it.optLong("bytes"), partial = !isBook(id), holder = if (isBook(id)) "" else holder(id))
        }.sortedByDescending { it.bytes },
    )

    /** Từ `Peers.unsent` + `Peers.cached`: `sendable` = thiết bị là máy tính nên "gửi trước" có nghĩa. */
    fun unsent(books: List<UnsentBook>, changes: Int, sendable: Boolean, cacheBooks: Int, cacheBytes: Long, places: Int) =
        Unsent(books, changes, sendable, cacheBooks, cacheBytes, places)

    /** Một mục của `Peers.libraries`: thiết bị, trạng thái và sách. */
    fun peer(json: JSONObject): PeerLibrary {
        val name = json.optString("name")
        val reach = when {
            json.optBoolean("unpaired") -> Reach.Unpaired
            json.optBoolean("pinChanged") -> Reach.Changed(json.optString("error"))
            json.has("error") -> Reach.Offline(json.optString("error"), json.optString("technical").takeIf { it.isNotEmpty() })
            else -> Reach.Ok
        }
        val books = books(json.optJSONArray("books"))
        val device = Paired(
            key = json.getString("key"), name = name.ifBlank { "Thiết bị" }, kind = kind(json.optString("kind")), via = json.optString("connectedVia"),
            fingerprint = json.optString("fingerprint"), reach = reach, books = books.size, host = json.optString("host"),
        )
        return PeerLibrary(device, books)
    }
}
