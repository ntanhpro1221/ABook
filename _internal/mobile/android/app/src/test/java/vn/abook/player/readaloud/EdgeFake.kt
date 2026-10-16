package vn.abook.player.readaloud

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Khung tin của máy chủ Edge giả cho bài thử clip phát luồng (cùng dạng với EdgePiecesTest, dùng chung cho các bài thử mới). */
object EdgeFake {
    fun frame(opcode: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(0x80 or opcode)
        if (payload.size < 126) out.write(payload.size) else { out.write(126); out.write(payload.size ushr 8); out.write(payload.size and 0xFF) }
        out.write(payload)
        return out.toByteArray()
    }

    fun text(path: String, body: String = "") = frame(WebSocket.OP_TEXT, "X-RequestId:r\r\nPath:$path\r\n\r\n$body".toByteArray())

    fun audioOf(data: ByteArray): ByteArray {
        val header = "X-RequestId:r\r\nContent-Type:audio/mpeg\r\nPath:audio\r\n".toByteArray()
        return frame(WebSocket.OP_BINARY, byteArrayOf((header.size ushr 8).toByte(), header.size.toByte()) + header + data)
    }

    fun metadata(offset: Long, duration: Long, word: String) =
        text("audio.metadata", """{"Metadata":[{"Type":"WordBoundary","Data":{"Offset":$offset,"Duration":$duration,"text":{"Text":"$word","Length":${word.length},"BoundaryType":"WordBoundary"}}}]}""")

    /** `count` khung mp3 hợp lệ (MPEG-2 lớp III, 48 kbps, 24 kHz, đơn kênh, 144 byte); byte 4-5 ghi số thứ tự khung, byte 6 là `tag`. */
    fun mp3Frames(count: Int, tag: Int = 0): ByteArray {
        val out = ByteArrayOutputStream()
        for (index in 0 until count) {
            val frame = ByteArray(EdgeJoin.FRAME_BYTES)
            frame[0] = 0xFF.toByte(); frame[1] = 0xF3.toByte(); frame[2] = 0x64; frame[3] = 0xC0.toByte()
            frame[4] = (index ushr 8).toByte(); frame[5] = index.toByte(); frame[6] = tag.toByte()
            out.write(frame)
        }
        return out.toByteArray()
    }

    /** Chữ trong khung SSML mà máy khách đã gửi vào `sent`. */
    fun spokenIn(sent: ByteArray): String {
        val input = ByteArrayInputStream(sent)
        WebSocket.decode(input) // speech.config
        val ssml = String(WebSocket.decode(input).payload)
        return ssml.substringAfter("volume='+0%'>").substringBefore("</prosody>")
    }

    /** Câu trả lời của một lượt: `head` tới trước, rồi (sau `gate` nếu có) `tail`; `cut`: sau `head` là lỗi mạng thay vì `tail`. */
    class Answer(val head: ByteArray, val tail: ByteArray, val gate: CountDownLatch? = null, val cut: Boolean = false)

    /** Luồng trả lời dựng khi máy khách đọc lần đầu (lúc ấy chữ đã gửi xong): `build(chữ đã gửi)`. Có `gate` thì giữa `head` và `tail` luồng đứng chờ tới khi `gate` mở (tối đa 10 giây) - như Edge gửi dần. */
    class Reply(val sent: ByteArrayOutputStream, val build: (String) -> Answer) : InputStream() {
        private var stage = 0
        private val answer by lazy { build(spokenIn(sent.toByteArray())) }
        private var current: ByteArrayInputStream? = null

        override fun read(): Int = throw UnsupportedOperationException()

        override fun read(b: ByteArray, off: Int, len: Int): Int {
            val now = current ?: ByteArrayInputStream(answer.head).also { current = it }
            val n = now.read(b, off, len)
            if (n >= 0) return n
            if (stage > 0) return -1
            stage = 1
            answer.gate?.await(10, TimeUnit.SECONDS)
            if (answer.cut) throw java.io.IOException("cắt giữa lượt")
            current = ByteArrayInputStream(answer.tail)
            return current!!.read(b, off, len)
        }
    }
}
