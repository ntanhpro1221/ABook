package vn.abook.player

import android.app.Instrumentation
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Phần dùng chung của [MusicLoopSeamTest] và [MusicBedSeamOnDeviceTest] (androidTest). */
@OptIn(UnstableApi::class)
internal object SeamTestSupport {
    /** Giải mã liền cả file ra PCM16 thô (trục R của §41); trả định dạng. */
    fun decodeToFile(file: File, out: File): LoopSeam.Decoded {
        FileOutputStream(out).use { stream ->
            var scratch = ByteArray(1 shl 16)
            return LoopSeam.decode(file) { _, pcm ->
                if (scratch.size < pcm.remaining()) scratch = ByteArray(pcm.remaining())
                val n = pcm.remaining()
                pcm.get(scratch, 0, n)
                stream.write(scratch, 0, n)
            }
        }
    }

    fun shortsOf(bytes: ByteArray, skip: Int): ShortArray {
        val view = ByteBuffer.wrap(bytes, skip, bytes.size - skip).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        return ShortArray(view.remaining()).also { view.get(it) }
    }

    /** Chạy `block` ở luồng chính, ném lại lỗi của nó ở luồng gọi. */
    fun <T> onMain(instrumentation: Instrumentation, block: () -> T): T {
        var result: Any? = null
        var error: Throwable? = null
        instrumentation.runOnMainSync {
            try {
                result = block()
            } catch (t: Throwable) {
                error = t
            }
        }
        error?.let { throw it }
        @Suppress("UNCHECKED_CAST")
        return result as T
    }
}
