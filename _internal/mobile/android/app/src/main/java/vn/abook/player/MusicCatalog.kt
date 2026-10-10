package vn.abook.player

import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.FilterInputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
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

    /** Luồng tải biết trước cỡ (Content-Length của [openUrl]; null = nguồn không báo) để bỏ bài quá lớn trước khi tải. */
    class Sized(input: InputStream, val length: Long?) : FilterInputStream(input)

    private val source by lazy { sourceOf().trimEnd('/') + "/" }
    private val remote get() = source.startsWith("http://") || source.startsWith("https://")
    private val lock = Any()
    private var manifest: JSONObject? = null
    private val parts = HashMap<String, JSONObject>()

    private fun fetch(relative: String): ByteArray = open(source + relative).use { it.readBytes() }

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

    /** Mục lục danh mục (cất ở `dir/manifest.json` + `.sig`, làm mới sau [MANIFEST_MAX_AGE_MS]); mất mạng hay bản tải về bị bỏ thì bản đã cất. */
    fun manifest(): JSONObject = synchronized(lock) {
        val path = File(dir, "manifest.json")
        val fresh = path.isFile && clock() - path.lastModified() < MANIFEST_MAX_AGE_MS
        manifest?.takeIf { fresh }?.let { return it }
        var current = manifest ?: cached() // bản đang giữ: mốc `issued` để không quay về bản cũ
        var rejected = false
        if (!fresh || current == null) {
            val fetched = try {
                fetch("manifest.json") to fetch("manifest.json.sig")
            } catch (_: Exception) {
                null // mất mạng: dùng bản đã cất nếu có
            }
            if (fetched != null) {
                val (raw, signature) = fetched
                val data = accept(raw, signature)
                if (data == null) {
                    log("danh mục nhạc: mục lục tải về sai chữ ký hay sai định dạng - giữ bản đã cất")
                } else if (current != null && data.getString("issued") < current.getString("issued")) {
                    log("danh mục nhạc: mục lục tải về cũ hơn bản đang giữ (${data.getString("issued")} < ${current.getString("issued")}) - bỏ")
                } else {
                    checkVersion(data)
                    Store.writeAtomic(path, raw)
                    Store.writeAtomic(File(dir, "manifest.json.sig"), signature)
                    current = data
                }
                rejected = current == null
            }
        }
        if (current == null) {
            throw CatalogError(if (rejected) "Danh mục nhạc nền tải về không có chữ ký hợp lệ - app không dùng." else "Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.")
        }
        checkVersion(current)
        if (manifest?.optString("revision") != current.optString("revision")) parts.clear()
        manifest = current
        current
    }

    fun playlists(): List<JSONObject> = Playlists.catalogue(manifest())

    /**
     * Một mảnh của danh mục. Phải khớp sha256 trong `files` của mục lục đã ký - không có trong `files` hay lệch thì null (coi như mảnh vắng,
     * các bài trong đó như không có), có ghi nhật ký. Mảnh đã cất cũng kiểm; lệch thì tải lại.
     */
    private fun part(relative: String): JSONObject? {
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
            JSONObject(String(raw, Charsets.UTF_8))
        } catch (_: JSONException) {
            log("danh mục nhạc: mảnh $relative không phải JSON - bỏ")
            return null
        }
        synchronized(lock) { parts[key] = value }
        return value
    }

    /** Dữ liệu đã gắn cho các link (link không có trong danh mục thì vắng). Các mảnh chưa cất tải song song. */
    fun lookup(links: List<String>): Map<String, JSONObject> {
        val existing = manifest().optJSONArray("shards")?.let { list -> (0 until list.length()).map { list.optString(it) }.toSet() } ?: emptySet()
        val wanted = links.groupBy(::shardOf).filterKeys { it in existing }
        val pool = Executors.newFixedThreadPool(SHARD_WORKERS)
        val loaded = try {
            wanted.keys.map { shard -> shard to pool.submit<JSONObject?> { part("tracks/$shard.json") } }.associate { (shard, job) ->
                shard to try {
                    job.get()
                } catch (error: java.util.concurrent.ExecutionException) {
                    throw error.cause as? CatalogError ?: CatalogError("Không tải được danh mục nhạc nền - kiểm tra mạng.")
                }
            }
        } finally {
            pool.shutdown()
        }
        val found = LinkedHashMap<String, JSONObject>()
        for ((shard, items) in wanted) for (link in items) loaded[shard]?.optJSONObject(link)?.let { found[link] = it }
        return found
    }

    /** File bài đã tải về máy (không tải); chưa có thì null. */
    fun cached(link: String): File? = fileOf(link).takeIf { it.isFile }

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
        for (url in listOf(link) + mirrors) {
            val part = File(target.path + ".${System.nanoTime()}.part")
            try {
                open(url).use { input -> part.outputStream().use { copyCapped(input, it) } }
                if (url != link && ((size != null && part.length() != size) || sha1(part.readBytes()) != expected)) throw IOException("bản sao khác bản gốc")
                if (!part.renameTo(target) && !target.isFile) throw IOException("không ghi được")
                return target
            } catch (error: TrackTooBig) { // bản sao cùng cỡ: khỏi thử
                markTooBig(link, error.size)
                throw error
            } catch (_: Exception) {
                // thử nguồn kế
            } finally {
                part.delete()
            }
        }
        return null
    }

    companion object {
        /** Địa chỉ danh mục (như `music_catalog.DEFAULT_CATALOG`). */
        const val DEFAULT_SOURCE = "https://abook-music.ngdtuanh.workers.dev/"
        const val FORMAT = "abook-music-catalog"
        const val FORMAT_VERSION = 1
        const val MANIFEST_MAX_AGE_MS = 24L * 3600 * 1000
        /** Bài nhạc nền lớn hơn thế (bản dài 30-50 phút, có bài 110 MB) máy này không dùng - cùng `MUSIC_TRACK_MAX_MB` của server.py. */
        const val TRACK_MAX_MB = 40
        const val TRACK_MAX_BYTES = TRACK_MAX_MB * 1024L * 1024
        private const val SHARD_WORKERS = 8
        private const val USER_AGENT = "ABook (+https://github.com/ntanhpro1221/ABook)"
        private val SHA1 = Regex("[0-9a-f]{40}")

        private fun sha1(bytes: ByteArray): String = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }

        private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

        /** Nhật ký mặc định; `android.util.Log` không chạy trong bài thử JVM nên nuốt lỗi (test truyền bộ ghi riêng). */
        private fun logWarning(message: String) {
            runCatching { android.util.Log.w("MusicCatalog", message) }
        }

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
                throw IOException("HTTP ${connection.responseCode}")
            }
            return Sized(connection.inputStream, connection.contentLengthLong.takeIf { it >= 0 })
        }
    }
}
