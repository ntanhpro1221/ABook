package vn.abook.player.ui.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import vn.abook.player.AppLog

/**
 * Phát file mẫu "Nghe thử": một [MediaPlayer] một lúc, tiếng nói (không phải nhạc) và xin tiếng tạm thời của hệ thống - nghe thử lúc đang phát sách thì sách nhỏ đi rồi
 * to lại, không đè lên nhau. Gọi từ luồng chính ([VoiceState] chạy ở đó). Test không dùng lớp này: đưa [SamplePlayer] giả, không bao giờ ra loa.
 */
class AndroidSamplePlayer(context: Context) : SamplePlayer {
    private val audio = context.applicationContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
    private var player: MediaPlayer? = null
    private var focused = false

    override fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit) {
        stop()
        @Suppress("DEPRECATION") // minSdk 24: cách xin tiếng tạm thời chung cho mọi bản
        focused = audio.requestAudioFocus(null, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        val next = MediaPlayer()
        player = next
        try {
            next.setAudioAttributes(attributes)
            next.setDataSource(path)
            next.setOnCompletionListener {
                release(next)
                onEnded()
            }
            next.setOnErrorListener { _, what, _ ->
                AppLog.w("Voice", "nghe thử không phát được (mã $what)")
                release(next)
                onFailed()
                true
            }
            next.setOnPreparedListener { it.start() }
            next.prepareAsync()
        } catch (error: Exception) {
            AppLog.w("Voice", "nghe thử không mở được mẫu: ${error.javaClass.simpleName}")
            release(next)
            onFailed()
        }
    }

    override fun stop() {
        player?.let(::release)
    }

    private fun release(finished: MediaPlayer) {
        if (player === finished) {
            player = null
            @Suppress("DEPRECATION")
            if (focused) audio.abandonAudioFocus(null)
            focused = false
        }
        runCatching { finished.release() }
    }
}
