package vn.abook.player

import android.content.Context
import android.net.Uri
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import androidx.media3.database.StandaloneDatabaseProvider
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.datasource.cache.CacheDataSource
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor
import androidx.media3.datasource.cache.SimpleCache
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MediaSource
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
     * chỉ máy kia được ghim ở HttpsURLConnection mặc định ([Pin.install]) - DefaultHttpDataSource đi qua đó.
     */
    fun mediaSourceFactory(context: Context): MediaSource.Factory {
        Pin.install(context)
        val http = DefaultHttpDataSource.Factory().setConnectTimeoutMs(5000).setReadTimeoutMs(20_000)
        val authorized = ResolvingDataSource.Factory(http) { spec ->
            spec.withAdditionalHeaders(mapOf("Authorization" to "Bearer ${SyncLink.tokenFor(context, spec.uri)}"))
        }
        val cached = CacheDataSource.Factory()
            .setCache(cache(context))
            .setUpstreamDataSourceFactory(authorized)
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)
        return DefaultMediaSourceFactory(DefaultDataSource.Factory(context, cached))
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
                if (!partial.renameTo(target)) {
                    target.delete()
                    partial.renameTo(target)
                }
                target
            } finally {
                connection.disconnect()
            }
        }.getOrNull()
    }
}
