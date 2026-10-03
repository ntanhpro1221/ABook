package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors

/**
 * Danh mục nhạc nền trên mây cho điện thoại - bản Kotlin của phần abook/webui/music_catalog.py mà "Nghe ngay" cần: mục lục
 * (`manifest.json`, giữ 24 giờ, mất mạng thì dùng bản đã cất), mảnh dữ liệu bài (`tracks/<xx>.json`, cất theo `revision`), và file bài
 * (tải một lần từ link gốc, hỏng thì bản sao `mirrors` phải khớp `sha1` + `bytes` như `server.music_track_file`). Không khoá, không
 * đăng nhập: chỉ là file tĩnh. Mọi lời gọi chặn - chạy ở luồng nền.
 *
 * `open(url)` mở một địa chỉ (http(s) hay đường dẫn thư mục cho test JVM) - chỉ đọc, không gửi gì ngoài User-Agent.
 */
class MusicCatalog(
    private val dir: File,
    source: String = DEFAULT_SOURCE,
    private val open: (String) -> InputStream = ::openUrl,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    /** Danh mục không đọc được (mất mạng lần đầu, định dạng mới hơn app). Câu chữ để người dùng đọc - như `CatalogError` bên Python. */
    class CatalogError(message: String) : Exception(message)

    private val source = source.trimEnd('/') + "/"
    private val remote = this.source.startsWith("http://") || this.source.startsWith("https://")
    private val lock = Any()
    private var manifest: JSONObject? = null
    private val parts = HashMap<String, JSONObject>()

    private fun fetch(relative: String): ByteArray = open(source + relative).use { it.readBytes() }

    /** Mục lục danh mục (cất ở `dir/manifest.json`, làm mới sau [MANIFEST_MAX_AGE_MS]); mất mạng thì bản đã cất. */
    fun manifest(): JSONObject = synchronized(lock) {
        val path = File(dir, "manifest.json")
        val fresh = path.isFile && clock() - path.lastModified() < MANIFEST_MAX_AGE_MS
        manifest?.takeIf { fresh }?.let { return it }
        var data: JSONObject? = null
        if (!fresh) {
            data = try {
                val raw = fetch("manifest.json")
                JSONObject(String(raw, Charsets.UTF_8)).also { Store.writeAtomic(path, raw) }
            } catch (_: Exception) {
                null // mất mạng: dùng bản đã cất nếu có
            }
        }
        if (data == null) {
            data = try {
                JSONObject(path.readText(Charsets.UTF_8))
            } catch (_: Exception) {
                throw CatalogError("Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.")
            }
        }
        if (data.optString("format") != FORMAT || data.opt("version") !is Int) throw CatalogError("Danh mục nhạc nền không đúng định dạng.")
        if (data.getInt("version") > FORMAT_VERSION) throw CatalogError("Danh mục nhạc nền mới hơn app - hãy cập nhật app.")
        if (manifest?.optString("revision") != data.optString("revision")) parts.clear()
        manifest = data
        data
    }

    fun playlists(): List<JSONObject> = Playlists.catalogue(manifest())

    private fun part(relative: String): JSONObject {
        val revision = manifest().getString("revision")
        val key = "$revision/$relative"
        synchronized(lock) { parts[key]?.let { return it } }
        val path = Store.contained(File(dir, revision), relative)
        val value = runCatching { JSONObject(path.readText(Charsets.UTF_8)) }.getOrNull() ?: run {
            // Mã phiên bản trong đường dẫn: CDN đệm mảnh 1 giờ - danh mục mới là đường dẫn mới, không lẫn mảnh cũ.
            val raw = try {
                fetch(if (remote) "$relative?v=$revision" else relative)
            } catch (error: IOException) {
                throw CatalogError("Không tải được danh mục nhạc nền - kiểm tra mạng.")
            }
            JSONObject(String(raw, Charsets.UTF_8)).also { runCatching { Store.writeAtomic(path, raw) } }
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
            wanted.keys.map { shard -> shard to pool.submit<JSONObject> { part("tracks/$shard.json") } }.associate { (shard, job) ->
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

    private fun fileOf(link: String) = File(File(dir, "files"), sha1(link.toByteArray(Charsets.UTF_8)) + ".mp3")

    /**
     * Tải bài `link` của danh mục về máy (đã có thì thôi): link gốc trước, hỏng thì bản sao trong `info.mirrors` - chỉ khi danh mục ghi
     * `sha1` của bản gốc, và bản sao phải khớp `sha1` (và `bytes`) mới dùng, không phát nhầm bài. Không lấy được thì null.
     */
    fun download(link: String, info: JSONObject?): File? {
        if (!link.startsWith("https://")) return null
        val target = fileOf(link)
        if (target.isFile) return target
        val expected = info?.optString("sha1")?.lowercase()?.takeIf { SHA1.matches(it) }
        val size = (info?.opt("bytes") as? Number)?.toLong()
        val mirrors = info?.optJSONArray("mirrors")?.takeIf { expected != null }?.let { list ->
            (0 until list.length()).mapNotNull { (list.opt(it) as? String)?.takeIf { url -> url.startsWith("https://") } }
        } ?: emptyList()
        target.parentFile?.mkdirs()
        for (url in listOf(link) + mirrors) {
            val part = File(target.path + ".${System.nanoTime()}.part")
            try {
                open(url).use { input -> part.outputStream().use { input.copyTo(it, 1 shl 16) } }
                if (url != link && ((size != null && part.length() != size) || sha1(part.readBytes()) != expected)) throw IOException("bản sao khác bản gốc")
                if (!part.renameTo(target) && !target.isFile) throw IOException("không ghi được")
                return target
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
        private const val SHARD_WORKERS = 8
        private const val USER_AGENT = "ABook (+https://github.com/ntanhpro1221/ABook)"
        private val SHA1 = Regex("[0-9a-f]{40}")

        private fun sha1(bytes: ByteArray): String = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }

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
            return connection.inputStream
        }
    }
}
