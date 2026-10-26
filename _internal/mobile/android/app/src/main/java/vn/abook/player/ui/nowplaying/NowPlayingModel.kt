package vn.abook.player.ui.nowplaying

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.State
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject
import java.math.BigDecimal
import kotlin.math.ceil

/** Public shared keys: the real library mini bar can use these without depending on its implementation. */
enum class NowPlayingPart { Container, Cover, Chapter, Book, Play }

@Immutable
data class PlayerChapter(val id: Int, val title: String, val durationMs: Long, val textPath: String = "")

@Immutable
data class CoverRef(val path: String, val stamp: Long)

@Immutable
data class PlayerVoice(val id: String, val name: String)

enum class SleepKind { Off, Minutes, Chapter }

/** A snapshot anchored to monotonic time; position ticks never change the screen state. */
@Immutable
data class PlayerSleep(
    val kind: SleepKind = SleepKind.Off,
    val remainingMs: Long = 0,
    val sampledAtMs: Long = 0,
    val counting: Boolean = false,
    val minutes: Int = 0,
) {
    fun leftMs(now: Long): Long = (remainingMs - if (counting) (now - sampledAtMs).coerceAtLeast(0) else 0).coerceAtLeast(0)
}

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
    val musicEnabled: Boolean = false,
    val returnAvailable: Boolean = false,
    /** Tăng mỗi lần tua / nhảy: chip "Về chỗ cũ" hiện lại và đếm lại từ đầu. */
    val returnSerial: Int = 0,
    val voices: List<PlayerVoice> = emptyList(),
    val voiceId: String = "",
)

/** Cheap clock, separate from immutable metadata. Read position only in draw/layout or snapshotFlow. */
@Stable
interface PlayerPosition {
    val milliseconds: State<Long>
    val realtimeMs: State<Long>
    fun sample()
}

@Stable
interface NowPlayingModel {
    val state: StateFlow<NowPlayingState>
    val position: PlayerPosition
    val readAlong: StateFlow<ReadAlongState>
    fun toggle()
    fun skip(seconds: Int)
    fun seek(milliseconds: Long)
    fun jump(chapterId: Int)
    fun next()
    fun previous()
    fun setRate(rate: Double)
    fun setSleep(kind: SleepKind, minutes: Int = 0)
    fun setMusic(enabled: Boolean)
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
    fun sleep(sleep: PlayerSleep, now: Long, clock: Boolean = false): String = when (sleep.kind) {
        SleepKind.Off -> if (clock) "Tắt" else "Hẹn giờ"
        SleepKind.Chapter -> "Hết chương"
        SleepKind.Minutes -> {
            val left = sleep.leftMs(now)
            if (clock) time(ceil(left / 1000.0).toLong() * 1000)
            else if (left < 60_000) "${ceil(left / 1000.0).toInt().coerceAtLeast(1)} giây"
            else "${ceil(left / 60_000.0).toInt()} phút"
        }
    }
}

/** Same native JSON contract as PlayerPlugin.getState, with no clock fields in screen metadata. */
fun mapPlaybackState(
    json: JSONObject, chapters: List<PlayerChapter>, cover: CoverRef?, now: Long,
): NowPlayingState {
    val timer = json.optJSONObject("sleep") ?: JSONObject()
    val kind = when (timer.optString("mode")) { "minutes" -> SleepKind.Minutes; "chapter" -> SleepKind.Chapter; else -> SleepKind.Off }
    val chapterId = if (json.isNull("chapterId")) null else json.optInt("chapterId")
    return NowPlayingState(
        bookId = json.optString("bookId"), bookTitle = json.optString("bookTitle"),
        chapterId = chapterId, chapterTitle = json.optString("chapterTitle"), cover = cover,
        playing = json.optBoolean("playing"), durationMs = (json.optDouble("duration", 0.0) * 1000).toLong().coerceAtLeast(0),
        rate = json.optDouble("rate", 1.0), chapters = chapters,
        sleep = PlayerSleep(kind, (timer.optDouble("remaining", 0.0) * 1000).toLong(), now, timer.optBoolean("counting"), timer.optInt("minutes")),
        readAlongAvailable = chapterId != null,
        error = json.optString("error").ifBlank { json.optString("saveError") },
    )
}
