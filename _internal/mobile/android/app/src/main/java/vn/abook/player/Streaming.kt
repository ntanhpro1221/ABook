package vn.abook.player

import android.content.Context
import android.net.Uri
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import androidx.media3.database.StandaloneDatabaseProvider
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.datasource.cache.CacheDataSource
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor
import androidx.media3.datasource.cache.SimpleCache
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.extractor.DefaultExtractorsFactory
import androidx.media3.extractor.Extractor
import androidx.media3.extractor.ExtractorsFactory
import androidx.media3.extractor.mp3.Mp3Extractor
import vn.abook.player.readaloud.LiveClips
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Nghe thẳng thư viện máy tính mà không tải về (stream play): chương nào đã có file trên máy thì phát file, chưa có thì
 * phát qua mạng từ máy tính đã ghép (webui/sync.py - cùng các đường tải sách, có tua theo byte).
 *
 * Audio đi qua bộ đệm đĩa của Media3 (giới hạn [CACHE_BYTES], bỏ cái ít dùng nhất): tua lại hay nghe lại không tải
 * lại, và Wi-Fi chập chờn không cắt ngang đoạn đã đệm. Khoá đệm gồm cả kích thước file trong gói sách: máy tính thu lại
 * một chương (file cùng tên, khác nội dung) thì điện thoại không phát nhầm bản cũ.
 */
@OptIn(UnstableApi::class)
object Streaming {
    private const val CACHE_BYTES = 1024L * 1024 * 1024
    private var cache: SimpleCache? = null

    @Synchronized
    private fun cache(context: Context): SimpleCache = cache ?: SimpleCache(
        File(context.cacheDir, "stream-audio"),
        LeastRecentlyUsedCacheEvictor(CACHE_BYTES),
        StandaloneDatabaseProvider(context),
    ).also { cache = it }

    /**
     * Nguồn media cho ExoPlayer: file:// đọc thẳng; https:// mang mã thiết bị (đọc lại mỗi lần - ghép lại thì mã đổi). Chứng
     * chỉ máy kia được ghim ở HttpsURLConnection mặc định ([Pin.install]) - DefaultHttpDataSource đi qua đó. `exactMp3Seek`: mp3 tua
     * đúng khung ([ExactSeekMp3Extractor]) - chỉ nhạc nền bật (lặp mờ chéo vào lại đúng loopStart); audio chương giữ cách tách mặc định.
     */
    fun mediaSourceFactory(context: Context, exactMp3Seek: Boolean = false): MediaSource.Factory {
        Pin.install(context)
        val http = DefaultHttpDataSource.Factory().setConnectTimeoutMs(5000).setReadTimeoutMs(20_000)
        val authorized = ResolvingDataSource.Factory(http) { spec ->
            spec.withAdditionalHeaders(mapOf("Authorization" to "Bearer ${SyncLink.tokenFor(context, spec.uri)}"))
        }
        val cached = CacheDataSource.Factory()
            .setCache(cache(context))
            .setUpstreamDataSourceFactory(authorized)
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)
        val normal = DefaultDataSource.Factory(context, cached)
        // Clip Edge đang đọc dở của Nghe ngay (abooklive://, uxfix57) đi qua nguồn riêng; mọi thứ khác như cũ.
        val routed = DataSource.Factory { LiveRoutingDataSource(LiveClipDataSource(), normal.createDataSource()) }
        return DefaultMediaSourceFactory(routed, liveAwareExtractors(exactMp3Seek))
    }

    /**
     * Bộ tách cho clip Edge đang lớn: chỉ mp3, tua theo tốc độ bit không đổi dù chưa biết độ dài file (Edge 48 kbps CBR; clip chưa xong thì không có tiêu đề Xing / độ dài). Chỉ dùng cho `abooklive://`:
     * mp3 khác (sách audio) giữ cách tách mặc định. Kiểm bằng bài thử rằng phát được và tua được trong phần đã ghi (LiveClipsTest).
     */
    fun liveExtractors(): Array<Extractor> = arrayOf(Mp3Extractor(Mp3Extractor.FLAG_ENABLE_CONSTANT_BITRATE_SEEKING or Mp3Extractor.FLAG_ENABLE_CONSTANT_BITRATE_SEEKING_ALWAYS))

    /** Mp3Extractor của bộ mặc định đổi thành [ExactSeekMp3Extractor]; các bộ tách khác và thứ tự giữ nguyên. */
    internal fun withExactMp3Seek(extractors: Array<Extractor>): Array<Extractor> =
        Array(extractors.size) { if (extractors[it].underlyingImplementation is Mp3Extractor) ExactSeekMp3Extractor() else extractors[it] }

    private fun liveAwareExtractors(exactMp3Seek: Boolean): ExtractorsFactory {
        val normal = DefaultExtractorsFactory()
        fun exact(extractors: Array<Extractor>) = if (exactMp3Seek) withExactMp3Seek(extractors) else extractors
        return object : ExtractorsFactory {
            override fun createExtractors(): Array<Extractor> = exact(normal.createExtractors())
            override fun createExtractors(uri: Uri, responseHeaders: MutableMap<String, MutableList<String>>): Array<Extractor> =
                if (uri.scheme == LiveClips.SCHEME) liveExtractors() else exact(normal.createExtractors(uri, responseHeaders))
        }
    }

    /** Có file trên máy thì file; không thì đường tới máy tính. */
    fun chapterUri(context: Context, id: String, file: String): Uri {
        val local = runCatching { Store.file(id, file) }.getOrNull()
        if (local != null && local.isFile) return Uri.fromFile(local)
        val (link, remote) = SyncLink.linkFor(context, id)
        return Uri.parse("${link.base}/sync/v1/books/${Uri.encode(remote)}/files/${Uri.encode(file, "/")}")
    }

    /** Khoá bộ đệm: sách + file + kích thước trong gói (null = file trên máy, không qua bộ đệm). */
    fun cacheKey(id: String, file: String): String? {
        val local = runCatching { Store.file(id, file) }.getOrNull()
        if (local != null && local.isFile) return null
        val chapters = Store.playableManifest(id)?.optJSONArray("chapters")
        var size = 0L
        if (chapters != null) {
            for (index in 0 until chapters.length()) {
                val chapter = chapters.getJSONObject(index)
                if (chapter.optString("file") == file) size = chapter.optLong("size")
            }
        }
        return "$id/$file#$size"
    }

    /** Gói sách của một cuốn trên máy tính (hay thiết bị ghép - `source`, `remoteId`: Peers), cất vào `stream.json` để lần
     *  sau mở ngay cả khi mạng chậm. Gói của thiết bị ghép mang nguồn trong chính nó (SyncLink.linkFor). */
    fun fetchManifest(context: Context, id: String, source: String? = null, remoteId: String? = null): JSONObject {
        val known = Store.playableManifest(id)
        val peer = source ?: known?.optString("source")?.takeIf { it.isNotEmpty() }
        val remote = remoteId ?: known?.optString("remoteId")?.takeIf { it.isNotEmpty() } ?: id
        val manifest = JSONObject(
            if (peer != null) Peers.request(context, peer, "GET", "/sync/v1/books/$remote/manifest")
            else SyncLink.request(context, "GET", "/sync/v1/books/$id/manifest"),
        )
        if (peer != null) manifest.put("id", id).put("source", peer).put("remoteId", remote).put("sourceKind", Peers.kindOf(context, peer))
        // Gói đổi (thêm/thu lại chương, đổi bìa): bỏ văn bản và dàn nhân vật đã cất để lần đọc sau lấy bản mới.
        val previous = Store.streamManifest(id)
        if (previous != null && previous.optString("version") != manifest.optString("version")) {
            File(Store.bookDir(id), "scripts").deleteRecursively()
            File(Store.bookDir(id), "cast.json").delete()
        }
        Store.writeAtomic(File(Store.bookDir(id), "stream.json"), manifest.toString())
        return manifest
    }

    /** Chữ đọc theo (`scripts/<n>.json`) của chương `chapterId` trong cuốn nghe thẳng mà máy này chưa có: tên file trong gói; cuốn đã
     *  tải về, chương không có chữ hay chữ đã về thì null. */
    fun missingScript(id: String, chapterId: Long): String? {
        if (Store.rawManifest(id) != null) return null
        val chapters = Store.streamManifest(id)?.optJSONArray("chapters") ?: return null
        val script = (0 until chapters.length()).mapNotNull { chapters.optJSONObject(it) }
            .firstOrNull { (it.opt("id") as? Number)?.toLong() == chapterId }?.optString("script").orEmpty()
        if (script.isBlank() || script == "null" || runCatching { Store.file(id, script).isFile }.getOrDefault(true)) return null
        return script
    }

    /** Chương đang phát của cuốn nghe thẳng: đệm chữ đọc theo của nó ở nền, cùng lúc với audio - máy tính tắt sau đó thì "Đọc theo" vẫn mở
     *  được chương đã nghe (như máy tính, webui/packages.chapter_file; soát a27 lỗi 12). */
    fun keepScript(context: Context, id: String, chapterId: Long) {
        val script = missingScript(id, chapterId) ?: return
        Thread({ fetchSmall(context, id, script) }, "abook-keep-script").apply { isDaemon = true }.start()
    }

    /**
     * Một file nhỏ của gói (văn bản chương, dàn nhân vật, câu mẫu, bìa): lấy từ máy tính rồi cất đúng chỗ của sách đã
     * tải. Trả về file, hoặc null khi máy tính không có hoặc không kết nối được.
     */
    fun fetchSmall(context: Context, id: String, relative: String): File? {
        val target = runCatching { Store.file(id, relative) }.getOrNull() ?: return null
        return runCatching {
            val (link, remote) = SyncLink.linkFor(context, id)
            val connection = URL("${link.base}/sync/v1/books/$remote/files/$relative").openConnection() as HttpURLConnection
            connection.connectTimeout = 3000
            connection.readTimeout = 15_000
            connection.setRequestProperty("Authorization", "Bearer ${link.token}")
            try {
                if (connection.responseCode != 200) return@runCatching null
                target.parentFile?.mkdirs()
                val partial = File(target.path + ".part")
                partial.outputStream().use { output -> connection.inputStream.use { it.copyTo(output) } }
                // Hai lời xin cùng một file cùng lúc (giao diện xin chữ chương để hiện, trình đọc xin để đọc - soát lại uxfix75): lời kia đã đổi tên
                // `.part` thành file thật thì file ấy là bản đủ - đừng xoá nó.
                if (!partial.renameTo(target) && partial.isFile) {
                    target.delete()
                    partial.renameTo(target)
                }
                target.takeIf { it.isFile }
            } finally {
                connection.disconnect()
            }
        }.getOrNull()
    }
}
