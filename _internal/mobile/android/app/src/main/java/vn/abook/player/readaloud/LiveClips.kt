package vn.abook.player.readaloud

import java.io.File
import java.io.IOException
import java.io.InterruptedIOException
import java.io.RandomAccessFile
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * Nghe ngay phát LUỒNG clip Edge (uxfix57; máy tính: `edge.py` `StreamSink` + MediaSource, uxfix56): đoạn người nghe đang đứng chờ (rank 0) đi vào ExoPlayer ngay khi byte tiếng đầu tiên về
 * thay vì đợi [EdgeTts.synthesize] đọc xong mọi mảnh (a57: nhảy tới câu chờ trung vị 6,6 giây, byte đầu tới sau ~2 giây). File mp3 đang được ghi lớn dần; ExoPlayer đọc nó qua
 * `abooklive://<id>` ([SCHEME], LiveClipDataSource) và chờ khi hết byte mà clip chưa xong.
 */
object LiveClips {
    const val SCHEME = "abooklive"
    /** Chờ byte mới quá chừng này (ms) mà không có gì: coi như clip hỏng (Edge tự bỏ cuộc ở 45 giây - [EdgeTts.TOTAL_MS]). */
    const val STALL_MS = 50_000L
    private const val KEEP = 16

    /** Một clip đang đọc: file đang ghi, số byte đã ghi, xong / hỏng. An toàn đa luồng (luồng đọc ghi, luồng nạp của ExoPlayer đọc). */
    class Entry(val id: String) {
        private val lock = ReentrantLock()
        private val changed = lock.newCondition()
        private var file: File? = null
        private var written = 0L
        private var finished = false
        private var error: Exception? = null

        /** File đang ghi (đổi chỗ khi clip vào bộ đệm - [relocate]); null khi chưa có byte nào. */
        fun file(): File? = lock.withLock { file }

        fun written(): Long = lock.withLock { written }

        val done: Boolean get() = lock.withLock { finished }

        val failure: Exception? get() = lock.withLock { error }

        /** `total` byte đầu của `file` đã ghi xong (không bao giờ giảm). */
        fun grew(file: File, total: Long) = lock.withLock {
            this.file = file
            if (total > written) written = total
            changed.signalAll()
        }

        /** Clip đọc xong: `total` byte là cả file. */
        fun finish(total: Long) = lock.withLock {
            if (error == null) {
                if (total > written) written = total
                finished = true
            }
            changed.signalAll()
        }

        fun fail(cause: Exception) = lock.withLock {
            if (!finished && error == null) error = cause
            changed.signalAll()
        }

        /** Số byte còn lại từ `position` khi clip đã xong (không bao giờ âm: tua quá cuối clip đã xong là hết dữ liệu); null khi clip còn đang lớn (độ dài chưa biết). */
        fun remainingFrom(position: Long): Long? = lock.withLock { if (finished) (written - position).coerceAtLeast(0) else null }

        /** Clip đã vào bộ đệm: file đổi chỗ (lần mở sau của ExoPlayer - tua - phải mở file mới). */
        fun relocate(moved: File) = lock.withLock { file = moved }

        /**
         * Chờ tới khi có byte ở `position`: trả số byte đã có từ đó (> 0), 0 khi clip xong và hết byte, ném [IOException] khi quá `stallMs` không có gì mới.
         * Clip hỏng giữa chừng (uxfix58): byte đã ghi vẫn được trao hết, rồi byte cuối cùng đã ghi là HẾT DỮ LIỆU (0) - phần đã về phát tới cùng, phần tiếp do [ReadAloud] nối sau; trước đây ném
         * lỗi ngay và mất cả phần đã về. Chưa có byte nào mà hỏng thì vẫn ném [IOException]. Luồng nạp bị ngắt (ExoPlayer huỷ lần nạp) thì thoát ngay bằng [InterruptedIOException].
         */
        fun awaitBytes(position: Long, stallMs: Long = STALL_MS): Long {
            lock.lock()
            try {
                var left = java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(stallMs)
                var seen = written
                while (true) {
                    if (position < written) return written - position
                    error?.let { if (written > 0) return 0 else throw IOException(it.message ?: "Clip đọc hỏng", it) }
                    if (finished) return 0
                    if (written != seen) {
                        seen = written
                        left = java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(stallMs)
                    }
                    if (left <= 0) throw IOException("Clip đọc dở không có thêm âm thanh")
                    try {
                        val slice = minOf(left, 200_000_000L)
                        left -= slice - changed.awaitNanos(slice)
                    } catch (interrupted: InterruptedException) {
                        Thread.currentThread().interrupt()
                        throw InterruptedIOException("Lần nạp bị huỷ")
                    }
                }
            } finally {
                lock.unlock()
            }
        }

        /** Đầu đọc từ byte `position` trở đi (mỗi lần mở của ExoPlayer một cái). */
        fun reader(position: Long, stallMs: Long = STALL_MS): Reader = Reader(this, position, stallMs)
    }

    /** Đọc tuần tự file đang lớn của một [Entry]; chỉ đọc file, không mạng. */
    class Reader(private val entry: Entry, private var position: Long, private val stallMs: Long) {
        private var raf: RandomAccessFile? = null
        private var opened: File? = null

        /** Đọc tối đa `length` byte; -1 khi clip xong và đã đọc hết. Chờ nếu chưa có byte mới. */
        fun read(buffer: ByteArray, offset: Int, length: Int): Int {
            if (length == 0) return 0
            val available = entry.awaitBytes(position, stallMs)
            if (available == 0L) return -1
            val file = open()
            val want = minOf(length.toLong(), available).toInt()
            file.seek(position)
            val got = file.read(buffer, offset, want)
            if (got < 0) throw IOException("File clip ngắn hơn số byte đã ghi")
            position += got
            return got
        }

        /** Mở file hiện tại của entry; file vừa được đổi chỗ vào bộ đệm giữa chừng thì thử lại với đường mới một lúc. */
        private fun open(): RandomAccessFile {
            raf?.let { return it }
            var lastError: IOException? = null
            repeat(25) {
                val file = entry.file() ?: throw IOException("Clip chưa có file")
                try {
                    return RandomAccessFile(file, "r").also {
                        raf = it
                        opened = file
                    }
                } catch (error: java.io.FileNotFoundException) {
                    lastError = error
                    try {
                        Thread.sleep(20)
                    } catch (interrupted: InterruptedException) {
                        Thread.currentThread().interrupt()
                        throw InterruptedIOException("Lần nạp bị huỷ")
                    }
                }
            }
            throw lastError ?: IOException("Không mở được file clip")
        }

        fun close() {
            runCatching { raf?.close() }
            raf = null
        }
    }

    private val entries = object : LinkedHashMap<String, Entry>(32, 0.75f, false) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Entry>?) = size > KEEP
    }

    /** Clip mới sắp phát luồng (`id` duy nhất). Giữ vài clip gần nhất; cũ hơn bị quên - ExoPlayer mở lại thì lỗi, người nghe được đọc lại ([ReadAloud.recoverFromPlayerError]). */
    fun create(id: String = java.util.UUID.randomUUID().toString()): Entry = Entry(id).also { synchronized(entries) { entries[id] = it } }

    fun get(id: String): Entry? = synchronized(entries) { entries[id] }

    fun uri(id: String): String = "$SCHEME://$id"

    /** Mã clip trong `abooklive://<id>`. */
    fun idOf(uri: String): String = uri.substringAfter("://").substringBefore('/').substringBefore('?')

    // ---- chỗ nhận của giọng ---------------------------------------------------------------------------------

    /** Chỗ nhận clip đang lớn của người dùng [EdgeTts] (luồng đọc gọi, phải nhanh): file vừa lớn thêm, mốc chữ tạm theo chữ ĐÃ bỏ (không phải chữ giọng nhận), xong, hỏng. */
    interface Target {
        /** Lượt này còn nhận luồng không? Đã phát luồng một lần thì lần thử lại ([ClipRetry], giọng đỡ) đi đường thường. */
        fun accepting(): Boolean

        /** `total` byte đầu của `file` đã ghi (lần đầu = byte tiếng đầu tiên về). */
        fun grew(file: File, total: Long)

        /**
         * Mốc chữ tạm, tính từ đầu clip tới giờ (`durationMs` = phần đã có), không dày hơn [LiveWords.EVERY_MS]. `heardMs` (uxfix58): hết mốc THẬT cuối cùng giọng đã báo - chữ chưa tới bị dồn vào
         * [heardMs, durationMs] nên chỉ có chỗ này nói được chữ nào đã nghe tới (clip đứt giữa chừng nối lại từ chữ đầu tiên chưa nghe - [SeekPlan.resumeWord]).
         */
        fun words(words: List<Span>, durationMs: Long, heardMs: Long)

        /** File đã ghi đủ `total` byte. */
        fun done(total: Long)

        fun failed(error: Exception)
    }

    /** Chỗ nhận + cách đổi mốc chữ giọng nhận về chữ hiện ([Voice.synthesize] đổi chữ thô thành chữ chuẩn hoá thì đặt `expand`). */
    class Here(val target: Target, var expand: (List<Span>) -> List<Span> = { it })

    private val here = ThreadLocal<Here?>()

    fun here(): Here? = here.get()

    /** Chạy `block` ở luồng này với `target` nhận clip đang lớn của giọng Edge gọi bên trong. */
    fun <T> receiving(target: Target?, block: () -> T): T {
        val before = here.get()
        here.set(target?.let { Here(it) })
        try {
            return block()
        } finally {
            here.set(before)
        }
    }

    /** Trong `block` mốc chữ tạm đi qua `expand` trước khi tới [Target] (không có chỗ nhận thì không làm gì). */
    fun <T> expanding(expand: (List<Span>) -> List<Span>, block: () -> T): T {
        val current = here.get() ?: return block()
        val before = current.expand
        current.expand = expand
        try {
            return block()
        } finally {
            current.expand = before
        }
    }
}

/** [EdgeTts.synthesize] báo clip đang lớn: file lớn thêm (đã ghi và flush), mốc chữ mới theo thứ tự đọc (đã bù chỗ nối), xong, hỏng (rồi ném lỗi như thường). */
interface LiveSink {
    fun grew(file: File, totalBytes: Long)
    fun boundaries(found: List<Boundary>)
    fun done(clip: Clip)
    fun failed(error: Exception)
}

/**
 * [LiveSink] của giọng Edge nối với [LiveClips.Target]: gom mốc, đổi thành mốc từng chữ của `text` (và `expand` về chữ hiện) không dày hơn [EVERY_MS] một lần. Mốc còn nằm chờ thì đẩy cả khi
 * tiếng về thêm (như `_Live.audio` của máy tính) và luôn đẩy nốt trước khi báo xong / hỏng (uxfix60): clip đứt thì chỗ "đã nghe tới" ([SeekPlan.resumeWord]) là mốc mới nhất, không cũ tới 0,5 giây.
 */
class LiveWords(
    private val text: String, private val expand: (List<Span>) -> List<Span>, private val target: LiveClips.Target,
    private val clock: () -> Long = System::nanoTime,
) : LiveSink {
    companion object {
        const val EVERY_MS = 500L
    }

    private val all = ArrayList<Boundary>()
    private var bytes = 0L
    private var lastPush = Long.MIN_VALUE
    private var pending = false

    override fun grew(file: File, totalBytes: Long) {
        bytes = totalBytes
        target.grew(file, totalBytes)
        if (pending) pushIfDue()
    }

    override fun boundaries(found: List<Boundary>) {
        if (found.isEmpty()) return
        all.addAll(found)
        pending = true
        pushIfDue()
    }

    private fun pushIfDue() {
        val now = clock()
        if (lastPush == Long.MIN_VALUE || (now - lastPush) / 1_000_000 >= EVERY_MS) push(now)
    }

    private fun push(now: Long) {
        lastPush = now
        pending = false
        val duration = maxOf(EdgeProtocol.durationMs(bytes), all.last().endMs)
        target.words(expand(WordTokens.map(text, all, duration)), duration, all.last().endMs)
    }

    override fun done(clip: Clip) {
        if (pending) push(clock())
        target.done(clip.file.length())
    }

    override fun failed(error: Exception) {
        if (pending) push(clock())
        target.failed(error)
    }
}

/** Quyết định phát luồng cho một lượt đọc đoạn (thuần tính toán, LiveClipsTest). */
object LivePolicy {
    /**
     * Lượt đọc này có phát luồng cho ExoPlayer không? Chỉ giọng Edge (nhà cung cấp có xếp hàng theo rank), đoạn người nghe đang đứng chờ (`rank` 0), không phải lần hỏi thăm ngầm; và không phải tua theo thanh thời gian
     * tới giữa đoạn chưa đọc (`waitingOffsetMs` > 0 mà không bấm chữ - `waitingWord` < 0): chỗ ấy ở sâu trong clip, phải đợi gần hết clip mới tới nên đọc cả đoạn như cũ. `waitingOffsetMs` null = không có chỗ chờ (hàng đợi cạn).
     */
    fun streams(voice: String, online: Boolean, rank: Int, probe: Boolean, waitingOffsetMs: Long?, waitingWord: Int): Boolean =
        online && rank == 0 && !probe && ClipCache.split(voice).first == "edge" && (waitingOffsetMs == null || waitingOffsetMs <= 0 || waitingWord >= 0)
}
