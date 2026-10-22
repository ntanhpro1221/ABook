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
            "getCurrentMediaItem" -> item
            "getMediaItemCount" -> if (item == null) 0 else 1
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
