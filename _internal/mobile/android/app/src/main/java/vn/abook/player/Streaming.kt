package vn.abook.player

import android.content.Context
import android.net.Uri
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.util.UnstableApi
import androidx.media3.database.StandaloneDatabaseProvider
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.HttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.datasource.cache.CacheDataSource
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor
import androidx.media3.datasource.cache.SimpleCache
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.extractor.DefaultExtractorsFactory
import androidx.media3.extractor.Extractor
import androidx.media3.extractor.ExtractorOutput
import androidx.media3.extractor.ExtractorsFactory
import androidx.media3.extractor.ForwardingExtractor
import androidx.media3.extractor.ForwardingExtractorOutput
import androidx.media3.extractor.ForwardingSeekMap
import androidx.media3.extractor.SeekMap
import androidx.media3.extractor.mp3.Mp3Extractor
import androidx.media3.extractor.wav.WavExtractor
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
 * lại, và Wi-Fi chập chờn không cắt ngang đoạn đã đệm. Khoá đệm gồm dấu SHA-256 của chương trong gói sách: máy tính thu lại
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
        val retrying = DataSource.Factory { RetryingDataSource(http.createDataSource()) }
        val authorized = ResolvingDataSource.Factory(retrying) { spec ->
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

    /** Chỉ replay GET khi chưa giao byte audio nào; giữ nguyên Range/DataSpec và pin TLS. */
    internal class RetryingDataSource(private val upstream: DataSource,
        private val pause: (Long) -> Unit = { Thread.sleep(it) }) : DataSource by upstream {
        override fun open(dataSpec: DataSpec): Long {
            for (attempt in 0..2) {
                try { return upstream.open(dataSpec) }
                catch (error: java.io.IOException) {
                    val busy = error is HttpDataSource.InvalidResponseCodeException && error.responseCode == 503
                    val closed = generateSequence<Throwable>(error) { it.cause }.any {
                        it is java.net.SocketException || it is java.io.EOFException || it is javax.net.ssl.SSLException
                    }
                    if (dataSpec.httpMethod != DataSpec.HTTP_METHOD_GET || attempt == 2 ||
                        Pin.isCertificateProblem(error) || (!busy && !closed)) throw error
                    runCatching { upstream.close() }
                    pause(if (attempt == 0) 200 else 800)
                }
            }
            error("unreachable")
        }
    }

    /**
     * Bộ tách cho clip đang lớn: mp3 của Edge, tua theo tốc độ bit không đổi dù chưa biết độ dài file (Edge 48 kbps CBR; clip chưa xong thì không có tiêu đề Xing / độ dài); WAV của giọng trên máy
     * ([vn.abook.player.readaloud.LocalLive]: cỡ 0xFFFFFFFF = đọc tới hết dữ liệu, [GrowingWav]). Chỉ dùng cho `abooklive://`: mp3 khác (sách audio) giữ cách tách mặc định. Kiểm bằng bài thử rằng
     * phát được và tua được trong phần đã ghi (LiveClipsTest; WAV: LiveStreamOnDeviceTest trên máy ảo).
     */
    fun liveExtractors(): Array<Extractor> =
        arrayOf(GrowingWav(), Mp3Extractor(Mp3Extractor.FLAG_ENABLE_CONSTANT_BITRATE_SEEKING or Mp3Extractor.FLAG_ENABLE_CONSTANT_BITRATE_SEEKING_ALWAYS))

    /**
     * WavExtractor cho WAV đang lớn: cỡ 0xFFFFFFFF làm nó báo độ dài ~13,5 giờ, mà ExoPlayer chỉ sang ENDED khi vị trí tới độ dài đã biết (máy ảo 20-10: phát hết tiếng rồi
     * đứng READY mãi). Độ dài thành "chưa biết" như mp3 Edge đang lớn; tua vẫn theo bảng tua của WavExtractor.
     */
    private class GrowingWav : ForwardingExtractor(WavExtractor()) {
        override fun init(output: ExtractorOutput) = super.init(object : ForwardingExtractorOutput(output) {
            override fun seekMap(seekMap: SeekMap) = super.seekMap(object : ForwardingSeekMap(seekMap) {
                override fun getDurationUs() = C.TIME_UNSET
            })
        })
    }

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

    /** Khoá bộ đệm: sách + file + SHA-256 trong gói (null = file trên máy, không qua bộ đệm). */
    fun cacheKey(id: String, file: String): String? {
        val local = runCatching { Store.file(id, file) }.getOrNull()
        if (local != null && local.isFile) return null
        val chapters = Store.playableManifest(id)?.optJSONArray("chapters")
        var digest = ""
        if (chapters != null) {
            for (index in 0 until chapters.length()) {
                val chapter = chapters.getJSONObject(index)
                if (chapter.optString("file") == file) digest = chapter.optString("sha256")
            }
        }
        return "$id/$file#$digest"
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
        PeerPaths.checkManifest(manifest)
        require(manifest.getString("id") == remote) { "Mã sách máy gửi trả về không khớp; bạn hãy thử lại." }
        if (peer != null) manifest.put("id", id).put("source", peer).put("remoteId", remote).put("sourceKind", Peers.kindOf(context, peer))
        // Gói đổi (thêm/thu lại chương, đổi bìa): chỉ bỏ chữ đọc theo của chương thật sự đổi; dàn nhân vật được thay khi tải được bản mới.
        val previous = Store.streamManifest(id)
        StreamRefresh.invalidateCover(Store.bookDir(id), previous, manifest)
        StreamRefresh.invalidateScripts(Store.bookDir(id), previous, manifest)
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
        return fetchSmallFile(target) {
            val (link, remote) = SyncLink.linkFor(context, id)
            val connection = URL("${link.base}/sync/v1/books/$remote/files/$relative").openConnection() as HttpURLConnection
            connection.connectTimeout = 3000
            connection.readTimeout = 15_000
            connection.setRequestProperty("Authorization", "Bearer ${link.token}")
            connection
        }
    }

    /** Luồng tải thật, tách phần tìm thiết bị để thử được bằng kết nối giả trên JVM. */
    internal fun fetchSmallFile(target: File, connect: () -> HttpURLConnection): File? = runCatching {
        val connection = PeerTransfer.openGet(connect = connect)
        var partial: File? = null
        try {
            if (connection.responseCode != 200) return@runCatching null
            target.parentFile?.mkdirs()
            val pending = File.createTempFile(".${target.name}.", ".part", target.parentFile)
            partial = pending
            val limit = PeerTransfer.budget(target.name)
            val expected = connection.getHeaderFieldLong("Content-Length", -1)
            if (expected > limit) throw PeerTransfer.Limit()
            java.io.FileOutputStream(pending).use { output ->
                connection.inputStream.use { PeerTransfer.copy(it, output, limit, target.parentFile!!) }
                output.fd.sync()
            }
            check(expected < 0 || pending.length() == expected) { "File tải chưa đủ; bạn hãy thử lại." }
            check(pending.renameTo(target)) { "Không lưu được file; bạn hãy thử lại." }
            target
        } finally {
            partial?.delete()
            connection.disconnect()
        }
    }.getOrNull()
}
