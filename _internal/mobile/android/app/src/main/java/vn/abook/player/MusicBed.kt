package vn.abook.player

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import org.json.JSONObject
import java.util.concurrent.Executors
import kotlin.math.abs
import kotlin.math.pow

/**
 * Nhạc nền dưới giọng đọc - bản Android của ui/src/listen/musicBed.ts.
 *
 * Mốc nhạc từng chương nằm ở mục `music` của book.json (file `.abook` hay gói tải qua Wi-Fi - webui/music_plan.package):
 * `{levelDb, tracks: {"music/<sha1>.mp3": {...}}, chapters: {"<id>": [{start, end, track, gainDb}]}}`
 * (`levelDb` = nhạc thấp hơn giọng bao nhiêu LU; `gainDb` tính sẵn cho từng bài ở máy chủ). File bài lấy cùng đường với
 * audio chương (Streaming.chapterUri): có trên máy thì đọc thẳng, không thì nghe thẳng từ máy tính, qua bộ đệm đĩa.
 *
 * Sách KHÔNG có mục `music` (sách chỉ có chữ nghe bằng "Nghe ngay") mà người nghe đã chọn một danh sách phát (`music.playlist` của
 * lớp sửa - [Playlists]): các bài của danh sách nối nhau theo thứ tự trộn sẵn trên một đồng hồ nhạc RIÊNG của cuốn, chạy khi giọng
 * chạy, không theo giây của chương - sang chương mới nhạc chơi tiếp. Chỗ đang tới trên đồng hồ nhớ theo cuốn + danh sách
 * (SharedPreferences "music_bed"), mở lại sách là nghe tiếp đúng bài. Giọng ngừng giây lát giữa hai đoạn / hai chương thì nhạc
 * không ngắt ([PAUSE_GRACE_MS]).
 *
 * Một ExoPlayer riêng cho mỗi bài đang kêu (hai khi đang chuyển mờ), lặp liền, KHÔNG giành audio focus: trình phát giọng
 * đọc giữ focus, nhạc chỉ chạy khi giọng đang chạy (`sync` từ Playback mỗi nhịp 0,5 giây và mỗi lần phát / dừng / tua).
 * Mọi thao tác ở luồng chính, như Playback; danh mục / tải bài ở một luồng nền riêng.
 */
object MusicBed {
    private const val FADE_MS = 2000L
    private const val STEP_MS = 50L
    private const val SEEK_JUMP_SECONDS = 3.0
    private const val PAUSE_GRACE_MS = 2500L
    private const val MAX_STEP_SECONDS = 3.0 // đồng hồ nhạc không nhảy xa khi máy ngủ giữa hai nhịp
    private const val SAVE_EVERY_MS = 5000L
    private const val PREFS = "music_bed"
    private val CREDIT_KEYS = listOf("title", "creator", "attribution", "landing", "license", "licenseUrl")
    private const val RETRY_MS = 5 * 60_000L // bài tải hỏng (mất mạng): chừng ấy sau, tới lúc đổi bài, thử lại

    /** `gainDb`: độ khuếch đại máy chủ đã tính cho bài này (music_plan.cue_gain_db, ghi sẵn vào mốc khi đóng gói); null = sách
     *  xuất bởi bản cũ -> mức chung `levelDb` của cuốn. Máy điện thoại không tự tính lại, chỉ áp con số. */
    private data class Cue(val start: Double, val end: Double, val track: String, val gainDb: Double?)
    private class Bed(val track: String, val player: ExoPlayer, val gain: Float) {
        var fadeFrom = 0.01f // âm lượng lúc bắt đầu mờ đi: bài to và bài nhỏ cùng tắt trong FADE_MS
    }

    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private var context: Context? = null
    private var book = ""
    private var music: JSONObject? = null
    private var chapter = Int.MIN_VALUE
    private var cues: List<Cue> = emptyList()
    private var gain = 0.1f
    private var playing = false
    private var lastSeconds = 0.0
    private var current: Bed? = null
    private val fading = mutableListOf<Bed>()
    private var fadingTicker = false
    // Bài không phát được -> lúc được thử lại (SystemClock.elapsedRealtime): tải hỏng (mất mạng) thì sau RETRY_MS, file hỏng thì không bao giờ trong phiên.
    private val failed = mutableMapOf<String, Long>()

    // ---- danh sách phát ("Nghe ngay") ----
    private var playlist: String? = null // danh sách đang dùng cho cuốn này; null = nhạc theo mốc của sách (hay không nhạc)
    private var tracks: List<Playlists.Track> = emptyList() // cả hàng bài của danh sách, kể cả bài đang bị bỏ tạm
    private var spans: List<Playlists.Span> = emptyList()
    private var infos: Map<String, JSONObject> = emptyMap()
    private var currentSpan = -1
    private var clockSeconds = 0.0
    private var clockAt = 0L // SystemClock.elapsedRealtime của lần cộng đồng hồ gần nhất; 0 = đồng hồ đang đứng
    private var savedAt = 0L
    private var generation = 0 // mỗi lần đổi cuốn / đổi lựa chọn: kết quả nạp muộn của lần trước bị bỏ
    private val downloading = mutableSetOf<String>()
    private val grace = Runnable { holdStill() }

    fun init(appContext: Context) {
        context = appContext.applicationContext
    }

    /** Lớp sửa của cuốn `bookId` vừa đổi (nhạc bật/tắt, mức, im lặng một đoạn, danh sách phát): lần `sync` kế đọc lại. */
    fun invalidate(bookId: String) {
        if (bookId == book) book = ""
    }

    /** Bài đang kêu (tên trong gói, hay link với danh sách phát) hay null khi im lặng - cho kiểm thử trên máy. */
    val activeTrack: String? get() = current?.track

    /** Ghi công bài đang kêu (CC BY đòi nêu tên ở nơi nhạc phát) - cùng khoá với máy tính (`_music_credits` của webui/server.py):
     *  title, creator, attribution, landing, license, licenseUrl, chỉ khoá nào có. null khi im lặng hay bài không có thông tin. */
    fun credit(): JSONObject? {
        val track = current?.track ?: return null
        val info = infos[track] ?: music?.optJSONObject("tracks")?.optJSONObject(track) ?: return null
        val out = JSONObject()
        for (key in CREDIT_KEYS) info.optString(key).takeIf { it.isNotEmpty() }?.let { out.put(key, it) }
        return out.takeIf { it.length() > 0 }
    }

    /** Giọng đọc đang ở `seconds` của chương `chapterId` trong cuốn `bookId`; `isPlaying` = giọng đang chạy. */
    fun sync(bookId: String, chapterId: Int?, seconds: Double, isPlaying: Boolean) {
        val appContext = context ?: return
        if (bookId != book) {
            stop()
            failed.clear()
            book = bookId
            music = if (bookId.isEmpty()) null else Store.playableManifest(bookId)?.optJSONObject("music")
            val level = music?.optDouble("levelDb", -20.0) ?: -20.0
            gain = 10.0.pow(level.coerceIn(-40.0, -6.0) / 20.0).toFloat()
            chapter = Int.MIN_VALUE
            if (music == null && bookId.isNotEmpty()) openPlaylist(appContext, bookId)
        }
        if (playlist != null) {
            syncPlaylist(isPlaying)
            return
        }
        if ((chapterId ?: Int.MIN_VALUE) != chapter) {
            chapter = chapterId ?: Int.MIN_VALUE
            cues = cuesOf(chapterId)
        }
        val seeked = abs(seconds - lastSeconds) > SEEK_JUMP_SECONDS
        lastSeconds = seconds
        playing = isPlaying
        val cue = cues.firstOrNull { seconds >= it.start && seconds < it.end }?.takeUnless { isFailed(it.track) }
        if (cue?.track != current?.track || (seeked && cue != null && current == null)) {
            switchTo(cue?.let { (it.track to Streaming.chapterUri(appContext, book, it.track)) }, gainOf(cue), seconds - (cue?.start ?: 0.0))
        }
        applyPlaying()
    }

    /** Dừng hẳn (đổi cuốn, tắt dịch vụ phát): nhả mọi trình phát nhạc, ghi chỗ đang tới của danh sách phát. */
    fun stop() {
        main.removeCallbacks(grace)
        advanceClock()
        saveClock()
        for (bed in listOfNotNull(current) + fading) bed.player.release()
        current = null
        fading.clear()
        cues = emptyList()
        chapter = Int.MIN_VALUE
        playlist = null
        tracks = emptyList()
        spans = emptyList()
        infos = emptyMap()
        currentSpan = -1
        clockAt = 0L
        generation++
    }

    private fun applyPlaying() {
        for (bed in listOfNotNull(current) + fading) {
            if (playing && !bed.player.isPlaying) bed.player.play()
            if (!playing && bed.player.isPlaying) bed.player.pause()
        }
    }

    // ---- danh sách phát -------------------------------------------------------------------------------------------

    private fun prefs(appContext: Context) = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun clockKey() = "playlist:$book:$playlist"

    /** Cuốn không có nhạc của người làm sách: có danh sách phát người nghe đã chọn thì nạp hàng bài ở luồng nền. */
    private fun openPlaylist(appContext: Context, bookId: String) {
        val changes = BookEdits.load(Store.bookDir(bookId)).optJSONObject("music") ?: return
        val choice = changes.optString("playlist").ifEmpty { return }
        val levelDb = changes.optDouble("levelDb", -20.0).takeIf { it.isFinite() } ?: -20.0
        playlist = choice
        clockSeconds = prefs(appContext).getFloat(clockKey(), 0f).toDouble()
        val ticket = generation
        worker.execute {
            val (tracks, found) = runCatching { resolve(appContext, choice, levelDb) }.getOrDefault(emptyList<Playlists.Track>() to emptyMap())
            main.post {
                if (ticket != generation) return@post
                infos = found
                this.tracks = tracks
                spans = Playlists.timeline(tracks)
                syncPlaylist(playing)
            }
        }
    }

    /** Hàng bài của lựa chọn `choice` (luồng nền: danh mục cần mạng lần đầu): bài + thông tin bài (để tải / bản sao). */
    private fun resolve(appContext: Context, choice: String, levelDb: Double): Pair<List<Playlists.Track>, Map<String, JSONObject>> {
        if (choice == Playlists.MINE) {
            val store = DeviceMusic.store(appContext)
            val entries = store.entries().reversed() // cũ trước: bài mới nhập nối vào cuối, chỗ đang nghe không xô lệch
            val found = entries.associateBy { it.getString("link") }
            return Playlists.queue(found.keys.toList(), found, levelDb) { store.file(it) != null } to found
        }
        val catalog = DeviceMusic.catalog(appContext)
        val links = Playlists.linksOf(catalog.playlists(), choice)
        val found = if (links.isEmpty()) emptyMap() else catalog.lookup(links)
        return Playlists.queue(links, found, levelDb) to found
    }

    /** File của một bài để phát; bài danh mục chưa tải thì tải ở luồng nền (lần `sync` sau mới phát) và trả null. */
    private fun uriOf(appContext: Context, link: String): Uri? {
        if (isFailed(link)) return null
        if (link.startsWith(MusicStore.LOCAL_PREFIX)) return DeviceMusic.store(appContext).file(link)?.let { Uri.fromFile(it) }
        val catalog = DeviceMusic.catalog(appContext)
        catalog.cached(link)?.let { return Uri.fromFile(it) }
        fetch(appContext, link)
        return null
    }

    private fun fetch(appContext: Context, link: String) {
        if (isFailed(link) || link.startsWith(MusicStore.LOCAL_PREFIX) || !downloading.add(link)) return
        val info = infos[link]
        worker.execute {
            val file = runCatching { DeviceMusic.catalog(appContext).download(link, info) }.getOrNull()
            main.post {
                downloading.remove(link)
                if (file == null) drop(link, retry = true) // không tải được (mạng, nguồn gỡ bài): bỏ qua bài này một lúc
            }
        }
    }

    /** Bài không phát được (`retry`: tải hỏng - thử lại sau [RETRY_MS]; không thì cả phiên): với danh sách phát, các bài sau dồn lên thay vì
     *  im lặng suốt khoảng của nó. Trước đây tải hỏng một lần lúc mất mạng là bài ấy im tới khi mở lại cuốn. */
    private fun drop(link: String, retry: Boolean = false) {
        failed[link] = if (retry) SystemClock.elapsedRealtime() + RETRY_MS else Long.MAX_VALUE
        if (playlist == null || spans.none { it.track.link == link }) return
        rebuild()
    }

    private fun isFailed(link: String): Boolean = (failed[link] ?: return false) > SystemClock.elapsedRealtime()

    /** Bỏ các bài đã hết hạn chờ khỏi danh sách hỏng; true nếu hàng bài của danh sách phát vì thế đổi. */
    private fun retryDue(): Boolean {
        val now = SystemClock.elapsedRealtime()
        val due = failed.filterValues { it <= now }.keys
        if (due.isEmpty()) return false
        failed.keys.removeAll(due)
        if (playlist == null || tracks.none { it.link in due }) return false
        rebuild()
        return true
    }

    private fun rebuild() {
        spans = Playlists.timeline(tracks.filter { !isFailed(it.link) })
        currentSpan = spans.firstOrNull { it.track.link == current?.track }?.index ?: -1
    }

    private fun advanceClock() {
        val now = SystemClock.elapsedRealtime()
        if (playlist != null && playing && clockAt != 0L) clockSeconds += minOf((now - clockAt) / 1000.0, MAX_STEP_SECONDS)
        clockAt = if (playing) now else 0L
    }

    private fun saveClock() {
        val appContext = context ?: return
        if (playlist == null) return
        prefs(appContext).edit().putFloat(clockKey(), clockSeconds.toFloat()).apply()
        savedAt = SystemClock.elapsedRealtime()
    }

    /** Giọng dừng hẳn (quá [PAUSE_GRACE_MS]): nhạc dừng theo, đồng hồ đứng, ghi chỗ. */
    private fun holdStill() {
        advanceClock()
        playing = false
        clockAt = 0L
        applyPlaying()
        saveClock()
    }

    private fun syncPlaylist(isPlaying: Boolean) {
        val appContext = context ?: return
        if (isPlaying) {
            main.removeCallbacks(grace)
            if (!playing) {
                playing = true
                clockAt = SystemClock.elapsedRealtime()
            }
            advanceClock()
        } else if (playing) {
            // Giọng vừa ngừng: có thể chỉ là chỗ nối hai đoạn / hai chương - chờ một chút rồi mới dừng nhạc.
            main.removeCallbacks(grace)
            main.postDelayed(grace, PAUSE_GRACE_MS)
        }
        val found = Playlists.at(spans, clockSeconds)
        if (found == null) {
            if (current != null) switchTo(null, 1f, 0.0)
            return
        }
        val (span, offset) = found
        if (span.index != currentSpan) {
            // Sắp đổi bài: bài bỏ tạm vì mất mạng đã tới lúc thử lại thì đưa về hàng - ngay lúc này chứ không giữa bài, nhạc không nhảy.
            if (retryDue()) return syncPlaylist(isPlaying)
            val uri = uriOf(appContext, span.track.link)
            if (uri != null) {
                currentSpan = span.index
                switchTo(span.track.link to uri, 10.0.pow(minOf(0.0, span.track.gainDb) / 20.0).toFloat(), offset)
            } else if (current != null) {
                switchTo(null, 1f, 0.0) // bài này đang tải: bài trước mờ đi, bài này vào ngay khi có file
            }
            // Bài kế tải sẵn trong lúc bài này chơi: sang bài không phải chờ mạng.
            spans.getOrNull((span.index + 1) % spans.size)?.let { next -> fetch(appContext, next.track.link) }
        }
        applyPlaying()
        if (SystemClock.elapsedRealtime() - savedAt > SAVE_EVERY_MS) saveClock()
    }

    // ---- nhạc theo mốc của sách --------------------------------------------------------------------------------

    private fun cuesOf(chapterId: Int?): List<Cue> {
        val tracks = music?.optJSONObject("tracks") ?: return emptyList()
        val list = music?.optJSONObject("chapters")?.optJSONArray(chapterId?.toString() ?: return emptyList())
            ?: return emptyList()
        return (0 until list.length()).mapNotNull { index ->
            val cue = list.optJSONObject(index) ?: return@mapNotNull null
            val track = cue.optString("track")
            if (!TRACK.matches(track) || !tracks.has(track)) null
            else Cue(
                cue.optDouble("start", 0.0), cue.optDouble("end", 0.0), track,
                if (cue.has("gainDb")) cue.optDouble("gainDb").takeIf { it.isFinite() } else null,
            )
        }
    }

    /** Âm lượng mục tiêu của bài: gainDb của mốc, không có
     *  thì mức chung. Tối đa 1 (ExoPlayer). */
    private fun gainOf(cue: Cue?): Float =
        cue?.gainDb?.let { 10.0.pow(it.coerceAtMost(0.0) / 20.0).toFloat() } ?: gain

    /** Bài đang kêu mờ đi; `next` = (tên bài, file) thì bài ấy vào, bắt đầu ở giây `offsetSeconds` của nó, lên tới `targetGain`. */
    private fun switchTo(next: Pair<String, Uri>?, targetGain: Float, offsetSeconds: Double) {
        current?.let {
            it.fadeFrom = maxOf(it.player.volume, 0.01f)
            fading += it
        }
        current = null
        val appContext = context ?: return
        if (next != null) {
            val (track, uri) = next
            val player = ExoPlayer.Builder(appContext)
                .setAudioAttributes(
                    AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                    false,
                )
                .setMediaSourceFactory(Streaming.mediaSourceFactory(appContext))
                .build()
            player.repeatMode = Player.REPEAT_MODE_ONE
            player.volume = 0f
            val offsetMs = (offsetSeconds.coerceAtLeast(0.0) * 1000).toLong()
            player.addListener(object : Player.Listener {
                override fun onPlaybackStateChanged(state: Int) {
                    if (state == Player.STATE_READY) {
                        player.removeListener(this)
                        val duration = player.duration
                        if (duration > 0) player.seekTo(offsetMs % duration)
                    }
                }
            })
            player.addListener(object : Player.Listener {
                // Điện thoại không tự tải nhạc của sách từ mạng: file thiếu trong gói / máy tính không phát được thì cho đoạn này im lặng.
                override fun onPlayerError(error: PlaybackException) {
                    main.post {
                        drop(track)
                        player.release()
                        if (current?.player === player) {
                            current = null
                            currentSpan = -1
                        }
                        fading.removeAll { it.player === player }
                    }
                }
            })
            player.setMediaItem(MediaItem.fromUri(uri))
            player.prepare()
            if (playing) player.play()
            current = Bed(track, player, targetGain)
        }
        startFade()
    }

    private fun startFade() {
        if (fadingTicker) return
        fadingTicker = true
        val step = STEP_MS.toFloat() / FADE_MS
        main.post(object : Runnable {
            override fun run() {
                var busy = false
                current?.let { bed ->
                    val player = bed.player
                    if (player.volume < bed.gain) {
                        player.volume = minOf(bed.gain, player.volume + step * bed.gain)
                        busy = busy || player.volume < bed.gain
                    }
                }
                val iterator = fading.iterator()
                while (iterator.hasNext()) {
                    val bed = iterator.next()
                    bed.player.volume = maxOf(0f, bed.player.volume - step * bed.fadeFrom)
                    if (bed.player.volume <= 0.001f) {
                        bed.player.release()
                        iterator.remove()
                    } else {
                        busy = true
                    }
                }
                if (busy) main.postDelayed(this, STEP_MS) else fadingTicker = false
            }
        })
    }

    // Bài danh mục luôn .mp3; bài người dùng nhập ("Nhạc của tôi") giữ định dạng của file (music_plan.TRACK_EXTENSIONS).
    private val TRACK = Regex("music/[0-9a-f]{40}\\.(?:mp3|m4a|ogg|opus|flac|wav)")
}
