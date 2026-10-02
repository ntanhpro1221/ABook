package vn.abook.player

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import org.json.JSONObject
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
 * Một ExoPlayer riêng cho mỗi bài đang kêu (hai khi đang chuyển mờ), lặp liền, KHÔNG giành audio focus: trình phát giọng
 * đọc giữ focus, nhạc chỉ chạy khi giọng đang chạy (`sync` từ Playback mỗi nhịp 0,5 giây và mỗi lần phát / dừng / tua).
 * Mọi thao tác ở luồng chính, như Playback.
 */
object MusicBed {
    private const val FADE_MS = 2000L
    private const val STEP_MS = 50L
    private const val SEEK_JUMP_SECONDS = 3.0

    /** `gainDb`: độ khuếch đại máy chủ đã tính cho bài này (music_plan.cue_gain_db, ghi sẵn vào mốc khi đóng gói); null = sách
     *  xuất bởi bản cũ -> mức chung `levelDb` của cuốn. Máy điện thoại không tự tính lại, chỉ áp con số. */
    private data class Cue(val start: Double, val end: Double, val track: String, val gainDb: Double?)
    private class Bed(val track: String, val player: ExoPlayer, val gain: Float) {
        var fadeFrom = 0.01f // âm lượng lúc bắt đầu mờ đi: bài to và bài nhỏ cùng tắt trong FADE_MS
    }

    private val main = Handler(Looper.getMainLooper())
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

    fun init(appContext: Context) {
        context = appContext.applicationContext
    }

    /** Lớp sửa của cuốn `bookId` vừa đổi (nhạc bật/tắt, mức, im lặng một đoạn): lần `sync` kế đọc lại mục `music` đã phủ sửa. */
    fun invalidate(bookId: String) {
        if (bookId == book) book = ""
    }

    /** Bài đang kêu (tên trong gói) hay null khi im lặng - cho kiểm thử trên máy. */
    val activeTrack: String? get() = current?.track

    /** Giọng đọc đang ở `seconds` của chương `chapterId` trong cuốn `bookId`; `isPlaying` = giọng đang chạy. */
    fun sync(bookId: String, chapterId: Int?, seconds: Double, isPlaying: Boolean) {
        if (context == null) return
        if (bookId != book) {
            stop()
            book = bookId
            music = if (bookId.isEmpty()) null else Store.playableManifest(bookId)?.optJSONObject("music")
            val level = music?.optDouble("levelDb", -20.0) ?: -20.0
            gain = 10.0.pow(level.coerceIn(-40.0, -6.0) / 20.0).toFloat()
            chapter = Int.MIN_VALUE
        }
        if ((chapterId ?: Int.MIN_VALUE) != chapter) {
            chapter = chapterId ?: Int.MIN_VALUE
            cues = cuesOf(chapterId)
        }
        val seeked = abs(seconds - lastSeconds) > SEEK_JUMP_SECONDS
        lastSeconds = seconds
        playing = isPlaying
        val cue = cues.firstOrNull { seconds >= it.start && seconds < it.end }
        if (cue?.track != current?.track || (seeked && cue != null && current == null)) switchTo(cue, seconds)
        for (bed in listOfNotNull(current) + fading) {
            if (playing && !bed.player.isPlaying) bed.player.play()
            if (!playing && bed.player.isPlaying) bed.player.pause()
        }
    }

    /** Dừng hẳn (đổi cuốn, tắt dịch vụ phát): nhả mọi trình phát nhạc. */
    fun stop() {
        for (bed in listOfNotNull(current) + fading) bed.player.release()
        current = null
        fading.clear()
        cues = emptyList()
        chapter = Int.MIN_VALUE
    }

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
    private fun gainOf(cue: Cue): Float =
        cue.gainDb?.let { 10.0.pow(it.coerceAtMost(0.0) / 20.0).toFloat() } ?: gain

    private fun switchTo(cue: Cue?, seconds: Double) {
        current?.let {
            it.fadeFrom = maxOf(it.player.volume, 0.01f)
            fading += it
        }
        current = null
        val appContext = context ?: return
        if (cue != null) {
            val player = ExoPlayer.Builder(appContext)
                .setAudioAttributes(
                    AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                    false,
                )
                .setMediaSourceFactory(Streaming.mediaSourceFactory(appContext))
                .build()
            player.repeatMode = Player.REPEAT_MODE_ONE
            player.volume = 0f
            val offsetMs = ((seconds - cue.start).coerceAtLeast(0.0) * 1000).toLong()
            player.addListener(object : Player.Listener {
                override fun onPlaybackStateChanged(state: Int) {
                    if (state == Player.STATE_READY) {
                        player.removeListener(this)
                        val duration = player.duration
                        if (duration > 0) player.seekTo(offsetMs % duration)
                    }
                }
            })
            player.setMediaItem(MediaItem.fromUri(Streaming.chapterUri(appContext, book, cue.track)))
            player.prepare()
            if (playing) player.play()
            current = Bed(cue.track, player, gainOf(cue))
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

    private val TRACK = Regex("music/[0-9a-f]{40}\\.mp3")
}
