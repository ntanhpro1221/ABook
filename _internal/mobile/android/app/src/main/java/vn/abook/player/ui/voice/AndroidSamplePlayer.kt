package vn.abook.player.ui.voice

import vn.abook.player.S

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
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
    private val handler = Handler(Looper.getMainLooper())
    private var outputState: ((Boolean) -> Unit)? = null
    private var stopAt: Runnable? = null

    override fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit) = playRange(path, 0, 0, onEnded, onFailed)

    override fun playRangeWithState(path: String, startMs: Int, endMs: Int, onEnded: () -> Unit, onFailed: () -> Unit, onPlaying: (Boolean) -> Unit) {
        playInternal(path, startMs, endMs, onEnded, onFailed, onPlaying)
    }

    override fun pause() { player?.pause(); outputState?.invoke(false) }
    override fun resume() { player?.let { it.start(); outputState?.invoke(it.isPlaying) } }
    override fun seek(ms: Int) { player?.seekTo(ms.coerceAtLeast(0)) }
    override fun positionMs(): Int = runCatching { player?.currentPosition ?: 0 }.getOrDefault(0)
    override fun durationMs(): Int = runCatching { player?.duration ?: 0 }.getOrDefault(0)

    override fun playRange(path: String, startMs: Int, endMs: Int, onEnded: () -> Unit, onFailed: () -> Unit) {
        playInternal(path, startMs, endMs, onEnded, onFailed, null)
    }

    private fun playInternal(path: String, startMs: Int, endMs: Int, onEnded: () -> Unit, onFailed: () -> Unit, onPlaying: ((Boolean) -> Unit)?) {
        stop()
        outputState = onPlaying
        @Suppress("DEPRECATION") // minSdk 24: cách xin tiếng tạm thời chung cho mọi bản
        focused = audio.requestAudioFocus(null, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        val next = MediaPlayer()
        player = next
        try {
            next.setAudioAttributes(attributes)
            next.setDataSource(path)
            next.setOnCompletionListener {
                if (player !== next) return@setOnCompletionListener
                release(next)
                onEnded()
            }
            next.setOnErrorListener { _, what, _ ->
                if (player !== next) return@setOnErrorListener true
                AppLog.w("Voice", S.s_nghe_thu_khong_phat_duoc_ma_0_2c05bef5(what))
                release(next)
                onFailed()
                true
            }
            next.setOnInfoListener { _, what, _ ->
                if (player !== next) return@setOnInfoListener false
                when (what) {
                    MediaPlayer.MEDIA_INFO_BUFFERING_START -> onPlaying?.invoke(false)
                    MediaPlayer.MEDIA_INFO_BUFFERING_END -> onPlaying?.invoke(next.isPlaying)
                }
                false
            }
            next.setOnPreparedListener { prepared ->
                if (player !== next) return@setOnPreparedListener
                if (startMs <= 0) {
                    prepared.start()
                    outputState?.invoke(true)
                    scheduleEnd(next, endMs - startMs, endMs > startMs, onEnded)
                } else {
                    // Đoạn giữa file: nhảy tới đầu đoạn rồi mới phát, dừng đúng cuối đoạn.
                    prepared.setOnSeekCompleteListener {
                        if (player !== next) return@setOnSeekCompleteListener
                        it.setOnSeekCompleteListener(null)
                        it.start()
                        outputState?.invoke(true)
                        scheduleEnd(next, endMs - startMs, endMs > startMs, onEnded)
                    }
                    prepared.seekTo(startMs)
                }
            }
            next.prepareAsync()
        } catch (error: Exception) {
            AppLog.w("Voice", S.s_nghe_thu_khong_mo_duoc_mau_0_5d43cda2(error.javaClass.simpleName))
            release(next)
            onFailed()
        }
    }

    override fun stop() {
        player?.let(::release)
    }

    /** Hết đoạn thì dừng như phát hết file (`onEnded`); đoạn không có cuối thì để file tự hết. */
    private fun scheduleEnd(current: MediaPlayer, lengthMs: Int, bounded: Boolean, onEnded: () -> Unit) {
        if (!bounded) return
        val task = Runnable {
            if (player === current) {
                release(current)
                onEnded()
            }
        }
        stopAt = task
        handler.postDelayed(task, lengthMs.toLong())
    }

    private fun release(finished: MediaPlayer) {
        if (player === finished) {
            stopAt?.let(handler::removeCallbacks)
            stopAt = null
            player = null
            outputState = null
            @Suppress("DEPRECATION")
            if (focused) audio.abandonAudioFocus(null)
            focused = false
        }
        runCatching { finished.release() }
    }
}
