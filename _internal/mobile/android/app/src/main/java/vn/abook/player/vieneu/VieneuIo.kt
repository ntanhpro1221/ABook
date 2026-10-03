package vn.abook.player.vieneu

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.io.RandomAccessFile
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
