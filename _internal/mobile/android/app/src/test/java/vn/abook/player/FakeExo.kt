package vn.abook.player

import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import java.lang.reflect.Proxy

/**
 * ExoPlayer giả cho test JVM của lõi phát (Playback): ý định phát (`playWhenReady`) tách khỏi `isPlaying`, tua đổi vị trí ngay như ExoPlayer thật. Phương thức nào không biết trả giá trị mặc định.
 * `calls` ghi tên các lệnh đã gọi (theo thứ tự).
 */
class FakeExo {
    var playWhenReady = false
    var playing = false
    var state = Player.STATE_READY
    var position = 0L
    var duration = 0L
    var speed = 1f
    var item: MediaItem? = null
    /** Hàng đợi nhiều mục (sau setMediaItems); rỗng thì chỉ có `item` như trước. */
    var items: List<MediaItem> = emptyList()
    var index = 0
    var volume = 1f
    val calls = mutableListOf<String>()
    val listeners = mutableListOf<Player.Listener>()

    val player: ExoPlayer = Proxy.newProxyInstance(ExoPlayer::class.java.classLoader, arrayOf(ExoPlayer::class.java)) { proxy, method, args ->
        calls += method.name
        when (method.name) {
            "getPlayWhenReady" -> playWhenReady
            "setPlayWhenReady" -> { playWhenReady = args!![0] as Boolean; null }
            "play" -> { playWhenReady = true; playing = state == Player.STATE_READY; null }
            "pause" -> { playWhenReady = false; playing = false; null }
            "isPlaying" -> playing
            "getPlaybackState" -> state
            "getCurrentPosition" -> position
            "getDuration" -> if (duration > 0) duration else androidx.media3.common.C.TIME_UNSET
            "getCurrentMediaItem" -> if (items.isNotEmpty()) items[index] else item
            "getMediaItemCount" -> if (items.isNotEmpty()) items.size else if (item == null) 0 else 1
            "getMediaItemAt" -> items[args!![0] as Int]
            "getCurrentMediaItemIndex" -> index
            "clearMediaItems" -> { item = null; items = emptyList(); null }
            "setMediaItems" -> {
                @Suppress("UNCHECKED_CAST")
                items = args!![0] as List<MediaItem>
                if (args.size == 3) { index = args[1] as Int; position = args[2] as Long } else { index = 0; position = 0 }
                item = items.getOrNull(index)
                null
            }
            "replaceMediaItems" -> {
                @Suppress("UNCHECKED_CAST")
                items = items.take(args!![0] as Int) + (args[2] as List<MediaItem>) + items.drop(args[1] as Int)
                index = items.indexOfFirst { it.mediaId == item?.mediaId }.coerceAtLeast(0)
                null
            }
            "seekTo" -> { position = args!!.last() as Long; null }
            "getPlaybackParameters" -> PlaybackParameters(speed)
            "setPlaybackParameters" -> { speed = (args!![0] as PlaybackParameters).speed; null }
            "getVolume" -> volume
            "setVolume" -> { volume = args!![0] as Float; null }
            "addListener" -> { listeners.add(args!![0] as Player.Listener); null }
            "removeListener" -> { listeners.remove(args!![0] as Player.Listener); null }
            "equals" -> args!![0] === proxy
            "hashCode" -> System.identityHashCode(this)
            "toString" -> "FakeExo"
            else -> when (method.returnType) {
                java.lang.Boolean.TYPE -> false
                java.lang.Integer.TYPE -> 0
                java.lang.Long.TYPE -> 0L
                java.lang.Float.TYPE -> 0f
                else -> null
            }
        }
    } as ExoPlayer
}
