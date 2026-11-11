package vn.abook.player.ui.data

import android.content.ComponentName
import android.content.Context
import android.os.Looper
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.MoreExecutors
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.Playback
import vn.abook.player.PlaybackService
import vn.abook.player.SleepTimer
import vn.abook.player.readaloud.ReadAloud

/**
 * Lõi phát thật cho giao diện native: chuyển lệnh xuống [Playback] (mọi lệnh ExoPlayer chạy ở luồng chính) sau khi bảo đảm dịch vụ phát đã chạy -
 * bằng một MediaController ghim vào luồng chính để Media3 khởi động / giữ sống dịch vụ.
 * `Playback.init` chạy ở lần dùng đầu (không ở dựng Activity: ngân sách mở nguội).
 */
class AndroidPlaybackCore(context: Context) : PlaybackCore {
    private val app = context.applicationContext
    private var controller: ListenableFuture<MediaController>? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val initialization = scope.async(Dispatchers.IO, start = CoroutineStart.LAZY) { Playback.init(app) }
    private val loadSequence = java.util.concurrent.atomic.AtomicLong()

    private fun withService(block: () -> Unit) {
        scope.launch {
            initialization.await()
            val future = controller ?: MediaController.Builder(app, SessionToken(app, ComponentName(app, PlaybackService::class.java)))
                .setApplicationLooper(Looper.getMainLooper()).buildAsync().also { controller = it }
            future.addListener({ Playback.onMain(block) }, MoreExecutors.directExecutor())
        }
    }

    override fun addListener(listener: (JSONObject) -> Unit) {
        Playback.addListener(listener)
        // The caller applies a snapshot right after attaching. Only a snapshot taken before
        // the background init finished is stale; a warm attach must not rebroadcast state.
        if (initialization.isCompleted) return
        scope.launch {
            initialization.await()
            Playback.emit("state")
        }
    }

    override fun removeListener(listener: (JSONObject) -> Unit) = Playback.removeListener(listener)
    override fun snapshot(): JSONObject = Playback.state()
    override fun play() = withService { Playback.play() }
    override fun pause() = withService { Playback.pause() }
    override fun close() = Playback.onMain { loadSequence.incrementAndGet(); Playback.closeBook() }
    override fun toggle() = withService { Playback.toggle() }
    override fun skip(deltaSeconds: Double) = withService { Playback.skip(deltaSeconds) }
    override fun seekTo(seconds: Double) = withService { Playback.seekTo(seconds) }
    override fun next() = withService { Playback.next() }
    override fun previous() = withService { Playback.previous() }
    override fun setRate(rate: Double) = withService { Playback.setRate(rate) }
    override fun jumpTo(chapterId: Int, seconds: Double) = withService { Playback.jumpTo(chapterId, seconds) }
    override fun positionMs(): Long = Playback.positionMs
    override fun chapters(): List<Playback.Chapter> = Playback.chapters
    override fun setSleep(mode: String, minutes: Int) = withService {
        when (mode) {
            "minutes" -> SleepTimer.setMinutes(minutes)
            "chapter" -> SleepTimer.setEndOfChapter(minutes.coerceAtLeast(1))
            else -> { SleepTimer.cancel(); vn.abook.player.Feedback.play("toggle") }
        }
    }

    override fun extendSleep() = withService { SleepTimer.extend() }

    override fun voiceId(): String = ReadAloud.voiceId
    override fun setVoice(voiceId: String) = withService { ReadAloud.chooseFor(Playback.bookId, voiceId, Playback.recordId) }
    override fun load(request: LoadRequest) {
        val sequence = loadSequence.incrementAndGet()
        scope.launch {
            initialization.await()
            val prepared = withContext(Dispatchers.IO) {
                with(request) { Playback.prepareBook(id, title, narrator, chapters) }
            }
            if (sequence != loadSequence.get()) return@launch
            withService {
                if (sequence != loadSequence.get()) return@withService
                // A cold restore must not replace a book selected by a widget or another controller.
                if (!request.restore || Playback.bookId.isEmpty()) {
                    if (vn.abook.player.Store.knownActiveRecord(request.id) != prepared.record) {
                        load(request)
                        return@withService
                    }
                    with(request) { Playback.load(id, title, narrator, chapters, startChapterId, startSeconds, rate, autoplay, prepared) }
                }
            }
        }
    }
}
