package vn.abook.player.ui.nowplaying

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.State
import kotlinx.coroutines.flow.StateFlow
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.music.MusicState
import vn.abook.player.ui.music.PlayerMusic
import vn.abook.player.ui.voice.VoiceState
import java.math.BigDecimal
import kotlin.math.ceil

/** Public shared keys: the real library mini bar uses these without depending on the window's implementation. */
enum class NowPlayingPart { Container, Cover, Chapter, Book, Play }

@Immutable
data class PlayerVoice(val id: String, val name: String, val gender: String = "", val online: Boolean = false)

enum class SleepKind { Off, Minutes, Chapter }

/** The timer as set (mode, minutes, whether it counts now). The time left runs on [PlayerPosition.sleepRemainingMs], never here. */
@Immutable
data class PlayerSleep(val kind: SleepKind = SleepKind.Off, val minutes: Int = 0, val counting: Boolean = false)

@Immutable
data class NowPlayingState(
    val bookId: String = "",
    val bookTitle: String = "",
    val chapterId: Int? = null,
    val chapterTitle: String = "",
    val cover: CoverRef? = null,
    val playing: Boolean = false,
    val durationMs: Long = 0,
    val rate: Double = 1.0,
    val sleep: PlayerSleep = PlayerSleep(),
    val chapters: List<PlayerChapter> = emptyList(),
    val readAlongAvailable: Boolean = false,
    val error: String = "",
    /** Nhạc đang kêu: ghi công, bài hỏng, mất mạng (lựa chọn của cuốn nằm ở [NowPlayingModel.music]). */
    val music: PlayerMusic = PlayerMusic.None,
    val returnAvailable: Boolean = false,
    /** Tăng mỗi lần tua / nhảy: chip "Về chỗ cũ" hiện lại và đếm lại từ đầu. */
    val returnSerial: Int = 0,
    /** Giọng chạy trên máy này (danh sách của tấm "Giọng đọc"): giọng trực tuyến chỉ chọn qua hộp hỏi đồng ý, không nằm ở đây. */
    val voices: List<PlayerVoice> = emptyList(),
    val voiceId: String = "",
    /** Tên giọng đang chọn (kể cả giọng trực tuyến), rỗng khi chưa biết: lời báo "giọng đang chọn không đọc được" nói tên giọng. */
    val voiceName: String = "",
)

/**
 * The window's view of the one clock ([vn.abook.player.ui.data.PlayerClock]). Read the values only in draw / layout lambdas or `snapshotFlow`.
 * [sample] refreshes the position from the core; the window calls it once per frame while it is open and playing.
 */
@Stable
interface PlayerPosition {
    val milliseconds: State<Long>
    val sleepRemainingMs: State<Long>
    fun sample()
}

@Stable
interface NowPlayingModel {
    val state: StateFlow<NowPlayingState>
    val position: PlayerPosition
    val readAlong: StateFlow<ReadAlongState>
    /** Nhạc nền của cuốn đang phát (chọn danh sách, mức to nhỏ); null = không có (bản thử) thì tấm Tuỳ chọn không có hàng Nhạc nền. */
    val music: MusicState? get() = null
    /** Giọng đọc làm thêm (tải giọng VieNeu ngay trong khối lỗi); null = không có (bản thử). */
    val voice: VoiceState? get() = null
    fun toggle()
    fun skip(seconds: Int)
    fun seek(milliseconds: Long)
    fun jump(chapterId: Int)
    fun next()
    fun previous()
    fun setRate(rate: Double)
    fun setSleep(kind: SleepKind, minutes: Int = 0)
    fun setVoice(id: String)
    suspend fun loadVoices()
    fun setReadAlongActive(active: Boolean)
    fun returnToPreviousPlace()
    suspend fun loadReadAlong()
}

object PlayerLabels {
    val rates = listOf(0.75, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.75, 2.0, 2.5, 3.0)
    val sleepMinutes = listOf(5, 10, 15, 30, 45, 60)
    fun rate(value: Double): String = BigDecimal.valueOf(value).setScale(2, java.math.RoundingMode.HALF_UP)
        .stripTrailingZeros().toPlainString().replace('.', ',') + "×"
    fun time(milliseconds: Long): String {
        val seconds = milliseconds.coerceAtLeast(0) / 1000
        return "${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}"
    }
    /** `leftMs`: the time left on the timer (the clock's `sleepRemainingMs`). `clock`: the sheet's big readout instead of the button label. */
    fun sleep(sleep: PlayerSleep, leftMs: Long, clock: Boolean = false): String = when (sleep.kind) {
        SleepKind.Off -> if (clock) "Tắt" else "Hẹn giờ"
        SleepKind.Chapter -> "Hết chương"
        SleepKind.Minutes -> {
            val left = leftMs.coerceAtLeast(0)
            if (clock) time(ceil(left / 1000.0).toLong() * 1000)
            else if (left < 60_000) "${ceil(left / 1000.0).toInt().coerceAtLeast(1)} giây"
            else "${ceil(left / 60_000.0).toInt()} phút"
        }
    }
}

/**
 * The repo's immutable snapshot -> what the window draws. Pure and run once per snapshot (never per clock tick); `voices` and the "return to place" chip are the
 * window's own extras. Rate comes through as is: the core reports the decimal the listener picked, so the sheet's choice compares equal.
 */
fun nowPlayingState(player: PlayerState, voices: List<PlayerVoice>, returnAvailable: Boolean, returnSerial: Int): NowPlayingState =
    NowPlayingState(
        bookId = player.bookId, bookTitle = player.bookTitle, chapterId = player.chapterId, chapterTitle = player.chapterTitle,
        cover = player.cover, playing = player.playing, durationMs = player.durationMs.coerceAtLeast(0), rate = player.rate,
        sleep = PlayerSleep(
            when (player.sleep.mode) { "minutes" -> SleepKind.Minutes; "chapter" -> SleepKind.Chapter; else -> SleepKind.Off },
            player.sleep.minutes, player.sleep.counting,
        ),
        chapters = player.chapters, readAlongAvailable = player.hasTrack, error = player.error,
        music = player.music, returnAvailable = returnAvailable, returnSerial = returnSerial,
        voices = voices.filter { !it.online }, voiceId = player.voiceId, voiceName = voices.firstOrNull { it.id == player.voiceId }?.name.orEmpty(),
    )
