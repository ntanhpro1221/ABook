package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/*
 * "Làm trước" trên điện thoại (docs/LISTEN_ANYTHING.md mục 3; máy tính: abook/readaloud/prepare.py): đọc sẵn các chương sắp nghe vào bộ đệm đoạn
 * ([ClipCache]) bằng giọng đã chọn của cuốn, để nghe được khi không có mạng (tàu điện, máy bay) và giọng chậm hơn tốc độ nghe (VieNeu trên máy tầm trung,
 * RTF ~1,8) vẫn nghe liền mạch. Phần thuần ở file này (thử được trên JVM); việc nền của WorkManager ở PrepareAhead.kt.
 *
 * Đoạn làm trước dùng ĐÚNG giọng đã chọn, không bao giờ rơi sang giọng khác ([ClipReader.readExactly]): âm thanh làm sẵn phải cùng một giọng từ đầu tới cuối.
 * Giọng trực tuyến hỏng giữa chừng (mất mạng, khoá bị từ chối) thì DỪNG và nói rõ - phần đã xong vẫn giữ, bấm làm trước lại là làm tiếp (đoạn đã có thì bỏ qua).
 */

/** Một chương trong việc làm trước: `done` đoạn đã có trong bộ đệm, `failed` đoạn giọng không đọc được gì (chỉ có dấu câu...) - bỏ qua, không chặn. */
class PrepareChapter(val id: Int, val title: String, val paragraphs: Int, val chars: Int, var done: Int = 0, var failed: Int = 0) {
    val ready: Boolean get() = paragraphs > 0 && done + failed >= paragraphs

    fun toJson(): JSONObject = JSONObject().put("id", id).put("title", title).put("paragraphs", paragraphs).put("chars", chars).put("done", done).put("failed", failed)

    companion object {
        fun fromJson(json: JSONObject) =
            PrepareChapter(json.getInt("id"), json.optString("title"), json.getInt("paragraphs"), json.getInt("chars"), json.optInt("done"), json.optInt("failed"))
    }
}

/** Việc làm trước đang có (một việc một lúc; việc mới thay việc cũ). Lưu xuống file sau mỗi đoạn nên app bị đóng / máy khởi động lại vẫn làm tiếp đúng chỗ. */
class PrepareJob(
    val id: String,
    val bookId: String,
    val voice: String,
    val label: String,
    val online: Boolean,
    val chapters: List<PrepareChapter>,
    /** Số chương / đoạn giao diện đưa (máy chỉ nhận chừng vừa phần bộ đệm dành cho làm trước). */
    val offeredChapters: Int,
    val offeredParagraphs: Int,
    var chargingOnly: Boolean,
    val started: Long,
    /** "running" (đang làm hay chờ điều kiện), "done", "cancelled", "error". */
    var state: String = "running",
    var error: String = "",
    /** Phần bộ đệm dành cho làm trước đã đầy: dừng sớm, phần còn lại đọc khi nghe tới. */
    var full: Boolean = false,
    var seconds: Double = 0.0,
    var charsTimed: Long = 0,
    var charsDone: Long = 0,
) {
    val total: Int get() = chapters.sumOf { it.paragraphs }
    val done: Int get() = chapters.sumOf { it.done + it.failed }
    val chars: Long get() = chapters.sumOf { it.chars.toLong() }

    fun toJson(): JSONObject = JSONObject()
        .put("id", id).put("bookId", bookId).put("voice", voice).put("label", label).put("online", online)
        .put("chapters", JSONArray().apply { chapters.forEach { put(it.toJson()) } })
        .put("offeredChapters", offeredChapters).put("offeredParagraphs", offeredParagraphs).put("chargingOnly", chargingOnly).put("started", started)
        .put("state", state).put("error", error).put("full", full).put("seconds", seconds).put("charsTimed", charsTimed).put("charsDone", charsDone)

    /**
     * Trạng thái cho giao diện (cùng hình dạng `PrepareStatus` của ui/src/listen/prepareAhead.ts). `perChar`: giây máy cần cho mỗi ký tự đo từ trước
     * ([VoiceSpeeds]) - dùng khi việc này chưa tự đo được; `waitingFor`: vì sao chưa làm lúc này ([PreparePlan.waitingFor]).
     */
    fun status(perChar: Double?, waitingFor: String?): JSONObject {
        val left = (chars - charsDone).coerceAtLeast(0)
        val speed = if (charsTimed > 0 && seconds > 0) seconds / charsTimed else perChar
        val array = JSONArray()
        chapters.forEach {
            array.put(JSONObject().put("id", it.id).put("title", it.title).put("total", it.paragraphs).put("done", it.done + it.failed).put("ready", it.ready))
        }
        return JSONObject()
            .put("state", state).put("bookId", bookId).put("voice", voice).put("label", label).put("online", online)
            .put("total", total).put("offered", offeredParagraphs).put("done", done)
            .put("audioSeconds", Math.round(chars / PreparePlan.CHARS_PER_SECOND))
            .put("secondsLeft", if (speed != null && state == "running") Math.round(left * speed) else JSONObject.NULL)
            .put("error", error).put("chargingOnly", chargingOnly).put("waitingFor", waitingFor ?: JSONObject.NULL)
            .put("chapters", array).put("chaptersOffered", offeredChapters).put("full", full)
    }

    companion object {
        fun fromJson(json: JSONObject): PrepareJob {
            val array = json.getJSONArray("chapters")
            return PrepareJob(
                json.getString("id"), json.getString("bookId"), json.getString("voice"), json.optString("label"), json.optBoolean("online"),
                (0 until array.length()).map { PrepareChapter.fromJson(array.getJSONObject(it)) },
                json.optInt("offeredChapters"), json.optInt("offeredParagraphs"), json.optBoolean("chargingOnly", true), json.optLong("started"),
                json.optString("state", "running"), json.optString("error"), json.optBoolean("full"),
                json.optDouble("seconds", 0.0), json.optLong("charsTimed"), json.optLong("charsDone"),
            )
        }
    }
}

/** Phần thuần của việc chọn và ước lượng. */
object PreparePlan {
    /** Phần bộ đệm đoạn dành cho đoạn làm trước (như máy tính, prepare.py SHARE). */
    const val SHARE = 0.6
    /** Như trình phát ước đoạn chưa đọc (readAloud.ts, prepare.py). */
    const val CHARS_PER_SECOND = 14.0
    /** Giọng chạy trên máy (không cần mạng): không đòi Wi-Fi. */
    private val LOCAL = setOf("device", "vieneu", "supertonic")

    fun online(voice: String): Boolean = voice.substringBefore(':') !in LOCAL

    /**
     * Byte bộ đệm cho mỗi giây nghe. Giọng chạy trên máy ghi WAV 16-bit đơn kênh: VieNeu Turbo 48 kHz, Nano 24 kHz, Supertonic 44,1 kHz, giọng của máy ~24 kHz
     * (VieNeu chưa rõ loại thì tính như Turbo cho chắc). Giọng trực tuyến ghi MP3 48 kbit/s.
     */
    fun bytesPerSecond(voice: String): Int = when {
        voice.startsWith("vieneu:nano") -> 48_000
        voice.startsWith("vieneu:") -> 96_000
        voice.startsWith("supertonic:") -> 88_200
        voice.startsWith("device:") -> 48_000
        else -> 6_000
    }

    /** Ước byte bộ đệm của một chương. */
    fun bytesOf(chars: Int, rate: Int): Long = Math.round(chars / CHARS_PER_SECOND * rate)

    /** Các chương đầu (theo thứ tự) vừa `budget` byte; luôn nhận ít nhất một chương. Chương không có đoạn nào thì bỏ. Cả chương hay không gì: sẵn sàng tính theo chương. */
    fun accept(chapters: List<PrepareChapter>, rate: Int, budget: Long): List<PrepareChapter> {
        val out = ArrayList<PrepareChapter>()
        var used = 0L
        for (chapter in chapters.filter { it.paragraphs > 0 }) {
            val size = bytesOf(chapter.chars, rate)
            if (out.isNotEmpty() && used + size > budget) break
            out.add(chapter)
            used += size
        }
        return out
    }

    /** Điều kiện của WorkManager: chỉ khi đang sạc (người nghe chọn, mặc định bật), Wi-Fi không tính tiền cho giọng trực tuyến, pin không yếu; không đòi máy rảnh. */
    data class Needs(val charging: Boolean, val unmetered: Boolean, val batteryNotLow: Boolean = true)

    fun needs(online: Boolean, chargingOnly: Boolean) = Needs(charging = chargingOnly, unmetered = online)

    /**
     * Vì sao việc đang có chưa chạy lúc này - câu cho người nghe ở giao diện: "listening" (nhường cho chương đang nghe), "charging", "wifi", "battery"; null = đang
     * làm hay sắp làm.
     */
    fun waitingFor(job: PrepareJob, working: Boolean, live: Boolean, charging: Boolean, unmetered: Boolean, batteryLow: Boolean): String? {
        if (job.state != "running") return null
        if (working) return if (live) "listening" else null
        val needs = needs(job.online, job.chargingOnly)
        return when {
            needs.charging && !charging -> "charging"
            needs.unmetered && !unmetered -> "wifi"
            batteryLow -> "battery"
            else -> null
        }
    }
}

/**
 * Tốc độ đo được của từng giọng (giây máy cần cho mỗi ký tự), từ cả lúc nghe trực tiếp lẫn lúc làm trước: ước "còn khoảng N phút" trước khi việc mới tự đo được.
 * Giữ tổng có trọng số: quá [WINDOW] ký tự thì chia đôi, số đo mới dần thắng.
 */
class VoiceSpeeds(private val file: File) {
    companion object {
        const val WINDOW = 20_000.0
    }

    private val data: JSONObject = runCatching { JSONObject(file.readText()) }.getOrElse { JSONObject() }

    @Synchronized
    fun record(voice: String, chars: Int, seconds: Double) {
        if (chars <= 0 || seconds <= 0) return
        val entry = data.optJSONObject(voice) ?: JSONObject()
        var c = entry.optDouble("chars", 0.0) + chars
        var s = entry.optDouble("seconds", 0.0) + seconds
        if (c > WINDOW) {
            c /= 2
            s /= 2
        }
        data.put(voice, JSONObject().put("chars", c).put("seconds", s))
        runCatching {
            val part = File(file.path + ".part")
            part.writeBytes(data.toString().toByteArray(Charsets.UTF_8))
            file.delete()
            part.renameTo(file)
        }
    }

    @Synchronized
    fun secondsPerChar(voice: String): Double? {
        val entry = data.optJSONObject(voice) ?: return null
        val chars = entry.optDouble("chars", 0.0)
        return if (chars > 0) entry.optDouble("seconds", 0.0) / chars else null
    }
}

/**
 * Vòng làm trước (không phụ thuộc Android): làm lần lượt các đoạn chưa có của từng chương, lưu tiến độ sau mỗi đoạn. Đoạn đã có thì bỏ qua (làm lại từ đầu là
 * an toàn - idempotent); có người đang nghe mà đoạn của họ đang được đọc ([live]) thì đứng chờ - nghe trực tiếp luôn đi trước.
 */
class PrepareRunner(
    /** Các đoạn của chương (đúng [Paragraphs.of], cùng khoá bộ đệm với lúc nghe); null = không đọc được chữ của chương. */
    private val texts: (PrepareChapter) -> List<String>?,
    private val cached: (String) -> Boolean,
    /** Đọc một đoạn vào bộ đệm bằng đúng giọng của việc; hỏng thì ném [VoiceException]. */
    private val make: (String) -> Unit,
    private val pin: (String) -> Unit,
    private val live: () -> Boolean,
    private val stopped: () -> Boolean,
    private val save: (PrepareJob) -> Unit,
    /** Phần bộ đệm dành cho làm trước đã đầy. */
    private val full: () -> Boolean = { false },
    private val timed: (Int, Double) -> Unit = { _, _ -> },
    /** Đồng hồ đơn điệu (ms). */
    private val clock: () -> Long = System::currentTimeMillis,
    private val sleep: (Long) -> Unit = { Thread.sleep(it) },
    /** Một lượt chạy tối đa chừng này ms (WorkManager cho một lượt ~10 phút), rồi trả [Outcome.SLICE] để xếp lượt sau. */
    private val sliceMs: Long = Long.MAX_VALUE,
) {
    enum class Outcome { DONE, STOPPED, SLICE, ERROR }

    companion object {
        /** Đoạn xong nhanh hơn thế là đã có sẵn - không nói gì về tốc độ (như prepare.py CACHED_SECONDS). */
        const val CACHED_MS = 50L
        const val LIVE_POLL_MS = 200L
    }

    fun run(job: PrepareJob): Outcome {
        val began = clock()
        val all = LinkedHashMap<PrepareChapter, List<String>>()
        // Đếm lại từ bộ đệm: tiến độ đã lưu có thể cũ (app chết giữa đoạn, Android dọn thư mục cache).
        job.charsDone = 0
        for (chapter in job.chapters) {
            val paragraphs = texts(chapter)
            if (paragraphs == null) {
                job.state = "error"
                job.error = "Không đọc được chữ của chương “${chapter.title}” - đã dừng làm trước."
                save(job)
                return Outcome.ERROR
            }
            all[chapter] = paragraphs
            chapter.failed = 0
            chapter.done = 0
            for (text in paragraphs) if (cached(text)) {
                pin(text)
                chapter.done += 1
                job.charsDone += text.length
            }
        }
        save(job)
        for ((chapter, paragraphs) in all) {
            for (text in paragraphs) {
                if (cached(text)) continue
                while (live() && !stopped()) sleep(LIVE_POLL_MS)
                if (stopped()) return Outcome.STOPPED
                if (clock() - began >= sliceMs) return Outcome.SLICE
                if (full()) {
                    job.full = true
                    job.state = "done"
                    save(job)
                    return Outcome.DONE
                }
                val start = clock()
                pin(text) // trước khi ghi: lần dọn ngay trong lúc ghi đã thấy nó là đoạn ghim
                try {
                    make(text)
                    chapter.done += 1
                } catch (error: VoiceException) {
                    if (error.reason != "empty") {
                        job.state = "error"
                        job.error = errorText(job, chapter, error)
                        save(job)
                        return Outcome.ERROR
                    }
                    chapter.failed += 1
                }
                job.charsDone += text.length
                val spent = clock() - start
                if (spent > CACHED_MS) {
                    job.charsTimed += text.length
                    job.seconds += spent / 1000.0
                    timed(text.length, spent / 1000.0)
                }
                save(job)
            }
        }
        job.state = "done"
        save(job)
        return Outcome.DONE
    }

    /** Câu cho người nghe: không rơi sang giọng khác (âm thanh làm sẵn phải cùng một giọng), nên nói rõ dừng ở đâu và làm sao làm tiếp. */
    private fun errorText(job: PrepareJob, chapter: PrepareChapter, error: VoiceException): String {
        val ready = job.chapters.count { it.ready }
        val kept = if (ready > 0) " Đã sẵn sàng $ready/${job.chapters.size} chương - phần đã xong vẫn giữ." else ""
        return if (job.online && error.offline) {
            "Mất mạng nên đã dừng làm trước ở “${chapter.title}”.$kept Có Wi-Fi thì bấm làm trước lại để làm tiếp."
        } else {
            "Không làm trước được “${chapter.title}”: ${error.message?.trimEnd('.')}.$kept"
        }
    }
}
