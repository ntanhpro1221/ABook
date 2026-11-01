package vn.abook.player

import android.content.ComponentName
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaBrowser
import androidx.media3.session.SessionToken
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.readaloud.ClipCache
import vn.abook.player.readaloud.ReadAloud
import java.io.File
import java.io.FilterInputStream
import java.io.InputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Tải sẵn bài đầu chương kế ([NextChapterWarm]) ĐẦU-CUỐI qua đường phát thật: sách chữ tự viết, nhạc theo cảnh, giọng Edge (mạng), PlaybackService + ReadAloud +
 * MusicBed thật. Tua chương 1 tới còn [LEFT_SECONDS] giây, để giọng tự sang chương 2, rồi đo: (a) bài mốc đầu chương 2 đã nằm trên máy trước ranh chương chưa (và
 * lúc bắt đầu tải / tải xong, tính bằng giây còn lại của chương 1), (b) từ đầu chương 2 tới lúc trình phát nhạc của bài ấy thật sự chạy (mix_playing), (c) giọng
 * có khựng không (vị trí đứng yên >= [STALL_MS] khi đang phát) trong lúc tải sẵn so với phần còn lại.
 * Như nghe thật: bài các mốc cuối chương 1 tải trước khi tua (người nghe đã ở chương 1 nhiều phút), bài đầu chương 2 thì chưa; tải xong kịp ranh chương tuỳ tốc độ
 * nguồn (incompetech: 30-900 KB/s) nên chỉ bắt buộc khi nguồn đủ nhanh, còn lúc bắt đầu tải thì luôn bắt buộc.
 *
 * Tham số (`-e`): `choice` = "" (máy tự chọn nhạc, mặc định) hay "scene" (người nghe chọn "Theo cảnh": được tải qua mạng tính phí); `expectWarm` = "true" / "false"
 * (ca mạng di động tính phí: KHÔNG được tải sẵn); `left` = giây còn lại của chương 1 lúc bắt đầu nghe (mặc định [LEFT_SECONDS]); `kbps` = giả nguồn bài chậm (KB/s, bọc
 * luồng tải của MusicCatalog) - khi có thì bài chương 2 BẮT BUỘC có trên máy trước ranh chương. Số in logcat thẻ "NextWarmE2E". Chạy bằng
 * `am instrument -e class vn.abook.player.NextChapterWarmEndToEndTest`.
 */
@RunWith(AndroidJUnit4::class)
class NextChapterWarmEndToEndTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val args = InstrumentationRegistry.getArguments()
    private val id = "nextwarm-e2e"
    private lateinit var browser: MediaBrowser

    // Chữ tự viết, mỗi chương một không khí khác hẳn để bài đầu chương 2 khác bài của chương 1.
    private val moods = listOf(
        listOf("Buổi sáng ở làng ven sông yên ả, khói bếp bay lên chậm rãi.", "Bà cụ ngồi vá lưới, thỉnh thoảng ngẩng lên nhìn đàn cò trắng.", "Tiếng trẻ con cười vọng lại từ bến nước."),
        listOf("Tiếng còi báo động xé toang màn đêm.", "Họ chạy thục mạng qua con hẻm tối, tim đập dồn dập.", "Phía sau, ánh đèn pin quét loang loáng trên tường ẩm."),
        listOf("Lễ hội mùa xuân rộn ràng khắp phố.", "Người ta nhảy múa, ca hát, tiếng trống vang lên không ngớt.", "Cậu bé cầm chiếc đèn lồng đỏ, cười rạng rỡ."),
    )

    private fun <T> onMain(block: () -> T): T {
        var result: Result<T>? = null
        instrumentation.runOnMainSync { result = runCatching(block) }
        return result!!.getOrThrow()
    }

    private fun log(line: String) = Log.i("NextWarmE2E", line)

    @Before
    fun setUp() {
        Store.init(context)
        Store.deleteBook(id)
        val dir = Store.bookDir(id)
        File(dir, "texts").mkdirs()
        val chapters = JSONArray()
        for ((index, lines) in moods.withIndex()) {
            val chapter = index + 1
            val text = (0 until 40).joinToString("\n\n") { p -> (0 until 3).joinToString(" ") { s -> lines[(p + s) % lines.size] } }
            File(dir, "texts/$chapter.txt").writeText(text)
            chapters.put(JSONObject().put("id", chapter).put("fullTitle", "Chương $chapter").put("state", "text").put("text", "texts/$chapter.txt"))
        }
        Store.writeAtomic(File(dir, "book.json"), JSONObject().put("id", id).put("title", "Sách thử tải sẵn nhạc").put("version", "1")
            .put("stage", "text").put("chapters", chapters).toString())
        val choice = args.getString("choice").orEmpty()
        if (choice.isNotEmpty()) BookEdits.save(dir, JSONObject().put("music", JSONObject().put("playlist", choice)))
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        browser = MediaBrowser.Builder(context, token).setApplicationLooper(Looper.getMainLooper()).buildAsync().get(30, TimeUnit.SECONDS)
    }

    @After
    fun tearDown() {
        onMain {
            Playback.closeBook()
            browser.stop()
            browser.release()
        }
        Store.deleteBook(id)
    }

    /** Bài đang là "bài hiện tại" của MusicBed và trình phát của nó có đang chạy không (null khi im lặng). */
    private fun musicNow(): Pair<String, Boolean>? {
        val bed = MusicBed::class.java.getDeclaredField("current").apply { isAccessible = true }.get(MusicBed) ?: return null
        val track = bed.javaClass.getDeclaredField("track").apply { isAccessible = true }.get(bed) as String
        val player = bed.javaClass.getDeclaredField("player").apply { isAccessible = true }.get(bed) as ExoPlayer
        return track to player.isPlaying
    }

    /** Trạng thái riêng của ReadAloud cho dòng chẩn đoán (đang chờ đoạn nào, lỗi, bị giữ, đang đọc). */
    private fun readAloudState(): String {
        val target = vn.abook.player.readaloud.ReadAloud
        fun field(name: String) = runCatching { target.javaClass.getDeclaredField(name).apply { isAccessible = true }.get(target) }.getOrNull()
        return "active=${target.active} inFlight=${field("inFlight")} waiting=${field("waiting") != null} failure=${field("failure")} held=${field("held")}"
    }

    /** Mốc của chương đã dựng (không xếp việc dựng), link bài mốc đầu; null khi chưa dựng xong / không nhạc. */
    private fun firstLink(chapterId: Int): String? {
        val done = CountDownLatch(1)
        var link: String? = null
        DeviceScenes.peek(context, id, chapterId) { result, _ ->
            link = result?.takeIf { !it.optBoolean("pending") }?.let { SceneAnchor.cuesOf(it).firstOrNull()?.link }
            done.countDown()
        }
        done.await(30, TimeUnit.SECONDS)
        return link
    }

    // `item` / `playerMs`: mục đang phát của ExoPlayer và vị trí trong mục, đọc thẳng (Playback.positionMs chỉ đổi theo nhịp 500 ms). `voiceMs`: giọng đã sẵn phía trước
    // (ReadAloud.voiceAheadMs); `yields`: lượt tải sẵn đang đứng nhường giọng (MusicBed.warmYields).
    private class Sample(val t: Long, val chapter: Int?, val positionMs: Long, val item: Int, val playerMs: Long, val wants: Boolean, val waiting: Boolean, val left: Double?, val starved: Boolean,
                         val voiceMs: Long, val yields: Boolean)

    /** Nguồn bài chậm giả: đọc tối đa `bytesPerSecond` mỗi giây (tính từ lần đọc đầu). */
    private class Throttled(input: InputStream, private val bytesPerSecond: Int) : FilterInputStream(input) {
        private var startedAt = 0L
        private var served = 0L
        override fun read(): Int = throw UnsupportedOperationException()
        override fun read(b: ByteArray, off: Int, len: Int): Int {
            if (startedAt == 0L) startedAt = SystemClock.elapsedRealtime()
            val read = super.read(b, off, minOf(len, 4096))
            if (read > 0) {
                served += read
                val wait = startedAt + served * 1000 / bytesPerSecond - SystemClock.elapsedRealtime()
                if (wait > 0) SystemClock.sleep(wait)
            }
            return read
        }
    }

    /** Trạng thái NextChapterWarm của MusicBed (đọc bằng phản chiếu, gọi trên luồng chính): vé đang hỏi, vé đã có lời đáp, hẹn hỏi lại, bài đang tải sẵn. */
    private fun warmState(): String {
        fun field(owner: Any, name: String): Any? = owner.javaClass.getDeclaredField(name).apply { isAccessible = true }.get(owner)
        val warm = field(MusicBed, "nextWarm") ?: return "-"
        return "asking=${field(warm, "asking")} done=${field(warm, "done")} retryAt=${field(warm, "retryAt")} warming=${field(MusicBed, "warming")} now=${SystemClock.elapsedRealtime()}"
    }

    private fun warmYields(): Boolean = MusicBed::class.java.getDeclaredField("warmYields").apply { isAccessible = true }.getBoolean(MusicBed)

    @Test
    fun theNextChapterOpensWithItsTrackAlreadyOnTheDevice() {
        val expectWarm = args.getString("expectWarm", "true") != "false"
        val leftSeconds = args.getString("left")?.toIntOrNull() ?: LEFT_SECONDS
        val kbps = args.getString("kbps")?.toIntOrNull()
        val metered = AndroidMusicStudent.metered(context)
        log("bắt đầu: choice='${args.getString("choice").orEmpty()}', mạng tính phí=$metered, expectWarm=$expectWarm, còn $leftSeconds s, nguồn giả ${kbps ?: "-"} KB/s")
        assertTrue(if (expectWarm) "ca tải sẵn phải chạy trên Wi-Fi không tính phí" else "ca không tải sẵn phải chạy trên mạng tính phí", metered != expectWarm)

        val manifest = assertNotNullAnd(Store.manifest(id))
        // Giao diện hỏi đồng ý gửi chữ cho giọng trực tuyến trước khi phát (player.tsx withConsent); thiếu thì ReadAloud đứng giữ ở đầu đoạn.
        onMain { ReadAloud.grantOnline(ClipCache.split(ReadAloud.DEFAULT_VOICE).first) }
        onMain { Playback.load(id, "Sách thử tải sẵn nhạc", "", Playback.chaptersOf(manifest), 1, 0.0, 1.0, autoplay = false) }
        var total: Double? = null
        val loadDeadline = SystemClock.elapsedRealtime() + 60_000
        while (total == null && SystemClock.elapsedRealtime() < loadDeadline) {
            total = onMain { ReadAloud.segmentTiming(id, 1)?.second }
            if (total == null) SystemClock.sleep(200)
        }
        assertNotNull("chương 1 nạp được", total)
        val start = total!! - leftSeconds
        log("chương 1 dài (ước) ${"%.1f".format(total)} s, tua tới $start s")
        // Nghe thật thì người nghe đã ở chương 1 nhiều phút: bài của các mốc còn lại đã tải xong từ lâu. Tải chúng trước khi tua, để phần còn lại
        // chỉ còn việc tải sẵn chương 2 (không thì bài chương 1 chiếm làn tải duy nhất của MusicBed và đo nhầm tốc độ nguồn).
        val catalog = DeviceMusic.catalog(context)
        var scene1 = DeviceScenes.cues(context, id, 1)
        val sceneDeadline = SystemClock.elapsedRealtime() + 120_000
        while (scene1.optBoolean("pending") && SystemClock.elapsedRealtime() < sceneDeadline) {
            SystemClock.sleep(500)
            scene1 = DeviceScenes.cues(context, id, 1)
        }
        val tail = SceneAnchor.cuesOf(scene1).filter { it.end > start }.map { it.link }.distinct()
        assertTrue("chương 1 có nhạc ở đoạn cuối: $scene1", tail.isNotEmpty())
        for (link in tail) {
            val t = SystemClock.elapsedRealtime()
            val had = catalog.use(link) != null
            val file = catalog.use(link) ?: catalog.download(link, null)
            log("bài chương 1 (đoạn cuối): ${if (had) "đã có" else "tải ${(file?.length() ?: 0) / 1024} KB mất ${SystemClock.elapsedRealtime() - t} ms"} ($link)")
            assertNotNull("tải được bài chương 1", file)
        }
        // Nguồn chậm giả: từ đây (bài chương 1 đã tải ở tốc độ thật), TRƯỚC khi MusicBed có thể xin bài chương 2 - lắp sau thì lượt tải sẵn đã mở bằng nguồn thật (đo 01-11:
        // 162 KB/s thay vì 29). Trả lại nguồn thật khi xong.
        val openField = MusicCatalog::class.java.getDeclaredField("open").apply { isAccessible = true }
        val realOpen = openField.get(catalog)
        if (kbps != null) {
            @Suppress("UNCHECKED_CAST") val real = realOpen as (String) -> InputStream
            // Chỉ bài (.mp3): danh mục ở nguồn khác (workers.dev) vẫn nhanh - bóp cả nó thì mốc chương 2 về trễ (đo 01-11: nhạc chương 2 vào sau 11 s dù bài đã có).
            openField.set(catalog, { url: String ->
                real(url).let { input -> if (!url.substringBefore('?').endsWith(".mp3")) input else MusicCatalog.Sized(Throttled(input, kbps * 1024), (input as? MusicCatalog.Sized)?.length) }
            })
        }
        try {
            prepareAndListen(catalog, tail, start, leftSeconds, kbps, expectWarm)
        } finally {
            openField.set(catalog, realOpen)
        }
    }

    private fun prepareAndListen(catalog: MusicCatalog, tail: Collection<String>, start: Double, leftSeconds: Int, kbps: Int?, expectWarm: Boolean) {
        // Bài đầu chương 2 chưa có trên máy lúc bắt đầu (lượt trước có thể đã tải): bỏ bản đã tải, trừ khi chương 1 cũng dùng nó.
        var ahead: String? = null
        val aheadDeadline = SystemClock.elapsedRealtime() + 60_000
        while (ahead == null && SystemClock.elapsedRealtime() < aheadDeadline) {
            ahead = firstLink(2)
            if (ahead == null) SystemClock.sleep(500)
        }
        val fileOf = MusicCatalog::class.java.getDeclaredMethod("fileOf", String::class.java).apply { isAccessible = true }
        ahead?.takeIf { it !in tail }?.let { link ->
            catalog.cached(link)?.let { file -> log("bỏ bản đã tải của bài đầu chương 2 (lượt trước): ${file.delete()}") }
            // `.part` của lượt trước bị giết giữa chừng (app tự dọn sau MusicCatalog.PART_STALE_MS): bỏ để mốc "bắt đầu tải" là của lượt này.
            val target = fileOf.invoke(catalog, link) as File
            target.parentFile?.listFiles()?.filter { it.name.startsWith(target.name + ".") && it.name.endsWith(".part") }?.forEach { log("bỏ .part cũ: ${it.delete()}") }
            // MusicBed chạy từ lúc dựng chương 1 ở trên: có thể đã hỏi chương 2 và thấy bài "đã có" ngay trước khi bị xoá (đo 01-11: sớm 3 ms) - vé ấy coi như xong, chỉ lưới
            // cuối còn xin lại. Quên lời đáp để lượt nghe bắt đầu như người nghe mở chương 1 khi bài chương 2 chưa có.
            onMain {
                val warm = MusicBed::class.java.getDeclaredField("nextWarm").apply { isAccessible = true }.get(MusicBed)!!
                for (name in listOf("done", "retryAt")) (warm.javaClass.getDeclaredField(name).apply { isAccessible = true }.get(warm) as HashMap<*, *>).clear()
            }
        }
        listen(catalog, fileOf, start, leftSeconds, kbps, expectWarm)
    }

    private fun listen(catalog: MusicCatalog, fileOf: java.lang.reflect.Method, start: Double, leftSeconds: Int, kbps: Int?, expectWarm: Boolean) {
        onMain {
            Playback.jumpTo(1, start)
            Playback.play()
        }

        var link1: String? = null
        var link2: String? = null
        var lastPeek = 0L
        var partAt: Long? = null
        var partLeft: Double? = null
        var cachedAt: Long? = null
        var cachedLeft: Double? = null
        var boundaryAt: Long? = null
        var mixAt: Long? = null
        val samples = ArrayList<Sample>()
        val t0 = SystemClock.elapsedRealtime()
        val deadline = t0 + (leftSeconds + 60) * 1000L + AFTER_BOUNDARY_MS
        while (SystemClock.elapsedRealtime() < deadline) {
            val now = SystemClock.elapsedRealtime()
            val sample = onMain {
                val chapter = Playback.currentChapter?.id
                val left = if (chapter == 1) ReadAloud.segmentTiming(id, 1)?.second?.minus(Playback.positionSeconds) else null
                // Hàng đợi giọng cạn (đọc chưa kịp - Edge qua mạng): ExoPlayer hết mục / đang đệm, hay ReadAloud đang chờ đoạn.
                val state = Playback.player?.playbackState
                Sample(now, chapter, Playback.positionMs, Playback.player?.currentMediaItemIndex ?: -1, Playback.player?.currentPosition ?: -1, ReadAloud.wantsPlay(), ReadAloud.isWaiting, left,
                    ReadAloud.isWaiting || state == Player.STATE_ENDED || state == Player.STATE_BUFFERING, ReadAloud.voiceAheadMs(), warmYields())
            }
            samples += sample
            if (samples.size % 100 == 1) {
                val state = onMain { "exo=${Playback.player?.isPlaying} pwr=${Playback.player?.playWhenReady} st=${Playback.player?.playbackState} music=${musicNow()} ${readAloudState()} warm=${warmState()}" }
                log("t=${(now - t0) / 1000} s chương ${sample.chapter} vị trí ${sample.positionMs / 1000} s còn ${sample.left?.toInt()} muốn phát ${sample.wants} chờ đoạn ${sample.waiting} giọng sẵn ${sample.voiceMs / 1000} s nhường ${sample.yields} $state")
            }
            if (link2 == null && now - lastPeek > 2_000) {
                lastPeek = now
                if (link1 == null) link1 = firstLink(1)
                link2 = firstLink(2)
                if (link2 != null) log("bài mốc đầu chương 2: $link2 (cùng bài chương 1: ${link2 == link1}; đã có sẵn: ${catalog.cached(link2!!) != null})")
            }
            link2?.let { link ->
                if (partAt == null && cachedAt == null) {
                    val target = fileOf.invoke(catalog, link) as File
                    if (target.parentFile?.listFiles()?.any { it.name.startsWith(target.name + ".") && it.name.endsWith(".part") } == true) {
                        partAt = now
                        partLeft = sample.left
                    }
                }
                if (cachedAt == null && catalog.cached(link) != null) {
                    cachedAt = now
                    cachedLeft = sample.left
                }
            }
            if (boundaryAt == null && sample.chapter == 2) boundaryAt = now
            if (boundaryAt != null && mixAt == null) {
                val music = onMain { musicNow() }
                if (music != null && music.first == link2 && music.second) mixAt = now
            }
            if (mixAt != null && now - mixAt!! > 5_000) break
            if (boundaryAt != null && now - boundaryAt!! > AFTER_BOUNDARY_MS) break
            SystemClock.sleep(SAMPLE_MS)
        }

        fun sec(ms: Long?) = ms?.let { "%.2f".format(it / 1000.0) } ?: "-"
        fun left(value: Double?) = value?.let { "%.1f".format(it) } ?: "-"
        log("bắt đầu tải sẵn: còn ${left(partLeft)} s của chương 1 (t=${sec(partAt?.minus(t0))})")
        log("bài chương 2 có trên máy: còn ${left(cachedLeft)} s của chương 1 (t=${sec(cachedAt?.minus(t0))}); ranh chương t=${sec(boundaryAt?.minus(t0))}")
        val before = cachedAt != null && boundaryAt != null && cachedAt!! <= boundaryAt!!
        val warmSize = link2?.let { catalog.cached(it)?.length() }
        if (partAt != null && cachedAt != null && warmSize != null) log("tải sẵn: ${warmSize / 1024} KB trong ${sec(cachedAt!! - partAt!!)} s (${"%.0f".format(warmSize / 1024.0 / ((cachedAt!! - partAt!!).coerceAtLeast(1) / 1000.0))} KB/s)")
        log("(a) có trước ranh chương: $before")
        val warmSamples = samples.filter { s -> partAt != null && s.t >= partAt!! && s.t <= (cachedAt ?: boundaryAt ?: s.t) }
        log("giọng sẵn phía trước lúc bắt đầu tải sẵn: ${samples.firstOrNull { it.t >= (partAt ?: Long.MAX_VALUE) }?.voiceMs?.div(1000.0) ?: "-"} s; thấp nhất trong lúc tải sẵn " +
            "${warmSamples.minOfOrNull { it.voiceMs }?.div(1000.0) ?: "-"} s; đứng nhường ${warmSamples.count { it.yields } * SAMPLE_MS / 1000.0} s")
        log("(b) đầu chương 2 -> nhạc chương 2 chạy: ${sec(if (mixAt != null && boundaryAt != null) mixAt!! - boundaryAt!! else null)} s")

        // (c) giọng khựng: vị trí đứng yên >= STALL_MS khi đang muốn phát, bỏ ±1,5 s quanh ranh chương (đổi chương đặt lại vị trí).
        val stalls = ArrayList<Triple<Long, Long, Boolean>>() // (từ, tới, hàng đợi giọng cạn lúc ấy)
        var still: Long? = null
        var starved = false
        for (i in 1 until samples.size) {
            val a = samples[i - 1]
            val b = samples[i]
            val nearBoundary = boundaryAt != null && kotlin.math.abs(b.t - boundaryAt!!) < 1_500
            val stuck = b.wants && b.chapter == a.chapter && b.item == a.item && b.playerMs == a.playerMs && !nearBoundary
            if (stuck) {
                if (still == null) starved = false
                still = still ?: a.t
                starved = starved || b.starved
            } else {
                still?.let { if (b.t - it >= STALL_MS) stalls += Triple(it, b.t, starved) }
                still = null
            }
        }
        still?.let { from -> samples.last().t.takeIf { it - from >= STALL_MS }?.let { stalls += Triple(from, it, starved) } } // khựng còn dở lúc thôi lấy mẫu
        val warmFrom = partAt ?: cachedAt
        val warmTo = cachedAt
        fun inWarm(from: Long, to: Long) = warmFrom != null && warmTo != null && to >= warmFrom && from <= warmTo + 2_000
        // Khựng khi hàng đợi giọng còn mục mà vị trí vẫn đứng = giật thật của trình phát (CPU / đĩa); khựng khi hàng đợi cạn = đọc chưa kịp (mạng của giọng).
        val jerks = stalls.filter { !it.third }
        val starvedStalls = stalls.filter { it.third }
        val warmMs = if (warmFrom != null && warmTo != null) warmTo - warmFrom + 2_000 else 0L
        val playedMs = samples.last().t - samples.first().t
        fun share(list: List<Triple<Long, Long, Boolean>>, inside: Boolean): String {
            val span = if (inside) warmMs else playedMs - warmMs
            val ms = list.filter { inWarm(it.first, it.second) == inside }.sumOf { it.second - it.first }
            return if (span > 0) "%.1f %%".format(100.0 * ms / span) else "-"
        }
        log("(c) khựng >= $STALL_MS ms: ${stalls.size} lần cả lượt [${stalls.joinToString { "${sec(it.first - t0)}-${sec(it.second - t0)}${if (it.third) " cạn" else ""}" }}]")
        log("(c) giật khi hàng đợi còn mục: ${jerks.size} lần, trong lúc tải sẵn ${jerks.count { inWarm(it.first, it.second) }}; thời gian đứng trong cửa sổ tải sẵn ${share(jerks, true)}, ngoài ${share(jerks, false)}")
        log("(c) đứng vì đọc chưa kịp: ${starvedStalls.size} lần; thời gian đứng trong cửa sổ tải sẵn (${sec(warmMs)} s) ${share(starvedStalls, true)}, ngoài ${share(starvedStalls, false)}")
        val during = jerks.count { inWarm(it.first, it.second) }

        assertNotNull("chương 2 có nhạc", link2)
        assertNotNull("giọng sang được chương 2", boundaryAt)
        if (link2 != link1) {
            if (expectWarm) {
                // Bắt đầu tải sẵn là việc của app: ngay khi chương có đồng hồ đọc và mốc chương kế đã dựng (nhịp sync 0,5 s, hỏi lại 15 s); tải xong kịp ranh chương còn
                // tuỳ tốc độ nguồn - (a) chỉ bắt buộc khi nguồn đủ nhanh cho quãng còn lại lúc bắt đầu tải.
                assertTrue("tải sẵn phải bắt đầu ngay đầu lượt nghe: còn $partLeft s", partLeft != null && partLeft!! > leftSeconds - WARM_START_SECONDS)
                val fastEnough = warmSize != null && partAt != null && cachedAt != null && warmSize * 1000.0 / (cachedAt!! - partAt!!) * (partLeft!! - 5) >= warmSize
                if (fastEnough || kbps != null) assertTrue("(a) bài chương 2 không có trên máy trước ranh chương (nguồn ${kbps ?: "đủ nhanh"} KB/s)", before)
                assertTrue("(c) trình phát không giật trong lúc tải sẵn", during == 0)
            } else {
                assertFalse("mạng tính phí: không được tải sẵn trước ranh chương", before)
                assertTrue("mạng tính phí: không được bắt đầu tải trước ranh chương", partAt == null || partAt!! >= boundaryAt!!)
            }
        }
    }

    private fun <T> assertNotNullAnd(value: T?): T {
        assertNotNull(value)
        return value!!
    }

    companion object {
        const val LEFT_SECONDS = 150
        const val SAMPLE_MS = 100L
        // Emulator chạy -no-audio: vị trí của ExoPlayer nhảy theo bước ~0,5 s dù tiếng đều, nên khựng thật = đứng >= 1 s.
        const val STALL_MS = 1_000L
        const val AFTER_BOUNDARY_MS = 120_000L
        /** Tải sẵn phải bắt đầu trong chừng này giây kể từ lúc phát (mốc chương kế đã dựng sẵn trước khi tua; một lần hỏi lại 15 s là cùng). */
        const val WARM_START_SECONDS = 20
    }
}
