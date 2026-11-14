package vn.abook.player.ui.music.library

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import kotlinx.coroutines.*
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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

    /** Use the signed catalogue's source order, also used for downloads. Called off main. */
    fun previewSources(link: String): List<String> {
        cached(link)?.let { return listOf(it.toURI().toString()) }
        val info = infos[link] ?: catalog.lookup(listOf(link))[link]
        val mirrors = info?.optJSONArray("mirrors")
        return (listOf(link) + (0 until (mirrors?.length() ?: 0)).map { mirrors!!.optString(it) })
            .filter { it.isNotBlank() }.distinct()
    }
}

/** HTTPS is opened by Media3, independently of the device vendor's NuPlayer. */
@androidx.media3.common.util.UnstableApi
class ExoPreviewPlayer(context: Context, private val source: AndroidLibrarySource,
    private val sourceUrls: (String) -> List<String> = source::previewSources,
) : PreviewPlayer {
    private val app = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val handler = Handler(Looper.getMainLooper())
    private var player: ExoPlayer? = null
    private var lookup: Job? = null
    private var request = 0L
    private var deadline: Runnable? = null

    override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit, onPlaying: (Boolean) -> Unit, onError: (String) -> Unit) {
        stop()
        val token = request
        lookup = scope.launch {
            val urls = try { withContext(Dispatchers.IO) { sourceUrls(link) } }
            catch (error: CancellationException) { throw error }
            catch (_: Exception) { null }
            if (token != request) return@launch
            if (urls.isNullOrEmpty()) { onError(vn.abook.player.S.s_chua_nghe_thu_duoc_luc_nay_58b11ef5); return@launch }
            var index = 0
            fun attempt() {
                clearDeadline()
                player?.release()
                val http = DefaultHttpDataSource.Factory().setConnectTimeoutMs(8000).setReadTimeoutMs(8000).setAllowCrossProtocolRedirects(true)
                val made = ExoPlayer.Builder(app)
                    .setMediaSourceFactory(DefaultMediaSourceFactory(DefaultDataSource.Factory(app, http))).build()
                player = made
                fun next(timedOut: Boolean) {
                    if (token != request || player !== made) return
                    Log.w("MusicPreview", "source_failed index=$index timeout=$timedOut")
                    if (++index < urls.size) attempt()
                    else { stop(); onError(if (timedOut) vn.abook.player.S.s_preview_timeout else vn.abook.player.S.s_chua_nghe_thu_duoc_luc_nay_58b11ef5) }
                }
                fun watch() {
                    clearDeadline()
                    deadline = Runnable { next(true) }.also { handler.postDelayed(it, SOURCE_TIMEOUT_MS) }
                }
                made.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(), true)
                made.volume = volume
                made.addListener(object : Player.Listener {
                    override fun onIsPlayingChanged(isPlaying: Boolean) {
                        if (token != request || player !== made) return
                        onPlaying(isPlaying)
                        if (isPlaying) {
                            clearDeadline()
                            Log.i("MusicPreview", "playing index=$index positionMs=${made.currentPosition}")
                        } else if (made.playbackState != Player.STATE_ENDED) watch()
                    }
                    override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
                        if (token == request && player === made && !playWhenReady && reason == Player.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_FOCUS_LOSS) onEnd()
                    }
                    override fun onPlaybackStateChanged(state: Int) {
                        if (token != request || player !== made) return
                        if (state == Player.STATE_BUFFERING) watch()
                        if (state == Player.STATE_ENDED) onEnd()
                    }
                    override fun onPlayerError(error: PlaybackException) { next(false) }
                })
                Log.i("MusicPreview", "loading index=$index")
                made.setMediaItem(MediaItem.fromUri(urls[index]), (startSeconds.coerceAtLeast(0.0) * 1000).toLong())
                watch()
                made.prepare()
                made.play()
            }
            attempt()
        }
    }

    private fun clearDeadline() { deadline?.let(handler::removeCallbacks); deadline = null }

    override fun stop() {
        request++
        lookup?.cancel()
        lookup = null
        clearDeadline()
        val held = player
        player = null
        held?.release()
    }

    companion object { const val SOURCE_TIMEOUT_MS = 12_000L }
}
