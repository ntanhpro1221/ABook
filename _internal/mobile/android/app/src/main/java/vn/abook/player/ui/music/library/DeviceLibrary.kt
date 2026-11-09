package vn.abook.player.ui.music.library

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import org.json.JSONObject
import vn.abook.player.AndroidMusicStudent
import vn.abook.player.DeviceMusic
import vn.abook.player.MusicLibrary
import vn.abook.player.Playlists

/**
 * Kho nhạc thật của điện thoại: danh mục ký số ([DeviceMusic.catalog]: mục lục + mọi mảnh bài, đã cất thì đọc đĩa - mất mạng vẫn mở được kho),
 * sổ bài đã lưu ([DeviceMusic.saved], ghim khỏi bộ dọn), tải bằng đúng đường tải của trình phát (kiểm byte + sha1, tải tiếp, bản sao).
 * Không cần máy tính.
 */
class AndroidLibrarySource(context: Context) : LibrarySource {
    private val app = context.applicationContext
    private val catalog get() = DeviceMusic.catalog(app)
    private val savedTracks get() = DeviceMusic.saved(app)
    @Volatile private var infos: Map<String, JSONObject> = emptyMap()

    override fun load(): LibraryIndex {
        val manifest = catalog.manifest()
        val raw = catalog.everything()
        infos = raw
        val taxonomy = manifest.optJSONObject("taxonomy")
        fun labels(key: String): List<Label> = taxonomy?.optJSONObject(key)?.let { map -> map.keys().asSequence().map { Label(it, map.optString(it)) }.toList() } ?: emptyList()
        val playlists = Playlists.catalogue(manifest).map { item ->
            val links = item.optJSONArray("tracks")
            LibraryPlaylist(item.optString("id"), item.optString("name"), (0 until (links?.length() ?: 0)).map { links!!.optString(it) })
        }
        return LibraryIndex(MusicLibrary.tracksOf(raw), playlists, labels("styles"), labels("emotions"))
    }

    override fun downloaded(links: Collection<String>): Set<String> = catalog.downloaded(links)
    override fun saved(): List<String> = savedTracks.links()
    override fun save(links: List<String>) {
        savedTracks.add(links)
    }

    override fun unsave(links: List<String>) {
        savedTracks.remove(links)
        for (link in links) catalog.forget(link)
    }

    override fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean) {
        val info = infos[link] ?: catalog.lookup(listOf(link))[link]
        catalog.download(link, info, progress = progress, cancelled = cancelled) ?: throw java.io.IOException()
    }

    override fun forget(link: String) = catalog.forget(link)
    override fun partial(link: String): Long = catalog.partial(link)
    override fun metered(): Boolean = AndroidMusicStudent.metered(app)

    override fun online(): Boolean {
        val manager = app.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return true
        val caps = manager.activeNetwork?.let { manager.getNetworkCapabilities(it) } ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    /** File đã tải của bài (nghe thử không mạng) hay null. */
    fun cached(link: String) = catalog.cached(link)
}

/** Nghe thử bằng MediaPlayer: file đã tải nếu có, không thì phát thẳng từ link gốc. Luồng âm thanh "nhạc" - không giành tiêu điểm của sách (sách đã dừng). */
class MediaPreviewPlayer(private val source: AndroidLibrarySource) : PreviewPlayer {
    private var player: MediaPlayer? = null

    override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit) {
        stop()
        val made = MediaPlayer()
        player = made
        runCatching {
            made.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
            val file = source.cached(link)
            if (file != null) made.setDataSource(file.path) else made.setDataSource(link)
            made.setVolume(volume, volume)
            made.setOnPreparedListener { prepared ->
                if (player !== prepared) return@setOnPreparedListener
                if (startSeconds > 0) prepared.seekTo((startSeconds * 1000).toInt())
                prepared.start()
            }
            made.setOnCompletionListener { onEnd() }
            made.setOnErrorListener { _, _, _ -> onEnd(); true }
            made.prepareAsync()
        }.onFailure { onEnd() }
    }

    override fun stop() {
        val held = player ?: return
        player = null
        runCatching { held.stop() }
        held.release()
    }
}
