package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock

/**
 * Điện thoại phát sách CỦA NÓ lên loa / TV (01-10) - cùng bộ não với máy tính (webui/cast.CastPlayers): một luồng nền tìm
 * thiết bị khi có người đang xem (nhịp 30 giây) và hỏi thiết bị đang phát mỗi giây - KỂ CẢ khi app ở nền - để lưu chỗ nghe
 * và tự sang chương sau. [view] chỉ đọc bản chụp, không đợi mạng. Lệnh ([send]) chạy thẳng trong luồng gọi, mỗi thiết bị
 * một khoá (có TV nghẹn khi hai lệnh chồng nhau).
 *
 * Chỗ TV thật hay vấp (thử bằng loa giả, DlnaTest): chỉ tua được khi đã chạy (Play, đợi PLAYING rồi mới Seek), hết bài về
 * STOPPED với vị trí 0 (nhớ vị trí xa nhất), không có Pause (dừng hẳn, "phát" đưa lại đúng chỗ), không báo vị trí (ước
 * theo đồng hồ), app khác chiếm thiết bị (bỏ phiên).
 */
class DlnaPlayers(
    private val book: (String) -> Book?,
    private val save: (String, Int, Double, Double) -> Unit,
    private val media: Dlna.Media = Dlna.Media(),
    private val find: () -> List<Pair<String, String>> = { Dlna.search() },
    private val read: (String, String) -> Dlna.Renderer? = { location, host -> Dlna.describe(location, host) },
    /** Vừa có phiên phát (đưa chương): app giữ một dịch vụ chạy nền để TV không đứt khi màn hình tắt (CastService). */
    private val onSession: () -> Unit = {},
) {
    data class Chapter(val id: Int, val title: String, val duration: Double, val file: File)
    data class Book(val title: String, val chapters: List<Chapter>)

    private class Session(val bookId: String, val bookTitle: String, val chapters: List<Chapter>, val chapter: Chapter, val url: String) {
        var duration = chapter.duration
        var position = 0.0
        var playing = true
        var buffering = true
        var state = ""
        var peak = 0.0
        var polled = 0L
        var heard = 0L
        var saved = 0L
        var grace = 0L
        var held = false
        var ended = false
        val token: String get() = url.substringAfterLast('/').substringBefore('.')

        fun estimate(now: Long): Double {
            if (!playing || buffering || polled == 0L) return position
            val at = position + maxOf(0L, now - polled) / 1000.0
            return if (duration > 0) minOf(at, duration) else at
        }
    }

    // Nhịp (bài thử rút ngắn).
    var searchEveryMs = 30_000L
    var forgetAfterMs = 95_000L
    var wantedForMs = 15_000L
    var playingPollMs = 1_000L
    var idlePollMs = 3_000L
    var graceMs = 6_000L
    var lostAfterMs = 60_000L
    private val endSlack = 4.0
    private val saveEveryMs = 10_000L

    private val lock = Any()
    private val renderers = LinkedHashMap<String, Pair<Dlna.Renderer, Long>>()
    private val described = HashMap<String, Pair<Long, Dlna.Renderer?>>()
    private val sessions = HashMap<String, Session>()
    private val deviceLocks = ConcurrentHashMap<String, ReentrantLock>()
    private val random = SecureRandom()
    private val wake = Semaphore(0)
    private var wanted = 0L
    private var searched = 0L
    private var thread: Thread? = null

    // -- nhìn -----------------------------------------------------------------------------------------------------

    /** Mỗi thiết bị một "trình phát" cùng hình dạng /sync/v1/player (thêm `id`) - RemotePlayers đặt mã "dlna:<id>". */
    fun view(): JSONArray {
        val now = System.currentTimeMillis()
        val items = synchronized(lock) {
            wanted = now
            ensureThread()
            renderers.values.map { (renderer, _) -> renderer to sessions[renderer.id] }
        }
        return JSONArray().also { out -> items.forEach { (renderer, session) -> out.put(presence(renderer, session, now)) } }
    }

    /** Người dùng mở "Phát trên…": tìm lại ngay. */
    fun scan() {
        synchronized(lock) {
            wanted = System.currentTimeMillis()
            searched = 0
            ensureThread()
        }
        wake.release()
    }

    fun owns(id: String): Boolean = synchronized(lock) { id in renderers }

    /** Tên thiết bị đang có phiên (đang phát hay tạm dừng) - dịch vụ chạy nền sống chừng nào danh sách còn khác rỗng. */
    fun active(): List<String> = synchronized(lock) {
        sessions.filter { !it.value.ended }.keys.mapNotNull { renderers[it]?.first?.name }
    }

    /** Phiên đang mở: (mã thiết bị, có đang phát không) - nút trên thông báo của CastService. */
    fun playing(): List<Pair<String, Boolean>> = synchronized(lock) {
        sessions.filter { !it.value.ended }.map { it.key to it.value.playing }
    }

    /** Thôi phát trên thiết bị (nút "Dừng" của thông báo): thiết bị dừng hẳn, chỗ nghe lưu ở chỗ dừng, phiên đóng. */
    fun end(id: String) {
        val (renderer, session) = synchronized(lock) { renderers[id]?.first to sessions[id] }
        if (renderer == null || session == null || session.ended) return
        val device = deviceLocks.getOrPut(id) { ReentrantLock() }
        device.lock()
        try {
            session.ended = true
            store(session, session.estimate(System.currentTimeMillis()))
            runCatching { call(renderer, "Stop") }
        } finally {
            device.unlock()
        }
    }

    /** App thôi phục vụ: thiết bị đang phát sách của điện thoại dừng hẳn, chỗ nghe lưu ở chỗ dừng, đóng cổng audio. */
    fun close() {
        val active = synchronized(lock) {
            sessions.filter { !it.value.ended && it.key in renderers }.map { renderers.getValue(it.key).first to it.value }
        }
        for ((renderer, session) in active) {
            session.ended = true
            store(session, session.estimate(System.currentTimeMillis()))
            runCatching { Dlna.soap(renderer.avUrl, renderer.avType, "Stop", listOf("InstanceID" to 0), timeoutMs = 2000) }
        }
        media.close()
    }

    private fun presence(renderer: Dlna.Renderer, session: Session?, now: Long): JSONObject {
        val out = JSONObject().put("id", renderer.id).put("name", renderer.name).put("kind", renderer.kind)
            .put("stream", false).put("books", JSONArray()).put("acks", JSONArray())
        if (session == null || session.ended) return out.put("state", JSONObject.NULL).put("age", 0.0)
        val state = JSONObject().put("bookId", session.bookId).put("bookTitle", session.bookTitle)
            .put("chapterId", session.chapter.id).put("chapterTitle", session.chapter.title)
            .put("position", session.position).put("duration", session.duration).put("playing", session.playing)
            .put("buffering", session.buffering).put("rate", 1.0)
        return out.put("state", state).put("age", if (session.polled > 0) maxOf(0L, now - session.polled) / 1000.0 else 0.0)
    }

    // -- lệnh -------------------------------------------------------------------------------------------------------

    /** Lệnh cùng hình dạng RemotePlayers gửi máy khác; lỗi -> [Dlna.Failure] "<tên thiết bị>: <vì sao>". */
    fun send(id: String, command: JSONObject): JSONObject {
        val (renderer, session) = synchronized(lock) { renderers[id]?.first to sessions[id] }
        renderer ?: throw Dlna.Failure("Không còn thấy thiết bị này trong mạng")
        val device = deviceLocks.getOrPut(id) { ReentrantLock() }
        device.lock()
        try {
            apply(renderer, session?.takeIf { !it.ended }, command)
        } catch (error: Dlna.Failure) {
            throw Dlna.Failure("${renderer.name}: ${error.message}", error.code)
        } finally {
            device.unlock()
        }
        wake.release()
        return JSONObject().put("id", ByteArray(6).also(random::nextBytes).joinToString("") { "%02x".format(it) })
    }

    private fun apply(renderer: Dlna.Renderer, session: Session?, command: JSONObject) {
        val action = command.optString("action")
        if (action == "load") {
            val chosen = book(command.optString("bookId")) ?: throw Dlna.Failure("điện thoại không có cuốn này")
            val chapter = chosen.chapters.firstOrNull { it.id == command.optInt("chapterId", -1) } ?: throw Dlna.Failure("chương này chưa nghe được")
            load(renderer, command.optString("bookId"), chosen.title, chosen.chapters, chapter, command.optDouble("seconds", 0.0))
            return
        }
        if (action == "rate") {
            if (Math.abs(command.optDouble("rate", 1.0) - 1.0) > 0.01) throw Dlna.Failure("loa, TV chỉ phát ở tốc độ 1x")
            return
        }
        session ?: throw Dlna.Failure("chưa phát gì từ điện thoại này")
        val now = System.currentTimeMillis()
        when (action) {
            "play", "pause", "toggle" -> {
                val want = if (action == "toggle") !session.playing else action == "play"
                if (want) {
                    if (session.held || session.state == "STOPPED" || session.state == "NO_MEDIA_PRESENT") {
                        load(renderer, session.bookId, session.bookTitle, session.chapters, session.chapter, session.position)
                        return
                    }
                    call(renderer, "Play", "Speed" to "1")
                    session.grace = now + graceMs
                } else {
                    session.position = session.estimate(now)
                    try {
                        call(renderer, "Pause")
                    } catch (error: Dlna.Failure) {
                        if (error.code != 401 && error.code != 701) throw error
                        call(renderer, "Stop") // thiết bị không có Pause: dừng hẳn, "phát" đưa lại đúng chỗ
                        session.held = true
                    }
                    store(session, session.position)
                }
                session.playing = want
                session.buffering = want
                session.polled = now
            }
            "seek", "skip" -> {
                var target = command.optDouble("seconds", 0.0) + if (action == "skip") session.estimate(now) else 0.0
                if (action == "skip" && session.duration > 0 && target >= session.duration - 1) {
                    neighbour(session, 1)?.let {
                        load(renderer, session.bookId, session.bookTitle, session.chapters, it, 0.0)
                        return
                    }
                }
                target = maxOf(0.0, if (session.duration > 1) minOf(target, session.duration - 1) else target)
                call(renderer, "Seek", "Unit" to "REL_TIME", "Target" to Dlna.clock(target))
                session.position = target
                session.peak = target
                session.polled = now
            }
            "next", "previous", "jump" -> {
                val chapter = if (action == "jump") {
                    session.chapters.firstOrNull { it.id == command.optInt("chapterId", -1) } ?: throw Dlna.Failure("chương này chưa nghe được")
                } else {
                    neighbour(session, if (action == "next") 1 else -1)
                        ?: throw Dlna.Failure(if (action == "next") "đã là chương cuối" else "đã là chương đầu")
                }
                load(renderer, session.bookId, session.bookTitle, session.chapters, chapter,
                    if (action == "jump") command.optDouble("seconds", 0.0) else 0.0)
            }
            else -> throw Dlna.Failure("thiết bị chưa làm được lệnh này")
        }
    }

    /** Đưa một chương cho thiết bị và phát từ [seconds]. Gọi khi đã giữ khoá thiết bị. */
    private fun load(renderer: Dlna.Renderer, bookId: String, bookTitle: String, chapters: List<Chapter>, chapter: Chapter, seconds: Double) {
        if (!chapter.file.isFile) throw Dlna.Failure("chương này chưa có trên điện thoại")
        val url = media.share(chapter.file, renderer.host)
        val mime = if (chapter.file.extension.equals("mp3", true)) "audio/mpeg" else "audio/mp4"
        val metadata = Dlna.didl(url, chapter.title, bookTitle, chapter.duration, chapter.file.length(), mime)
        val arguments = arrayOf<Pair<String, Any>>("CurrentURI" to url, "CurrentURIMetaData" to metadata)
        try {
            call(renderer, "SetAVTransportURI", *arguments)
        } catch (error: Dlna.Failure) {
            if (error.code != 701 && error.code != 705) throw error
            call(renderer, "Stop") // có TV không nhận bài mới khi đang phát bài cũ
            call(renderer, "SetAVTransportURI", *arguments)
        }
        call(renderer, "Play", "Speed" to "1")
        val now = System.currentTimeMillis()
        val session = Session(bookId, bookTitle, chapters, chapter, url).apply {
            polled = now
            heard = now
            saved = now
            grace = now + graceMs
        }
        if (seconds >= 1 && (chapter.duration <= 0 || seconds < chapter.duration - 1)) {
            session.position = seekWhenReady(renderer, seconds)
            session.peak = session.position
        }
        val previous = synchronized(lock) { sessions.put(renderer.id, session) }
        if (previous != null && !previous.ended && previous.chapter.id != chapter.id) store(previous, previous.position)
        store(session, session.position)
        runCatching(onSession)
    }

    /** Phần lớn TV chỉ tua được khi đã chạy: đợi PLAYING (tới 8 giây) rồi tua. Không tua được thì phát từ đầu. */
    private fun seekWhenReady(renderer: Dlna.Renderer, seconds: Double): Double {
        val deadline = System.currentTimeMillis() + 8000
        while (System.currentTimeMillis() < deadline) {
            val state = runCatching { call(renderer, "GetTransportInfo")["CurrentTransportState"] }.getOrNull().orEmpty()
            if (state == "PLAYING" || state == "PAUSED_PLAYBACK") {
                return try {
                    call(renderer, "Seek", "Unit" to "REL_TIME", "Target" to Dlna.clock(seconds))
                    seconds
                } catch (_: Dlna.Failure) {
                    0.0
                }
            }
            Thread.sleep(300)
        }
        return 0.0
    }

    private fun call(renderer: Dlna.Renderer, action: String, vararg arguments: Pair<String, Any>): Map<String, String> =
        Dlna.soap(renderer.avUrl, renderer.avType, action, listOf<Pair<String, Any>>("InstanceID" to 0) + arguments)

    private fun neighbour(session: Session, step: Int): Chapter? {
        val index = session.chapters.indexOfFirst { it.id == session.chapter.id }
        if (index < 0) return null
        return session.chapters.getOrNull(index + step)
    }

    private fun store(session: Session, seconds: Double) {
        session.saved = System.currentTimeMillis()
        runCatching { save(session.bookId, session.chapter.id, seconds, session.duration) }
    }

    // -- nền --------------------------------------------------------------------------------------------------------

    private fun ensureThread() {
        if (thread?.isAlive == true) return
        thread = Thread(::loop, "dlna-players").apply {
            isDaemon = true
            start()
        }
    }

    private fun loop() {
        while (true) {
            val now = System.currentTimeMillis()
            val (wanting, active, due) = synchronized(lock) {
                val wanting = now - wanted < wantedForMs
                val active = sessions.filter { !it.value.ended }.keys.toList()
                if (!wanting && active.isEmpty()) {
                    thread = null
                    return
                }
                val due = wanting && now - searched >= searchEveryMs
                if (due) searched = now
                Triple(wanting, active, due)
            }
            if (due) search()
            active.forEach(::poll)
            val playing = synchronized(lock) { sessions.values.any { it.playing && !it.ended } }
            wake.drainPermits()
            wake.tryAcquire(if (playing || active.isEmpty() || wanting && active.isEmpty()) playingPollMs else idlePollMs, TimeUnit.MILLISECONDS)
        }
    }

    private fun search() {
        val found = runCatching { find() }.getOrDefault(emptyList())
        val now = System.currentTimeMillis()
        val pool = Executors.newFixedThreadPool(maxOf(1, minOf(8, found.size)))
        val results = try {
            found.map { (location, host) ->
                pool.submit<Dlna.Renderer?> {
                    val cached = synchronized(lock) { described[location] }
                    // Mô tả giữ 10 phút; đọc hỏng thì thử lại sau 1 phút (thiết bị vừa bật còn khởi động).
                    if (cached != null && now - cached.first < if (cached.second != null) 600_000 else 60_000) {
                        cached.second
                    } else {
                        val renderer = runCatching { read(location, host) }.getOrNull()
                        synchronized(lock) { described[location] = now to renderer }
                        renderer
                    }
                }
            }.map { runCatching { it.get(10, TimeUnit.SECONDS) }.getOrNull() }
        } finally {
            pool.shutdown()
        }
        synchronized(lock) {
            results.filterNotNull().forEach { renderers[it.id] = it to now }
            renderers.entries.removeIf { (id, entry) ->
                now - entry.second > forgetAfterMs && sessions[id].let { it == null || it.ended }
            }
        }
    }

    private fun poll(id: String) {
        val (renderer, session) = synchronized(lock) { renderers[id]?.first to sessions[id] }
        if (renderer == null || session == null || session.ended) return
        val device = deviceLocks.getOrPut(id) { ReentrantLock() }
        if (!device.tryLock(200, TimeUnit.MILLISECONDS)) return // đang có lệnh: lượt sau hỏi
        try {
            if (synchronized(lock) { sessions[id] } !== session) return
            val (state, info) = try {
                call(renderer, "GetTransportInfo")["CurrentTransportState"].orEmpty().trim().uppercase() to call(renderer, "GetPositionInfo")
            } catch (_: Dlna.Failure) {
                session.buffering = session.playing
                if (System.currentTimeMillis() - session.heard > lostAfterMs) {
                    store(session, session.position)
                    session.ended = true
                }
                return
            }
            if (observe(session, state, info)) {
                store(session, session.duration) // chương xong: "đã nghe hết" như trình phát trong app
                val following = neighbour(session, 1)
                if (following == null) {
                    session.ended = true
                    return
                }
                try {
                    load(renderer, session.bookId, session.bookTitle, session.chapters, following, 0.0)
                } catch (_: Dlna.Failure) {
                    session.ended = true
                }
            }
        } finally {
            device.unlock()
        }
    }

    /** Cập nhật phiên theo lời thiết bị; true khi vừa hết chương (đã tới cuối rồi về STOPPED). */
    private fun observe(session: Session, state: String, info: Map<String, String>): Boolean {
        val now = System.currentTimeMillis()
        session.heard = now
        val uri = info["TrackURI"].orEmpty()
        if (uri.isNotEmpty() && session.token !in uri && state in setOf("PLAYING", "PAUSED_PLAYBACK", "TRANSITIONING")) {
            session.ended = true // có người phát thứ khác trên thiết bị (app khác, điều khiển TV)
            return false
        }
        val duration = Dlna.secondsOf(info["TrackDuration"])
        if (duration > 1 && Math.abs(duration - session.duration) > 1) session.duration = duration
        var reported = Dlna.secondsOf(info["RelTime"])
        val before = session.state
        session.state = state
        var advance = false
        when {
            state == "PLAYING" -> {
                if (reported <= 0 && session.playing && !session.buffering && session.polled > 0) {
                    reported = session.estimate(now) // thiết bị không báo vị trí: ước theo đồng hồ
                }
                session.playing = true
                session.buffering = false
                session.held = false
                session.position = reported
                session.peak = maxOf(session.peak, reported)
            }
            state == "PAUSED_PLAYBACK" -> {
                session.playing = false
                session.buffering = false
                if (reported > 0) session.position = reported
            }
            state == "TRANSITIONING" -> session.buffering = true
            now < session.grace -> session.buffering = session.playing
            session.held || !session.playing -> {
                session.playing = false
                session.buffering = false
            }
            session.duration > 0 && maxOf(session.peak, session.estimate(now)) >= session.duration - endSlack -> advance = true
            else -> { // dừng giữa chương: điều khiển TV, hay thiết bị không phát được
                session.playing = false
                session.buffering = false
            }
        }
        session.polled = now
        if (!advance && (state != before || session.playing && now - session.saved >= saveEveryMs)) store(session, session.position)
        return advance
    }
}
