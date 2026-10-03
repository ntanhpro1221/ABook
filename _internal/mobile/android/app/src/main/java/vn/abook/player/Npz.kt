package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.ZipInputStream

/**
 * Đọc file `.npz` của numpy (zip của các file `.npy`): chỉ phần đầu trò nhạc cần (docs/MUSIC_IMPORT.md) - mảng số `<f4` / `<f8`
 * (hay số nguyên `<i4` / `<i8`) và mảng chữ `<U` theo thứ tự C. Kiểu nào khác, hay thứ tự Fortran, thì từ chối kèm lý do: đầu trò
 * hỏng không được đọc bừa thành số.
 */
class NpyArray(val shape: IntArray, val numbers: DoubleArray?, val strings: List<String>?) {
    val size: Int get() = shape.fold(1) { total, dimension -> total * dimension }

    fun doubles(): DoubleArray = numbers ?: throw IllegalArgumentException("mảng này không phải số")

    fun texts(): List<String> = strings ?: throw IllegalArgumentException("mảng này không phải chữ")
}

object Npz {
    private val MAGIC = byteArrayOf(0x93.toByte(), 'N'.code.toByte(), 'U'.code.toByte(), 'M'.code.toByte(), 'P'.code.toByte(), 'Y'.code.toByte())
    private val DESCR = Regex("'descr'\\s*:\\s*'([^']+)'")
    private val FORTRAN = Regex("'fortran_order'\\s*:\\s*(True|False)")
    private val SHAPE = Regex("'shape'\\s*:\\s*\\(([^)]*)\\)")

    /** Tên mảng (không có `.npy`) -> mảng. */
    fun read(file: File): Map<String, NpyArray> = file.inputStream().buffered().use { read(it) }

    fun read(stream: InputStream): Map<String, NpyArray> {
        val found = LinkedHashMap<String, NpyArray>()
        ZipInputStream(stream).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                if (entry.isDirectory || !entry.name.endsWith(".npy")) continue
                val bytes = ByteArrayOutputStream().also { zip.copyTo(it) }.toByteArray()
                found[entry.name.removeSuffix(".npy")] = parse(bytes, entry.name)
            }
        }
        return found
    }

    fun parse(bytes: ByteArray, name: String = "npy"): NpyArray {
        fun bad(why: String): Nothing = throw IllegalArgumentException("$name: $why")
        if (bytes.size < 10 || !bytes.copyOfRange(0, 6).contentEquals(MAGIC)) bad("không phải file .npy")
        val major = bytes[6].toInt()
        val headerLength: Int
        val headerStart: Int
        when (major) {
            1 -> {
                headerLength = (bytes[8].toInt() and 0xFF) or ((bytes[9].toInt() and 0xFF) shl 8)
                headerStart = 10
            }
            2, 3 -> {
                headerLength = ByteBuffer.wrap(bytes, 8, 4).order(ByteOrder.LITTLE_ENDIAN).int
                headerStart = 12
            }
            else -> bad("phiên bản .npy $major chưa hỗ trợ")
        }
        if (headerLength < 0 || headerStart + headerLength > bytes.size) bad("đầu file hỏng")
        val header = String(bytes, headerStart, headerLength, if (major == 3) Charsets.UTF_8 else Charsets.ISO_8859_1)
        val descr = DESCR.find(header)?.groupValues?.get(1) ?: bad("thiếu kiểu số")
        if (FORTRAN.find(header)?.groupValues?.get(1) != "False") bad("chỉ đọc được thứ tự C")
        val dimensions = SHAPE.find(header)?.groupValues?.get(1)?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() }?.map { it.toInt() }
            ?: bad("thiếu hình dạng")
        val shape = dimensions.toIntArray()
        val count = shape.fold(1L) { total, dimension -> total * dimension }
        if (count > Int.MAX_VALUE) bad("mảng quá lớn")
        val data = ByteBuffer.wrap(bytes, headerStart + headerLength, bytes.size - headerStart - headerLength).order(ByteOrder.LITTLE_ENDIAN)
        val numbers = when (descr) {
            "<f4" -> 4
            "<f8" -> 8
            "<i4" -> 4
            "<i8" -> 8
            else -> 0
        }
        if (numbers > 0) {
            if (data.remaining() < count * numbers) bad("thiếu dữ liệu")
            val out = DoubleArray(count.toInt()) {
                when (descr) {
                    "<f4" -> data.float.toDouble()
                    "<f8" -> data.double
                    "<i4" -> data.int.toDouble()
                    else -> data.long.toDouble()
                }
            }
            return NpyArray(shape, out, null)
        }
        if (descr.startsWith("<U")) {
            val width = descr.substring(2).toIntOrNull() ?: bad("kiểu $descr lạ")
            if (data.remaining().toLong() < count * width * 4) bad("thiếu dữ liệu")
            val strings = List(count.toInt()) {
                val builder = StringBuilder()
                var ended = false
                repeat(width) {
                    val point = data.int
                    if (point == 0) ended = true else if (!ended) builder.appendCodePoint(point)
                }
                builder.toString()
            }
            return NpyArray(shape, null, strings)
        }
        bad("kiểu $descr chưa hỗ trợ")
    }
}
