package vn.abook.player

/**
 * Chuẩn hoá một ảnh bìa người nghe chọn - phần của `covers.render_cover` (abook/webui/covers.py) cần đến bộ giải mã ảnh của máy:
 * ra JPEG đã xoay theo EXIF, bỏ kênh trong suốt (đặt lên nền trắng), cạnh dài tối đa 1400, chất lượng 88, cùng màu chủ đạo
 * và cỡ. Tách thành giao diện để test JVM (không có Bitmap) thay bằng bản giả; máy thật dùng [AndroidCoverCodec].
 */
interface CoverCodec {
    class Normalized(val jpeg: ByteArray, val color: String, val width: Int, val height: Int)

    /** Ảnh không dùng được làm bìa - câu chữ để người dùng đọc (cùng câu với `covers.CoverError`). */
    class CoverError(message: String) : Exception(message)

    fun normalize(raw: ByteArray): Normalized
}

/** Phần của covers.py không cần bộ giải mã ảnh: nhận ảnh từ giao diện gửi lên dạng data URL. */
object Covers {
    const val MAX_UPLOAD_BYTES = 16 * 1024 * 1024
    const val MAX_SIDE = 1400
    const val MIN_SIDE = 64
    private val DATA_URL = Regex("""data:image/(png|jpe?g|webp|gif|bmp);base64,([A-Za-z0-9+/=\s]+)""", RegexOption.IGNORE_CASE)

    fun tooLarge() = CoverCodec.CoverError("Ảnh quá lớn (tối đa ${MAX_UPLOAD_BYTES / (1 shl 20)} MB)")

    /** Byte của ảnh trong một data URL (PNG, JPEG, WebP, GIF, BMP) - `covers._decode`; lỗi thì [CoverCodec.CoverError]. */
    fun decodeDataUrl(dataUrl: String): ByteArray {
        val match = DATA_URL.matchEntire(dataUrl.trim { it.isWhitespace() || Character.isSpaceChar(it) })
            ?: throw CoverCodec.CoverError("Chỉ nhận ảnh PNG, JPEG, WebP, GIF hoặc BMP")
        val raw = base64(match.groupValues[2].filterNot { it.isWhitespace() || Character.isSpaceChar(it) })
            ?: throw CoverCodec.CoverError("Dữ liệu ảnh bị hỏng")
        if (raw.size > MAX_UPLOAD_BYTES) throw tooLarge()
        return raw
    }

    /** Base64 chặt như `b64decode(validate=True)`: đúng bảng chữ, độ dài chia hết cho 4, `=` chỉ ở cuối; sai thì null. */
    fun base64(text: String): ByteArray? {
        if (text.length % 4 != 0) return null
        val padding = text.takeLastWhile { it == '=' }.length
        if (padding > 2 || text.dropLast(padding).contains('=')) return null
        val out = java.io.ByteArrayOutputStream(text.length / 4 * 3)
        var buffer = 0
        var bits = 0
        for (char in text.dropLast(padding)) {
            val value = when (char) {
                in 'A'..'Z' -> char - 'A'
                in 'a'..'z' -> char - 'a' + 26
                in '0'..'9' -> char - '0' + 52
                '+' -> 62
                '/' -> 63
                else -> return null
            }
            buffer = (buffer shl 6) or value
            bits += 6
            if (bits >= 8) {
                bits -= 8
                out.write((buffer shr bits) and 0xff)
            }
        }
        return out.toByteArray()
    }
}
