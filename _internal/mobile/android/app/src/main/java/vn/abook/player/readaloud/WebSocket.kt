package vn.abook.player.readaloud

import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URI
import java.security.MessageDigest
import java.security.SecureRandom
import javax.net.ssl.SSLSocketFactory

/** Máy chủ không đồng ý nâng lên WebSocket (Edge trả 403 khi đồng hồ máy lệch: `headers["date"]` cho biết giờ máy chủ). */
class HandshakeException(val status: Int, val headers: Map<String, String>) : IOException("máy chủ trả $status khi bắt tay WebSocket")

/**
 * Máy khách WebSocket (RFC 6455) tối thiểu trên SSLSocket, đủ cho dịch vụ đọc to của Edge: bắt tay, khung chữ + nhị phân (có ghép mảnh), ping/pong, đóng.
 * Không thêm thư viện nào vào APK (OkHttp không có sẵn trên đường dẫn lớp). Không nén (không xin `permessage-deflate`). Một luồng dùng một kết nối.
 */
class WebSocket internal constructor(private val socket: java.io.Closeable, private val input: InputStream, private val output: OutputStream) : AutoCloseable {
    sealed class Message {
        class Text(val text: String) : Message()
        class Binary(val data: ByteArray) : Message()
        /** Máy chủ đóng: mã + lý do của khung CLOSE (1005 / "" khi không có) - Azure báo hết hạn mức bằng lý do đóng. */
        class Closed(val code: Int = 1005, val reason: String = "") : Message()
    }

    class Frame(val fin: Boolean, val opcode: Int, val payload: ByteArray)

    companion object {
        const val OP_CONTINUATION = 0
        const val OP_TEXT = 1
        const val OP_BINARY = 2
        const val OP_CLOSE = 8
        const val OP_PING = 9
        const val OP_PONG = 10
        private const val GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        /** Khung lớn nhất nhận vào (một đoạn mp3 vài chục KB; chặn máy chủ gửi vô hạn). */
        const val MAX_PAYLOAD = 8L * 1024 * 1024
        private val random = SecureRandom()

        /** `Sec-WebSocket-Accept` mà máy chủ phải trả cho `key`. */
        fun acceptFor(key: String): String =
            base64(MessageDigest.getInstance("SHA-1").digest((key + GUID).toByteArray(Charsets.US_ASCII)))

        private const val B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

        /** Base64 chuẩn có đệm `=` (java.util.Base64 cần API 26, app hỗ trợ từ 24; android.util.Base64 không chạy được trong bài thử JVM). */
        fun base64(bytes: ByteArray): String {
            val out = StringBuilder((bytes.size + 2) / 3 * 4)
            var i = 0
            while (i < bytes.size) {
                val n = ((bytes[i].toInt() and 0xFF) shl 16) or ((bytes.getOrElse(i + 1) { 0 }.toInt() and 0xFF) shl 8) or (bytes.getOrElse(i + 2) { 0 }.toInt() and 0xFF)
                out.append(B64[(n shr 18) and 63]).append(B64[(n shr 12) and 63])
                out.append(if (i + 1 < bytes.size) B64[(n shr 6) and 63] else '=').append(if (i + 2 < bytes.size) B64[n and 63] else '=')
                i += 3
            }
            return out.toString()
        }

        /** Ngược của [base64] (bỏ qua khoảng trắng / xuống dòng); ký tự lạ -> IllegalArgumentException. Google trả audio dạng base64 (GoogleTts.kt). */
        fun unbase64(text: String): ByteArray {
            val out = java.io.ByteArrayOutputStream(text.length * 3 / 4)
            var buffer = 0
            var bits = 0
            for (c in text) {
                if (c == '=' || c.isWhitespace()) continue
                val value = B64.indexOf(c)
                require(value >= 0) { "base64 hỏng" }
                buffer = (buffer shl 6) or value
                bits += 6
                if (bits >= 8) {
                    bits -= 8
                    out.write((buffer shr bits) and 0xFF)
                }
            }
            return out.toByteArray()
        }

        /** Khung của MÁY KHÁCH: luôn có mặt nạ (RFC 6455 mục 5.3). `mask` 4 byte (kiểm thử đưa số cố định; chạy thật là ngẫu nhiên). */
        fun encode(opcode: Int, payload: ByteArray, mask: ByteArray = ByteArray(4).also(random::nextBytes), fin: Boolean = true): ByteArray {
            require(mask.size == 4)
            val out = ByteArrayOutputStream(payload.size + 14)
            out.write((if (fin) 0x80 else 0) or opcode)
            when {
                payload.size < 126 -> out.write(0x80 or payload.size)
                payload.size <= 0xFFFF -> {
                    out.write(0x80 or 126)
                    out.write(payload.size ushr 8)
                    out.write(payload.size and 0xFF)
                }
                else -> {
                    out.write(0x80 or 127)
                    for (shift in 56 downTo 0 step 8) out.write(((payload.size.toLong() ushr shift) and 0xFF).toInt())
                }
            }
            out.write(mask)
            for (i in payload.indices) out.write(payload[i].toInt() xor mask[i and 3].toInt())
            return out.toByteArray()
        }

        /** Đọc một khung (khung của máy chủ không có mặt nạ, nhưng nếu có thì gỡ). Hết luồng giữa chừng: EOFException. */
        fun decode(input: InputStream): Frame {
            val head = readFully(input, 2)
            val fin = head[0].toInt() and 0x80 != 0
            val opcode = head[0].toInt() and 0x0F
            val masked = head[1].toInt() and 0x80 != 0
            var length = (head[1].toInt() and 0x7F).toLong()
            if (length == 126L) {
                val b = readFully(input, 2)
                length = ((b[0].toInt() and 0xFF) shl 8 or (b[1].toInt() and 0xFF)).toLong()
            } else if (length == 127L) {
                val b = readFully(input, 8)
                length = 0
                for (byte in b) length = (length shl 8) or (byte.toLong() and 0xFF)
            }
            if (length < 0 || length > MAX_PAYLOAD) throw IOException("khung WebSocket quá lớn: $length")
            val mask = if (masked) readFully(input, 4) else null
            val payload = readFully(input, length.toInt())
            if (mask != null) for (i in payload.indices) payload[i] = (payload[i].toInt() xor mask[i and 3].toInt()).toByte()
            return Frame(fin, opcode, payload)
        }

        private fun readFully(input: InputStream, count: Int): ByteArray {
            val data = ByteArray(count)
            var read = 0
            while (read < count) {
                val n = input.read(data, read, count - read)
                if (n < 0) throw EOFException("kết nối đóng giữa chừng")
                read += n
            }
            return data
        }

        /** Dòng trạng thái + header (tên viết thường) của câu trả lời bắt tay, đọc tới dòng trống. */
        fun readHead(input: InputStream): Pair<Int, Map<String, String>> {
            val text = StringBuilder()
            while (!text.endsWith("\r\n\r\n")) {
                val b = input.read()
                if (b < 0) throw EOFException("máy chủ đóng kết nối khi bắt tay")
                text.append(b.toChar())
                if (text.length > 16 * 1024) throw IOException("câu trả lời bắt tay quá dài")
            }
            val lines = text.toString().split("\r\n")
            val status = lines[0].split(" ").getOrNull(1)?.toIntOrNull() ?: throw IOException("dòng trạng thái lạ: ${lines[0]}")
            val headers = lines.drop(1).filter { it.contains(':') }.associate { it.substringBefore(':').trim().lowercase() to it.substringAfter(':').trim() }
            return status to headers
        }

        /**
         * Mở `wss://...` với các header cho trước. `connectTimeoutMs` cho nối TCP + TLS + bắt tay; `readTimeoutMs` cho mỗi lần chờ dữ liệu về sau đó
         * (hết hạn: SocketTimeoutException - người gọi không bao giờ chờ mãi).
         */
        fun connect(url: String, headers: Map<String, String>, connectTimeoutMs: Int, readTimeoutMs: Int): WebSocket {
            val uri = URI(url)
            require(uri.scheme == "wss") { "chỉ hỗ trợ wss://" }
            val port = if (uri.port > 0) uri.port else 443
            val socket = Socket()
            try {
                socket.connect(InetSocketAddress(uri.host, port), connectTimeoutMs)
                socket.soTimeout = connectTimeoutMs
                val tls = (SSLSocketFactory.getDefault() as SSLSocketFactory).createSocket(socket, uri.host, port, true) as javax.net.ssl.SSLSocket
                tls.useClientMode = true
                tls.startHandshake()
                // Kiểm tên máy trong chứng chỉ (SSLSocket không tự kiểm khi không dùng HttpsURLConnection).
                val verifier = javax.net.ssl.HttpsURLConnection.getDefaultHostnameVerifier()
                if (!verifier.verify(uri.host, tls.session)) throw javax.net.ssl.SSLPeerUnverifiedException("chứng chỉ không khớp ${uri.host}")
                val keyBytes = ByteArray(16).also(random::nextBytes)
                val key = base64(keyBytes)
                val path = (uri.rawPath.ifEmpty { "/" }) + (uri.rawQuery?.let { "?$it" } ?: "")
                val request = StringBuilder("GET $path HTTP/1.1\r\nHost: ${uri.host}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Key: $key\r\n")
                headers.forEach { (name, value) -> request.append(name).append(": ").append(value).append("\r\n") }
                request.append("\r\n")
                tls.outputStream.write(request.toString().toByteArray(Charsets.US_ASCII))
                tls.outputStream.flush()
                val (status, answer) = readHead(tls.inputStream)
                if (status != 101) throw HandshakeException(status, answer)
                if (answer["sec-websocket-accept"] != acceptFor(key)) throw IOException("máy chủ trả Sec-WebSocket-Accept sai")
                tls.soTimeout = readTimeoutMs
                return WebSocket(tls, tls.inputStream, tls.outputStream)
            } catch (error: Throwable) {
                runCatching { socket.close() }
                throw error
            }
        }
    }

    private var closed = false

    @Synchronized
    private fun send(opcode: Int, payload: ByteArray) {
        output.write(encode(opcode, payload))
        output.flush()
    }

    fun sendText(text: String) = send(OP_TEXT, text.toByteArray(Charsets.UTF_8))

    /** Tin kế tiếp (đã ghép mảnh). Ping được trả lời pong ngay; đóng thì trả [Message.Closed]. */
    fun receive(): Message {
        var kind = -1
        val buffer = ByteArrayOutputStream()
        while (true) {
            val frame = decode(input)
            when (frame.opcode) {
                OP_PING -> send(OP_PONG, frame.payload)
                OP_PONG -> Unit
                OP_CLOSE -> {
                    runCatching { send(OP_CLOSE, frame.payload.take(2).toByteArray()) }
                    closed = true
                    val payload = frame.payload
                    val code = if (payload.size >= 2) ((payload[0].toInt() and 0xFF) shl 8) or (payload[1].toInt() and 0xFF) else 1005
                    val reason = if (payload.size > 2) String(payload, 2, payload.size - 2, Charsets.UTF_8) else ""
                    return Message.Closed(code, reason)
                }
                OP_TEXT, OP_BINARY, OP_CONTINUATION -> {
                    if (frame.opcode != OP_CONTINUATION) {
                        kind = frame.opcode
                        buffer.reset()
                    } else if (kind < 0) throw IOException("khung nối tiếp không có khung đầu")
                    buffer.write(frame.payload)
                    if (buffer.size() > MAX_PAYLOAD) throw IOException("tin WebSocket quá lớn")
                    if (frame.fin) {
                        return if (kind == OP_TEXT) Message.Text(String(buffer.toByteArray(), Charsets.UTF_8)) else Message.Binary(buffer.toByteArray())
                    }
                }
                else -> throw IOException("opcode lạ: ${frame.opcode}")
            }
        }
    }

    override fun close() {
        if (!closed) {
            closed = true
            runCatching { send(OP_CLOSE, byteArrayOf(0x03, 0xE8.toByte())) }
        }
        runCatching { socket.close() }
    }
}
