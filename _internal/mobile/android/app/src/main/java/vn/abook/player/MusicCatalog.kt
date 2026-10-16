package vn.abook.player

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import org.json.JSONTokener
import java.io.File
import java.io.FileNotFoundException
import java.io.FilterInputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors

/**
 * Danh mục nhạc nền trên mây cho điện thoại - bản Kotlin của phần abook/webui/music_catalog.py mà "Nghe ngay" cần: mục lục
 * (`manifest.json` + chữ ký `manifest.json.sig`, giữ 24 giờ, mất mạng thì dùng bản đã cất), mảnh dữ liệu bài (`tracks/<xx>.json`, cất theo
 * `revision`), và file bài (tải một lần từ link gốc, hỏng thì bản sao `mirrors` phải khớp `sha1` + `bytes` như `server.music_track_file`).
 * Không khoá, không đăng nhập: chỉ là file tĩnh. Mọi lời gọi chặn - chạy ở luồng nền.
 *
 * Có chữ ký (cùng luật với máy tính): mục lục phải đúng chữ ký Ed25519 của [publicKey], `issued` không lùi so với bản đang giữ, và mọi mảnh
 * phải khớp sha256 trong `files` của mục lục. Sai thì giữ danh mục đã cất, không bao giờ dùng link của bản lạ; mảnh lệch / không được
 * liệt kê coi như không có (ghi qua [log]). Cất cả byte gốc lẫn `.sig`, đọc lại bản cất cũng kiểm lại.
 *
 * `open(url)` mở một địa chỉ (http(s) hay đường dẫn thư mục cho test JVM) - chỉ đọc, không gửi gì ngoài User-Agent. Địa chỉ danh mục lấy
 * qua `sourceOf` MỘT lần, ở lần cần mạng đầu tiên (luồng nền): nó đọc cấu hình từ xa ([RemoteConfig.musicCatalogs]) nên có thể chặn mạng.
 */
class MusicCatalog(
    private val dir: File,
    sourceOf: () -> String,
    private val open: (String) -> InputStream = ::openUrl,
    private val clock: () -> Long = System::currentTimeMillis,
    private val publicKey: ByteArray = RemoteConfig.PUBLIC_KEY,
    private val log: (String) -> Unit = ::logWarning,
) {
    constructor(
        dir: File,
        source: String = DEFAULT_SOURCE,
        open: (String) -> InputStream = ::openUrl,
        clock: () -> Long = System::currentTimeMillis,
        publicKey: ByteArray = RemoteConfig.PUBLIC_KEY,
        log: (String) -> Unit = ::logWarning,
    ) : this(dir, { source }, open, clock, publicKey, log)

    /** Danh mục không đọc được (mất mạng lần đầu, định dạng mới hơn app). Câu chữ để người dùng đọc - như `CatalogError` bên Python. */
    class CatalogError(message: String) : Exception(message)

    /** Bài lớn hơn [TRACK_MAX_MB] (`bytes` của danh mục, Content-Length hay số byte đếm được khi tải): máy này không dùng - như
     *  `TrackTooBig` của webui/server.py. Không phải lỗi mạng: không thử lại. */
    class TrackTooBig(val size: Long) : IOException("bài nhạc quá $TRACK_MAX_MB MB")

    /** Nguồn trả lời nhưng báo lỗi HTTP (404, 403...): nguồn vẫn nối được, chỉ bài / file ấy hỏng - KHÔNG phải lỗi mạng (như `urllib.error.HTTPError`). */
    class HttpFailure(val code: Int) : IOException("HTTP $code")

    /** Lỗi tại chỗ không do mạng (bản sao khác bản gốc, không ghi được file): bài ấy hỏng thật. */
    class LocalFailure(message: String) : IOException(message)

    /** Mọi nguồn của bài hỏng vì MẠNG (không phân giải được tên, không nối được, hết giờ, đứt giữa chừng, bắt tay SSL): bài vẫn tốt, chỉ chưa
     *  tải được - người gọi không tính vào số lần bỏ bài, thử lại khi có mạng (như `network_only` của `music_track_file`). */
    class Offline(message: String = "không có mạng") : IOException(message)

    /** Kết quả [lookupPartial]: dữ liệu các link tìm được + các mảnh không tải được (mạng) - bài thuộc mảnh ấy chưa biết, chờ tải lại. */
    class Lookup(val found: Map<String, JSONObject>, val missingShards: Set<String>)

    /** Luồng tải biết trước cỡ (Content-Length của [openUrl]; null = nguồn không báo) để bỏ bài quá lớn trước khi tải. */
    class Sized(input: InputStream, val length: Long?) : FilterInputStream(input)

    private val source by lazy { sourceOf().trimEnd('/') + "/" }
    private val remote get() = source.startsWith("http://") || source.startsWith("https://")
    private val lock = Any()
    private var manifest: JSONObject? = null
    /** Mảnh đã đọc: `tracks/` là JSONObject, `cells/` là JSONArray. */
    private val parts = HashMap<String, Any>()

    private fun fetch(relative: String): ByteArray {
        val url = source + relative
        try {
            return open(url).use { it.readBytes() }.also { note(url, failed = false) }
        } catch (error: IOException) {
            note(url, failed = isNetworkFailure(error))
            throw error
        }
    }

    // ---- cờ mạng theo NGUỒN (host), như `_music_note` / `_music_host_down` của server.py ----------------------------------------
    // Một nguồn chết (hay bị chặn) chỉ khoá bài của nguồn ấy; nguồn trả lời được (tải xong, hay trả lỗi HTTP) thì xoá cờ.
    private val hostLock = Any()
    private val hosts = HashMap<String, Pair<Boolean, Long>>() // host -> (hỏng vì mạng?, lúc ghi)

    private fun hostOf(url: String): String = runCatching { URI(url).authority }.getOrNull().orEmpty().lowercase()

    private fun note(url: String, failed: Boolean) {
        val host = hostOf(url)
        synchronized(hostLock) { hosts[host] = failed to clock() }
    }

    /** Nguồn của `url` vừa hỏng vì mạng (chưa quá [HOST_REST_MS]): đừng chờ nó hết giờ thêm lần nữa. */
    fun hostDown(url: String): Boolean = synchronized(hostLock) {
        hosts[hostOf(url)]?.let { (failed, at) -> failed && clock() - at < HOST_REST_MS } ?: false
    }

    /** Có nguồn nào đang nghỉ vì mạng không (`_music_degraded`): bài của nguồn ấy chưa tải được - giao diện nói "mất mạng". */
    fun degraded(): Boolean = synchronized(hostLock) {
        val now = clock()
        hosts.values.any { (failed, at) -> failed && now - at < HOST_REST_MS }
    }

    /** Cả máy coi như mất mạng (`_music_offline`): từ [OFFLINE_HOSTS] nguồn cùng hỏng vì mạng trong [HOST_REST_MS] gần đây mà không nguồn nào vừa trả lời được. */
    fun offline(): Boolean = synchronized(hostLock) {
        val now = clock()
        val recent = hosts.values.filter { (_, at) -> now - at < HOST_REST_MS }
        recent.size >= OFFLINE_HOSTS && recent.all { (failed, _) -> failed }
    }

    // Bài tải hỏng thật (nguồn gỡ bài, 404, bản sao sai): nghỉ [UNAVAILABLE_MS] rồi thử lại (`_music_unavailable` của server.py; ở đây chỉ trong tiến trình, máy tính ghi ra đĩa).
    private val brokenAt = HashMap<String, Long>()

    /** Tải bài `link` hỏng thật: bộ chọn nhạc theo cảnh tránh nó trong [UNAVAILABLE_MS]. */
    fun markUnavailable(link: String) {
        synchronized(hostLock) { brokenAt[link] = clock() }
    }

    /** Lời báo "mất mạng" cho giao diện (cùng chữ `MUSIC_OFFLINE_MESSAGE` của server.py) khi có bài đang bị giữ vì mạng, không thì rỗng. */
    fun offlineNotice(): String = if (degraded()) OFFLINE_MESSAGE else ""

    /** Mục lục đã kiểm: chữ ký đúng khoá, JSON đúng hình dạng, có `issued` và `files`. Không thì null (không ném lỗi). */
    private fun accept(raw: ByteArray, signature: ByteArray): JSONObject? {
        if (!Signatures.verifyBase64(publicKey, raw, signature)) return null
        val data = try {
            JSONObject(String(raw, Charsets.UTF_8))
        } catch (_: JSONException) {
            return null
        }
        if (data.optString("format") != FORMAT || data.opt("version") !is Int) return null
        if (data.opt("issued") !is String || data.optJSONObject("files") == null) return null
        return data
    }

    /** Mục lục đã cất trên đĩa, kiểm lại chữ ký (file đĩa bị sửa hay ghi dở thì coi như không có). */
    private fun cached(): JSONObject? = try {
        accept(File(dir, "manifest.json").readBytes(), File(dir, "manifest.json.sig").readBytes())
    } catch (_: IOException) {
        null
    }

    private fun checkVersion(data: JSONObject) {
        if (data.getInt("version") > FORMAT_VERSION) throw CatalogError("Danh mục nhạc nền mới hơn app - hãy cập nhật app.")
    }

    /** Mục lục còn mới (đã đọc, cất trên đĩa chưa quá [MANIFEST_MAX_AGE_MS]) hay null. Gọi khi giữ [lock]. */
    private fun freshManifest(): JSONObject? {
        val path = File(dir, "manifest.json")
        val fresh = path.isFile && clock() - path.lastModified() < MANIFEST_MAX_AGE_MS
        return manifest?.takeIf { fresh }
    }

    /** Lần làm mới mục lục gần nhất không thành (mất mạng, sai chữ ký, cũ hơn bản đang giữ): trong [MANIFEST_RETRY_MS] sau đó dùng bản đã cất, không gọi mạng lại. */
    private var refreshFailedAt = -MANIFEST_RETRY_MS
    /** Mỗi lúc chỉ một luồng làm mới mục lục; các luồng khác chờ ở đây - KHÔNG giữ [lock] trong lúc gọi mạng (hỏi bài / cỡ bài ở luồng khác vẫn chạy). */
    private val refresh = Any()

    /** Mục lục danh mục (cất ở `dir/manifest.json` + `.sig`, làm mới sau [MANIFEST_MAX_AGE_MS]); mất mạng hay bản tải về bị bỏ thì bản đã cất. */
    fun manifest(): JSONObject {
        synchronized(lock) { freshManifest()?.let { return it } }
        synchronized(refresh) {
            var current: JSONObject?
            val needFetch: Boolean
            synchronized(lock) {
                freshManifest()?.let { return it } // luồng khác vừa làm mới xong
                current = manifest ?: cached() // bản đang giữ: mốc `issued` để không quay về bản cũ
                needFetch = current == null || clock() - refreshFailedAt >= MANIFEST_RETRY_MS
            }
            var rejected = false
            if (needFetch) {
                val fetched = try {
                    fetch("manifest.json") to fetch("manifest.json.sig") // ngoài [lock]: mạng chậm không chặn các luồng hỏi bài
                } catch (_: Exception) {
                    null // mất mạng: dùng bản đã cất nếu có
                }
                var accepted = false
                if (fetched != null) {
                    val (raw, signature) = fetched
                    val data = accept(raw, signature)
                    val held = current
                    if (data == null) {
                        log("danh mục nhạc: mục lục tải về sai chữ ký hay sai định dạng - giữ bản đã cất")
                    } else if (held != null && data.getString("issued") < held.getString("issued")) {
                        log("danh mục nhạc: mục lục tải về cũ hơn bản đang giữ (${data.getString("issued")} < ${held.getString("issued")}) - bỏ")
                    } else {
                        checkVersion(data)
                        Store.writeAtomic(File(dir, "manifest.json"), raw)
                        Store.writeAtomic(File(dir, "manifest.json.sig"), signature)
                        current = data
                        accepted = true
                    }
                    rejected = current == null
                }
                synchronized(lock) { refreshFailedAt = if (accepted) -MANIFEST_RETRY_MS else clock() }
            }
            synchronized(lock) {
                val result = current
                if (result == null) {
                    throw CatalogError(if (rejected) "Danh mục nhạc nền tải về không có chữ ký hợp lệ - app không dùng." else "Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.")
                }
                checkVersion(result)
                if (manifest?.optString("revision") != result.optString("revision")) {
                    parts.clear()
                    pruneRevisions(result.optString("revision"))
                }
                manifest = result
                return result
            }
        }
    }

    fun playlists(): List<JSONObject> = Playlists.catalogue(manifest())

    /**
     * Một mảnh của danh mục. Phải khớp sha256 trong `files` của mục lục đã ký - không có trong `files` hay lệch thì null (coi như mảnh vắng,
     * các bài trong đó như không có), có ghi nhật ký. Mảnh đã cất cũng kiểm; lệch thì tải lại.
     */
    private fun part(relative: String): Any? {
        val manifest = manifest()
        val revision = manifest.getString("revision")
        val key = "$revision/$relative"
        synchronized(lock) { parts[key]?.let { return it } }
        val expected = manifest.getJSONObject("files").optString(relative).takeIf { it.isNotEmpty() }
        if (expected == null) {
            log("danh mục nhạc: mảnh $relative không có trong mục lục đã ký - bỏ")
            return null
        }
        val path = Store.contained(File(dir, revision), relative)
        var raw = runCatching { path.readBytes() }.getOrNull()?.takeIf { sha256(it) == expected }
        if (raw == null) {
            // Mã phiên bản trong đường dẫn: CDN đệm mảnh 1 giờ - danh mục mới là đường dẫn mới, không lẫn mảnh cũ.
            val fetched = try {
                fetch(if (remote) "$relative?v=$revision" else relative)
            } catch (error: IOException) {
                throw CatalogError("Không tải được danh mục nhạc nền - kiểm tra mạng.")
            }
            if (sha256(fetched) != expected) {
                log("danh mục nhạc: mảnh $relative lệch sha256 của mục lục đã ký - bỏ")
                return null
            }
            runCatching { Store.writeAtomic(path, fetched) }
            raw = fetched
        }
        val value = try {
            JSONTokener(String(raw, Charsets.UTF_8)).nextValue()
        } catch (_: JSONException) {
            log("danh mục nhạc: mảnh $relative không phải JSON - bỏ")
            return null
        }
        if (value !is JSONObject && value !is JSONArray) {
            log("danh mục nhạc: mảnh $relative không phải JSON - bỏ")
            return null
        }
        synchronized(lock) { parts[key] = value }
        return value
    }

    /** Dữ liệu đã gắn cho các link (link không có trong danh mục thì vắng). Các mảnh chưa cất tải song song. Mảnh không tải được (mạng) thì bỏ
     *  qua, các mảnh còn lại vẫn dùng - xem [lookupPartial] để biết mảnh nào còn thiếu mà tải lại. */
    fun lookup(links: List<String>): Map<String, JSONObject> = lookupPartial(links).found

    /** Như [lookup] nhưng nói rõ các mảnh hỏng: một mảnh lỗi mạng không làm mất cả danh sách phát. Mục lục không có (mất mạng lần đầu) vẫn ném
     *  [CatalogError]. Mảnh lệch sha256 / không được liệt kê là vắng thật (không tải lại được), không nằm trong `missingShards`. */
    fun lookupPartial(links: List<String>): Lookup {
        val existing = manifest().optJSONArray("shards")?.let { list -> (0 until list.length()).map { list.optString(it) }.toSet() } ?: emptySet()
        val wanted = links.groupBy(::shardOf).filterKeys { it in existing }
        val pool = Executors.newFixedThreadPool(SHARD_WORKERS)
        val loaded = HashMap<String, JSONObject?>()
        val missing = LinkedHashSet<String>()
        try {
            val jobs = wanted.keys.map { shard -> shard to pool.submit<JSONObject?> { part("tracks/$shard.json") as? JSONObject } }
            for ((shard, job) in jobs) {
                try {
                    loaded[shard] = job.get()
                } catch (error: java.util.concurrent.ExecutionException) {
                    log("danh mục nhạc: mảnh tracks/$shard.json chưa tải được (${error.cause?.message}) - các mảnh khác vẫn dùng, thử lại sau")
                    missing += shard
                }
            }
        } finally {
            pool.shutdown()
        }
        val found = LinkedHashMap<String, JSONObject>()
        for ((shard, items) in wanted) for (link in items) loaded[shard]?.optJSONObject(link)?.let { found[link] = it }
        return Lookup(found, missing)
    }

    /**
     * `MusicCatalog.cell`: bài của ô cảm xúc (`valenceIndex`, `arousalIndex`) - mảnh `cells/<v>_<a>.json` (mảng các mục như `tracks/`, thêm `valence` /
     * `arousal` / `tension`...). Mục lục không kê ô ấy (hay ô rỗng) thì rỗng, không tải gì. Cùng luật chữ ký / sha256 như mọi mảnh; mất mạng thì [CatalogError].
     */
    fun cell(valenceIndex: Int, arousalIndex: Int): List<JSONObject> {
        val name = "${valenceIndex}_$arousalIndex"
        val listed = when (val count = manifest().optJSONObject("cells")?.opt(name)) {
            null, JSONObject.NULL, false -> false
            is Number -> count.toDouble() != 0.0
            is String -> count.isNotEmpty()
            is JSONObject -> count.length() > 0
            is JSONArray -> count.length() > 0
            else -> true
        }
        if (!listed) return emptyList()
        val items = part("cells/$name.json") as? JSONArray ?: return emptyList()
        return (0 until items.length()).mapNotNull { items.optJSONObject(it) }
    }

    /** `MusicCatalog.near`: bài trong ô của (valence, arousal) và các ô kề trong bán kính `radius`, theo thứ tự của Python ([SceneMusic.near]). */
    fun near(valence: Double, arousal: Double, radius: Int = 1): List<JSONObject> {
        val grid = manifest().optInt("grid", 5).takeIf { it != 0 } ?: 5
        // Lần đầu 9 ô là 9 lượt tải nối nhau (~1 giây mỗi lượt): tải song song trước, rồi đọc theo thứ tự cũ (thứ tự là thứ tự hoà của xếp hạng, `SceneMusic.near`).
        val wanted = ArrayList<Pair<Int, Int>>()
        SceneMusic.near<JSONObject>(grid, valence, arousal, radius) { v, a -> wanted.add(v to a); emptyList() }
        if (wanted.size > 1) {
            val pool = Executors.newFixedThreadPool(SHARD_WORKERS)
            try {
                wanted.map { (v, a) -> pool.submit { runCatching { cell(v, a) } } }.forEach { runCatching { it.get() } } // lỗi mạng ném lại ở lượt đọc tuần tự bên dưới
            } finally {
                pool.shutdown()
            }
        }
        return SceneMusic.near(grid, valence, arousal, radius, ::cell)
    }

    /** File bài đã tải về máy (không tải); chưa có thì null. */
    fun cached(link: String): File? = fileOf(link).takeIf { it.isFile }

    /** Như [cached] nhưng ghi nhận bài vừa được dùng (giờ sửa file = lần dùng gần nhất, để [prune] xoá bài lâu không nghe trước); chỉ ghi lại khi đã quá [TOUCH_MS]. */
    fun use(link: String): File? = cached(link)?.also { file ->
        val now = clock()
        if (now - file.lastModified() > TOUCH_MS) file.setLastModified(now)
    }

    /**
     * Giữ thư mục bài tải về không phình mãi: quá `capBytes` ([FILES_CAP_BYTES]) thì xoá bài lâu không dùng nhất ([use]) cho tới khi vừa, trừ các bài trong `keep` (đang kêu / vừa tải); file
     * `.part` bỏ dở quá [PART_STALE_MS] cũng xoá. Bài bị xoá tải lại được lúc cần (cũng qua [download]). Luồng nền.
     */
    fun prune(keep: Collection<String> = emptyList(), capBytes: Long = FILES_CAP_BYTES) {
        val all = File(dir, "files").listFiles() ?: return
        val now = clock()
        all.filter { it.name.endsWith(".part") && now - it.lastModified() > PART_STALE_MS }.forEach { it.delete() }
        val tracks = all.filter { it.name.endsWith(".mp3") }
        var total = tracks.sumOf { it.length() }
        if (total <= capBytes) return
        val protected = keep.map { fileOf(it).name }.toSet()
        for (file in tracks.sortedBy { it.lastModified() }) {
            if (total <= capBytes) break
            if (file.name in protected) continue
            val size = file.length()
            if (file.delete()) total -= size
        }
    }

    /** Mảnh danh mục của các phiên bản (`revision`) cũ không bao giờ được đọc lại: xoá mọi thư mục trừ `files/` và phiên bản đang dùng (mỗi lần danh mục đổi phiên bản thì cả bộ mảnh mới nằm ở thư mục mới). */
    fun pruneRevisions(revision: String) {
        val folders = dir.listFiles { file -> file.isDirectory && file.name != "files" && file.name != revision } ?: return
        for (folder in folders) runCatching { folder.deleteRecursively() }
    }

    /** Các bài đã biết là quá [TRACK_MAX_MB] (`dir/too_big.json`: {link: số byte}) - không hết hạn: cỡ bài không đổi. */
    private val tooBig by lazy {
        val found = HashMap<String, Long>()
        runCatching { JSONObject(File(dir, "too_big.json").readText()) }.getOrNull()?.let { data ->
            for (key in data.keys()) (data.opt(key) as? Number)?.let { found[key] = it.toLong() }
        }
        found
    }

    private fun markTooBig(link: String, size: Long) {
        synchronized(lock) {
            if (tooBig[link] == size) return
            tooBig[link] = size
            runCatching { Store.writeAtomic(File(dir, "too_big.json"), JSONObject(tooBig.toMap()).toString().toByteArray(Charsets.UTF_8)) }
        }
    }

    /**
     * Bài `link` dùng được TRÊN MÁY NÀY không (`server.music_track_available`): đã tải thì được; quá [TRACK_MAX_MB] theo `bytes` của
     * danh mục (`info`) hay theo lần tải trước thì không - danh sách phát bỏ nó, bài sau dồn lên. Chưa biết cỡ thì cứ coi là được.
     */
    fun usable(link: String, info: JSONObject?): Boolean {
        if (cached(link) != null) return true
        val size = (info?.opt("bytes") as? Number)?.toLong()
        if (size != null && size > TRACK_MAX_BYTES) return false
        return synchronized(lock) { (tooBig[link] ?: 0L) <= TRACK_MAX_BYTES }
    }

    /**
     * Bài `link` dùng được TRÊN MÁY NÀY lúc này không - bộ chọn nhạc theo cảnh hỏi (`server.music_track_available(sizes=False)`, cùng đầu vào thì cùng lựa chọn): đã tải thì được (kể cả khi
     * không có mạng); chưa tải thì không nếu bài đã biết là quá [TRACK_MAX_MB], nguồn của nó vừa hỏng vì mạng ([hostDown]) hay cả máy đang mất mạng ([offline]), hay bài vừa tải hỏng
     * thật ([markUnavailable], chưa quá [UNAVAILABLE_MS]). Chưa biết thì coi là được. Khác [usable] (chỉ cỡ): [usable] hỏi chuyện BÀI, hàm này hỏi cả chuyện MẠNG.
     */
    fun available(link: String): Boolean {
        if (cached(link) != null) return true
        if (link.startsWith(MusicStore.LOCAL_PREFIX)) return false // nhạc người dùng nhập không tải từ đâu được: không có file là không dùng được
        if (!usable(link, null)) return false
        if (offline() || hostDown(link)) return false
        val failedAt = synchronized(hostLock) { brokenAt[link] }
        return failedAt == null || clock() - failedAt >= UNAVAILABLE_MS
    }

    /** Bài đã tra cỡ trong danh mục ([verifySizes]) và không quá [TRACK_MAX_BYTES]: khỏi tra lại. */
    private val sized = HashSet<String>()

    /**
     * Tra cỡ (`bytes` của mảnh `tracks/`; ô `cells/` không có) của các bài trong MỘT lượt (mảnh tải song song, [lookup]) và ghi sổ `too_big` bài nào quá [TRACK_MAX_MB]
     * (`server.music_verify_sizes`). True khi VỪA phát hiện bài quá cỡ - người gọi chọn lại, [usable] từ đó loại nó. Bài đã tra / đã tải về khỏi tra lại; danh mục chưa đọc
     * được hay bài không ghi cỡ: chưa biết, coi là vừa (Content-Length bù khi tải).
     */
    fun verifySizes(links: Collection<String>): Boolean {
        val unknown = synchronized(lock) { links.filter { it !in sized && (tooBig[it] ?: 0L) <= TRACK_MAX_BYTES } }.distinct().sorted().filter { cached(it) == null }
        if (unknown.isEmpty()) return false
        val found = try {
            lookup(unknown)
        } catch (_: Exception) {
            return false
        }
        var oversize = false
        for (link in unknown) {
            val info = found[link] ?: continue
            val size = (info.opt("bytes") as? Number)?.toLong()
            if (size != null && size > TRACK_MAX_BYTES) {
                markTooBig(link, size)
                oversize = true
            } else {
                synchronized(lock) { sized.add(link) }
            }
        }
        return oversize
    }

    /** Chép bài đang tải, dừng ([TrackTooBig]) khi quá [TRACK_MAX_BYTES]: Content-Length báo trước, hay đếm thật khi nguồn không báo. */
    private fun copyCapped(input: InputStream, sink: OutputStream) {
        (input as? Sized)?.length?.let { if (it > TRACK_MAX_BYTES) throw TrackTooBig(it) }
        val buffer = ByteArray(1 shl 16)
        var copied = 0L
        while (true) {
            val read = input.read(buffer)
            if (read < 0) return
            copied += read
            if (copied > TRACK_MAX_BYTES) throw TrackTooBig(copied)
            sink.write(buffer, 0, read)
        }
    }

    private fun fileOf(link: String) = File(File(dir, "files"), sha1(link.toByteArray(Charsets.UTF_8)) + ".mp3")

    /**
     * Tải bài `link` của danh mục về máy (đã có thì thôi): link gốc trước, hỏng thì bản sao trong `info.mirrors` - chỉ khi danh mục ghi
     * `sha1` của bản gốc, và bản sao phải khớp `sha1` (và `bytes`) mới dùng, không phát nhầm bài. Không lấy được thì null. Bài quá
     * [TRACK_MAX_MB] (danh mục, Content-Length hay đếm khi tải) thì ném [TrackTooBig] và ghi nhớ - [usable] từ đó trả false.
     */
    fun download(link: String, info: JSONObject?): File? {
        if (!link.startsWith("https://")) return null
        val target = fileOf(link)
        if (target.isFile) return target
        val expected = info?.optString("sha1")?.lowercase()?.takeIf { SHA1.matches(it) }
        val size = (info?.opt("bytes") as? Number)?.toLong()
        if (size != null && size > TRACK_MAX_BYTES) {
            markTooBig(link, size)
            throw TrackTooBig(size)
        }
        val mirrors = info?.optJSONArray("mirrors")?.takeIf { expected != null }?.let { list ->
            (0 until list.length()).mapNotNull { (list.opt(it) as? String)?.takeIf { url -> url.startsWith("https://") } }
        } ?: emptyList()
        target.parentFile?.mkdirs()
        // Như `music_track_file`: mọi nguồn hỏng vì MẠNG thì bài vẫn tốt ([Offline], các nguồn ấy nghỉ [HOST_REST_MS]); còn lại: bài hỏng thật (null).
        var networkOnly = true
        val attempted = mutableListOf<String>()
        for (url in listOf(link) + mirrors) {
            if (hostDown(url)) continue // nguồn này vừa hỏng vì mạng: khỏi chờ nó hết giờ lần nữa (nguồn khác vẫn thử)
            attempted += url
            val part = File(target.path + ".${System.nanoTime()}.part")
            try {
                open(url).use { input -> part.outputStream().use { copyCapped(input, it) } }
                if (url != link && ((size != null && part.length() != size) || sha1(part.readBytes()) != expected)) throw LocalFailure("bản sao khác bản gốc")
                if (!part.renameTo(target) && !target.isFile) throw LocalFailure("không ghi được")
                note(url, failed = false) // tải được = nguồn ấy có mạng
                return target
            } catch (error: TrackTooBig) { // bản sao cùng cỡ: khỏi thử
                note(url, failed = false)
                markTooBig(link, error.size)
                throw error
            } catch (error: Exception) {
                // thử nguồn kế
                networkOnly = networkOnly && isNetworkFailure(error)
                if (error is HttpFailure) note(url, failed = false) // nguồn trả lời (404...): nối được, chỉ bài hỏng
            } finally {
                part.delete()
            }
        }
        if (networkOnly) {
            for (url in attempted) note(url, failed = true)
            throw Offline()
        }
        return null
    }

    companion object {
        /** Địa chỉ danh mục (như `music_catalog.DEFAULT_CATALOG`). */
        const val DEFAULT_SOURCE = "https://abook-music.ngdtuanh.workers.dev/"
        const val FORMAT = "abook-music-catalog"
        const val FORMAT_VERSION = 1
        const val MANIFEST_MAX_AGE_MS = 24L * 3600 * 1000
        /** Làm mới mục lục không thành thì chừng này mới thử lại (trong lúc ấy dùng bản đã cất): hỏi bài / ô dồn dập không kéo theo dồn dập lượt gọi mạng chờ hết giờ. */
        const val MANIFEST_RETRY_MS = 60_000L
        /** Bài nhạc nền lớn hơn thế (bản dài 30-50 phút, có bài 110 MB) máy này không dùng - cùng `MUSIC_TRACK_MAX_MB` của server.py. */
        const val TRACK_MAX_MB = 40
        const val TRACK_MAX_BYTES = TRACK_MAX_MB * 1024L * 1024
        /** Trần thư mục bài đã tải: bằng bộ đệm đọc to (ClipCache, 300 MB) - chừng 40 bài cỡ thường (vài MB tới chục MB) đủ cho cả những cuốn nghe gần đây, nhạc theo cảnh lặp lại bài nhiều;
         *  hai bộ đệm cộng lại vẫn dưới nửa GB của `cacheDir`. */
        const val FILES_CAP_BYTES = 300L * 1024 * 1024
        private const val TOUCH_MS = 3_600_000L
        private const val PART_STALE_MS = 600_000L
        private const val SHARD_WORKERS = 8
        /** Nguồn tải hỏng vì mạng nghỉ chừng này (`MUSIC_OFFLINE_SECONDS`): bài của nó chờ, bài của nguồn khác vẫn chạy. */
        const val HOST_REST_MS = 300_000L
        /** Bấy nhiêu nguồn cùng hỏng vì mạng (và không nguồn nào vừa trả lời) = máy mất mạng (`MUSIC_OFFLINE_HOSTS`). */
        const val OFFLINE_HOSTS = 2
        /** Bài tải hỏng thật nghỉ chừng này rồi thử lại (`MUSIC_UNAVAILABLE_SECONDS`, 24 giờ). */
        const val UNAVAILABLE_MS = 24L * 3600 * 1000
        /** Chữ báo khi bài nhạc bị giữ lại vì mạng - đúng chữ `MUSIC_OFFLINE_MESSAGE` của webui/server.py. */
        const val OFFLINE_MESSAGE = "Không tải được nhạc vì mất mạng - giữ nguyên nhạc hiện tại, bạn thử lại sau nhé"
        private const val USER_AGENT = "ABook (+https://github.com/ntanhpro1221/ABook)"
        private val SHA1 = Regex("[0-9a-f]{40}")

        private fun sha1(bytes: ByteArray): String = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }

        private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

        /** Nhật ký mặc định; `android.util.Log` không chạy trong bài thử JVM nên nuốt lỗi (test truyền bộ ghi riêng). */
        private fun logWarning(message: String) {
            runCatching { android.util.Log.w("MusicCatalog", message) }
        }

        /** Lỗi tầng mạng (không phân giải được tên, không nối được, hết giờ, đứt giữa chừng, bắt tay SSL) - khác nguồn trả lỗi HTTP, bản sao sai,
         *  bài quá lớn, lỗi ghi file (`_music_network_failure` của server.py). Lỗi không phải IOException cũng không phải lỗi mạng. */
        fun isNetworkFailure(error: Throwable): Boolean =
            error is IOException && error !is HttpFailure && error !is LocalFailure && error !is TrackTooBig && error !is FileNotFoundException

        /** `music_catalog.shard_of`: hai ký tự đầu sha1 của link. */
        fun shardOf(link: String): String = sha1(link.toByteArray(Charsets.UTF_8)).take(2)

        /** http(s): GET kèm User-Agent, chờ có hạn; còn lại: một file trên đĩa (test). */
        fun openUrl(url: String): InputStream {
            if (!url.startsWith("http://") && !url.startsWith("https://")) return File(url.substringBefore('?')).inputStream()
            val connection = URL(url).openConnection() as HttpURLConnection
            connection.connectTimeout = 15_000
            connection.readTimeout = 60_000
            connection.setRequestProperty("User-Agent", USER_AGENT)
            if (connection.responseCode !in 200..299) {
                connection.disconnect()
                throw HttpFailure(connection.responseCode)
            }
            return Sized(connection.inputStream, connection.contentLengthLong.takeIf { it >= 0 })
        }
    }
}
