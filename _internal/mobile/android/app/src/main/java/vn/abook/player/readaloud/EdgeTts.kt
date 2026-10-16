package vn.abook.player.readaloud

import org.json.JSONObject
import vn.abook.player.Py
import java.io.File
import java.io.IOException
import java.io.OutputStream
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.SecureRandom
import java.util.Locale
import java.util.concurrent.CancellationException
import java.util.concurrent.ExecutionException
import java.util.concurrent.ExecutorCompletionService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * Phần giao thức của dịch vụ đọc to của Edge (không đụng mạng, kiểm thử được): theo dự án mã mở edge-tts (rany2/edge-tts, `constants.py`, `drm.py`,
 * `communicate.py`, đọc 03-10, bản Chromium 143). Dịch vụ không chính thức: hằng số dưới đây đổi khi Microsoft đổi (thường là [CHROMIUM_FULL_VERSION] và cách
 * tính Sec-MS-GEC) - hỏng thì giọng Edge báo lỗi và app tự rơi về giọng của máy. Token là v2 từ tháng 10/2026 (v1 bị từ chối 403 với mọi người): mã ở
 * [EdgeToken] (chuyển từ `drm.py` của edge-tts, LGPL-3.0); khi hỏng lần nữa đối chiếu `drm.py` / `constants.py` của edge-tts bản mới nhất.
 */
object EdgeProtocol {
    const val TRUSTED_CLIENT_TOKEN = EdgeToken.TRUSTED_CLIENT_TOKEN
    const val CHROMIUM_FULL_VERSION = "143.0.3650.75"
    val CHROMIUM_MAJOR = CHROMIUM_FULL_VERSION.substringBefore('.')
    val SEC_MS_GEC_VERSION = "2-$CHROMIUM_FULL_VERSION"
    const val WSS_BASE = "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1"
    const val OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
    /** 48 kbps không đổi = 6000 byte mỗi giây: độ dài và độ lệch giữa các lần gọi tính chính xác từ số byte. */
    const val BYTES_PER_SECOND = 6000L
    /** Một lần gọi nhận tối đa chừng này byte chữ đã escape (edge-tts cắt ở 4096). */
    const val MAX_TEXT_BYTES = 4000
    /**
     * Mốc `WordBoundary` của Edge sớm hơn âm thanh giải mã chừng 100 ms (trễ bộ mã mp3; đo 03-10, docs/LISTEN_ANYTHING.md "Word timings - measured"):
     * một hằng số cho cả giọng, cộng vào mọi mốc trước khi khớp với chữ.
     */
    const val BOUNDARY_SHIFT_MS = 100L

    fun userAgent() = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$CHROMIUM_MAJOR.0.0.0 Safari/537.36 Edg/$CHROMIUM_MAJOR.0.0.0"

    /** Sec-MS-GEC (v2): "<CS64>-<SHA-256 biến thể>" của "<giờ Windows file time làm tròn xuống 5 phút><token>" - xem [EdgeToken]. `unixSeconds` đã cộng độ lệch đồng hồ. */
    fun secMsGec(unixSeconds: Double): String = EdgeToken.secMsGecV2(unixSeconds)

    fun connectionId(random: SecureRandom = SecureRandom()): String = ByteArray(16).also(random::nextBytes).joinToString("") { "%02x".format(it) }

    fun url(connectionId: String, unixSeconds: Double): String =
        "$WSS_BASE?TrustedClientToken=$TRUSTED_CLIENT_TOKEN&ConnectionId=$connectionId&Sec-MS-GEC=${secMsGec(unixSeconds)}&Sec-MS-GEC-Version=$SEC_MS_GEC_VERSION"

    /** Giờ kiểu JavaScript mà dịch vụ đòi trong `X-Timestamp`. */
    fun dateString(epochMs: Long): String {
        val format = java.text.SimpleDateFormat("EEE MMM dd yyyy HH:mm:ss 'GMT+0000 (Coordinated Universal Time)'", Locale.US)
        format.timeZone = java.util.TimeZone.getTimeZone("UTC")
        return format.format(java.util.Date(epochMs))
    }

    /** Tin cấu hình đầu tiên: xin mốc từng chữ, mp3 24 kHz 48 kbps. */
    fun speechConfig(timestamp: String): String =
        "X-Timestamp:$timestamp\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n" +
            "{\"context\":{\"synthesis\":{\"audio\":{\"metadataoptions\":{\"sentenceBoundaryEnabled\":\"false\",\"wordBoundaryEnabled\":\"true\"}," +
            "\"outputFormat\":\"$OUTPUT_FORMAT\"}}}}\r\n"

    /** Escape XML + thay ký tự điều khiển mà dịch vụ không nhận (edge-tts `remove_incompatible_characters`). */
    fun escape(text: String): String = buildString {
        for (c in text) when {
            c == '&' -> append("&amp;")
            c == '<' -> append("&lt;")
            c == '>' -> append("&gt;")
            c.code in 0..8 || c.code in 11..12 || c.code in 14..31 -> append(' ')
            else -> append(c)
        }
    }

    /** Số byte UTF-8 của một ký tự sau khi escape (để cắt chữ dài theo [MAX_TEXT_BYTES]). */
    fun escapedBytes(c: Char): Int = when {
        c == '&' -> 5
        c == '<' || c == '>' -> 4
        c.code < 0x80 -> 1
        c.code < 0x800 -> 2
        Character.isSurrogate(c) -> 2 // hai nửa cặp thay thế = 4 byte
        else -> 3
    }

    fun ssml(voiceName: String, escapedText: String, requestId: String, timestamp: String): String =
        "X-RequestId:$requestId\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:${timestamp}Z\r\nPath:ssml\r\n\r\n" +
            "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='$voiceName'>" +
            "<prosody pitch='+0Hz' rate='+0%' volume='+0%'>$escapedText</prosody></voice></speak>"

    /** Header "Khoá:giá trị" của một tin (chữ hay nhị phân) thành bảng; tên khoá giữ nguyên hoa/thường như dịch vụ gửi. */
    fun headers(block: String): Map<String, String> =
        block.split("\r\n").filter { it.contains(':') }.associate { it.substringBefore(':') to it.substringAfter(':') }

    /** Tin nhị phân: 2 byte (big-endian) độ dài header, header, rồi âm thanh. Trả (header, âm thanh); null nếu hỏng. */
    fun parseBinary(data: ByteArray): Pair<Map<String, String>, ByteArray>? {
        if (data.size < 2) return null
        val length = ((data[0].toInt() and 0xFF) shl 8) or (data[1].toInt() and 0xFF)
        if (length + 2 > data.size) return null
        return headers(String(data, 2, length, Charsets.UTF_8)) to data.copyOfRange(length + 2, data.size)
    }

    private fun unescape(text: String) = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    /**
     * Thân tin `audio.metadata` thành các mốc chữ. `Offset`/`Duration` tính bằng 100 ns; `shiftMs` = độ lệch cộng thêm cho mọi mốc (lệch giữa các lần gọi +
     * [BOUNDARY_SHIFT_MS]). Loại mốc khác `WordBoundary`/`SentenceBoundary` (SessionEnd...) bỏ qua.
     */
    fun parseMetadata(body: String, shiftMs: Long): List<Boundary> {
        val list = ArrayList<Boundary>()
        val array = JSONObject(body).optJSONArray("Metadata") ?: return list
        for (i in 0 until array.length()) {
            val item = array.getJSONObject(i)
            if (item.optString("Type") != "WordBoundary" && item.optString("Type") != "SentenceBoundary") continue
            val data = item.getJSONObject("Data")
            val start = data.getLong("Offset") / 10_000 + shiftMs
            val end = start + data.getLong("Duration") / 10_000
            list.add(Boundary(start, end, unescape(data.getJSONObject("text").getString("Text"))))
        }
        return list
    }

    /**
     * Nhận một lượt đọc tới `turn.end`: ghi mp3 (tin nhị phân `Path:audio`) vào `sink`, thêm mốc của `audio.metadata` (cộng `shiftMs`), trả số byte âm thanh. Dùng
     * chung cho Edge và Azure Speech (cùng khung tin - AzureTts.kt). `label`: tên giọng trong câu báo lỗi; `onClose`: đổi khung CLOSE của máy chủ thành lỗi riêng
     * (Azure báo hết hạn mức bằng lý do đóng) - null thì là "đóng trước khi đọc xong". Quá `totalMs` hay một lần chờ tin quá lâu: [VoiceException] reason "timeout" (có mạng mà dịch vụ chậm -
     * lỗi thoáng qua, không phải mất mạng); mất kết nối giữa chừng: `onDrop`.
     */
    fun readTurn(
        socket: WebSocket, sink: OutputStream, shiftMs: Long, boundaries: MutableList<Boundary>, label: String, totalMs: Long,
        onClose: (WebSocket.Message.Closed) -> VoiceException? = { null },
        /** Lượt bị cắt giữa chừng (mất kết nối / đóng sớm): Edge biến nó thành lỗi thử lại được; mặc định là "không có mạng". */
        onDrop: (String, Throwable?) -> Exception = { message, cause -> VoiceException(message, offline = true, cause = cause) },
        /** Gọi ngay khi nhận khung tiếng (sau khi đã ghi vào `sink`) / tin mốc (các mốc mới, đã cộng `shiftMs`): clip phát luồng ([EdgeTts.synthesize] có [LiveSink]). null = như cũ. */
        onAudio: ((ByteArray) -> Unit)? = null,
        onBoundaries: ((List<Boundary>) -> Unit)? = null,
    ): Long {
        val deadline = System.nanoTime() + totalMs * 1_000_000
        var audio = 0L
        while (true) {
            if (System.nanoTime() > deadline) throw VoiceException("$label trả lời quá chậm", reason = "timeout")
            val message = try {
                socket.receive()
            } catch (error: java.net.SocketTimeoutException) {
                throw VoiceException("$label trả lời quá chậm", cause = error, reason = "timeout")
            } catch (error: java.io.IOException) {
                throw onDrop("Mất kết nối với ${label.replaceFirstChar { it.lowercase() }} giữa chừng", error)
            }
            when (message) {
                is WebSocket.Message.Closed -> throw onClose(message) ?: onDrop("$label đóng kết nối trước khi đọc xong", null)
                is WebSocket.Message.Text -> {
                    val head = message.text.substringBefore("\r\n\r\n")
                    when (headers(head)["Path"]) {
                        "audio.metadata" -> {
                            val found = parseMetadata(message.text.substringAfter("\r\n\r\n"), shiftMs)
                            boundaries.addAll(found)
                            if (onBoundaries != null && found.isNotEmpty()) onBoundaries(found)
                        }
                        "turn.end" -> return audio
                    }
                }
                is WebSocket.Message.Binary -> {
                    val (headers, data) = parseBinary(message.data) ?: throw VoiceException("$label gửi tin hỏng")
                    if (headers["Path"] == "audio" && data.isNotEmpty()) {
                        sink.write(data)
                        audio += data.size
                        onAudio?.invoke(data)
                    }
                }
            }
        }
    }

    /** Độ dài tính từ số byte mp3 (48 kbps không đổi). */
    fun durationMs(bytes: Long): Long = bytes * 1000 / BYTES_PER_SECOND
}

/**
 * Chỗ kết nối Edge của cả tiến trình ([EdgePieces.EDGE_CONNECTIONS] chỗ; máy tính: `ConnectionSlots` trong edge.py, cùng luật). Hết chỗ thì người chờ xếp hàng theo `rank` (số đoạn người nghe phải nghe
 * trước đoạn này: 0 = đoạn họ đang đứng chờ, 1 = đoạn kế...; mặc định [EdgePieces.RANK_BACKGROUND]: việc nền), cùng rank thì ai đến trước được trước. Mảnh đang giữ chỗ không bị đuổi; chỉ chỗ vừa nhả
 * được trao theo hàng. Riêng rank 0 không chờ trần [size]: được lấy thêm tới [extra] chỗ vượt trần (a55: đoạn người nghe đứng chờ đến sau ba clip đọc trước chỉ vài ms đã phải đợi 4-11 giây vì chúng
 * chiếm hết chỗ - hàng chờ chỉ xếp thứ tự người CHỜ, không đòi lại được chỗ đang giữ). Quá size + extra thì rank 0 cũng chờ; rank >= 1 chỉ được chỗ khi số chỗ giữ xuống dưới [size].
 */
class ConnectionSlots(val size: Int, val extra: Int = 0) {
    private class Ticket(val rank: Int, val turn: Long)

    private val lock = ReentrantLock()
    private val changed = lock.newCondition()
    private var free = size // size - số chỗ đang giữ; âm khi rank 0 đang giữ chỗ vượt trần
    private var turns = 0L
    private val queue = java.util.PriorityQueue<Ticket>(compareBy<Ticket>({ it.rank }, { it.turn }))

    /** Số chỗ đang trống (bài thử kiểm chỗ đã nhả hết). */
    fun availablePermits(): Int = lock.withLock { free }

    /** Số người đang xếp hàng chờ chỗ (bài thử). */
    internal fun waiting(): Int = lock.withLock { queue.size }

    /** Lấy một chỗ; false khi quá `timeoutMs`. Vé không bao giờ ở lại hàng sau khi bỏ cuộc (quá hạn, luồng bị ngắt). */
    fun tryAcquire(timeoutMs: Long, rank: Int = EdgePieces.RANK_BACKGROUND): Boolean {
        var left = TimeUnit.MILLISECONDS.toNanos(timeoutMs.coerceAtLeast(0))
        val allowance = if (rank == 0) extra else 0 // chỗ vượt trần được phép với rank này
        lock.lock()
        try {
            val ticket = Ticket(rank, turns++)
            queue.add(ticket)
            try {
                while (!(free + allowance > 0 && queue.peek() === ticket)) {
                    if (left <= 0) return false
                    left = changed.awaitNanos(left)
                }
                free -= 1
                return true
            } finally {
                queue.remove(ticket)
                changed.signalAll() // người kế trong hàng có thể đã tới lượt (còn chỗ), hay người này bỏ cuộc
            }
        } finally {
            lock.unlock()
        }
    }

    /** Giữ một chỗ không hạn (bài thử). */
    fun acquire() {
        tryAcquire(Long.MAX_VALUE / 4_000_000)
    }

    fun release() = lock.withLock {
        check(free < size) { "Trả chỗ kết nối quá số đã giữ" }
        free += 1
        changed.signalAll()
    }
}

/**
 * Đọc SONG SONG các câu của MỘT đoạn (uxfix47; máy tính: `edge.py` `speech_pieces`, cùng hằng số, cùng bộ ví dụ `tests/fixtures/readaloud/edge/pieces.json` - đổi một bên thì đổi
 * cả hai bên và bộ ví dụ). Soát a49: chữ Edge chưa từng đọc ra audio chỉ nhanh cỡ 1x thời gian thật (đoạn 15 giây mất 13-27 giây) mà các yêu cầu song song không làm nhau chậm đi.
 * Độ dài tính bằng ký tự UTF-16 (Python: code point) - bộ ví dụ chỉ có chữ trong BMP.
 */
object EdgePieces {
    /** Tối đa chừng này mảnh một đoạn (và chừng này kết nối cùng lúc cho một clip). */
    const val PIECE_PARALLEL = 3
    /** Riêng đoạn người nghe đang đứng chờ (rank 0): cắt tới chừng này mảnh. Soát a54 (4 đoạn, mạng thật): 3 -> 6 mảnh rút thời gian chờ trung vị 6,96 -> 5,36 giây, chỗ nối vẫn 855-889 ms. */
    const val TARGET_PIECES = 6
    /** Trần kết nối Edge đang mở của cả tiến trình: đọc trước nhiều đoạn x mảnh không mở hàng chục ổ cắm cùng lúc. */
    const val EDGE_CONNECTIONS = 8
    /** [ConnectionSlots] rank của việc không có người nghe đứng chờ ngay (Làm trước, lượt gọi không nói rõ): đứng sau mọi đoạn người nghe sắp nghe. */
    const val RANK_BACKGROUND = 99
    /** Rank lớn nhất còn xếp trước việc nền (máy chủ máy tính nhận 0-98). */
    const val MAX_RANK = RANK_BACKGROUND - 1
    /** Đoạn ngắn hơn chừng này ký tự giữ một yêu cầu: câu đơn 90-100 ký tự đo 5,8-13,9 giây, cắt đôi không nhanh hơn mà tốn thêm một lần nối (~0,45 giây). */
    const val WHOLE_CHARS = 100
    /** Mảnh không nhỏ hơn chừng này (gộp câu ngắn): mảnh quá ngắn thêm chỗ nối mà không rút ngắn thời gian chờ. */
    const val MIN_PIECE_CHARS = 50
    /** Câu dài hơn chừng này được cắt tiếp ở ; : , (sau dấu có khoảng trắng - không bao giờ giữa chữ hay số như "3,5"). */
    const val LONG_SENTENCE_CHARS = 200
    /** uxfix55: câu dài hơn 130% x (tổng / số mảnh) cũng được cắt ở vế, để một câu dài không làm một mảnh dài gấp đôi các mảnh kia (a57: mảnh 209 ký tự Edge mất 7,9 giây, các mảnh khác 3,5-5,5). */
    const val PIECE_SLACK_PERCENT = 130
    private const val SENTENCE_END = ".!?…"
    private const val CLOSERS = "\"'”’)]»"
    private const val CLAUSE_MARKS = ";:,"

    /** Số mảnh tối đa của một đoạn theo rank: đoạn người nghe đang đứng chờ (0) [TARGET_PIECES], mọi đoạn khác [PIECE_PARALLEL] (máy tính: `piece_limit`). */
    fun pieceLimit(rank: Int): Int = if (rank == 0) TARGET_PIECES else PIECE_PARALLEL

    /** Câu dài hơn chừng này ký tự được cắt tiếp ở vế (máy tính: `clause_threshold`): [LONG_SENTENCE_CHARS], hay thấp hơn khi một mảnh cân bằng (total / limit) ngắn hơn thế nhiều, nhưng không bao giờ dưới [MIN_PIECE_CHARS]. */
    fun clauseThreshold(total: Int, limit: Int): Int =
        minOf(LONG_SENTENCE_CHARS, maxOf(MIN_PIECE_CHARS, (PIECE_SLACK_PERCENT * total + 100 * limit - 1) / (100 * limit)))

    /** Các mảnh gửi Edge cho `text`, mảnh nào cũng vừa [EdgeProtocol.MAX_TEXT_BYTES]; ghép theo thứ tự cho đúng chữ gốc. */
    fun split(text: String, rank: Int = RANK_BACKGROUND): List<String> =
        speechPieces(text, rank).flatMap { piece -> TextChunks.split(piece, EdgeProtocol.MAX_TEXT_BYTES, EdgeProtocol::escapedBytes).map { Py.strip(it.second) } }.filter { it.isNotEmpty() }

    /** Chưa tính giới hạn byte: đoạn ngắn (< [WHOLE_CHARS]) một mảnh; còn lại cắt ở hết câu, câu dài hơn [clauseThreshold] cắt tiếp ở vế, gộp thành tối đa [pieceLimit] mảnh cân bằng. */
    fun speechPieces(text: String, rank: Int = RANK_BACKGROUND): List<String> {
        val body = Py.strip(text)
        if (body.length >= WHOLE_CHARS) {
            val limit = pieceLimit(rank)
            val threshold = clauseThreshold(body.length, limit)
            val units = splitSentences(body).flatMap { if (it.length > threshold) splitClauses(it) else listOf(it) }
            if (units.size > 1) return groupUnits(units, limit)
        }
        return if (body.isEmpty()) emptyList() else listOf(body)
    }

    /**
     * Cắt ở hết câu: dấu . ! ? … (và dấu đóng ngoặc / nháy đi liền), rồi khoảng trắng, rồi chữ KHÔNG viết thường. Giữ nguyên "Anh A. Nguyễn" (chữ đơn trước dấu chấm =
     * tên viết tắt) và `"Thật à?" anh hỏi` (sau dấu hỏi là chữ thường).
     */
    fun splitSentences(text: String): List<String> {
        val out = ArrayList<String>()
        var start = 0
        var i = 0
        val n = text.length
        while (i < n) {
            if (text[i] !in SENTENCE_END) {
                i += 1
                continue
            }
            var end = i + 1
            while (end < n && text[end] in SENTENCE_END) end += 1
            var close = end
            while (close < n && text[close] in CLOSERS) close += 1
            var after = close
            while (after < n && Py.isSpace(text[after].code)) after += 1
            // Python: text[i - 1].isalpha() và not text[i - 2].isalnum() - theo code point, và isalnum tính cả số như ² ½ (Py.isAlnum; isLetterOrDigit của Kotlin thì không).
            val initial = text[i] == '.' && end == i + 1 && i >= 1 && Character.isLetter(text.codePointBefore(i)) &&
                (i - Character.charCount(text.codePointBefore(i)) == 0 || !Py.isAlnum(text.codePointBefore(i - Character.charCount(text.codePointBefore(i)))))
            if (after > close && after < n && !text[after].isLowerCase() && !initial) {
                out.add(Py.strip(text.substring(start, close)))
                start = after
                i = after
            } else {
                i = end
            }
        }
        out.add(Py.strip(text.substring(start)))
        return out.filter { it.isNotEmpty() }
    }

    /** Một câu dài thành các vế: cắt sau ; : , khi sau dấu có khoảng trắng. */
    fun splitClauses(sentence: String): List<String> {
        val out = ArrayList<String>()
        var start = 0
        for (i in 0 until sentence.length - 1) {
            if (sentence[i] in CLAUSE_MARKS && Py.isSpace(sentence[i + 1].code)) {
                out.add(Py.strip(sentence.substring(start, i + 1)))
                start = i + 1
            }
        }
        out.add(Py.strip(sentence.substring(start)))
        return out.filter { it.isNotEmpty() }
    }

    /**
     * Gộp các câu / vế liền nhau thành tối đa `limit` mảnh cân bằng độ dài (mỗi mảnh >= [MIN_PIECE_CHARS]). Nhiều mảnh hơn số kết nối cùng lúc chỉ xếp hàng thêm một
     * vòng chờ ~5-10 giây của Edge, nên 8 câu 60 ký tự thành 3 mảnh chứ không phải 8. Cắt cân bằng với số mảnh nhiều nhất còn giữ mọi mảnh >= [MIN_PIECE_CHARS]
     * (uxfix55: bớt dần số mảnh rồi cắt lại, không gộp mảnh nhỏ vào hàng xóm - vế ngắn làm gộp dây chuyền thành một mảnh duy nhất).
     */
    private fun groupUnits(units: List<String>, limit: Int): List<String> {
        val total = units.sumOf { it.length }
        val prefix = IntArray(units.size + 1)
        for (k in units.indices) prefix[k + 1] = prefix[k] + units[k].length
        var count = minOf(limit, units.size, maxOf(1, total / MIN_PIECE_CHARS))
        while (true) {
            val cuts = arrayListOf(0)
            for (j in 1 until count) {
                // Chỗ cắt thứ j: số câu ở j mảnh đầu sao cho độ dài dồn gần nhất total*j/count (hoà thì lấy sớm hơn); còn chỗ cho các mảnh sau.
                var best = cuts.last() + 1
                var bestScore = Int.MAX_VALUE
                for (at in cuts.last() + 1..units.size - (count - j)) {
                    val score = Math.abs(prefix[at] * count - total * j)
                    if (score < bestScore) {
                        best = at
                        bestScore = score
                    }
                }
                cuts.add(best)
            }
            cuts.add(units.size)
            if (count == 1 || (0 until count).all { prefix[cuts[it + 1]] - prefix[cuts[it]] >= MIN_PIECE_CHARS }) {
                return (0 until count).map { units.subList(cuts[it], cuts[it + 1]).joinToString(" ") }
            }
            count -= 1
        }
    }
}

/**
 * Chỗ nối giữa hai mảnh của một đoạn (uxfix50; máy tính: `edge.py` `trim_join_tail`, cùng hằng số, cùng bộ ví dụ `tests/fixtures/readaloud/edge/join_tail.json` - đổi một bên thì đổi cả hai bên
 * và bộ ví dụ). Mỗi lượt của Edge kết thúc bằng ~0,85 giây lặng đuôi + ~0,13 giây lặng đầu của mảnh kế (soát a51: chỗ nối lặng 0,95-0,99 giây), trong khi Edge tự nghỉ giữa hai câu TRONG một lượt
 * chỉ 0,86 giây (đo a52: khoảng cách mốc 862-875 ms; sau dấu phẩy 137-263 ms). Nên mảnh không phải mảnh cuối bị cắt đuôi, ở ranh giới khung MP3 (24 kHz, 48 kbps CBR, không đệm: 144 byte = 24 ms),
 * giữ lại [TAIL_SENTENCE_MS] sau mốc hết chữ cuối nếu mảnh kết thúc ở dấu hết câu, [TAIL_OTHER_MS] nếu không (dấu phẩy, cắt giữa câu): chỗ nối nghỉ đúng cỡ Edge nghỉ ở dấu ấy. Chữ cuối kết thúc trong
 * khoảng -27..+15 ms quanh mốc hết chữ (đo 30 mảnh) nên 100 ms còn dư cho bộ giải mã; phần cắt đo được là lặng (RMS < 0,1% giọng nói). Khung nào không đúng dạng ấy thì giữ nguyên cả mảnh.
 */
object EdgeJoin {
    const val TAIL_SENTENCE_MS = 730
    const val TAIL_OTHER_MS = 100
    const val FRAME_BYTES = 144
    const val FRAME_MS = 24
    private const val SENTENCE_END = ".!?…"
    private const val CLOSERS = "\"'”’)]»"

    /** Giữ bao lâu sau mốc hết chữ cuối của `piece` (xem mô tả trên). */
    fun tailMs(piece: String): Int {
        val body = piece.trimEnd().trimEnd { it in CLOSERS }
        return if (body.isNotEmpty() && body.last() in SENTENCE_END) TAIL_SENTENCE_MS else TAIL_OTHER_MS
    }

    /**
     * `lastEndMs`: mốc hết chữ cuối của mảnh theo dịch vụ (CHƯA cộng [EdgeProtocol.BOUNDARY_SHIFT_MS]); null = không có mốc thì không cắt. Trả nguyên `audio` khi không có gì để cắt hay khung nào không đúng dạng.
     */
    fun trim(audio: ByteArray, piece: String, lastEndMs: Long?): ByteArray {
        if (lastEndMs == null || audio.isEmpty() || audio.size % FRAME_BYTES != 0) return audio
        val keep = (lastEndMs + tailMs(piece) + FRAME_MS - 1) / FRAME_MS // làm tròn LÊN: không cắt sớm hơn
        if (keep * FRAME_BYTES >= audio.size) return audio
        val expected = Triple(FRAME_BYTES, 576, 24_000)
        var at = 0
        while (at < audio.size) {
            if (Mp3.frameAt(audio, at) != expected) return audio
            at += FRAME_BYTES
        }
        return audio.copyOf((keep * FRAME_BYTES).toInt())
    }
}

/** Nơi mỗi lần thử của một mảnh báo tiếng / mốc đang về cho [PieceAssembler] (chỉ khi clip phát luồng). */
internal interface PieceTap {
    /** Bắt đầu một lần thử mới của mảnh (lần trước hỏng giữa chừng). */
    fun restart()
    fun audio(data: ByteArray)
    fun boundaries(found: List<Boundary>)
}

/**
 * Ghép các mảnh của MỘT clip Edge theo thứ tự đọc: cắt lặng đuôi mảnh không phải mảnh cuối ([EdgeJoin.trim]), bù mốc theo số byte đã ghi (48 kbps không đổi nên chính xác). MỘT đường ghép cho cả hai chế độ
 * (máy tính: `edge.py` bộ phát theo thứ tự, cùng luật):
 *  - `live` null: mảnh nào xong mới ghi (thành đoạn liền nhau theo thứ tự, như bản cũ ghép một lượt ở cuối);
 *  - có `live`: MẢNH ĐỨNG ĐẦU ghi ngay khi byte về (`out` flush, `live.grew`); mảnh đứng đầu mà không phải mảnh cuối chỉ ghi tới khung thứ floor(mốc hết chữ cuối đã nhận / [EdgeJoin.FRAME_MS])
 *    - phần đó chắc chắn không bị [EdgeJoin.trim] cắt vì trim giữ tới mốc hết chữ cuối + ít nhất [EdgeJoin.TAIL_OTHER_MS]; xong thì ghi nốt tới chỗ trim. Mảnh sau giữ trong bộ nhớ tới lượt.
 * Bất biến (bài thử): file ghi dần == file của đường thường; mốc đã báo == mốc của đường thường.
 *
 * Mảnh đầu mà đã ghi rồi mới hỏng giữa chừng, lần thử lại ([restart]) phải ra ĐÚNG phần đã ghi (cùng byte, cùng mốc) rồi mới ghi tiếp - không thì [VoiceException] "service" (clip hỏng), không bao giờ nối hai bản khác nhau.
 */
internal class PieceAssembler(private val pieces: List<String>, private val out: OutputStream, private val live: LiveSink?, private val file: File) {
    private class Buffer : java.io.ByteArrayOutputStream(8192) {
        fun array(): ByteArray = buf
    }

    private class Piece {
        var audio = Buffer()
        var found = ArrayList<Boundary>()
        var final: ByteArray? = null
        var shift = -1L
        var emitted = 0
        var reported = 0
        /** Phần đã phát của lần thử hỏng trước (byte / mốc thô): lần thử lại phải trùng. */
        var committedAudio: ByteArray? = null
        var committedFound: List<Boundary>? = null
    }

    private val lock = Any()
    private val state = Array(pieces.size) { Piece() }
    private var head = 0

    /** Byte đã ghi vào `out`. */
    var bytes = 0L
        private set

    /** Mốc đã báo (đã bù chỗ nối), đúng thứ tự: cuối cùng là mốc của cả clip. */
    val boundaries = ArrayList<Boundary>()

    fun tap(index: Int): PieceTap? {
        if (live == null) return null
        return object : PieceTap {
            override fun restart() = restart(index)
            override fun audio(data: ByteArray) = audio(index, data)
            override fun boundaries(found: List<Boundary>) = boundaries(index, found)
        }
    }

    private fun mismatch(): Nothing = throw VoiceException("Giọng Edge trả lời khác đi giữa hai lần thử", reason = "service")

    private fun restart(index: Int) = synchronized(lock) {
        val piece = state[index]
        if (piece.emitted > 0 && piece.audio.size() >= piece.emitted) piece.committedAudio = piece.audio.array().copyOf(piece.emitted)
        if (piece.reported > 0 && piece.found.size >= piece.reported) piece.committedFound = ArrayList(piece.found.subList(0, piece.reported))
        piece.audio = Buffer()
        piece.found = ArrayList()
    }

    private fun audio(index: Int, data: ByteArray) = synchronized(lock) {
        val piece = state[index]
        val before = piece.audio.size()
        piece.audio.write(data)
        piece.committedAudio?.let { committed ->
            for (at in before until minOf(piece.audio.size(), committed.size)) if (piece.audio.array()[at] != committed[at]) mismatch()
        }
        advance()
    }

    private fun boundaries(index: Int, found: List<Boundary>) = synchronized(lock) {
        val piece = state[index]
        val before = piece.found.size
        piece.found.addAll(found)
        piece.committedFound?.let { committed ->
            for (at in before until minOf(piece.found.size, committed.size)) if (piece.found[at] != committed[at]) mismatch()
        }
        advance()
    }

    /** Mảnh `index` đọc xong: `result` = (mp3, mốc thô của lần thử cuối). */
    fun finish(index: Int, result: Pair<ByteArray, List<Boundary>>) = synchronized(lock) {
        val (audio, found) = result
        val piece = state[index]
        if ((piece.committedAudio?.size ?: 0) > audio.size || (piece.committedFound?.size ?: 0) > found.size) mismatch()
        // Mảnh không phải mảnh cuối bị cắt lặng đuôi trước khi bù mốc cho mảnh sau ([EdgeJoin]); mốc ở đây đã cộng BOUNDARY_SHIFT_MS nên trừ lại.
        piece.final = if (index < pieces.size - 1) EdgeJoin.trim(audio, pieces[index], found.lastOrNull()?.let { it.endMs - EdgeProtocol.BOUNDARY_SHIFT_MS }) else audio
        piece.found = ArrayList(found)
        advance()
    }

    private fun advance() {
        while (head < pieces.size) {
            val piece = state[head]
            // Mốc của mỗi mảnh tính từ đầu mảnh ấy: bù bằng độ dài mp3 các mảnh trước (48 kbps không đổi nên chính xác).
            if (piece.shift < 0) piece.shift = EdgeProtocol.durationMs(bytes)
            val final = piece.final
            val limit = when {
                final != null -> final.size
                live == null -> 0
                head == pieces.size - 1 -> piece.audio.size()
                else -> safeLimit(piece)
            }
            if (limit > piece.emitted) {
                val source = final ?: piece.audio.array()
                out.write(source, piece.emitted, limit - piece.emitted)
                out.flush()
                bytes += limit - piece.emitted
                piece.emitted = limit
                live?.grew(file, bytes)
            }
            if (final != null || live != null) report(piece)
            if (final == null || piece.emitted < final.size) return
            head += 1
        }
    }

    /** Số byte đầu của mảnh đang đọc (chưa xong, không phải mảnh cuối) chắc chắn còn nằm trong file cuối: tới khung [EdgeJoin.FRAME_MS] của mốc hết chữ cuối đã nhận. */
    private fun safeLimit(piece: Piece): Int {
        val last = piece.found.lastOrNull() ?: return 0
        val frames = (last.endMs - EdgeProtocol.BOUNDARY_SHIFT_MS).coerceAtLeast(0) / EdgeJoin.FRAME_MS
        return minOf(piece.audio.size() / EdgeJoin.FRAME_BYTES.toLong(), frames).toInt() * EdgeJoin.FRAME_BYTES
    }

    private fun report(piece: Piece) {
        if (piece.reported >= piece.found.size) return
        val fresh = piece.found.subList(piece.reported, piece.found.size)
            .map { if (piece.shift == 0L) it else it.copy(startMs = it.startMs + piece.shift, endMs = it.endMs + piece.shift) }
        piece.reported = piece.found.size
        boundaries.addAll(fresh)
        live?.boundaries(fresh)
    }
}

/**
 * Giọng Microsoft qua dịch vụ đọc to của Edge (`vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`): không khoá, cần mạng. Mỗi mảnh một kết nối WebSocket ([WebSocket]);
 * đoạn từ [EdgePieces.WHOLE_CHARS] ký tự cắt ở hết câu thành tối đa [EdgePieces.PIECE_PARALLEL] mảnh đọc SONG SONG (mảnh quá 4000 byte cắt tiếp ở dấu cách), mốc ghép lại theo số byte mp3 đã nhận. Mọi chặn đều có hạn: nối 5 giây, mỗi lần chờ tin 15
 * giây, cả đoạn 45 giây (MỘT hạn chung cho cả clip: chờ chỗ kết nối, nối, nhận tin và các mảnh đều tính vào đó) - quá hạn hay không có mạng là [VoiceException] (người gọi rơi về giọng
 * của máy), không bao giờ chờ mãi. Clip bị huỷ ([ClipCancel]: tua, đổi chương, dừng) hay hỏng một mảnh thì ổ cắm của các mảnh còn lại đóng ngay, không để chúng giữ chỗ kết nối tới hết lượt.
 */
class EdgeTts(
    private val voiceName: String,
    private val connect: Connector = Connector.Real,
    private val pause: (Long) -> Unit = { Thread.sleep(it) },
) : Voice {
    override val id = "edge:$voiceName"
    override val extension = "mp3"

    /** Chỗ nối mạng, để bài thử thay bằng máy chủ giả. */
    fun interface Connector {
        fun open(url: String, headers: Map<String, String>): WebSocket

        object Real : Connector {
            override fun open(url: String, headers: Map<String, String>) = WebSocket.connect(url, headers, CONNECT_MS, READ_MS)
        }
    }

    companion object {
        /** Nối + bắt tay TLS + nâng cấp WebSocket. Bắt tay thật xong trong 0,4-1,2 giây (p50 0,5, p99 1,2 giây: 222 lượt đo máy tính a48-a51); thỉnh thoảng một lần treo ~10 giây (a51: 8 trong 95 mảnh, khi nhiều kết nối mở cùng lúc) -
         *  nên hết giờ sớm rồi thử lại ([ConnectTimedOut]) thay vì đợi. Điện thoại có thể đi sóng yếu (mỗi vòng ~0,3 giây x 4 vòng) nên 5 giây, máy tính (edge.py CONNECT_TIMEOUT) 4 giây. */
        const val CONNECT_MS = 5_000
        const val READ_MS = 15_000
        const val TOTAL_MS = 45_000L
        /** Hạn chung của một clip ([TOTAL_MS]); bài thử đặt ngắn hơn để kiểm hạn mà không chờ 45 giây. */
        @Volatile internal var totalMs = TOTAL_MS
        /** Lỗi thoáng qua ([Dropped]) thử lại tối đa chừng này lần, mỗi lần một kết nối mới, nghỉ lùi dần theo [BACKOFF_MS]: đủ cho một đoạn mạng chập
         *  chờn (qua vùng sóng yếu, wifi đổi sóng) mà chưa bắt người nghe chờ quá lâu (soát UX a9; trước 2 lần × 0,3 s - mạng mất 2 giây là dừng). */
        const val RETRIES = 3
        val BACKOFF_MS = longArrayOf(0L, 1_500L, 4_000L) // lần thử lại đầu nối lại ngay (kết nối mới); chỉ lần sau mới nghỉ
        /** Hết cách thử lại vì MẤT MẠNG thật: câu nói thẳng cho người nghe (thay cho "Mất kết nối với giọng Edge giữa chừng"). */
        const val LOST_NETWORK = "Mất mạng - giọng trực tuyến tạm dừng. Bấm phát để thử lại, hoặc chọn giọng trên máy."
        /** Hết cách thử lại mà mạng vẫn còn (dịch vụ cắt lượt / bận): không nói "mất mạng". */
        const val NOT_ANSWERING = "Giọng Edge đang không trả lời - bấm phát để thử lại, hoặc chọn giọng trên máy."
        /** Lệch giữa đồng hồ máy và máy chủ (giây), học từ header `Date` của lần bị từ chối 403; dùng chung cho mọi lần gọi. */
        @Volatile var clockSkewSeconds = 0.0
        /** Kết nối Edge đang mở của cả tiến trình (mọi đoạn đọc trước x mảnh); bài thử thay bằng cái nhỏ hơn để kiểm trần. */
        @Volatile internal var connections = productionSlots()
        /** Trần cứng EDGE_CONNECTIONS + TARGET_PIECES: chỉ đoạn rank 0 vượt EDGE_CONNECTIONS (máy tính: `_connections` trong edge.py). */
        internal fun productionSlots() = ConnectionSlots(EdgePieces.EDGE_CONNECTIONS, EdgePieces.TARGET_PIECES)
        private val random = SecureRandom()

        /** Đọc `Date: Sat, 03 Oct 2026 12:00:00 GMT` của máy chủ thành giây Unix; null nếu không đọc được. */
        fun parseHttpDate(value: String?): Double? = try {
            val format = java.text.SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss zzz", Locale.US)
            format.parse(value ?: return null)?.time?.div(1000.0)
        } catch (error: java.text.ParseException) {
            null
        }
    }

    /** Clip đang đọc cho người nghe (rank 0, [LiveClips.receiving]): file lớn dần cho ExoPlayer, xem [LiveClips]. Không có chỗ nhận (hay chỗ nhận đã phát luồng một lần) thì đường thường. */
    override fun synthesize(text: String, out: File): Clip {
        val here = LiveClips.here()?.takeIf { it.target.accepting() }
        return synthesize(text, out, here?.let { LiveWords(text, it.expand, it.target) })
    }

    /**
     * `live` != null: file `out` được GHI DẦN theo thứ tự đọc ([PieceAssembler]) và `live` được báo mỗi lần nó lớn thêm / có mốc mới / xong / hỏng; file cuối cùng, mốc và độ dài đúng như đường thường
     * (`live` null: cả clip ghép trong bộ nhớ rồi ghi một lần). Mảnh đầu đang phát luồng mà hỏng giữa chừng thì lần thử lại của nó phải ra đúng phần đã phát ([PieceAssembler.restart]).
     */
    fun synthesize(text: String, out: File, live: LiveSink?): Clip {
        val pieces = EdgePieces.split(text, ClipBudget.rank())
        val received = AtomicLong(0)
        val run = ClipRun(System.nanoTime() + totalMs * 1_000_000)
        // Người gọi huỷ lượt đọc (tua / đổi chương / dừng): đóng ổ cắm của mọi mảnh đang chạy ngay thay vì để chúng giữ chỗ kết nối tới hết lượt.
        val outer = ClipBudget.current()?.cancel
        val link = AutoCloseable { run.cancel.cancel() }
        outer?.register(link)
        val memory = if (live == null) java.io.ByteArrayOutputStream() else null
        val sink: OutputStream = memory ?: java.io.FileOutputStream(out)
        val assembler = PieceAssembler(pieces, sink, live, out)
        val clip = try {
            try {
                if (pieces.size <= 1) pieces.forEachIndexed { index, piece -> assembler.finish(index, speakPiece(piece, received, run, assembler.tap(index))) }
                else speakInParallel(pieces, received, run, assembler)
            } catch (error: Exception) {
                if (run.cancel.cancelled && error !is CancellationException) throw CancellationException("Lượt đọc đã bị huỷ").apply { initCause(error) }
                throw error
            } finally {
                outer?.unregister(link)
                run.cancel.cancel() // mảnh nào còn chạy (một mảnh khác hỏng, quá hạn) thì ổ cắm đóng ngay
            }
            if (memory != null) out.outputStream().use { it.write(memory.toByteArray()) }
            if (assembler.bytes == 0L) throw VoiceException("Giọng Edge không trả về âm thanh")
            val duration = EdgeProtocol.durationMs(assembler.bytes)
            Clip(out, duration, WordTokens.map(text, assembler.boundaries, duration), id)
        } catch (error: Exception) {
            live?.failed(error)
            throw error
        } finally {
            if (live != null) runCatching { sink.close() }
        }
        live?.done(clip)
        return clip
    }

    /** Một clip đang đọc: hạn chung ([totalMs], tính từ lúc bắt đầu) và nơi giữ ổ cắm của các mảnh để huỷ cùng lúc. */
    private class ClipRun(val deadlineNanos: Long) {
        val cancel = ClipCancel()
        fun remainingMs(): Long = maxOf(0L, (deadlineNanos - System.nanoTime()) / 1_000_000)
        /** Hạn cho một lượt chờ / nhận tin: phần còn lại của clip; lần thử lại còn bị quỹ [ClipBudget] cắt ngắn thêm. */
        fun attemptMs(retry: Boolean): Long = ClipBudget.attemptMs(remainingMs(), retry)
        fun checkNotCancelled() {
            if (cancel.cancelled) throw CancellationException("Lượt đọc đã bị huỷ")
        }
    }

    /**
     * Các mảnh của một đoạn đọc cùng lúc (tối đa [EdgePieces.PIECE_PARALLEL], đoạn rank 0 tối đa [EdgePieces.TARGET_PIECES]), trả theo thứ tự đọc. Chờ theo thứ tự HOÀN THÀNH: mảnh nào hỏng trước thì cả đoạn hỏng ngay với đúng lỗi ấy
     * (không đợi mảnh đứng trước), và quá hạn chung của clip là [VoiceException] "timeout". Mảnh còn lại bị huỷ, ổ cắm của chúng đóng ([synthesize]).
     */
    private fun speakInParallel(pieces: List<String>, received: AtomicLong, run: ClipRun, assembler: PieceAssembler) {
        val budget = ClipBudget.current() // luồng phụ cùng quỹ thời gian thử lại của đoạn
        val rank = ClipBudget.rank() // và cùng rank xếp hàng chờ chỗ kết nối
        val pool = Executors.newFixedThreadPool(minOf(EdgePieces.pieceLimit(rank), pieces.size)) { Thread(it, "edge-piece").apply { isDaemon = true } }
        val completion = ExecutorCompletionService<Pair<Int, Pair<ByteArray, List<Boundary>>>>(pool)
        val futures = pieces.mapIndexed { index, piece -> completion.submit {
            val rankBefore = ClipBudget.enterRank(rank)
            try {
                ClipBudget.inherit(budget) { index to speakPiece(piece, received, run, assembler.tap(index)) }
            } finally {
                ClipBudget.leaveRank(rankBefore)
            }
        } }
        try {
            repeat(pieces.size) {
                val done = completion.poll(run.remainingMs(), TimeUnit.MILLISECONDS) ?: throw VoiceException("Giọng Edge trả lời quá chậm", reason = "timeout")
                val (index, result) = try {
                    done.get()
                } catch (error: ExecutionException) {
                    throw error.cause ?: error
                }
                assembler.finish(index, result)
            }
        } finally {
            futures.forEach { it.cancel(true) }
            pool.shutdownNow()
        }
    }

    /**
     * Một mảnh, thử lại khi dịch vụ cắt lượt / mạng chập chờn. `received`: số byte mp3 các mảnh của đoạn đã nhận xong - còn 0 mà lần đầu đã không có mạng thì thôi ngay
     * (rơi sang giọng kế), như đoạn một mảnh.
     */
    private fun speakPiece(part: String, received: AtomicLong, run: ClipRun, tap: PieceTap?): Pair<ByteArray, List<Boundary>> {
        var attempt = 0
        while (true) {
            run.checkNotCancelled()
            val failure: Exception = try {
                val result = readPart(part, attempt > 0, run, tap)
                received.addAndGet(result.first.size.toLong())
                return result
            } catch (error: Dropped) {
                // Dịch vụ cắt lượt giữa chừng hay bận lúc bắt tay: thử lại mảnh ấy bằng kết nối mới, không rơi ngay về giọng của máy.
                run.checkNotCancelled() // ổ cắm bị đóng vì huỷ cũng hiện ra như bị cắt: không thử lại
                error
            } catch (error: VoiceException) {
                run.checkNotCancelled()
                // Mất mạng GIỮA CHỪNG (đã cắt lượt trước đó, hay mảnh khác vừa đọc xong): kết nối mới cũng báo "không có mạng" - vẫn thử lại, mạng
                // hay chập chờn vài giây. Ngay lần đầu mà đã không có mạng thì thôi, rơi sang giọng kế liền như trước.
                if (!(error.offline || error.reason == "timeout") || (attempt == 0 && received.get() == 0L)) throw error
                error
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                run.checkNotCancelled() // ghi vào ổ cắm đã đóng
                throw error
            }
            // Hết quỹ thời gian thử lại của đoạn ([ClipBudget]) hay hạn chung của clip: thôi ngay - lần thử nữa sẽ không kịp, người gọi rơi sang giọng kế.
            if (attempt == RETRIES || !ClipBudget.fits(BACKOFF_MS[attempt]) || run.remainingMs() <= BACKOFF_MS[attempt]) {
                val offline = (failure as? VoiceException)?.offline == true || failure is ConnectTimedOut
                throw VoiceException(if (offline) LOST_NETWORK else NOT_ANSWERING, offline = offline, cause = failure)
            }
            if (BACKOFF_MS[attempt] > 0) pause(BACKOFF_MS[attempt])
            attempt += 1
        }
    }

    /**
     * Lỗi thoáng qua của MỘT lượt (thử lại được): dịch vụ cắt kết nối giữa lượt, hay lúc bắt tay trả HTTP 429 / 5xx hoặc reset kết nối. Khác "không có mạng"
     * (không tìm thấy máy chủ, bị từ chối nối) và khác "bị từ chối / đổi giao thức" - hai thứ ấy ném [VoiceException] ngay.
     */
    private open class Dropped(message: String, cause: Throwable? = null) : Exception(message, cause)

    /** Bắt tay quá [CONNECT_MS]: thử lại được như [Dropped]; hết lần thử mà lần nào cũng treo thì là mất mạng thật (sóng bị chặn, máy chủ không tới được) - báo "mất mạng" như trước. */
    private class ConnectTimedOut(message: String, cause: Throwable? = null) : Dropped(message, cause)

    /** Một mảnh chữ: (mp3, mốc tính từ đầu mảnh, đã cộng [EdgeProtocol.BOUNDARY_SHIFT_MS]). Chỉ trả khi đọc trọn lượt, nên lượt hỏng thử lại không để sót mảnh âm thanh dở. */
    private fun readPart(part: String, retry: Boolean, run: ClipRun, tap: PieceTap?): Pair<ByteArray, List<Boundary>> {
        // Giữ một chỗ trong [connections] suốt đời kết nối (không giữ khi nghỉ chờ thử lại, nên không có chuyện giữ chỗ mà đợi chỗ).
        // Chờ chỗ, nối và nhận tin cùng ăn vào MỘT hạn của clip ([ClipRun.attemptMs]).
        // Hết chỗ thì đoạn gần người nghe hơn ([ClipBudget.rank]) đứng trước.
        val slots = connections
        if (!slots.tryAcquire(run.attemptMs(retry), ClipBudget.rank())) throw VoiceException("Giọng Edge trả lời quá chậm", reason = "timeout")
        try {
            run.checkNotCancelled()
            val socket = open()
            // Huỷ clip thì đóng ổ cắm này ngay (luồng đang chờ đọc văng ra và nhả chỗ kết nối), không đợi hết lượt.
            val closer = AutoCloseable { socket.abort() }
            run.cancel.register(closer)
            try {
                val stamp = EdgeProtocol.dateString(System.currentTimeMillis())
                socket.sendText(EdgeProtocol.speechConfig(stamp))
                socket.sendText(EdgeProtocol.ssml(voiceName, EdgeProtocol.escape(part), EdgeProtocol.connectionId(random), stamp))
                val audio = java.io.ByteArrayOutputStream()
                val boundaries = ArrayList<Boundary>()
                tap?.restart() // lần thử mới của mảnh này: bộ ghép bỏ phần dở của lần trước (phần đã phát luồng thì đối chiếu)
                EdgeProtocol.readTurn(
                    socket, audio, EdgeProtocol.BOUNDARY_SHIFT_MS, boundaries, "Giọng Edge", run.attemptMs(retry), onDrop = { message, cause -> Dropped(message, cause) },
                    onAudio = tap?.let { it::audio }, onBoundaries = tap?.let { it::boundaries },
                )
                return audio.toByteArray() to boundaries
            } finally {
                run.cancel.unregister(closer)
                socket.close()
            }
        } finally {
            slots.release()
        }
    }

    /** Mở kết nối; 403 thì học độ lệch đồng hồ từ header `Date` rồi thử lại một lần (Sec-MS-GEC phụ thuộc giờ). */
    private fun open(): WebSocket {
        var retried = false
        while (true) {
            val now = System.currentTimeMillis() / 1000.0 + clockSkewSeconds
            val headers = mapOf(
                "Pragma" to "no-cache", "Cache-Control" to "no-cache",
                "Origin" to "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
                "Sec-WebSocket-Version" to "13",
                "User-Agent" to EdgeProtocol.userAgent(), "Accept-Language" to "en-US,en;q=0.9",
                "Cookie" to "muid=" + ByteArray(16).also(random::nextBytes).joinToString("") { "%02X".format(it) } + ";",
            )
            try {
                return connect.open(EdgeProtocol.url(EdgeProtocol.connectionId(random), now), headers)
            } catch (error: HandshakeException) {
                val server = parseHttpDate(error.headers["date"])
                if (error.status == 403 && server != null && !retried) {
                    // Gán tuyệt đối như máy tính (`server - time.time()`): các mảnh song song cùng bị 403 mà cộng dồn thì độ lệch thành 2-3 lần.
                    clockSkewSeconds = server - System.currentTimeMillis() / 1000.0
                    retried = true
                    continue
                }
                if (error.status == 429 || error.status >= 500) throw Dropped("Giọng Edge đang bận (HTTP ${error.status})", error)
                throw VoiceException("Dịch vụ giọng Edge từ chối (${error.status}) - có thể đã đổi cách dùng", cause = error, reason = "rejected")
            } catch (error: UnknownHostException) {
                throw offline(error)
            } catch (error: ConnectException) {
                throw offline(error)
            } catch (error: SocketTimeoutException) {
                // Máy chủ đã tìm thấy (DNS xong) mà bắt tay treo: thử lại như một lượt bị cắt, không báo mất mạng ngay (a51: một lần treo làm cả chương dừng "Không có mạng").
                throw ConnectTimedOut("Giọng Edge không bắt tay kịp (quá giờ)", error)
            } catch (error: IOException) {
                if (isReset(error)) throw Dropped("Giọng Edge cắt kết nối lúc bắt tay", error)
                throw offline(error)
            }
        }
    }

    /** Kết nối bị reset / huỷ giữa lúc bắt tay (kể cả bọc trong lỗi TLS): máy chủ cắt ngang, không phải mất mạng. */
    private fun isReset(error: Throwable): Boolean =
        generateSequence(error) { it.cause }.take(4).any { cause ->
            cause is java.net.SocketException && cause !is ConnectException &&
                (cause.message.orEmpty().contains("reset", ignoreCase = true) || cause.message.orEmpty().contains("abort", ignoreCase = true))
        }

    private fun offline(cause: Throwable) = VoiceException("Không có mạng để dùng giọng Edge", offline = true, cause = cause)
}
