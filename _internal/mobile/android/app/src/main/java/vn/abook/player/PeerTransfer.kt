package vn.abook.player

import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.io.IOException
import java.io.EOFException
import java.net.HttpURLConnection
import java.net.SocketException
import javax.net.ssl.SSLException

/** Cùng ngân sách peer_limits.py; kiểm trước khi ghi từng khối, kể cả stream không có Content-Length. */
internal object PeerTransfer {
    const val JSON_BYTES = 16L * 1024 * 1024
    const val ERROR_BYTES = 64L * 1024
    const val COVER_BYTES = 8L * 1024 * 1024
    const val JOB_BYTES = 64L * 1024 * 1024 * 1024
    const val JOB_FILES = 20000
    const val DISK_MARGIN = 64L * 1024 * 1024

    class Limit : IOException("File vượt giới hạn tải; bạn hãy kiểm tra lại máy gửi sách.")

    /** Chỉ dùng GET; retry trước khi giao stream cho caller, không phát lại POST hoặc stream đã đọc dở. */
    fun openGet(pause: (Long) -> Unit = { Thread.sleep(it) }, connect: () -> HttpURLConnection): HttpURLConnection {
        for (attempt in 0..2) {
            var connection: HttpURLConnection? = null
            try {
                connection = connect()
                check(connection.requestMethod == "GET")
                val code = connection.responseCode
                if (code != 503 || attempt == 2) return connection
            } catch (error: IOException) {
                connection?.disconnect()
                connection = null
                if (attempt == 2 || Pin.isCertificateProblem(error) ||
                    (error !is SocketException && error !is EOFException && error !is SSLException)) throw error
            } catch (error: Exception) {
                connection?.disconnect()
                throw error
            }
            connection?.disconnect()
            pause(if (attempt == 0) 200 else 800)
        }
        error("unreachable")
    }

    fun budget(name: String, expected: Long = 0): Long {
        val lower = name.lowercase()
        val cap = when {
            lower.startsWith("music/") -> 2L * 1024 * 1024 * 1024
            lower.endsWith(".mp3") || lower.endsWith(".m4b") -> 8L * 1024 * 1024 * 1024
            lower.endsWith(".wav") -> 64L * 1024 * 1024
            listOf(".jpg", ".png", ".webp").any(lower::endsWith) -> COVER_BYTES
            else -> JSON_BYTES
        }
        if (expected < 0 || expected > cap) throw Limit()
        return if (expected > 0) expected else cap
    }

    fun copy(input: InputStream, output: OutputStream, limit: Long, dir: File, have: Long = 0, check: () -> Unit = {}): Long {
        var total = have
        if (have > limit) throw Limit()
        val buffer = ByteArray(64 * 1024)
        while (true) {
            check()
            val count = input.read(buffer, 0, minOf(buffer.size.toLong(), limit - total + 1).toInt())
            if (count < 0) return total
            if (count == 0) continue
            if (count > limit - total) throw Limit()
            if (dir.usableSpace < DISK_MARGIN + count) throw IOException("Máy không đủ chỗ trống; bạn hãy dọn bớt rồi tải lại.")
            output.write(buffer, 0, count)
            total += count
        }
    }

    /**
     * Tải một file về `partial`, nối tiếp phần dở khi đúng phiên bản (dùng chung cho sách tải về điện thoại và clip của Studio từ xa). `open(resumeFrom, ifRange)`
     * mở kết nối GET (đã ghim vân tay); `label` đứng trong lời lỗi. Phần dở chỉ được nối khi biết nó thuộc phiên bản nào (ETag cạnh nó) và máy kia xác nhận đúng
     * phiên bản + đúng chỗ ([PartResume]). `keepPartial`: lỗi giữa chừng giữ phần dở để nối lại (mặc định chỉ khi biết cỡ file); khi chưa biết cỡ, cỡ thật lấy từ
     * Content-Range / Content-Length và file thiếu thì ném lỗi (phần dở còn đó). Không đổi tên `partial`: nơi gọi kiểm cuối rồi đổi.
     */
    fun fetchResumable(
        open: (resumeFrom: Long, ifRange: String) -> HttpURLConnection,
        label: String,
        partial: File,
        expectedSize: Long,
        limit: Long,
        dir: File,
        keepPartial: Boolean = expectedSize > 0,
        check: () -> Unit = {},
    ) {
        var (have, tag) = PartResume.point(partial, expectedSize)
        var connection = open(have, tag)
        var code = Pin.guard { connection.responseCode }
        // 416: phần dở dài hơn file hiện có trên máy kia (file đã đổi) - bỏ phần dở như đuôi lạ bên dưới.
        if (code >= 400 && !(code == 416 && have > 0)) {
            connection.disconnect()
            throw IllegalStateException("Chưa tải được $label (mã $code)")
        }
        var answer = if (code == 416) PartResume.Answer.STALE_TAIL
        else PartResume.answer(code, connection.getHeaderField("Content-Range"), connection.getHeaderField("ETag"), have, tag)
        if (have > 0 && answer == PartResume.Answer.STALE_TAIL) {
            // 206 mà ETag lệch (máy kia bỏ qua If-Range): đây là đuôi của file khác. Bỏ phần dở, hỏi lại cả file.
            connection.disconnect()
            PartResume.discard(partial)
            have = 0
            connection = open(0, "")
            code = Pin.guard { connection.responseCode }
            if (code >= 400) {
                connection.disconnect()
                throw IllegalStateException("Chưa tải được $label (mã $code)")
            }
            answer = PartResume.Answer.WHOLE
        }
        val append = answer == PartResume.Answer.RESUME
        try {
            val initial = if (append) have else 0L
            val length = connection.getHeaderFieldLong("Content-Length", -1)
            if (length > limit - initial) throw Limit()
            java.io.FileOutputStream(partial, append).use { output ->
                // Ghi phiên bản SAU khi cắt `.part` (mở không nối): phần cũ không bao giờ mang ETag mới.
                if (!append) PartResume.stamp(partial, connection.getHeaderField("ETag"))
                connection.inputStream.use { input -> copy(input, output, limit, dir, initial, check) }
                output.fd.sync()
            }
            if (expectedSize <= 0 && length >= 0 && partial.length() < initial + length) throw IOException("Tải $label chưa đủ (${partial.length()}/${initial + length} byte)")
        } catch (error: Exception) {
            if (error is Limit || !keepPartial) PartResume.discard(partial)
            throw error
        } finally {
            connection.disconnect()
        }
    }

    fun checkJob(files: List<Pair<String, Long>>) {
        if (files.size > JOB_FILES) throw Limit()
        var remaining = JOB_BYTES
        for ((name, size) in files) {
            val cap = budget(name, size)
            if (cap > remaining) throw Limit()
            remaining -= cap
        }
    }
}
