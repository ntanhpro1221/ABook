package vn.abook.player.readaloud

import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.OutputStream
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Locale

/**
 * Phần giao thức của dịch vụ đọc to của Edge (không đụng mạng, kiểm thử được): theo dự án mã mở edge-tts (rany2/edge-tts, `constants.py`, `drm.py`,
 * `communicate.py`, đọc 03-10, bản Chromium 143). Dịch vụ không chính thức: hằng số dưới đây đổi khi Microsoft đổi (thường là [CHROMIUM_FULL_VERSION] và cách
 * tính Sec-MS-GEC) - hỏng thì giọng Edge báo lỗi và app tự rơi về giọng của máy.
 */
object EdgeProtocol {
    const val TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
    const val CHROMIUM_FULL_VERSION = "143.0.3650.75"
    val CHROMIUM_MAJOR = CHROMIUM_FULL_VERSION.substringBefore('.')
    val SEC_MS_GEC_VERSION = "1-$CHROMIUM_FULL_VERSION"
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
    private const val WIN_EPOCH = 11_644_473_600L

    fun userAgent() = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$CHROMIUM_MAJOR.0.0.0 Safari/537.36 Edg/$CHROMIUM_MAJOR.0.0.0"

    /** Sec-MS-GEC: sha256 (hoa) của "<giờ Windows file time làm tròn xuống 5 phút, đơn vị 100 ns><token>". `unixSeconds` đã cộng độ lệch đồng hồ. */
    fun secMsGec(unixSeconds: Double): String {
        val seconds = Math.floor(unixSeconds).toLong() + WIN_EPOCH
        val ticks = (seconds - seconds % 300) * 10_000_000L
        return MessageDigest.getInstance("SHA-256").digest("$ticks$TRUSTED_CLIENT_TOKEN".toByteArray(Charsets.US_ASCII))
            .joinToString("") { "%02X".format(it) }
    }

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
     * (Azure báo hết hạn mức bằng lý do đóng) - null thì là "đóng trước khi đọc xong". Quá `totalMs` hay mất kết nối: [VoiceException] (offline).
     */
    fun readTurn(
        socket: WebSocket, sink: OutputStream, shiftMs: Long, boundaries: MutableList<Boundary>, label: String, totalMs: Long,
        onClose: (WebSocket.Message.Closed) -> VoiceException? = { null },
        /** Lượt bị cắt giữa chừng (mất kết nối / đóng sớm): Edge biến nó thành lỗi thử lại được; mặc định là "không có mạng". */
        onDrop: (String, Throwable?) -> Exception = { message, cause -> VoiceException(message, offline = true, cause = cause) },
    ): Long {
        val deadline = System.nanoTime() + totalMs * 1_000_000
        var audio = 0L
        while (true) {
            if (System.nanoTime() > deadline) throw VoiceException("$label trả lời quá chậm", offline = true)
            val message = try {
                socket.receive()
            } catch (error: java.net.SocketTimeoutException) {
                throw VoiceException("$label trả lời quá chậm", offline = true, cause = error)
            } catch (error: java.io.IOException) {
                throw onDrop("Mất kết nối với ${label.replaceFirstChar { it.lowercase() }} giữa chừng", error)
            }
            when (message) {
                is WebSocket.Message.Closed -> throw onClose(message) ?: onDrop("$label đóng kết nối trước khi đọc xong", null)
                is WebSocket.Message.Text -> {
                    val head = message.text.substringBefore("\r\n\r\n")
                    when (headers(head)["Path"]) {
                        "audio.metadata" -> boundaries.addAll(parseMetadata(message.text.substringAfter("\r\n\r\n"), shiftMs))
                        "turn.end" -> return audio
                    }
                }
                is WebSocket.Message.Binary -> {
                    val (headers, data) = parseBinary(message.data) ?: throw VoiceException("$label gửi tin hỏng")
                    if (headers["Path"] == "audio" && data.isNotEmpty()) {
                        sink.write(data)
                        audio += data.size
                    }
                }
            }
        }
    }

    /** Độ dài tính từ số byte mp3 (48 kbps không đổi). */
    fun durationMs(bytes: Long): Long = bytes * 1000 / BYTES_PER_SECOND
}

/**
 * Giọng Microsoft qua dịch vụ đọc to của Edge (`vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`): không khoá, cần mạng. Mỗi đoạn một kết nối WebSocket ([WebSocket]);
 * đoạn dài hơn 4000 byte cắt ở dấu cách, mỗi mảnh một kết nối, mốc ghép lại theo số byte mp3 đã nhận. Mọi chặn đều có hạn: nối 8 giây, mỗi lần chờ tin 15
 * giây, cả đoạn 45 giây - quá hạn hay không có mạng là [VoiceException] (người gọi rơi về giọng của máy), không bao giờ chờ mãi.
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
        const val CONNECT_MS = 8_000
        const val READ_MS = 15_000
        const val TOTAL_MS = 45_000L
        /** Lỗi thoáng qua ([Dropped]) thử lại tối đa chừng này lần, mỗi lần một kết nối mới, nghỉ 0,3 s × số lần đã thử (như `edge.py` RETRIES). */
        const val RETRIES = 2
        /** Lệch giữa đồng hồ máy và máy chủ (giây), học từ header `Date` của lần bị từ chối 403; dùng chung cho mọi lần gọi. */
        @Volatile var clockSkewSeconds = 0.0
        private val random = SecureRandom()

        /** Đọc `Date: Sat, 03 Oct 2026 12:00:00 GMT` của máy chủ thành giây Unix; null nếu không đọc được. */
        fun parseHttpDate(value: String?): Double? = try {
            val format = java.text.SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss zzz", Locale.US)
            format.parse(value ?: return null)?.time?.div(1000.0)
        } catch (error: java.text.ParseException) {
            null
        }
    }

    override fun synthesize(text: String, out: File): Clip {
        val boundaries = ArrayList<Boundary>()
        var bytes = 0L
        out.outputStream().use { sink ->
            for ((_, part) in TextChunks.split(text, EdgeProtocol.MAX_TEXT_BYTES, EdgeProtocol::escapedBytes)) {
                val shift = EdgeProtocol.durationMs(bytes) + EdgeProtocol.BOUNDARY_SHIFT_MS
                var attempt = 0
                while (true) {
                    try {
                        val (audio, found) = readPart(part, shift)
                        sink.write(audio)
                        boundaries.addAll(found)
                        bytes += audio.size
                        break
                    } catch (error: Dropped) {
                        // Dịch vụ cắt lượt giữa chừng hay bận lúc bắt tay: thử lại mảnh ấy bằng kết nối mới, không rơi ngay về giọng của máy.
                        if (attempt == RETRIES) throw VoiceException(error.message ?: "Giọng Edge cắt kết nối giữa chừng", cause = error)
                        attempt += 1
                        pause(300L * attempt)
                    }
                }
            }
        }
        if (bytes == 0L) throw VoiceException("Giọng Edge không trả về âm thanh")
        val duration = EdgeProtocol.durationMs(bytes)
        return Clip(out, duration, WordTokens.map(text, boundaries, duration), id)
    }

    /**
     * Lỗi thoáng qua của MỘT lượt (thử lại được): dịch vụ cắt kết nối giữa lượt, hay lúc bắt tay trả HTTP 429 / 5xx hoặc reset kết nối. Khác "không có mạng"
     * (không tìm thấy máy chủ, bị từ chối nối) và khác "bị từ chối / đổi giao thức" - hai thứ ấy ném [VoiceException] ngay.
     */
    private class Dropped(message: String, cause: Throwable? = null) : Exception(message, cause)

    /** Một mảnh chữ: (mp3, mốc đã cộng `shiftMs`). Chỉ trả khi đọc trọn lượt, nên lượt hỏng thử lại không để sót mảnh âm thanh dở. */
    private fun readPart(part: String, shiftMs: Long): Pair<ByteArray, List<Boundary>> {
        val socket = open()
        try {
            val stamp = EdgeProtocol.dateString(System.currentTimeMillis())
            socket.sendText(EdgeProtocol.speechConfig(stamp))
            socket.sendText(EdgeProtocol.ssml(voiceName, EdgeProtocol.escape(part), EdgeProtocol.connectionId(random), stamp))
            val audio = java.io.ByteArrayOutputStream()
            val boundaries = ArrayList<Boundary>()
            EdgeProtocol.readTurn(socket, audio, shiftMs, boundaries, "Giọng Edge", TOTAL_MS, onDrop = { message, cause -> Dropped(message, cause) })
            return audio.toByteArray() to boundaries
        } finally {
            socket.close()
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
                    clockSkewSeconds += server - now
                    retried = true
                    continue
                }
                if (error.status == 429 || error.status >= 500) throw Dropped("Giọng Edge đang bận (HTTP ${error.status})", error)
                throw VoiceException("Dịch vụ giọng Edge từ chối (${error.status}) - có thể đã đổi cách dùng", cause = error)
            } catch (error: UnknownHostException) {
                throw offline(error)
            } catch (error: ConnectException) {
                throw offline(error)
            } catch (error: SocketTimeoutException) {
                throw offline(error)
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
