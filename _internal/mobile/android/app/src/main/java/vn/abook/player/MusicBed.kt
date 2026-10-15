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
 * Một ExoPlayer riêng cho mỗi bài đang kêu (hai khi đang chuyển mờ), KHÔNG giành audio focus: trình phát giọng
 * đọc giữ focus, nhạc chỉ chạy khi giọng đang chạy (`sync` từ Playback mỗi nhịp 0,5 giây và mỗi lần phát / dừng / tua).
 * Mọi thao tác ở luồng chính, như Playback; danh mục / tải bài ở một luồng nền riêng.
 *
 * Nhạc của sách lặp bằng mờ chéo trong đoạn nghe được (lô 2 mix-loop, [MusicCues.loopBounds]): tới E - X một ExoPlayer MỚI của chính
 * bài vào từ A, cái cũ mờ đi trong X giây ([crossLoop]); bài quá ngắn và danh sách phát thì vẫn REPEAT_MODE_ONE.
 */
object MusicBed {
    private const val STEP_MS = MusicCues.TICK_MS
    private const val SEEK_JUMP_SECONDS = 3.0
    private const val PAUSE_GRACE_MS = 2500L
    private const val MAX_STEP_SECONDS = 3.0 // đồng hồ nhạc không nhảy xa khi máy ngủ giữa hai nhịp
    private const val SAVE_EVERY_MS = 5000L
    private const val PREFS = "music_bed"
    private val CREDIT_KEYS = listOf("title", "creator", "attribution", "landing", "license", "licenseUrl")

    /** Một bài đang kêu. `goal` = âm lượng đang hướng tới, `perTick` = mỗi nhịp STEP_MS nhích bao nhiêu; `entering` = đang mờ vào
     *  (tua lúc này không nhảy thẳng tới mức) trong `fadeMs`; `cue` = mốc đang phát (bước âm lượng), null với danh sách phát. */
    private class Bed(val track: String, val player: ExoPlayer, var goal: Float, var perTick: Float, var cue: MusicCues.Cue?, val fadeMs: Long) {
        var entering = true
        var fadeStep = 0.001f // âm lượng bớt mỗi nhịp khi mờ đi: bài to và bài nhỏ cùng tắt trong cùng thời gian
        var early = false // vào sớm: bài trước kết tự nhiên trước đầu mốc này; tới `cue.start` giọng vẫn ở mốc cũ - không chuyển ngược
        var final = false // vòng cuối của mốc `tail`: không mở phần tử lặp nữa, bài chơi tới E là hết
    }

    /** Vòng lặp của bài `player` theo mốc `cue` (độ dài thật chưa biết: NaN). */
    private fun boundsOf(cue: MusicCues.Cue, player: ExoPlayer): MusicCues.Loop =
        MusicCues.loopBounds(cue, if (player.duration > 0) player.duration / 1000.0 else Double.NaN)

    /** Bài của mốc `cue` lặp thường (REPEAT_MODE_ONE) chỉ khi quá ngắn để mờ chéo; vòng cuối của mốc `tail` thì không lặp. Danh sách
     *  phát (`cue` null) lặp thường như cũ. */
    private fun repeatFor(cue: MusicCues.Cue?, player: ExoPlayer, final: Boolean = false): Int = when {
        cue == null -> Player.REPEAT_MODE_ONE
        final || boundsOf(cue, player).crossfade -> Player.REPEAT_MODE_OFF
        else -> Player.REPEAT_MODE_ONE
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
        MusicCues.mix = MusicMix.load(appContext)
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
        val newChapter = (chapterId ?: Int.MIN_VALUE) != chapter
        if (newChapter) {
            chapter = chapterId ?: Int.MIN_VALUE
            cues = MusicCues.of(music, chapterId)
        }
        val seeked = abs(seconds - lastSeconds) > SEEK_JUMP_SECONDS
        lastSeconds = seconds
        playing = isPlaying
        var cue = MusicCues.at(cues, seconds, failed)
        current?.takeIf { it.early }?.let { bed ->
            // Bài vào sớm giữ chỗ tới đầu mốc của nó; tua thì theo mốc tại chỗ tua như thường.
            val mine = bed.cue
            if (!seeked && mine != null && seconds < mine.start) cue = mine else bed.early = false
        }
        if (!MusicCues.continues(current?.track, cue, newChapter) && (cue != null || current != null)) {
            switchTo(cue?.let { (it.track to Streaming.chapterUri(appContext, book, it.track)) },
                cue?.let { MusicCues.targetGain(it, seconds, gain) } ?: gain, seconds - (cue?.start ?: 0.0), cue)
        } else if (cue != null) {
            current?.cue = cue // cùng bài sang mốc kề: chơi tiếp, bước âm lượng theo mốc mới
            // Vừa tua trong cùng bài: dời nhạc theo chỗ mới, không chơi tiếp từ chỗ cũ (soát a26 L8).
            if (seeked) current?.let { bed ->
                bed.final = false // vòng cuối của mốc `tail` tính lại theo chỗ mới (finishTail)
                bed.player.repeatMode = repeatFor(cue, bed.player)
                MusicCues.offsetMs(cue, seconds, bed.player.duration)?.let(bed.player::seekTo)
            }
        }
        retarget(seconds, seeked)
        finishTail(appContext, seconds)
        crossLoop(seconds)
        applyPlaying()
    }

    /** Mốc `tail`: vòng cuối thì thôi lặp ([MusicCues.finalLoop]), bài chơi tới E là hết ([MusicCues.finished]). Bài đã hết trước
     *  hết mốc mà mốc kế bắt đầu đúng ở đó ([MusicCues.nextAfter]): mốc kế vào ngay, mờ vào như thường, không để quãng im. Không có mốc
     *  kế thì im tới hết mốc. */
    private fun finishTail(appContext: Context, seconds: Double) {
        val bed = current ?: return
        val cue = bed.cue?.takeIf { it.tail } ?: return
        val player = bed.player
        val bounds = boundsOf(cue, player)
        val position = player.currentPosition / 1000.0
        if (!bed.final && player.duration > 0 && MusicCues.finalLoop(cue, seconds, position, bounds)) {
            bed.final = true
            player.repeatMode = Player.REPEAT_MODE_OFF // bài quá ngắn lặp thường: chơi nốt vòng này rồi thôi
        }
        val ended = player.playbackState == Player.STATE_ENDED
        val done = if (bed.final) MusicCues.finished(bounds, position, ended) else ended
        if (!done || seconds >= cue.end) return
        val next = MusicCues.nextAfter(cues, cue)?.takeUnless { it.track == cue.track || isFailed(it.track) } ?: return
        switchTo(next.track to Streaming.chapterUri(appContext, book, next.track), MusicCues.targetGain(next, seconds, gain), 0.0, next)
        current?.early = true
    }

    /** Lặp mờ chéo: bài đang kêu tới E - X ([MusicCues.loopDue]) thì một ExoPlayer MỚI của chính bài vào từ A, mờ chéo X giây; cái
     *  cũ mờ đi rồi nhả. Vòng cuối của mốc `tail` ([finishTail]), bài quá ngắn (lặp thường) và danh sách phát thì không. */
    private fun crossLoop(seconds: Double) {
        val bed = current ?: return
        val cue = bed.cue ?: return
        val player = bed.player
        if (bed.final || seconds >= cue.end || player.duration <= 0) return
        val bounds = boundsOf(cue, player)
        if (!MusicCues.loopDue(bounds, player.currentPosition / 1000.0)) return
        val appContext = context ?: return
        val fadeMs = Math.round(MusicCues.mix.loopCrossfadeSeconds * 1000)
        bed.fadeStep = maxOf(player.volume, 0.01f) * STEP_MS / fadeMs
        fading += bed
        current = open(appContext, bed.track to Streaming.chapterUri(appContext, book, bed.track), bed.goal, 0.0, cue, fadeMs, bounds.start)
            .also { it.early = bed.early }
        startFade()
    }

    /** Mức đích của bài đang kêu đổi (sang bước âm lượng mới): trượt dần trong stepRampSeconds; vừa tua thì vào thẳng mức mới
     *  (trừ lúc bài đang mờ vào). */
    private fun retarget(seconds: Double, seeked: Boolean) {
        val bed = current ?: return
        val cue = bed.cue ?: return
        val goal = MusicCues.targetGain(cue, seconds, gain)
        if (abs(goal - bed.goal) < 1e-6f) return
        bed.goal = goal
        when {
            bed.entering -> bed.perTick = goal * STEP_MS / bed.fadeMs
            seeked -> {
                bed.player.volume = goal
                return
            }
            else -> bed.perTick = abs(goal - bed.player.volume) * STEP_MS / MusicCues.mix.stepRampMs
        }
        startFade()
    }

    /** Dừng hẳn (đổi cuốn, tắt dịch vụ phát): nhả mọi trình phát nhạc, ghi chỗ đang tới của danh sách phát. */
    fun stop() {
        main.removeCallbacks(grace)
        catalogRetry?.let(main::removeCallbacks)
        catalogRetry = null
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
            val resolved = choice?.let { runCatching { resolve(appContext, it, levelDb) }.getOrNull() }
            main.post {
                if (ticket != generation) return@post
                if (stored.isEmpty()) {
                    if (choice == null) return@post // máy không chọn được: không nhạc
                    playlist = choice
                    clockSeconds = prefs(appContext).getFloat(clockKey(), 0f).toDouble()
                }
                infos = resolved?.infos ?: emptyMap()
                queue.load(resolved?.tracks ?: emptyList())
                syncPlaylist(playing)
                // Danh mục chưa đủ (mất mạng lần đầu, một mảnh lỗi): chơi các bài đã có, tải lại phần thiếu - không để danh sách im lặng tới khi mở lại cuốn.
                if (choice != null && (resolved == null || resolved.incomplete)) retryCatalogLater(appContext, choice, levelDb, ticket)
            }
        }
    }

    /** Danh sách máy chọn cho cuốn ở `dir` (luồng nền): luật của mục lục danh mục, chưa tải được danh mục thì luật đóng kèm app. */
    private fun autoChoice(appContext: Context, dir: java.io.File): String? {
        val manifest = runCatching { DeviceMusic.catalog(appContext).manifest() }.getOrNull()
        return Playlists.autoPlaylist(dir, manifest, DeviceMusic.bundledPicker(appContext))
    }

    /** Hàng bài của lựa chọn `choice` (luồng nền: danh mục cần mạng lần đầu): bài + thông tin bài (để tải / bản sao). */
    private fun resolve(appContext: Context, choice: String, levelDb: Double): Resolved {
        if (choice == Playlists.MINE) {
            val store = DeviceMusic.store(appContext)
            val entries = store.entries().reversed() // cũ trước: bài mới nhập nối vào cuối, chỗ đang nghe không xô lệch
            val found = entries.associateBy { it.getString("link") }
            return Resolved(Playlists.queue(found.keys.toList(), found, levelDb) { store.file(it) != null }, found, false)
        }
        val catalog = DeviceMusic.catalog(appContext)
        val links = Playlists.linksOf(catalog.playlists(), choice)
        val partial = if (links.isEmpty()) MusicCatalog.Lookup(emptyMap(), emptySet()) else catalog.lookupPartial(links)
        val found = partial.found
        // Bài quá MusicCatalog.TRACK_MAX_MB (theo `bytes` của danh mục, hay lần tải trước) không vào hàng: bài sau dồn lên, như máy tính.
        // Bài thuộc mảnh chưa tải được (mạng) cũng chưa vào: chưa biết độ dài / độ to - các bài còn lại phát, mảnh về sau thì thêm vào.
        val tracks = Playlists.queue(links, found, levelDb) { MusicCatalog.shardOf(it) !in partial.missingShards && catalog.usable(it, found[it]) }
        return Resolved(tracks, found, partial.missingShards.isNotEmpty())
    }

    /** Kết quả [resolve]: hàng bài + thông tin bài; `incomplete`: còn mảnh danh mục chưa tải được (mạng) - tải lại sau. */
    private class Resolved(val tracks: List<Playlists.Track>, val infos: Map<String, JSONObject>, val incomplete: Boolean)

    /** Một lần tải lại danh mục đang chờ ([retryCatalogLater]); null = không có. */
    private var catalogRetry: Runnable? = null

    /** Danh mục chưa đủ: sau [MusicFailures.RETRY_MS] tải lại phần thiếu (một việc chờ duy nhất, không vòng lặp bận); đủ rồi thì thêm các bài
     *  mới vào hàng, chưa đủ thì chờ lần nữa. Đổi cuốn / đổi lựa chọn ([generation]) thì thôi. */
    private fun retryCatalogLater(appContext: Context, choice: String, levelDb: Double, ticket: Int) {
        catalogRetry?.let(main::removeCallbacks)
        val job = Runnable {
            catalogRetry = null
            if (ticket != generation) return@Runnable
            worker.execute {
                val resolved = runCatching { resolve(appContext, choice, levelDb) }.getOrNull()
                main.post {
                    if (ticket != generation) return@post
                    if (resolved != null) {
                        infos = resolved.infos
                        queue.replace(resolved.tracks, current?.track, clockSeconds)
                    }
                    if (resolved == null || resolved.incomplete) retryCatalogLater(appContext, choice, levelDb, ticket)
                }
            }
        }
        catalogRetry = job
        main.postDelayed(job, MusicFailures.RETRY_MS)
    }

    /** Lời báo "mất mạng" khi có bài của danh sách phát đang bị giữ lại vì mạng (một nguồn nhạc nghỉ vì mạng) - giao diện nói ra thay vì để nhạc
     *  im lặng không lời; rỗng khi ổn. */
    fun offlineNotice(): String = if (playlist != null) context?.let { DeviceMusic.catalog(it).offlineNotice() }.orEmpty() else ""

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
            var offline = false
            val file = try {
                DeviceMusic.catalog(appContext).download(link, info)
            } catch (_: MusicCatalog.TrackTooBig) {
                tooBig = true
                null
            } catch (_: MusicCatalog.Offline) {
                offline = true
                null
            } catch (_: Exception) {
                null
            }
            main.post {
                downloading.remove(link)
                when {
                    file != null -> {}
                    tooBig -> drop(link) // quá MusicCatalog.TRACK_MAX_MB: máy này không dùng bài ấy, bài khác thay
                    offline -> { // mất mạng: bài vẫn tốt - bỏ qua một lúc, thử lại khi có mạng, không tính vào số lần bỏ bài (như máy tính)
                        failed.dropOffline(link)
                        replan(link)
                    }
                    else -> { // nguồn gỡ bài, bản sao sai...: bỏ qua bài này một lúc, lùi dần, có hạn
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
     *  `cue`: mốc của sách (bước âm lượng; mốc `sibling` = nối bài anh em ở điểm kết bài: mờ chéo dài hơn, bài cũ chơi nốt rồi thôi,
     *  không quay lại đầu bài, mờ trong phần còn lại tới E nếu ngắn hơn - [MusicCues.siblingFadeSeconds]). */
    private fun switchTo(next: Pair<String, Uri>?, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue? = null) {
        val mix = MusicCues.mix
        val fadeMs = if (cue?.sibling == true) mix.siblingFadeMs else mix.fadeMs
        current?.let {
            var oldFadeMs = fadeMs
            if (cue?.sibling == true) {
                it.player.repeatMode = Player.REPEAT_MODE_OFF
                val was = it.cue
                if (was != null && it.player.duration > 0) {
                    oldFadeMs = Math.round(MusicCues.siblingFadeSeconds(boundsOf(was, it.player), it.player.currentPosition / 1000.0) * 1000)
                }
            }
            it.fadeStep = maxOf(it.player.volume, 0.01f) * STEP_MS / oldFadeMs
            fading += it
        }
        current = null
        val appContext = context ?: return
        if (next != null) current = open(appContext, next, targetGain, offsetSeconds, cue, fadeMs)
        startFade()
    }

    /** Một ExoPlayer mới cho bài `next`, mờ vào tới `targetGain` trong `fadeMs`. `startAt` (phần tử lặp, giây trong bài): vào đúng
     *  chỗ ấy (A), không căn theo giây chương - đồng hồ bài lệch giọng vài phần giây thì căn lại có khi rơi về cuối vòng. */
    private fun open(appContext: Context, next: Pair<String, Uri>, targetGain: Float, offsetSeconds: Double, cue: MusicCues.Cue?,
                     fadeMs: Long, startAt: Double? = null): Bed {
        val (track, uri) = next
        val player = ExoPlayer.Builder(appContext)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                false,
            )
            .setMediaSourceFactory(Streaming.mediaSourceFactory(appContext))
            .build()
        player.repeatMode = Player.REPEAT_MODE_ONE // biết độ dài bài (STATE_READY) mới biết lặp mờ chéo hay lặp thường
        player.volume = 0f
        val offsetMs = (offsetSeconds.coerceAtLeast(0.0) * 1000).toLong()
        val bed = Bed(track, player, targetGain, targetGain * STEP_MS / fadeMs, cue, fadeMs)
        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY) {
                    player.removeListener(this)
                    failed.forget(track)
                    val duration = player.duration
                    player.repeatMode = repeatFor(bed.cue, player, bed.final)
                    if (startAt != null || duration <= 0) return
                    // Nhạc của sách tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất của chương (soát a26 L8).
                    val mine = bed.cue
                    val latest = if (mine != null && current === bed) MusicCues.offsetMs(mine, lastSeconds, duration) else null
                    player.seekTo(latest ?: (offsetMs % duration))
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
        if (startAt != null) player.setMediaItem(MediaItem.fromUri(uri), (startAt * 1000).toLong())
        else player.setMediaItem(MediaItem.fromUri(uri))
        player.prepare()
        if (playing) player.play()
        return bed
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
