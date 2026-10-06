package vn.abook.player

import android.os.Looper
import androidx.annotation.OptIn
import androidx.media3.common.C
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

/**
 * Lệnh của màn hình khoá, tai nghe, đồng hồ, xe hơi (phiên media) -> lệnh cùng hình dạng RemotePlayers gửi [DlnaPlayers]:
 * phát / dừng, lùi / tới 15 giây, chương trước / sau, tua tới một chỗ. Tách khỏi [CastPlayer] để thử được trên JVM.
 */
object CastControls {
    const val SKIP_MS = 15_000L

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
}

/**
 * Loa / TV điện thoại đang phát, dưới dạng một Player của Media3 - để [CastService] gắn một phiên media: màn hình khoá,
 * nút tai nghe, đồng hồ điều khiển được như trình phát trong app. Trạng thái đọc bản chụp [DlnaPlayers.now] (không đợi
 * mạng; CastService gọi [refresh] mỗi giây); lệnh đi [DlnaPlayers.send] trong một luồng riêng (lệnh tới thiết bị qua mạng).
 * Danh sách phát là các chương nghe được của cuốn, nên "bài trước / sau" là chương trước / sau.
 *
 * Phím âm lượng: không đụng tới - DlnaPlayers chưa đọc âm lượng của thiết bị, nên phím vẫn chỉnh âm lượng điện thoại.
 */
@OptIn(UnstableApi::class)
class CastPlayer(private val players: DlnaPlayers, looper: Looper = Looper.getMainLooper()) : SimpleBasePlayer(looper) {
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "cast-session").apply { isDaemon = true } }

    /** Bản chụp lần dựng trạng thái cuối: lệnh nhắm thiết bị và danh sách chương người dùng đang thấy. */
    private var shown: DlnaPlayers.Now? = null

    fun refresh() = invalidateState()

    override fun getState(): State {
        val now = players.now().also { shown = it }
            ?: return State.Builder().setAvailableCommands(Player.Commands.EMPTY).setPlaybackState(Player.STATE_IDLE).build()
        val index = now.chapters.indexOfFirst { it.id == now.chapterId }.coerceAtLeast(0)
        val items = now.chapters.mapIndexed { place, chapter ->
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
        return State.Builder()
            .setAvailableCommands(COMMANDS)
            .setPlayWhenReady(now.playing, Player.PLAY_WHEN_READY_CHANGE_REASON_REMOTE)
            .setPlaybackState(if (now.playing && now.buffering) Player.STATE_BUFFERING else Player.STATE_READY)
            .setPlaylist(items)
            .setCurrentMediaItemIndex(index)
            .setContentPositionMs(if (moving) PositionSupplier.getExtrapolating(positionMs, 1f) else PositionSupplier.getConstant(positionMs))
            .setSeekBackIncrementMs(CastControls.SKIP_MS)
            .setSeekForwardIncrementMs(CastControls.SKIP_MS)
            .build()
    }

    override fun handleSetPlayWhenReady(playWhenReady: Boolean): ListenableFuture<*> = send(CastControls.playPause(playWhenReady))

    override fun handleSeek(mediaItemIndex: Int, positionMs: Long, seekCommand: Int): ListenableFuture<*> {
        val now = shown ?: return Futures.immediateVoidFuture()
        val chapters = now.chapters.map { it.id }
        return send(CastControls.seek(seekCommand, mediaItemIndex, positionMs, chapters.indexOf(now.chapterId), chapters))
    }

    /** "Dừng" (đồng hồ, xe hơi): thôi phát trên thiết bị, chỗ nghe lưu ở chỗ dừng - như nút "Dừng" của thông báo. */
    override fun handleStop(): ListenableFuture<*> = later { id -> players.end(id) }

    override fun handleRelease(): ListenableFuture<*> {
        worker.shutdown()
        return Futures.immediateVoidFuture()
    }

    private fun send(command: JSONObject): ListenableFuture<*> = later { id -> players.send(id, command) }

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
    }
}
