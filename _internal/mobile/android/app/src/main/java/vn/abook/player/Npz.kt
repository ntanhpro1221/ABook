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

    fun doubles(): DoubleArray = numbers ?: throw IllegalArgumentException(S.s_mang_nay_khong_phai_so_48d2cabf)

    fun texts(): List<String> = strings ?: throw IllegalArgumentException(S.s_mang_nay_khong_phai_chu_1b06838a)
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

    /** Đầu một file `.npy`: kiểu số (`descr`), thứ tự Fortran hay không, hình dạng, và vị trí byte đầu tiên của dữ liệu. */
    class Header(val descr: String, val fortran: Boolean, val shape: IntArray, val dataOffset: Int)

    /** Đọc đầu `.npy` từ [bytes] (chỉ cần phần đầu file); đầu hỏng thì ném lỗi kèm lý do. */
    fun header(bytes: ByteArray, name: String = "npy"): Header {
        fun bad(why: String): Nothing = throw IllegalArgumentException("$name: $why")
        if (bytes.size < 10 || !bytes.copyOfRange(0, 6).contentEquals(MAGIC)) bad(S.s_khong_phai_file_npy_92e72f32)
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
            else -> bad(S.s_phien_ban_npy_0_chua_ho_tro_782d5112(major))
        }
        if (headerLength < 0 || headerStart + headerLength > bytes.size) bad(S.s_dau_file_hong_9ffba96b)
        val header = String(bytes, headerStart, headerLength, if (major == 3) Charsets.UTF_8 else Charsets.ISO_8859_1)
        val descr = DESCR.find(header)?.groupValues?.get(1) ?: bad(S.s_thieu_kieu_so_03af5124)
        val fortran = FORTRAN.find(header)?.groupValues?.get(1) != "False"
        val dimensions = SHAPE.find(header)?.groupValues?.get(1)?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() }?.map { it.toInt() }
            ?: bad(S.s_thieu_hinh_dang_58758a2f)
        return Header(descr, fortran, dimensions.toIntArray(), headerStart + headerLength)
    }

    fun parse(bytes: ByteArray, name: String = "npy"): NpyArray {
        fun bad(why: String): Nothing = throw IllegalArgumentException("$name: $why")
        val head = header(bytes, name)
        if (head.fortran) bad(S.s_chi_doc_duoc_thu_tu_c_087035f9)
        val descr = head.descr
        val shape = head.shape
        val count = shape.fold(1L) { total, dimension -> total * dimension }
        if (count > Int.MAX_VALUE) bad(S.s_mang_qua_lon_2d0bc2cb)
        val data = ByteBuffer.wrap(bytes, head.dataOffset, bytes.size - head.dataOffset).order(ByteOrder.LITTLE_ENDIAN)
        val numbers = when (descr) {
            "<f4" -> 4
            "<f8" -> 8
            "<i4" -> 4
            "<i8" -> 8
            else -> 0
        }
        if (numbers > 0) {
            if (data.remaining() < count * numbers) bad(S.s_thieu_du_lieu_d2b05c2e)
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
            val width = descr.substring(2).toIntOrNull() ?: bad(S.s_kieu_0_la_a9618525(descr))
            if (data.remaining().toLong() < count * width * 4) bad(S.s_thieu_du_lieu_d2b05c2e)
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
        bad(S.s_kieu_0_chua_ho_tro_477e655f(descr))
    }
}
