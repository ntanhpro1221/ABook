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

/**
 * Phiên bản bìa THEO NỘI DUNG - `covers.content_version` (abook/webui/covers.py): 8 byte đầu SHA-256 của JPEG đã chuẩn hoá, chia dư 10^10 (lớp sửa
 * nhận phiên bản tới 10^10). Hai ảnh khác nhau không bao giờ chung địa chỉ `?v=` dù đặt cùng một giây (soát a97 T2).
 */
object CoverVersion {
    private val MODULUS = java.math.BigInteger.TEN.pow(10)

    fun of(jpeg: ByteArray): Long =
        java.math.BigInteger(1, java.security.MessageDigest.getInstance("SHA-256").digest(jpeg).copyOf(8)).mod(MODULUS).toLong()
}

/** Phần của covers.py không cần bộ giải mã ảnh: nhận ảnh từ giao diện gửi lên dạng data URL. */
object Covers {
    const val MAX_UPLOAD_BYTES = 16 * 1024 * 1024
    const val MAX_SIDE = 1400
    const val MIN_SIDE = 64

    /** Trần điểm ảnh sau khi giải mã - `covers.MAX_PIXELS`: ảnh nén nhỏ mà nhiều điểm ảnh (PNG 8000x8000) giải ra hàng trăm MB. */
    const val MAX_PIXELS = 40_000_000L
    private val DATA_URL = Regex("""data:image/(png|jpe?g|webp|gif|bmp);base64,([A-Za-z0-9+/=\s]+)""", RegexOption.IGNORE_CASE)

    /** Số điểm ảnh phải giải mã - `covers.render_cover`: JPEG được giải thẳng ở 1/8, 1/4 hay 1/2 cỡ (PIL `draft`) chừng nào CẢ HAI cạnh còn >= [MAX_SIDE];
     *  định dạng khác giải đủ cỡ. */
    fun decodedPixels(width: Int, height: Int, jpeg: Boolean): Long {
        val scale = if (jpeg) listOf(8, 4, 2).firstOrNull { width / it >= MAX_SIDE && height / it >= MAX_SIDE } ?: 1 else 1
        return (width / scale).toLong() * (height / scale)
    }

    fun tooManyPixels() = CoverCodec.CoverError("Ảnh có quá nhiều điểm ảnh (tối đa ${MAX_PIXELS / 1_000_000} triệu) - bạn thu nhỏ ảnh rồi thử lại")

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
