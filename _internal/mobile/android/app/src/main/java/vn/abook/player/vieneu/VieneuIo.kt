package vn.abook.player.vieneu

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.IntBuffer
import java.nio.LongBuffer
import java.nio.channels.FileChannel

/**
 * Raw little-endian arrays (`.f32` / `.i32` / `.f64`) as written by `scripts/vieneu_phone_bench_export.py`: the model's embedding
 * tables and the voice data are shipped this way (numpy's `.npz` would unzip into doubles first, 2x the memory on a phone).
 */
object RawFiles {
    fun floats(file: File): FloatArray = map(file) { it.asFloatBuffer().let { buffer -> FloatArray(buffer.remaining()).also(buffer::get) } }

    fun ints(file: File): IntArray = map(file) { it.asIntBuffer().let { buffer -> IntArray(buffer.remaining()).also(buffer::get) } }

    fun doubles(file: File): DoubleArray = map(file) { it.asDoubleBuffer().let { buffer -> DoubleArray(buffer.remaining()).also(buffer::get) } }

    private fun <T> map(file: File, read: (java.nio.ByteBuffer) -> T): T = RandomAccessFile(file, "r").use { handle ->
        val mapped = handle.channel.map(FileChannel.MapMode.READ_ONLY, 0, handle.length())
        read(mapped.order(ByteOrder.LITTLE_ENDIAN))
    }
}

/**
 * float32 arrays straight out of an UNCOMPRESSED numpy `.npz` (what `np.savez` writes: `vieneu_v3_heads.npz` of Turbo, `constants.npz` of
 * Nano - the pinned upstream files, so the phone downloads exactly what the desktop does). The zip's central directory (zip64 too, numpy
 * forces it) gives each `.npy` member's offset; its data is read in place, never unzipped to a temporary copy.
 */
class NpzFile(private val file: File) {
    class Floats(val shape: IntArray, val data: FloatArray)

    private class Member(val method: Int, val size: Long, val headerOffset: Long)

    private val members: Map<String, Member> = RandomAccessFile(file, "r").use { readDirectory(it) }

    val names: Set<String> get() = members.keys.map { it.removeSuffix(".npy") }.toSet()

    fun floats(name: String): Floats = RandomAccessFile(file, "r").use { handle ->
        val member = members["$name.npy"] ?: throw IllegalArgumentException("${file.name}: không có mảng $name")
        require(member.method == 0) { "${file.name}: mảng $name bị nén (chỉ đọc được npz không nén)" }
        val local = ByteArray(30).also { handle.seek(member.headerOffset); handle.readFully(it) }
        val head = ByteBuffer.wrap(local).order(ByteOrder.LITTLE_ENDIAN)
        require(head.getInt(0) == 0x04034b50) { "${file.name}: đầu mục zip hỏng" }
        val start = member.headerOffset + 30 + (head.getShort(26).toInt() and 0xFFFF) + (head.getShort(28).toInt() and 0xFFFF)
        val probe = ByteArray(minOf(member.size, 4096L).toInt()).also { handle.seek(start); handle.readFully(it) }
        val npy = vn.abook.player.Npz.header(probe, name)
        require(npy.descr == "<f4" && !npy.fortran) { "${file.name}: $name là ${npy.descr}, cần <f4 thứ tự C" }
        val count = npy.shape.fold(1L) { total, dimension -> total * dimension }
        require(npy.dataOffset + count * 4 <= member.size) { "${file.name}: $name cụt" }
        val mapped = handle.channel.map(FileChannel.MapMode.READ_ONLY, start + npy.dataOffset, count * 4).order(ByteOrder.LITTLE_ENDIAN)
        Floats(npy.shape, FloatArray(count.toInt()).also { mapped.asFloatBuffer().get(it) })
    }

    private fun readDirectory(handle: RandomAccessFile): Map<String, Member> {
        val length = handle.length()
        val tailSize = minOf(length, 22L + 65_535L).toInt()
        val tail = ByteArray(tailSize).also { handle.seek(length - tailSize); handle.readFully(it) }
        val buffer = ByteBuffer.wrap(tail).order(ByteOrder.LITTLE_ENDIAN)
        val eocd = (tailSize - 22 downTo 0).firstOrNull { buffer.getInt(it) == 0x06054b50 } ?: throw IllegalArgumentException("${file.name}: không phải file zip")
        var entries = (buffer.getShort(eocd + 10).toInt() and 0xFFFF).toLong()
        var directory = buffer.getInt(eocd + 16).toLong() and 0xFFFFFFFFL
        if (entries == 0xFFFFL || directory == 0xFFFFFFFFL) { // zip64: the locator sits right before the classic record
            val locator = eocd - 20
            require(locator >= 0 && buffer.getInt(locator) == 0x07064b50) { "${file.name}: thiếu bản ghi zip64" }
            val record = ByteArray(56).also { handle.seek(buffer.getLong(locator + 8)); handle.readFully(it) }
            val zip64 = ByteBuffer.wrap(record).order(ByteOrder.LITTLE_ENDIAN)
            require(zip64.getInt(0) == 0x06064b50) { "${file.name}: bản ghi zip64 hỏng" }
            entries = zip64.getLong(32)
            directory = zip64.getLong(48)
        }
        val found = LinkedHashMap<String, Member>()
        var at = directory
        repeat(entries.toInt()) {
            val fixed = ByteArray(46).also { handle.seek(at); handle.readFully(it) }
            val entry = ByteBuffer.wrap(fixed).order(ByteOrder.LITTLE_ENDIAN)
            require(entry.getInt(0) == 0x02014b50) { "${file.name}: mục lục zip hỏng" }
            val nameLength = entry.getShort(28).toInt() and 0xFFFF
            val extraLength = entry.getShort(30).toInt() and 0xFFFF
            val commentLength = entry.getShort(32).toInt() and 0xFFFF
            val rest = ByteArray(nameLength + extraLength).also { handle.readFully(it) }
            var size = entry.getInt(20).toLong() and 0xFFFFFFFFL
            val raw = entry.getInt(24).toLong() and 0xFFFFFFFFL
            var offset = entry.getInt(42).toLong() and 0xFFFFFFFFL
            val extra = ByteBuffer.wrap(rest, nameLength, extraLength).order(ByteOrder.LITTLE_ENDIAN)
            while (extra.remaining() >= 4) {
                val id = extra.short.toInt() and 0xFFFF
                val dataLength = extra.short.toInt() and 0xFFFF
                val next = extra.position() + dataLength
                if (id == 0x0001) { // zip64 sizes / offset, each present only when the 32-bit field is saturated
                    if (raw == 0xFFFFFFFFL) extra.long
                    if (size == 0xFFFFFFFFL) size = extra.long
                    if (offset == 0xFFFFFFFFL) offset = extra.long
                }
                extra.position(next)
            }
            found[String(rest, 0, nameLength, Charsets.UTF_8)] = Member(entry.getShort(10).toInt() and 0xFFFF, size, offset)
            at += 46 + nameLength + extraLength + commentLength
        }
        return found
    }
}

/** Tensors for the ONNX Runtime Java API (heap arrays are copied into native memory by the API). */
internal object Tensors {
    fun floats(env: OrtEnvironment, data: FloatArray, vararg shape: Long): OnnxTensor = OnnxTensor.createTensor(env, FloatBuffer.wrap(data), shape)

    fun longs(env: OrtEnvironment, data: LongArray, vararg shape: Long): OnnxTensor = OnnxTensor.createTensor(env, LongBuffer.wrap(data), shape)

    fun ints(env: OrtEnvironment, data: IntArray, vararg shape: Long): OnnxTensor = OnnxTensor.createTensor(env, IntBuffer.wrap(data), shape)

    fun bools(env: OrtEnvironment, data: Array<BooleanArray>): OnnxTensor = OnnxTensor.createTensor(env, data)

    /** A float tensor of the given shape with a zero-length axis (the empty KV cache of the first acoustic step). */
    fun emptyFloats(env: OrtEnvironment, vararg shape: Long): OnnxTensor = OnnxTensor.createTensor(env, FloatBuffer.allocate(0), shape)

    fun floatData(tensor: OnnxTensor): FloatArray {
        val buffer = tensor.floatBuffer
        return FloatArray(buffer.remaining()).also { buffer.duplicate().get(it) }
    }

    /** Last `width` floats of a `[.., width]` tensor, i.e. the last row of the sequence. */
    fun lastRow(tensor: OnnxTensor, width: Int): FloatArray {
        val buffer = tensor.floatBuffer.duplicate()
        buffer.position(buffer.limit() - width)
        return FloatArray(width).also { buffer.get(it) }
    }
}

/**
 * Which kernels run the graphs. [CPU] is ORT's own (what the desktop uses); [XNNPACK] takes the float ops it supports and runs them on its
 * own pool of `threads` (the session's pool is then one thread, as ORT advises, so the two pools do not fight; ops it does not take, e.g.
 * the dynamically quantised MatMuls of Turbo int8, then run single-threaded); [NNAPI] hands what it can to the phone's driver.
 */
enum class VieneuBackend {
    CPU, XNNPACK, NNAPI;

    companion object {
        fun parse(name: String): VieneuBackend = valueOf(name.trim().uppercase())
    }
}

/** ONNX Runtime session options the VieNeu graphs are run with (same as the desktop engine: no spinning, one inter-op thread). */
internal fun sessionOptions(threads: Int, backend: VieneuBackend = VieneuBackend.CPU, spinning: Boolean = false): OrtSession.SessionOptions =
    OrtSession.SessionOptions().apply {
        setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        setInterOpNumThreads(1)
        setIntraOpNumThreads(if (backend == VieneuBackend.XNNPACK) 1 else threads)
        addConfigEntry("session.intra_op.allow_spinning", if (spinning) "1" else "0")
        when (backend) {
            VieneuBackend.CPU -> Unit
            VieneuBackend.XNNPACK -> addXnnpack(mapOf("intra_op_num_threads" to threads.toString()))
            VieneuBackend.NNAPI -> addNnapi()
        }
    }

/** Run [block] and add its wall time to [clock]. */
internal inline fun <T> timed(clock: LongArray, slot: Int, block: () -> T): T {
    val started = System.nanoTime()
    try {
        return block()
    } finally {
        clock[slot] += System.nanoTime() - started
    }
}
