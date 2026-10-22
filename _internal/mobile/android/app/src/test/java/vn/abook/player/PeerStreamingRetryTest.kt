package vn.abook.player

import android.net.Uri
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.TransferListener
import java.io.EOFException
import org.junit.Assert.*
import org.junit.Test

class PeerStreamingRetryTest {
    // DataSpec cần Uri Android trong constructor; JVM chỉ cần identity + HTTP method để thử open.
    private fun spec(method: Int): DataSpec {
        val type = Class.forName("sun.misc.Unsafe")
        val unsafe = type.getDeclaredField("theUnsafe").apply { isAccessible = true }.get(null)
        val spec = type.getMethod("allocateInstance", Class::class.java).invoke(unsafe, DataSpec::class.java) as DataSpec
        DataSpec::class.java.getField("httpMethod").apply { isAccessible = true }.setInt(spec, method)
        return spec
    }

    private class Source : DataSource {
        var attempts = 0
        var closes = 0
        val seen = mutableListOf<DataSpec>()
        override fun open(dataSpec: DataSpec): Long {
            seen.add(dataSpec)
            if (++attempts <= 2) throw EOFException("closed before audio")
            return 123L
        }
        override fun read(buffer: ByteArray, offset: Int, length: Int) = -1
        override fun getUri(): Uri? = null
        override fun close() { closes++ }
        override fun addTransferListener(transferListener: TransferListener) {}
    }

    @Test fun streaming_get_reopens_same_spec_twice_before_delivering_audio() {
        val source = Source()
        val delays = mutableListOf<Long>()
        val retrying = Streaming.RetryingDataSource(source) { delays.add(it) }
        val request = spec(DataSpec.HTTP_METHOD_GET)
        assertEquals(123L, retrying.open(request))
        assertEquals(listOf(200L, 800L), delays)
        assertEquals(2, source.closes)
        assertTrue(source.seen.all { it === request })
    }

    @Test fun streaming_post_is_not_reopened() {
        val source = Source()
        val retrying = Streaming.RetryingDataSource(source) { fail("POST replayed") }
        assertTrue(runCatching { retrying.open(spec(DataSpec.HTTP_METHOD_POST)) }.exceptionOrNull() is EOFException)
        assertEquals(1, source.attempts)
    }
}
