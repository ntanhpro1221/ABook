package vn.abook.player.net

import androidx.test.core.app.ApplicationProvider
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.StudioError
import vn.abook.player.SyncLink
import vn.abook.player.ui.studio.StudioUpload
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.Base64

/**
 * Gửi file nguồn lên máy tính (soát điện thoại thật 02-11: "Chữ dán.txt" bị từ chối "không phải TXT/EPUB/DOCX/PDF"). Gốc: thân gửi theo kiểu chunked, mà máy tính chỉ đọc
 * thân theo Content-Length - thân chunked thành rỗng, tên file rỗng, lời từ chối đúng của "tên không có đuôi". Máy giả ở đây đọc y như máy tính: đúng Content-Length byte.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class UploadBodyLengthTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    private fun written(folder: String, name: String, bytes: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        StudioUpload.body(folder, name, bytes.size.toLong()) { ByteArrayInputStream(bytes) }.write(out)
        return out.toByteArray()
    }

    @Test fun theDeclaredLengthIsTheWrittenLengthAtEveryEdgeAndForVietnameseNames() {
        for (name in listOf("Chữ dán.txt", "a \"b\".txt", "Chương 1.TXT")) {
            for (size in listOf(1, 2, 3, 4, 49_151, 49_152, 49_153, 100_000)) {
                val bytes = ByteArray(size) { (it * 13 + 5).toByte() }
                assertEquals("$name $size", StudioUpload.length("Tải lên 02-11", name, size.toLong()), written("Tải lên 02-11", name, bytes).size.toLong())
            }
        }
    }

    @Test fun anUnknownSizeIsMeasuredByReadingItAndTooBigIsTooBig() {
        val bytes = ByteArray(1000) { it.toByte() }
        val body = StudioUpload.body("f", "a.txt", 0) { ByteArrayInputStream(bytes) }
        val out = ByteArrayOutputStream()
        body.write(out)
        assertEquals(body.length, out.size().toLong())
        val json = JSONObject(out.toString(Charsets.UTF_8))
        assertTrue(bytes.contentEquals(Base64.getDecoder().decode(json.getString("data"))))
        val tooBig = runCatching { StudioUpload.body("f", "a.txt", -1) { object : java.io.InputStream() { override fun read() = 1 } } }.exceptionOrNull()
        assertTrue("$tooBig", tooBig is StudioError.TooBig)
    }

    @Test fun aFileThatChangesSizeWhileSendingIsRefusedNotSentWithAWrongLength() {
        val shorter = StudioUpload.body("f", "a.txt", 100) { ByteArrayInputStream(ByteArray(60)) }
        assertTrue(runCatching { shorter.write(ByteArrayOutputStream()) }.exceptionOrNull() is IOException)
        val longer = StudioUpload.body("f", "a.txt", 100) { ByteArrayInputStream(ByteArray(140)) }
        assertTrue(runCatching { longer.write(ByteArrayOutputStream()) }.exceptionOrNull() is IOException)
    }

    @Test fun theRealRequestCarriesContentLengthNotChunkedAndTheComputerCanDecodeItsName() {
        val bytes = "Xin chào các bạn.\nChương một.".toByteArray(Charsets.UTF_8)
        var head = ""
        var received = ByteArray(0)
        FakeHost { _, socket, text ->
            head = text
            val length = Regex("""(?i)content-length: *(\d+)""").find(text)?.groupValues?.get(1)?.toInt() ?: 0
            val body = ByteArray(length)
            var done = 0
            while (done < length) {
                val read = socket.getInputStream().read(body, done, length - done)
                if (read < 0) break
                done += read
            }
            received = body.copyOf(done)
            FakeHost.reply(socket, 200, """{"folder":"up:x","path":"up:x/Chữ dán.txt"}""")
        }.use { host ->
            val reply = SyncLink.request(context, "POST", "/api/sources/upload", auth = false, root = host.base, token = "t", connectTimeoutMs = 1000,
                stream = StudioUpload.body("Tải lên", "Chữ dán.txt", bytes.size.toLong()) { ByteArrayInputStream(bytes) })
            assertTrue(reply, reply.contains("up:x/"))
        }
        assertFalse(head, head.contains("chunked", ignoreCase = true))
        assertTrue(head, head.contains("Content-Length", ignoreCase = true))
        val json = JSONObject(String(received, Charsets.UTF_8))
        assertEquals("Chữ dán.txt", json.getString("name"))
        assertTrue(bytes.contentEquals(Base64.getDecoder().decode(json.getString("data"))))
    }
}
