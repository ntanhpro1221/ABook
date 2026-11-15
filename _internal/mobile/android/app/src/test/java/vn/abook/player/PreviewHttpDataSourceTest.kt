package vn.abook.player

import android.net.Uri
import androidx.media3.common.C
import androidx.media3.datasource.DataSpec
import java.io.ByteArrayInputStream
import java.io.EOFException
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PreviewHttpDataSourceTest {
    private class Response(val status: Int, val body: String, val length: String? = body.length.toString()) : HttpURLConnection(URL("https://catalog.example/music.mp3")) {
        var disconnected = false
        override fun connect() = Unit
        override fun disconnect() { disconnected = true }
        override fun usingProxy() = false
        override fun getResponseCode() = status
        override fun getInputStream() = ByteArrayInputStream(body.toByteArray())
        override fun getHeaderField(name: String): String? = if (name.equals("Content-Length", true)) length else null
    }
    private fun spec(position: Long = 0, length: Long = C.LENGTH_UNSET.toLong()) =
        DataSpec.Builder().setUri(Uri.parse("https://catalog.example/music.mp3")).setPosition(position).setLength(length).build()
    private fun read(source: PreviewHttpDataSource): String {
        val buffer = ByteArray(64)
        val count = source.read(buffer, 0, buffer.size)
        return if (count < 0) "" else String(buffer, 0, count)
    }

    @Test fun rangedResponseRetainsTheHostnameAndPassesRangeHeaders() {
        val response = Response(206, "def")
        var headers: Map<String, String> = emptyMap()
        val source = PreviewHttpDataSource { url, sent -> assertEquals("https://catalog.example/music.mp3", url); headers = sent; response }
        assertEquals(3L, source.open(spec(3, 3)))
        assertEquals("bytes=3-5", headers["Range"])
        assertEquals("identity", headers["Accept-Encoding"])
        assertEquals("def", read(source))
        assertEquals("", read(source))
        source.close()
        assertTrue(response.disconnected)
    }

    @Test fun aServerIgnoringRangeIsSkippedWithoutChangingTheRequestedLength() {
        val source = PreviewHttpDataSource { _, _ -> Response(200, "abcdef") }
        assertEquals(2L, source.open(spec(2, 2)))
        assertEquals("cd", read(source))
        assertEquals("", read(source))
        source.close()
    }

    @Test fun anUnknownLengthReadsUntilEof() {
        val source = PreviewHttpDataSource { _, _ -> Response(200, "abc", null) }
        assertEquals(C.LENGTH_UNSET.toLong(), source.open(spec()))
        assertEquals("abc", read(source))
        assertEquals("", read(source))
        source.close()
    }

    @Test fun aRejectedStatusClosesTheConnectionAndTheSourceCanReopen() {
        val response = Response(503, "busy")
        var calls = 0
        val source = PreviewHttpDataSource { _, _ -> if (calls++ == 0) response else Response(200, "ok") }
        assertThrows(IOException::class.java) { source.open(spec()) }
        assertTrue(response.disconnected)
        assertEquals(2L, source.open(spec()))
        assertEquals("ok", read(source))
        source.close()
    }

    @Test fun aTruncatedRangedBodyFailsInsteadOfPretendingTheTrackEnded() {
        val source = PreviewHttpDataSource { _, _ -> Response(206, "ab", "3") }
        source.open(spec(3, 3))
        assertEquals("ab", read(source))
        assertThrows(EOFException::class.java) { read(source) }
        source.close()
    }
}
