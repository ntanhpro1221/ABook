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
 * `{levelDb, tracks: {"music/<sha1>.mp3": {...}}, chapters: {"<id>": [{start, end, track, gainDb, steps?, sibling?}]}}`
 * (`levelDb` = nhạc thấp hơn giọng bao nhiêu LU; `gainDb` tính sẵn cho từng bài ở máy chủ; `steps` / `sibling`: [MusicCues]).
 * File bài lấy cùng đường với
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
    private const val STEP_MS = 50L
    private const val SEEK_JUMP_SECONDS = 3.0
    private const val PAUSE_GRACE_MS = 2500L
    private const val MAX_STEP_SECONDS = 3.0 // đồng hồ nhạc không nhảy xa khi máy ngủ giữa hai nhịp
    private const val SAVE_EVERY_MS = 5000L
    private const val PREFS = "music_bed"
    private val CREDIT_KEYS = listOf("title", "creator", "attribution", "landing", "license", "licenseUrl")

    /** Một bài đang kêu. `goal` = âm lượng đang hướng tới, `perTick` = mỗi nhịp STEP_MS nhích bao nhiêu; `entering` = đang mờ vào
     *  (tua lúc này không nhảy thẳng tới mức); `cue` = mốc đang phát (bước âm lượng), null với danh sách phát. */
    private class Bed(val track: String, val player: ExoPlayer, var goal: Float, var perTick: Float, var cue: MusicCues.Cue?) {
        var entering = true
        var fadeStep = 0.001f // âm lượng bớt mỗi nhịp khi mờ đi: bài to và bài nhỏ cùng tắt trong cùng thời gian
    }

    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private var context: Context? = null
    private var book = ""
    private var music: JSONObject? = null
    private var chapter = Int.MIN_VALUE
    private var cues: List<MusicCues.Cue> = emptyList()
    private var gain = 0.1f
    private var playing = false
    private var lastSeconds = 0.0
    private var current: Bed? = null
    private val fading = mutableListOf<Bed>()
    private var fadingTicker = false
    // Bài không phát được -> lúc được thử lại: tải hỏng (mất mạng) thì sau RETRY_MS, file hỏng thì không bao giờ trong phiên.
    private val failed = MusicFailures { SystemClock.elapsedRealtime() }

    // ---- danh sách phát ("Nghe ngay") ----
    private var playlist: String? = null // danh sách đang dùng cho cuốn này; null = nhạc theo mốc của sách (hay không nhạc)
    private val queue = PlaylistQueue(failed) // hàng bài trên đồng hồ nhạc, trừ bài đang bị bỏ tạm
    private var infos: Map<String, JSONObject> = emptyMap()
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

    /** Có bài nhạc của sách ở chương này đang bị bỏ vì không phát được (đoạn ấy im lặng, chờ thử lại) - giao diện nói ra thay vì chỉ
     *  "Nhạc nền: Bật" (ui/src/listen/musicBed.ts `failing`, soát a26 L7). */
    fun brokenHere(): Boolean = playlist == null && cues.any { isFailed(it.track) }

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
            cues = MusicCues.of(music, chapterId)
        }
        val seeked = abs(seconds - lastSeconds) > SEEK_JUMP_SECONDS
        lastSeconds = seconds
        playing = isPlaying
        val cue = MusicCues.at(cues, seconds, failed)
        if (cue?.track != current?.track || (seeked && cue != null && current == null)) {
            switchTo(cue?.let { (it.track to Streaming.chapterUri(appContext, book, it.track)) },
                cue?.let { MusicCues.targetGain(it, seconds, gain) } ?: gain, seconds - (cue?.start ?: 0.0), cue)
        } else if (cue != null) {
            current?.cue = cue // cùng bài sang mốc kề: chơi tiếp, bước âm lượng theo mốc mới
            // Vừa tua trong cùng bài: dời nhạc theo chỗ mới, không chơi tiếp từ chỗ cũ (soát a26 L8).
            if (seeked) current?.player?.let { player -> MusicCues.offsetMs(cue, seconds, player.duration)?.let(player::seekTo) }
        }
        retarget(seconds, seeked)
        applyPlaying()
    }

    /** Mức đích của bài đang kêu đổi (sang bước âm lượng mới): trượt dần [MusicCues.STEP_RAMP_MS]; vừa tua thì vào thẳng mức mới
     *  (trừ lúc bài đang mờ vào). */
    private fun retarget(seconds: Double, seeked: Boolean) {
        val bed = current ?: return
        val cue = bed.cue ?: return
        val goal = MusicCues.targetGain(cue, seconds, gain)
        if (abs(goal - bed.goal) < 1e-6f) return
        bed.goal = goal
        when {
            bed.entering -> bed.perTick = goal * STEP_MS / (if (cue.sibling) MusicCues.SIBLING_FADE_MS else MusicCues.FADE_MS)
            seeked -> {
                bed.player.volume = goal
                return
            }
            else -> bed.perTick = abs(goal - bed.player.volume) * STEP_MS / MusicCues.STEP_RAMP_MS
        }
        startFade()
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
        queue.clear()
        infos = emptyMap()
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

    /** Cuốn không có nhạc của người làm sách: nạp hàng bài của danh sách phát ở luồng nền - người nghe đã chọn, hay (chưa chọn gì) máy tự chọn
     *  ([Playlists.autoPlaylist]); "off" là tắt. Máy chọn thì chỉ biết mã sau khi đọc chữ sách, nên danh sách vào việc ở lần nạp xong. */
    private fun openPlaylist(appContext: Context, bookId: String) {
        val dir = Store.bookDir(bookId)
        val changes = BookEdits.load(dir).optJSONObject("music") ?: JSONObject()
        val stored = changes.optString("playlist")
        if (stored == Playlists.OFF) return
        val levelDb = changes.optDouble("levelDb", -20.0).takeIf { it.isFinite() } ?: -20.0
        if (stored.isNotEmpty()) {
            playlist = stored
            clockSeconds = prefs(appContext).getFloat(clockKey(), 0f).toDouble()
        }
        val ticket = generation
        worker.execute {
            val choice = stored.ifEmpty { runCatching { autoChoice(appContext, dir) }.getOrNull() }
            val (tracks, found) = choice?.let { runCatching { resolve(appContext, it, levelDb) }.getOrNull() } ?: (emptyList<Playlists.Track>() to emptyMap())
            main.post {
                if (ticket != generation) return@post
                if (stored.isEmpty()) {
                    if (choice == null) return@post // máy không chọn được: không nhạc
                    playlist = choice
                    clockSeconds = prefs(appContext).getFloat(clockKey(), 0f).toDouble()
                }
                infos = found
                queue.load(tracks)
                syncPlaylist(playing)
            }
        }
    }

    /** Danh sách máy chọn cho cuốn ở `dir` (luồng nền): luật của mục lục danh mục, chưa tải được danh mục thì luật đóng kèm app. */
    private fun autoChoice(appContext: Context, dir: java.io.File): String? {
        val manifest = runCatching { DeviceMusic.catalog(appContext).manifest() }.getOrNull()
        return Playlists.autoPlaylist(dir, manifest, DeviceMusic.bundledPicker(appContext))
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
        // Bài quá MusicCatalog.TRACK_MAX_MB (theo `bytes` của danh mục, hay lần tải trước) không vào hàng: bài sau dồn lên, như máy tính.
        return Playlists.queue(links, found, levelDb) { catalog.usable(it, found[it]) } to found
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
            var tooBig = false
            val file = try {
                DeviceMusic.catalog(appContext).download(link, info)
            } catch (_: MusicCatalog.TrackTooBig) {
                tooBig = true
                null
            } catch (_: Exception) {
                null
            }
            main.post {
                downloading.remove(link)
                when {
                    file != null -> {}
                    tooBig -> drop(link) // quá MusicCatalog.TRACK_MAX_MB: máy này không dùng bài ấy, bài khác thay
                    else -> { // không tải được (mạng, nguồn gỡ bài): bỏ qua bài này một lúc, lùi dần, có hạn
                        failed.dropDownload(link)
                        replan(link)
                    }
                }
            }
        }
    }

    /** Bài không phát được (`retry`: phát hỏng - thử lại sau [MusicFailures.RETRY_MS]; không thì cả phiên): với danh sách phát, các bài sau
     *  dồn lên thay vì im lặng suốt khoảng của nó. Trước đây tải hỏng một lần lúc mất mạng là bài ấy im tới khi mở lại cuốn. */
    private fun drop(link: String, retry: Boolean = false) {
        failed.drop(link, retry)
        replan(link)
    }

    private fun replan(link: String) {
        if (playlist != null) queue.drop(link, current?.track)
    }

    private fun isFailed(link: String): Boolean = failed.isFailed(link)

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
        // Sắp đổi bài: bài bỏ tạm vì mất mạng đã tới lúc thử lại thì về hàng (PlaylistQueue.at) - ngay lúc này chứ không giữa bài.
        val found = queue.at(clockSeconds, current?.track)
        if (found == null) {
            if (current != null) switchTo(null, 1f, 0.0)
            return
        }
        val (span, offset) = found
        if (span.index != queue.currentSpan) {
            val uri = uriOf(appContext, span.track.link)
            if (uri != null) {
                queue.currentSpan = span.index
                switchTo(span.track.link to uri, 10.0.pow(minOf(0.0, span.track.gainDb) / 20.0).toFloat(), offset)
            } else if (current != null) {
                switchTo(null, 1f, 0.0) // bài này đang tải: bài trước mờ đi, bài này vào ngay khi có file
            }
            // Bài kế tải sẵn trong lúc bài này chơi: sang bài không phải chờ mạng.
            queue.spans.getOrNull((span.index + 1) % queue.spans.size)?.let { next -> fetch(appContext, next.track.link) }
        }
        applyPlaying()
        if (SystemClock.elapsedRealtime() - savedAt > SAVE_EVERY_MS) saveClock()
    }

    // ---- nhạc theo mốc của sách --------------------------------------------------------------------------------

    /** Bài đang kêu mờ đi; `next` = (tên bài, file) thì bài ấy vào, bắt đầu ở giây `offsetSeconds` của nó, lên tới `targetGain`.
     *  `cue`: mốc của sách (bước âm lượng; mốc `sibling` = nối bài anh em ở điểm kết bài: mờ chéo [MusicCues.SIBLING_FADE_MS], bài cũ
     *  chơi nốt rồi thôi, không quay lại đầu bài). */
    private fun switchTo(next: Pair<String, Uri>?, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue? = null) {
        val fadeMs = if (cue?.sibling == true) MusicCues.SIBLING_FADE_MS else MusicCues.FADE_MS
        current?.let {
            it.fadeStep = maxOf(it.player.volume, 0.01f) * STEP_MS / fadeMs
            if (cue?.sibling == true) it.player.repeatMode = Player.REPEAT_MODE_OFF
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
                        failed.forget(track)
                        val duration = player.duration
                        // Nhạc của sách tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất của chương (soát a26 L8).
                        val latest = if (cue != null && current?.player === player) MusicCues.offsetMs(cue, lastSeconds, duration) else null
                        if (duration > 0) player.seekTo(latest ?: (offsetMs % duration))
                    }
                }
            })
            player.addListener(object : Player.Listener {
                // Nhạc của sách hỏng (file thiếu trong gói, mạng tới máy tính rớt khi nghe thẳng): đoạn này im lặng, RETRY_MS sau thử
                // lại như máy tính. Bài của danh sách phát phát hỏng (file hỏng) thì bỏ cả phiên - tải hỏng đã có fetch lo.
                override fun onPlayerError(error: PlaybackException) {
                    main.post {
                        drop(track, retry = playlist == null)
                        player.release()
                        if (current?.player === player) {
                            current = null
                            queue.currentSpan = -1
                        }
                        fading.removeAll { it.player === player }
                    }
                }
            })
            player.setMediaItem(MediaItem.fromUri(uri))
            player.prepare()
            if (playing) player.play()
            current = Bed(track, player, targetGain, targetGain * STEP_MS / fadeMs, cue)
        }
        startFade()
    }

    private fun startFade() {
        if (fadingTicker) return
        fadingTicker = true
        main.post(object : Runnable {
            override fun run() {
                var busy = false
                current?.let { bed ->
                    val player = bed.player
                    player.volume = MusicCues.toward(player.volume, bed.goal, bed.perTick)
                    if (abs(player.volume - bed.goal) < 1e-4f) bed.entering = false else busy = true
                }
                val iterator = fading.iterator()
                while (iterator.hasNext()) {
                    val bed = iterator.next()
                    bed.player.volume = maxOf(0f, bed.player.volume - bed.fadeStep)
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
}
