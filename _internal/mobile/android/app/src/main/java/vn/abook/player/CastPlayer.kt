package vn.abook.player

import android.os.Looper
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.DeviceInfo
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.SimpleBasePlayer
import androidx.media3.common.util.UnstableApi
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.SettableFuture
import org.json.JSONObject
import java.util.concurrent.Executors

/** Một chương trong danh sách phát của phiên media. */
data class CastChapter(val id: Int, val title: String, val duration: Double)

/**
 * Phiên loa / TV đang mở, chụp lại cho phiên media (màn hình khoá, tai nghe): điện thoại tự phát ([DlnaPlayers], mã thiết
 * bị trần) hay máy tính phát ([ComputerCasts], mã "cast:…"). [volume] 0-100 khi thiết bị cho chỉnh âm lượng từ xa.
 */
data class CastNow(
    val id: String,
    val device: String,
    val bookId: String,
    val bookTitle: String,
    val chapters: List<CastChapter>,
    val chapterId: Int,
    val position: Double,
    val duration: Double,
    val playing: Boolean,
    val buffering: Boolean,
    val volume: Int? = null,
)

/** Nơi [CastPlayer] đọc trạng thái (bản chụp, không đợi mạng) và gửi lệnh (chạy ngoài luồng chính, có thể đợi mạng). */
interface CastSource {
    fun now(): CastNow?

    fun send(id: String, command: JSONObject): Any?

    /** Thôi phát trên thiết bị, chỗ nghe lưu ở chỗ dừng (nút "Dừng"). */
    fun end(id: String)
}

/**
 * Lệnh của màn hình khoá, tai nghe, đồng hồ, xe hơi (phiên media) -> lệnh cùng hình dạng RemotePlayers gửi loa / TV:
 * phát / dừng, lùi / tới 15 giây, chương trước / sau, tua tới một chỗ, âm lượng. Tách khỏi [CastPlayer] để thử trên JVM.
 */
object CastControls {
    const val SKIP_MS = 15_000L

    /** Một nấc phím âm lượng trên thang 0-100 (thang của DLNA, Cast nhân 100): 1 nấc là quá nhỏ để nghe ra. */
    const val VOLUME_STEP = 5

    fun playPause(play: Boolean): JSONObject = JSONObject().put("action", if (play) "play" else "pause")

    /**
     * [seekCommand]: lệnh Player.COMMAND_* mà phiên media chuyển tới; [index]: chương đích trong danh sách phát (chương nghe
     * được theo thứ tự - [chapters] là mã của chúng), [current]: chương đang phát; [positionMs] C.TIME_UNSET = đầu chương.
     */
    fun seek(seekCommand: Int, index: Int, positionMs: Long, current: Int, chapters: List<Int>): JSONObject {
        val seconds = if (positionMs == C.TIME_UNSET) 0.0 else maxOf(0L, positionMs) / 1000.0
        return when {
            seekCommand == Player.COMMAND_SEEK_BACK -> JSONObject().put("action", "skip").put("seconds", -SKIP_MS / 1000.0)
            seekCommand == Player.COMMAND_SEEK_FORWARD -> JSONObject().put("action", "skip").put("seconds", SKIP_MS / 1000.0)
            index == current || index !in chapters.indices -> JSONObject().put("action", "seek").put("seconds", seconds)
            index == current + 1 && seconds == 0.0 -> JSONObject().put("action", "next")
            index == current - 1 && seconds == 0.0 -> JSONObject().put("action", "previous")
            else -> JSONObject().put("action", "jump").put("chapterId", chapters[index]).put("seconds", seconds)
        }
    }

    /** Thanh âm lượng màn hình khoá kéo tới [level]. */
    fun volume(level: Int): JSONObject = JSONObject().put("action", "volume").put("level", level.coerceIn(0, 100))

    /** Phím âm lượng: một nấc lên / xuống từ [current]. */
    fun step(current: Int, up: Boolean): JSONObject = volume(current + if (up) VOLUME_STEP else -VOLUME_STEP)
}

/**
 * Loa / TV đang phát, dưới dạng một Player của Media3 - để [CastService] gắn một phiên media: màn hình khoá, nút tai nghe,
 * đồng hồ điều khiển được như trình phát trong app. Trạng thái đọc bản chụp [CastSource.now] (không đợi mạng; CastService
 * gọi [refresh] mỗi giây); lệnh đi [CastSource.send] trong một luồng riêng (lệnh tới thiết bị qua mạng). Danh sách phát là
 * các chương nghe được của cuốn, nên "bài trước / sau" là chương trước / sau.
 *
 * Âm lượng: thiết bị chỉnh được từ xa (DLNA RenderingControl, Cast SET_VOLUME) thì phiên là "phát từ xa" (DeviceInfo
 * REMOTE, thang 0-100) - phím âm lượng và thanh âm lượng màn hình khoá chỉnh loa / TV. Không chỉnh được thì phiên là phát
 * tại chỗ, phím âm lượng vẫn chỉnh điện thoại.
 */
@OptIn(UnstableApi::class)
class CastPlayer(private val source: CastSource, looper: Looper = Looper.getMainLooper()) : SimpleBasePlayer(looper) {
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "cast-session").apply { isDaemon = true } }

    /** Bản chụp lần dựng trạng thái cuối: lệnh nhắm thiết bị và danh sách chương người dùng đang thấy. */
    private var shown: CastNow? = null

    fun refresh() = invalidateState()

    override fun getState(): State {
        val now = source.now().also { shown = it }
            ?: return State.Builder().setAvailableCommands(Player.Commands.EMPTY).setPlaybackState(Player.STATE_IDLE).build()
        val chapters = now.chapters.ifEmpty { listOf(CastChapter(now.chapterId, "", now.duration)) }
        val index = chapters.indexOfFirst { it.id == now.chapterId }.coerceAtLeast(0)
        val items = chapters.mapIndexed { place, chapter ->
            val seconds = if (place == index && now.duration > 0) now.duration else chapter.duration
            val metadata = MediaMetadata.Builder().setTitle(chapter.title).setArtist(now.bookTitle).setAlbumTitle(now.bookTitle)
                .setSubtitle("Trên ${now.device}").build()
            val uid = "${now.bookId}#${chapter.id}"
            MediaItemData.Builder(uid)
                .setMediaItem(MediaItem.Builder().setMediaId(uid).setMediaMetadata(metadata).build())
                .setDurationUs(if (seconds > 0) (seconds * 1_000_000).toLong() else C.TIME_UNSET)
                .setIsSeekable(true)
                .build()
        }
        val positionMs = (now.position * 1000).toLong()
        val moving = now.playing && !now.buffering
        val builder = State.Builder()
            .setAvailableCommands(if (now.volume != null) REMOTE_COMMANDS else COMMANDS)
            .setPlayWhenReady(now.playing, Player.PLAY_WHEN_READY_CHANGE_REASON_REMOTE)
            .setPlaybackState(if (now.playing && now.buffering) Player.STATE_BUFFERING else Player.STATE_READY)
            .setPlaylist(items)
            .setCurrentMediaItemIndex(index)
            .setContentPositionMs(if (moving) PositionSupplier.getExtrapolating(positionMs, 1f) else PositionSupplier.getConstant(positionMs))
            .setSeekBackIncrementMs(CastControls.SKIP_MS)
            .setSeekForwardIncrementMs(CastControls.SKIP_MS)
        if (now.volume != null) builder.setDeviceInfo(REMOTE).setDeviceVolume(now.volume)
        return builder.build()
    }

    override fun handleSetPlayWhenReady(playWhenReady: Boolean): ListenableFuture<*> = send(CastControls.playPause(playWhenReady))

    override fun handleSeek(mediaItemIndex: Int, positionMs: Long, seekCommand: Int): ListenableFuture<*> {
        val now = shown ?: return Futures.immediateVoidFuture()
        val chapters = now.chapters.map { it.id }
        return send(CastControls.seek(seekCommand, mediaItemIndex, positionMs, chapters.indexOf(now.chapterId), chapters))
    }

    override fun handleSetDeviceVolume(deviceVolume: Int, flags: Int): ListenableFuture<*> = send(CastControls.volume(deviceVolume))

    override fun handleIncreaseDeviceVolume(flags: Int): ListenableFuture<*> = step(up = true)

    override fun handleDecreaseDeviceVolume(flags: Int): ListenableFuture<*> = step(up = false)

    private fun step(up: Boolean): ListenableFuture<*> {
        val level = shown?.volume ?: return Futures.immediateVoidFuture()
        return send(CastControls.step(level, up))
    }

    /** "Dừng" (đồng hồ, xe hơi): thôi phát trên thiết bị, chỗ nghe lưu ở chỗ dừng - như nút "Dừng" của thông báo. */
    override fun handleStop(): ListenableFuture<*> = later { id -> source.end(id) }

    override fun handleRelease(): ListenableFuture<*> {
        worker.shutdown()
        return Futures.immediateVoidFuture()
    }

    private fun send(command: JSONObject): ListenableFuture<*> = later { id -> source.send(id, command) }

    /** Làm [work] với thiết bị đang hiện, ngoài luồng chính; lỗi (thiết bị tắt, bị chiếm) thì thôi - lượt chụp sau nói thật. */
    private fun later(work: (String) -> Unit): ListenableFuture<*> {
        val id = shown?.id ?: return Futures.immediateVoidFuture()
        val done = SettableFuture.create<Unit>()
        worker.execute {
            runCatching { work(id) }
            done.set(Unit)
        }
        return done
    }

    private companion object {
        val COMMANDS: Player.Commands = Player.Commands.Builder().addAll(
            Player.COMMAND_PLAY_PAUSE, Player.COMMAND_STOP, Player.COMMAND_RELEASE,
            Player.COMMAND_SEEK_BACK, Player.COMMAND_SEEK_FORWARD,
            Player.COMMAND_SEEK_TO_NEXT, Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
            Player.COMMAND_SEEK_TO_PREVIOUS, Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
            Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM, Player.COMMAND_SEEK_TO_MEDIA_ITEM, Player.COMMAND_SEEK_TO_DEFAULT_POSITION,
            Player.COMMAND_GET_CURRENT_MEDIA_ITEM, Player.COMMAND_GET_TIMELINE, Player.COMMAND_GET_METADATA,
        ).build()

        @Suppress("DEPRECATION") // bộ điều khiển cũ (MediaSessionCompat) còn hỏi hai lệnh không cờ
        val REMOTE_COMMANDS: Player.Commands = COMMANDS.buildUpon().addAll(
            Player.COMMAND_GET_DEVICE_VOLUME,
            Player.COMMAND_SET_DEVICE_VOLUME, Player.COMMAND_SET_DEVICE_VOLUME_WITH_FLAGS,
            Player.COMMAND_ADJUST_DEVICE_VOLUME, Player.COMMAND_ADJUST_DEVICE_VOLUME_WITH_FLAGS,
        ).build()

        val REMOTE: DeviceInfo = DeviceInfo.Builder(DeviceInfo.PLAYBACK_TYPE_REMOTE).setMinVolume(0).setMaxVolume(100).build()
    }
}
