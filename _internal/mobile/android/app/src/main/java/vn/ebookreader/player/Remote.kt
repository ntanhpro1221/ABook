package vn.ebookreader.player

import android.content.ComponentName
import android.content.Context
import android.os.Looper
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.MoreExecutors
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * Máy tính điều khiển trình phát trên điện thoại - kiểu Spotify Connect, gói trong mạng nhà (PLAYER_RESEARCH #12).
 *
 * Điện thoại không mở cổng nào: một luồng "hỏi dài" gửi trạng thái đang phát lên máy tính (webui/sync.py: Remote) và
 * treo tới 25 giây chờ lệnh - có lệnh là máy tính trả lời ngay, nên bấm dừng trên máy tính thì điện thoại dừng sau một
 * lượt mạng. Đổi trạng thái (phát, dừng, tua, sang chương) thì gửi thêm một lần không chờ để máy tính thấy liền.
 *
 * Chỉ chạy khi đã ghép nối VÀ (app đang mở, hoặc đang phát, hoặc vừa dừng chưa tới 10 phút): điện thoại nằm yên cả đêm
 * thì không giữ mạng. Mọi thao tác trên trình phát chạy ở luồng chính như mọi chỗ khác (Playback).
 */
object Remote {
    private const val WAIT_SECONDS = 25
    private const val IDLE_MS = 10 * 60_000L
    private const val ACK_MS = 20_000L

    private lateinit var context: Context
    private val loop = Executors.newSingleThreadExecutor()
    private val kicks = Executors.newSingleThreadExecutor()
    private val running = AtomicBoolean(false)
    private val kickQueued = AtomicBoolean(false)
    private val acks = ArrayDeque<Pair<Long, JSONObject>>()
    private var service: ListenableFuture<MediaController>? = null

    /** App đang hiện trên màn hình (MainActivity): mở app là máy tính thấy điện thoại, kể cả khi chưa phát gì. */
    @Volatile
    var foreground = false
        set(value) {
            field = value
            if (value) ensure()
        }

    @Volatile
    private var playing = false

    @Volatile
    private var pausedAtMs = 0L

    fun init(appContext: Context) {
        if (!::context.isInitialized) context = appContext
    }

    fun onPlaying(isPlaying: Boolean) {
        playing = isPlaying
        if (!isPlaying) pausedAtMs = System.currentTimeMillis()
        ensure()
    }

    private fun shouldRun(): Boolean =
        ::context.isInitialized && SyncLink.paired(context) &&
            (foreground || playing || System.currentTimeMillis() - pausedAtMs < IDLE_MS)

    /** Bật vòng hỏi dài nếu nên chạy mà chưa chạy. */
    fun ensure() {
        if (!shouldRun() || !running.compareAndSet(false, true)) return
        loop.execute {
            var backoffMs = 3_000L
            try {
                while (shouldRun()) {
                    try {
                        execute(report(WAIT_SECONDS))
                        backoffMs = 3_000L
                    } catch (_: Exception) {
                        // Máy tính tắt, đổi mạng, tắt đồng bộ: thử lại thưa dần, không đốt pin.
                        Thread.sleep(backoffMs)
                        backoffMs = (backoffMs * 2).coerceAtMost(60_000L)
                    }
                }
            } finally {
                running.set(false)
            }
            // Điều kiện có thể vừa đổi trong khoảnh khắc giữa lần kiểm cuối và lúc hạ cờ.
            if (shouldRun()) ensure()
        }
    }

    /** Trạng thái vừa đổi: báo máy tính ngay (gộp các đổi dồn dập trong 300 ms thành một lần). */
    fun kick() {
        if (!shouldRun()) return
        ensure()
        if (!kickQueued.compareAndSet(false, true)) return
        kicks.execute {
            Thread.sleep(300)
            kickQueued.set(false)
            runCatching { execute(report(0)) }
        }
    }

    private fun report(wait: Int): JSONArray? {
        val body = JSONObject().put("state", snapshot()).put("books", downloadedBooks()).put("wait", wait)
        synchronized(acks) {
            val now = System.currentTimeMillis()
            while (acks.isNotEmpty() && now - acks.first().first > ACK_MS) acks.removeFirst()
            // Gửi lại kết quả lệnh trong 20 giây: giao diện máy tính hỏi 1,5 giây một lần, không được lỡ một lỗi.
            if (acks.isNotEmpty()) body.put("acks", JSONArray(acks.map { it.second }))
        }
        val reply = SyncLink.request(context, "POST", "/sync/v1/remote", body, readTimeoutMs = (wait + 15) * 1000)
        return JSONObject(reply).optJSONArray("commands")
    }

    /** Trạng thái trình phát, đọc ở luồng chính (ExoPlayer chỉ cho đọc từ luồng của nó). */
    private fun snapshot(): JSONObject {
        val result = AtomicReference(JSONObject())
        val done = CountDownLatch(1)
        Playback.onMain {
            runCatching { result.set(Playback.state()) }
            done.countDown()
        }
        done.await(2, TimeUnit.SECONDS)
        return result.get()
    }

    /** Sách đã tải xong về máy (có book.json) - máy tính chỉ mời "Phát trên điện thoại" với những cuốn này. */
    private fun downloadedBooks(): JSONArray = JSONArray().also { array ->
        File(Store.root, "books").listFiles()?.filter { File(it, "book.json").isFile }?.forEach { array.put(it.name) }
    }

    private fun execute(commands: JSONArray?) {
        if (commands == null || commands.length() == 0) return
        Playback.onMain {
            for (index in 0 until commands.length()) {
                val command = commands.optJSONObject(index) ?: continue
                val problem = runCatching { apply(command) }.getOrElse { it.message ?: it.javaClass.simpleName }
                val ack = JSONObject().put("id", command.optString("id")).put("ok", problem == null).put("message", problem ?: "")
                synchronized(acks) { acks.addLast(System.currentTimeMillis() to ack) }
            }
            kick()
        }
    }

    /** Một lệnh từ máy tính (luồng chính). Trả lý do nếu không làm được - máy tính hiện cho người dùng. */
    private fun apply(command: JSONObject): String? {
        val loaded = Playback.player != null && Playback.bookId.isNotEmpty()
        when (command.optString("action")) {
            "play", "toggle" -> when {
                loaded && command.optString("action") == "toggle" -> Playback.toggle()
                loaded -> Playback.play()
                Playback.lastListened() == null -> return "Điện thoại chưa nghe cuốn nào"
                else -> withService { Playback.resumeLast() }
            }
            "pause" -> if (loaded) Playback.pause()
            "skip" -> if (loaded) Playback.skip(command.optDouble("seconds", 0.0))
            "seek" -> if (loaded) Playback.seekTo(command.optDouble("seconds", 0.0))
            "next" -> if (loaded) Playback.next()
            "previous" -> if (loaded) Playback.previous()
            "jump" -> if (loaded) Playback.jumpTo(command.optInt("chapterId"), command.optDouble("seconds", 0.0))
            "rate" -> if (loaded) Playback.setRate(command.optDouble("rate", 1.0).coerceIn(0.5, 3.0))
            "load" -> return load(command)
            else -> return "Điện thoại chưa hiểu lệnh này - cập nhật app trên điện thoại"
        }
        return null
    }

    /** "Phát trên điện thoại": nạp đúng cuốn, đúng chương, đúng giây máy tính đang nghe. */
    private fun load(command: JSONObject): String? {
        val id = command.optString("bookId")
        val manifest = Store.manifest(id) ?: return "Điện thoại chưa tải cuốn này"
        val chapters = Playback.chaptersOf(manifest).filter { Store.file(id, it.file).isFile }
        val chapterId = command.optInt("chapterId")
        if (chapters.none { it.id == chapterId }) return "Điện thoại chưa tải chương này - mở Thư viện trên điện thoại để cập nhật"
        val rate = Store.state(id).optDouble("rate", 1.0)
        withService {
            Playback.load(id, manifest.optString("title"), manifest.optString("narrator"), chapters, chapterId,
                command.optDouble("seconds", 0.0), rate, autoplay = true)
        }
        return null
    }

    /** Dịch vụ phát chưa chạy (mở app mà chưa nghe gì): dựng nó như PlayerPlugin rồi mới làm. */
    private fun withService(block: () -> Unit) {
        if (Playback.player != null) {
            block()
            return
        }
        val future = service ?: MediaController.Builder(
            context, SessionToken(context, ComponentName(context, PlaybackService::class.java)),
        ).setApplicationLooper(Looper.getMainLooper()).buildAsync().also { service = it }
        future.addListener({ Playback.onMain(block) }, MoreExecutors.directExecutor())
    }
}
