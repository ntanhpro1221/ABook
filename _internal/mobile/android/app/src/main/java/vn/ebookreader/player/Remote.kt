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
import java.util.concurrent.atomic.AtomicInteger
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
    // Mã lệnh đã nhận: máy tính giao lại lệnh chưa thấy kết quả (lần trả lời trước có thể đã rơi) - mỗi mã làm một lần.
    private val handled = LinkedHashMap<String, Long>()
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
        val body = JSONObject().put("state", snapshot()).put("books", downloadedBooks())
            .put("stream", true) // nghe thẳng được mọi cuốn của máy tính, không chỉ cuốn đã tải
            .put("wait", wait)
        synchronized(acks) {
            val now = System.currentTimeMillis()
            while (acks.isNotEmpty() && now - acks.first().first > ACK_MS) acks.removeFirst()
            // Gửi lại kết quả lệnh trong 20 giây: giao diện máy tính hỏi 1,5 giây một lần, không được lỡ một lỗi.
            if (acks.isNotEmpty()) body.put("acks", JSONArray(acks.map { it.second }))
        }
        val reply = SyncLink.request(context, "POST", "/sync/v1/remote", body, readTimeoutMs = (wait + 15) * 1000)
        return JSONObject(reply).optJSONArray("commands")
    }

    /** Lệnh từ một máy đã ghép gửi THẲNG tới điện thoại (LibraryServer, POST /sync/v1/player - mạng trạm bước 4): làm ở
     *  luồng chính như lệnh của máy tính chính, trả lý do nếu không làm được. Chờ tối đa 5 giây. */
    fun applyNow(command: JSONObject): String? {
        val result = AtomicReference<String?>(null)
        val claim = AtomicInteger(0) // 0 chờ, 1 đã bắt đầu làm, 2 bên gọi đã bỏ
        val done = CountDownLatch(1)
        Playback.onMain {
            // Đã báo "không kịp" thì KHÔNG làm muộn: người bấm đã được bảo lệnh không thành, nó không được tự xảy ra sau.
            if (!claim.compareAndSet(0, 1)) return@onMain
            result.set(runCatching { apply(command) }.getOrElse { it.message ?: it.javaClass.simpleName })
            done.countDown()
            kick()
        }
        if (done.await(5, TimeUnit.SECONDS)) return result.get()
        if (claim.compareAndSet(0, 2)) return "Điện thoại không trả lời kịp"
        // Đã bắt đầu làm (luồng chính chậm): chờ kết quả thật thay vì báo sai.
        return if (done.await(10, TimeUnit.SECONDS)) result.get() else "Điện thoại vẫn đang làm lệnh này"
    }

    /** Trạng thái trình phát, đọc ở luồng chính (ExoPlayer chỉ cho đọc từ luồng của nó). */
    fun snapshot(): JSONObject {
        val result = AtomicReference(JSONObject())
        val done = CountDownLatch(1)
        Playback.onMain {
            runCatching { result.set(Playback.state()) }
            done.countDown()
        }
        done.await(2, TimeUnit.SECONDS)
        return result.get()
    }

    /** Sách đã tải xong về máy (có book.json) - máy tính biết cuốn nào nghe được cả khi mất mạng. */
    private fun downloadedBooks(): JSONArray = JSONArray().also { array ->
        File(Store.root, "books").listFiles()?.filter { File(it, "book.json").isFile }?.forEach { array.put(it.name) }
    }

    private fun execute(received: JSONArray?) {
        if (received == null || received.length() == 0) return
        val commands = JSONArray()
        synchronized(handled) {
            val now = System.currentTimeMillis()
            handled.entries.removeAll { now - it.value > 60_000L }
            for (index in 0 until received.length()) {
                val command = received.optJSONObject(index) ?: continue
                val id = command.optString("id")
                if (id.isNotEmpty() && handled.containsKey(id)) continue
                if (id.isNotEmpty()) handled[id] = now
                commands.put(command)
            }
        }
        if (commands.length() == 0) return
        // Việc mạng làm ở đây (luồng hỏi), trước khi sang luồng chính: "Phát trên điện thoại" một cuốn chưa tải thì lấy
        // gói sách từ máy tính để nghe thẳng.
        val fetchProblems = mutableMapOf<String, String>()
        for (index in 0 until commands.length()) {
            val command = commands.optJSONObject(index) ?: continue
            val id = command.optString("bookId")
            if (command.optString("action") == "load" && Store.manifest(id) == null) {
                runCatching { Streaming.fetchManifest(context, id) }
                    .onFailure { fetchProblems[command.optString("id")] = "Không lấy được sách từ máy tính: ${it.message}" }
            }
        }
        Playback.onMain {
            for (index in 0 until commands.length()) {
                val command = commands.optJSONObject(index) ?: continue
                val problem = fetchProblems[command.optString("id")]
                    ?: runCatching { apply(command) }.getOrElse { it.message ?: it.javaClass.simpleName }
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

    /** "Phát trên điện thoại": nạp đúng cuốn, đúng chương, đúng giây máy tính đang nghe - chương chưa tải thì nghe thẳng. */
    private fun load(command: JSONObject): String? {
        val id = command.optString("bookId")
        val manifest = Store.playableManifest(id) ?: return "Điện thoại chưa có cuốn này"
        val chapters = Playback.chaptersOf(manifest)
        val chapterId = command.optInt("chapterId")
        if (chapters.none { it.id == chapterId }) return "Chương này chưa nghe được trên điện thoại"
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
