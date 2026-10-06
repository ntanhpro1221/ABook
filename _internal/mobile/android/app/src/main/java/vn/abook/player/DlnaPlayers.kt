package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.FutureTask
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock

/**
 * Điện thoại phát sách CỦA NÓ lên loa / TV (01-10) - cùng bộ não với máy tính (webui/cast.CastPlayers): một luồng nền tìm
 * thiết bị khi có người đang xem (nhịp 30 giây) và hỏi thiết bị đang phát mỗi giây - KỂ CẢ khi app ở nền - để lưu chỗ nghe
 * và tự sang chương sau. [view] chỉ đọc bản chụp, không đợi mạng. Lệnh ([send]) chạy thẳng trong luồng gọi, mỗi thiết bị
 * một khoá (có TV nghẹn khi hai lệnh chồng nhau).
 *
 * Hai giao thức (02-10), mỗi giao thức một [CastBackend]: DLNA ([DlnaBackend], tìm bằng SSDP) và Google Cast - Chromecast,
 * Google TV, loa Nest ([GoogleCast], tìm bằng mDNS). Phiên phát, vòng hỏi, lưu chỗ nghe, sang chương, nhận ra bị chiếm máy
 * đều chung ở đây; backend chỉ nói chuyện với MỘT thiết bị.
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
    /** Google Cast (mDNS, đã đủ thông tin) - mặc định không tìm gì, để bài thử không gửi multicast ra mạng; app đưa `GCast.discover` vào. */
    private val findGoogle: () -> List<Dlna.Renderer> = { emptyList() },
    private val backend: (Dlna.Renderer) -> CastBackend = ::backendFor,
    /** Vừa có phiên phát (đưa chương): app giữ một dịch vụ chạy nền để TV không đứt khi màn hình tắt (CastService). */
    private val onSession: () -> Unit = {},
) {
    data class Chapter(val id: Int, val title: String, val duration: Double, val file: File)
    data class Book(val title: String, val chapters: List<Chapter>)

    private class Session(val bookId: String, val bookTitle: String, val chapters: List<Chapter>, var chapter: Chapter, val url: String) {
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

    /**
     * Hẹn giờ tắt của một thiết bị - đếm ở đây vì chỉ điện thoại biết thiết bị đang phát hay dừng (hỏi mỗi giây), như hẹn
     * giờ của trình phát trong app: thời gian chỉ trôi khi ĐANG PHÁT. Theo thiết bị, không theo phiên: sang chương vẫn đếm.
     * [minutes] 0: dừng khi hết chương này. Như `cast._Sleep` của máy tính.
     */
    private class Sleep(val minutes: Double, var leftMs: Double = minutes * 60_000, var since: Long = 0L) {
        fun remaining(now: Long): Double = maxOf(0.0, leftMs - if (since > 0) maxOf(0L, now - since).toDouble() else 0.0)

        /** Đồng hồ ngừng khi thiết bị dừng, chạy tiếp khi nó phát. */
        fun follow(playing: Boolean, now: Long) {
            if (playing && since == 0L) {
                since = now
            } else if (!playing && since != 0L) {
                leftMs = remaining(now)
                since = 0L
            }
        }

        fun view(now: Long): JSONObject = if (minutes <= 0) {
            JSONObject().put("kind", "chapter")
        } else {
            JSONObject().put("kind", "minutes").put("minutes", minutes).put("left", Math.round(remaining(now) / 100.0) / 10.0)
                .put("counting", since != 0L)
        }
    }

    /** Phiên đang mở, chụp lại cho phiên media (màn hình khoá, tai nghe - [CastPlayer]): không đợi mạng. */
    data class Now(
        val id: String,
        val device: String,
        val bookId: String,
        val bookTitle: String,
        val chapters: List<Chapter>,
        val chapterId: Int,
        val position: Double,
        val duration: Double,
        val playing: Boolean,
        val buffering: Boolean,
    )

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
    private val backends = HashMap<String, CastBackend>() // thiết bị -> backend đang giữ kết nối (có phiên) hay vừa dùng
    private val sessions = HashMap<String, Session>()
    private val sleeps = HashMap<String, Sleep>() // thiết bị -> hẹn giờ tắt đang đặt
    private val deviceLocks = ConcurrentHashMap<String, ReentrantLock>()
    private val random = SecureRandom()
    private val wake = Semaphore(0)
    private var wanted = 0L
    private var searched = 0L
    private var thread: Thread? = null

    // -- nhìn -----------------------------------------------------------------------------------------------------

    /** Mỗi thiết bị một "trình phát" cùng hình dạng /sync/v1/player (thêm `id`, `protocol`) - RemotePlayers đặt mã "dlna:<id>". */
    fun view(): JSONArray {
        val now = System.currentTimeMillis()
        val items = synchronized(lock) {
            wanted = now
            ensureThread()
            renderers.values.map { (renderer, _) -> Triple(renderer, sessions[renderer.id], sleeps[renderer.id]?.view(now)) }
        }
        return JSONArray().also { out -> items.forEach { (renderer, session, sleep) -> out.put(presence(renderer, session, sleep, now)) } }
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

    /** Phiên cho màn hình khoá, tai nghe: thiết bị đang phát trước, không thì phiên đang dừng đầu tiên; null khi không có. */
    fun now(): Now? = synchronized(lock) {
        val (id, session) = sessions.entries.filter { !it.value.ended && it.key in renderers }
            .sortedByDescending { it.value.playing }.firstOrNull()?.toPair() ?: return null
        Now(id, renderers.getValue(id).first.name, session.bookId, session.bookTitle, session.chapters, session.chapter.id,
            session.estimate(System.currentTimeMillis()), session.duration, session.playing, session.buffering)
    }

    /** Thôi phát trên thiết bị (nút "Dừng" của thông báo): thiết bị dừng hẳn, chỗ nghe lưu ở chỗ dừng, phiên đóng. */
    fun end(id: String) {
        val (renderer, session) = synchronized(lock) { renderers[id]?.first to sessions[id] }
        if (renderer == null || session == null || session.ended) return
        val device = deviceLocks.getOrPut(id) { ReentrantLock() }
        device.lock()
        try {
            session.ended = true
            synchronized(lock) { sleeps.remove(id) }
            store(session, session.estimate(System.currentTimeMillis()))
            stop(renderer, 5000)
        } finally {
            device.unlock()
        }
    }

    /**
     * App thôi phục vụ: thiết bị đang phát sách của điện thoại dừng hẳn, chỗ nghe lưu ở chỗ dừng, đóng cổng audio (sắp đóng -
     * để thiết bị phát nốt phần đã tải rồi báo lỗi thì khó hiểu hơn).
     */
    fun close() {
        val active = synchronized(lock) {
            sleeps.clear()
            sessions.filter { !it.value.ended && it.key in renderers }.map { renderers.getValue(it.key).first to it.value }
        }
        for ((renderer, session) in active) {
            session.ended = true
            store(session, session.estimate(System.currentTimeMillis()))
            stop(renderer, 2000)
        }
        val rest = synchronized(lock) { backends.values.toList().also { backends.clear() } }
        rest.forEach { runCatching { it.close() } }
        media.close()
    }

    /** Dừng thiết bị và trả nó về nguyên trạng; thiết bị không trả lời thì thôi - chỗ nghe đã lưu rồi. */
    private fun stop(renderer: Dlna.Renderer, timeoutMs: Int) {
        val client = synchronized(lock) { backends.remove(renderer.id) } ?: return
        try {
            client.stop(timeoutMs)
        } catch (_: Dlna.Failure) {
        }
        runCatching { client.close(release = true) }
    }

    private fun presence(renderer: Dlna.Renderer, session: Session?, sleep: JSONObject?, now: Long): JSONObject {
        val out = JSONObject().put("id", renderer.id).put("name", renderer.name).put("kind", renderer.kind)
            .put("protocol", renderer.protocol).put("stream", false).put("books", JSONArray()).put("acks", JSONArray())
        if (session == null || session.ended) return out.put("state", JSONObject.NULL).put("age", 0.0).put("sleep", JSONObject.NULL)
        out.put("sleep", sleep ?: JSONObject.NULL)
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
        followSleep(id)
        wake.release()
        return JSONObject().put("id", ByteArray(6).also(random::nextBytes).joinToString("") { "%02x".format(it) })
    }

    private fun apply(renderer: Dlna.Renderer, session: Session?, command: JSONObject) {
        val action = command.optString("action")
        if (action == "load") {
            val chosen = book(command.optString("bookId")) ?: throw Dlna.Failure("điện thoại không có cuốn này")
            val chapter = chosen.chapters.firstOrNull { it.id == command.optInt("chapterId", -1) } ?: throw Dlna.Failure("chương này chưa nghe được")
            load(renderer, command.optString("bookId"), chosen.title, chosen.chapters, chapter, command.optDouble("seconds", 0.0))
            synchronized(lock) { sleeps.remove(renderer.id) } // một lần "Phát trên…" mới: không mang hẹn giờ của lần trước
            return
        }
        if (action == "rate") {
            if (Math.abs(command.optDouble("rate", 1.0) - 1.0) > 0.01) throw Dlna.Failure("loa, TV chỉ phát ở tốc độ 1x")
            return
        }
        // Hẹn giờ tắt: `minutes` > 0 (đếm khi đang phát) hay `endOfChapter`; không có gì = tắt hẹn giờ.
        val chapterEnd = action == "sleep" && command.optBoolean("endOfChapter")
        val minutes = command.optDouble("minutes", 0.0).takeIf { !it.isNaN() }?.coerceIn(0.0, 1440.0) ?: 0.0
        if (session == null) {
            // "Nghe trên máy này" / tắt hẹn giờ sau khi thiết bị đã bị chiếm hay tự hết: không còn gì để làm
            if (action == "stop" || action == "sleep" && !chapterEnd && minutes <= 0) return
            throw Dlna.Failure("chưa phát gì từ điện thoại này")
        }
        val client = backendOf(renderer)
        val now = System.currentTimeMillis()
        when (action) {
            "stop" -> {
                // Người nghe chuyển sang máy khác: dừng hẳn, trả thiết bị về nguyên trạng, chỗ nghe lưu đúng chỗ dừng.
                session.ended = true
                synchronized(lock) { sleeps.remove(renderer.id) }
                store(session, session.estimate(now))
                stop(renderer, 5000)
            }
            "sleep" -> {
                val sleep = when {
                    chapterEnd -> Sleep(0.0)
                    minutes > 0 -> Sleep(minutes, since = if (session.playing) now else 0L)
                    else -> null
                }
                synchronized(lock) {
                    if (sleep != null) sleeps.put(renderer.id, sleep) else sleeps.remove(renderer.id)
                }
            }
            "play", "pause", "toggle" -> {
                val want = if (action == "toggle") !session.playing else action == "play"
                if (!want) {
                    pause(client, session, now)
                    return
                }
                if (session.held || session.state == "STOPPED" || session.state == "NO_MEDIA_PRESENT") {
                    load(renderer, session.bookId, session.bookTitle, session.chapters, session.chapter, session.position)
                    return
                }
                client.play()
                session.grace = now + graceMs
                session.playing = true
                session.buffering = true
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
                client.seek(target)
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

    /** Tạm dừng (nút, hẹn giờ tắt): thiết bị không có Pause thì dừng hẳn và nhớ chỗ; chỗ nghe lưu ngay. Giữ khoá thiết bị. */
    private fun pause(client: CastBackend, session: Session, now: Long) {
        session.position = session.estimate(now)
        session.held = client.pause() || session.held
        store(session, session.position)
        session.playing = false
        session.buffering = false
        session.polled = now
    }

    /** Cho đồng hồ hẹn giờ theo thiết bị đang phát hay dừng -> mili giây còn lại (null: không hẹn, hay hẹn hết chương). */
    private fun followSleep(id: String): Double? = synchronized(lock) {
        val sleep = sleeps[id]
        val session = sessions[id]
        if (sleep == null || sleep.minutes <= 0 || session == null) return null
        val now = System.currentTimeMillis()
        sleep.follow(session.playing && !session.ended, now)
        sleep.remaining(now)
    }

    /**
     * Hẹn "hết chương" đã tới: dừng ở đây nhưng trỏ phiên sang chương kế ở 0:00 và lưu nó làm chỗ nghe tiếp - như trình
     * phát trong app, sáng mai bấm phát là vào chương mới (thiết bị đã dừng: "phát" đưa chương ấy cho nó).
     */
    private fun park(session: Session, following: Chapter) {
        session.chapter = following
        session.duration = following.duration
        session.position = 0.0
        session.peak = 0.0
        session.playing = false
        session.buffering = false
        session.held = true
        session.polled = System.currentTimeMillis()
        store(session, 0.0)
    }

    /** Đưa một chương cho thiết bị và phát từ [seconds]. Gọi khi đã giữ khoá thiết bị. */
    private fun load(renderer: Dlna.Renderer, bookId: String, bookTitle: String, chapters: List<Chapter>, chapter: Chapter, seconds: Double) {
        if (!chapter.file.isFile) throw Dlna.Failure("chương này chưa có trên điện thoại")
        val url = media.share(chapter.file, renderer.host)
        val mime = if (chapter.file.extension.equals("mp3", true)) "audio/mpeg" else "audio/mp4"
        val track = CastTrack(url, chapter.title, bookTitle, chapter.duration, chapter.file.length(), mime)
        val resume = seconds >= 1 && (chapter.duration <= 0 || seconds < chapter.duration - 1)
        val started = try {
            backendOf(renderer).load(track, if (resume) seconds else 0.0)
        } catch (error: Dlna.Failure) {
            val idle = synchronized(lock) { sessions[renderer.id].let { it == null || it.ended } }
            if (idle) release(renderer.id, stop = true) // lần đưa đầu hỏng: đừng giữ kết nối (Cast: cả ứng dụng đã mở) cho một phiên không có
            throw error
        }
        val now = System.currentTimeMillis()
        val session = Session(bookId, bookTitle, chapters, chapter, url).apply {
            polled = now
            heard = now
            saved = now
            grace = now + graceMs
        }
        if (resume) {
            session.position = started
            session.peak = started
        }
        val previous = synchronized(lock) { sessions.put(renderer.id, session) }
        if (previous != null && !previous.ended && previous.chapter.id != chapter.id) store(previous, previous.position)
        store(session, session.position) // "Nghe tiếp" trỏ ngay tới chương đang phát trên thiết bị
        runCatching(onSession)
    }

    private fun backendOf(renderer: Dlna.Renderer): CastBackend = synchronized(lock) {
        backends.getOrPut(renderer.id) { backend(renderer) }
    }

    /** Bỏ backend của thiết bị (phiên đã hết); [stop]: trả thiết bị về nguyên trạng - không dùng khi bị chiếm máy. */
    private fun release(id: String, stop: Boolean = false) {
        val client = synchronized(lock) { backends.remove(id) }
        client?.let { runCatching { it.close(release = stop) } }
    }

    /** Phiên hết (bị chiếm máy, thiết bị tắt, hết chương cuối): thôi hỏi, đóng kết nối - không đụng tới thứ đang phát. */
    private fun finish(id: String, session: Session) {
        session.ended = true
        val current = synchronized(lock) { (sessions[id] === session).also { if (it) sleeps.remove(id) } }
        if (current) release(id)
    }

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
        // mDNS và SSDP cùng lúc: một lượt tìm vẫn chừng 2 giây.
        val google = FutureTask<List<Dlna.Renderer>> { runCatching { findGoogle() }.getOrDefault(emptyList()) }
        Thread(google, "cast-google").apply { isDaemon = true }.start()
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
        val casts = runCatching { google.get(15, TimeUnit.SECONDS) }.getOrDefault(emptyList())
        synchronized(lock) {
            (results.filterNotNull() + casts).forEach { renderers[it.id] = it to now }
            renderers.entries.removeIf { (id, entry) ->
                now - entry.second > forgetAfterMs && sessions[id].let { it == null || it.ended }
            }
        }
    }

    private fun poll(id: String) {
        val (renderer, session, client) = synchronized(lock) { Triple(renderers[id]?.first, sessions[id], backends[id]) }
        if (renderer == null || session == null || session.ended || client == null) return
        val device = deviceLocks.getOrPut(id) { ReentrantLock() }
        if (!device.tryLock(200, TimeUnit.MILLISECONDS)) return // đang có lệnh: lượt sau hỏi
        try {
            if (synchronized(lock) { sessions[id] } !== session) return
            val status = try {
                client.status()
            } catch (_: Dlna.Failure) {
                session.buffering = session.playing
                if (System.currentTimeMillis() - session.heard > lostAfterMs) {
                    store(session, session.position)
                    finish(id, session)
                }
                return
            }
            val advance = observe(session, status)
            if (session.ended) { // bị chiếm máy hay thiết bị báo lỗi: lưu chỗ nghe cuối rồi thôi
                store(session, session.estimate(System.currentTimeMillis()))
                finish(id, session)
                return
            }
            if (advance) {
                store(session, session.duration) // chương xong: "đã nghe hết" như trình phát trong app
                val following = neighbour(session, 1)
                if (following == null) {
                    finish(id, session)
                    return
                }
                val asleep = synchronized(lock) { sleeps[id]?.takeIf { it.minutes <= 0 }?.also { sleeps.remove(id) } != null }
                if (asleep) {
                    park(session, following)
                    return
                }
                try {
                    load(renderer, session.bookId, session.bookTitle, session.chapters, following, 0.0)
                } catch (_: Dlna.Failure) {
                    finish(id, session)
                }
                return
            }
            val left = followSleep(id)
            if (left != null && left <= 0 && session.playing) {
                try {
                    pause(client, session, System.currentTimeMillis())
                } catch (_: Dlna.Failure) {
                    return // thiết bị không nhận lệnh lượt này: hẹn giờ còn đó, lượt hỏi sau thử lại
                }
                synchronized(lock) { sleeps.remove(id) }
            }
        } finally {
            device.unlock()
        }
    }

    /** Cập nhật phiên theo lời thiết bị; true khi vừa hết chương (thiết bị báo hết, hay đã tới cuối rồi về STOPPED). */
    private fun observe(session: Session, status: CastStatus): Boolean {
        val now = System.currentTimeMillis()
        session.heard = now
        val state = status.state
        if (status.uri.isNotEmpty() && session.token !in status.uri && state in setOf("PLAYING", "PAUSED_PLAYBACK", "TRANSITIONING")) {
            session.ended = true // có người phát thứ khác trên thiết bị (app khác, điều khiển TV)
            return false
        }
        if (status.reason == "interrupted" || status.reason == "error") {
            session.ended = true // bị chiếm máy, hay thiết bị không phát được file
            return false
        }
        // Độ dài thật của file; đang dừng hẳn thì thiết bị có thể còn báo chương trước (hẹn "hết chương" đã trỏ sang chương kế).
        if (!session.held && status.duration > 1 && Math.abs(status.duration - session.duration) > 1) session.duration = status.duration
        var reported = status.position
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
            status.reason == "finished" && session.playing && !session.held -> advance = true // thiết bị tự nói đã hết (Cast: IDLE / FINISHED)
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
