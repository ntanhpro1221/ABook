package vn.abook.player

import java.io.File
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import javax.net.ssl.SSLException
import javax.net.ssl.SSLHandshakeException
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Soát a68 (hai máy): lỗi mạng thành câu theo loại (lỗi 4, 5), tên điện thoại dễ đọc (16), chỗ trống trước khi tải (10), chỗ nghe chờ đẩy khi mất
 * kết nối (9), chỗ nghe vượt độ dài chương không được lưu (2), giọng riêng của cuốn đi theo hồ sơ nghe (8).
 */
class TwoDevicesTest {
    @Test
    fun `loi mang thanh cau theo loai, 401 la da thoi ghep`() {
        assertEquals(NetErrors.Kind.UNREACHABLE, NetErrors.kind(ConnectException("Failed to connect to /10.0.2.2:47679")))
        assertEquals(NetErrors.Kind.TIMEOUT, NetErrors.kind(IOException("wrapped", SocketTimeoutException("timeout"))))
        assertEquals(NetErrors.Kind.SECURITY, NetErrors.kind(SSLHandshakeException("Unable to parse TLS packet header")))
        // Android báo kết nối TLS bị cắt ngang bằng SSLException: đứt mạng, không phải lỗi bảo mật.
        assertEquals(NetErrors.Kind.DROPPED, NetErrors.kind(SSLException("Read error: ssl=0x7: I/O error during system call, Connection reset by peer")))
        assertNull(NetErrors.kind(IllegalStateException("Không có sách này")))
        assertTrue(NetErrors.unpaired(IOException("x", NetErrors.Refused(401, "Thiết bị chưa ghép nối"))))
        assertFalse(NetErrors.unpaired(NetErrors.Refused(404, "Không có sách này")))
        val message = NetErrors.message(NetErrors.Kind.UNREACHABLE, "máy tính NGDtuanh-Lecoo")
        assertTrue(message, message.startsWith("Không tới được máy tính NGDtuanh-Lecoo"))
        assertFalse(message.contains("Failed to connect"))
        assertEquals("IOException: wrapped (SocketTimeoutException: timeout)", NetErrors.technical(IOException("wrapped", SocketTimeoutException("timeout"))))
    }

    @Test
    fun `ten dien thoai de doc, may ao khong lo ten tho`() {
        assertEquals("Điện thoại Google (máy ảo)", DeviceName.fallback(null, "Google", "sdk_gphone64_x86_64"))
        assertEquals("Điện thoại Google (máy ảo)", DeviceName.fallback("sdk_gphone64_x86_64", "Google", "sdk_gphone64_x86_64"))
        assertEquals("Điện thoại Samsung SM-A525F", DeviceName.fallback("", "samsung", "SM-A525F"))
        assertEquals("Điện thoại Xiaomi 13", DeviceName.fallback(null, "Xiaomi", "xiaomi 13"))
        // Tên người dùng đặt trong Cài đặt Android thắng - trừ khi nó chỉ là đời máy thô.
        assertEquals("Máy của Mai", DeviceName.fallback("Máy của Mai", "OPPO", "CPH2387"))
        assertEquals("Điện thoại OPPO CPH2387", DeviceName.fallback("CPH2387", "OPPO", "CPH2387"))
    }

    @Test
    fun `cho trong truoc khi tai tinh phan con thieu`() {
        val dir = BookEditsFixtures.tempDir("abook-space")
        val whole = File(dir, "a.mp3").apply { writeBytes(ByteArray(10)) }
        assertEquals(0L, DownloadSpace.stillNeeded(10, whole))
        val half = File(dir, "b.mp3")
        File(dir, "b.mp3.part").writeBytes(ByteArray(4))
        PartResume.stamp(File(dir, "b.mp3.part"), "\"v1\"") // a part only counts when its version is known (PartResume)
        assertEquals(6L, DownloadSpace.stillNeeded(10, half))
        assertEquals(0L, DownloadSpace.stillNeeded(0, half))
        val mb = 1L shl 20
        assertNull(DownloadSpace.shortage(10 * mb, 200 * mb))
        val short = DownloadSpace.shortage(125 * mb, 50 * mb)!!
        assertTrue(short, short.contains("cần khoảng 225 MB, còn 50 MB"))
        val manifest = JSONObject("""{"chapters":[{"available":true,"size":1000},{"available":false,"size":500},{"available":true,"size":24}]}""")
        assertEquals(1024L, DownloadSpace.bookBytes(manifest))
    }

    @Test
    fun `cuon cho day nho ca khi app mo lai`() {
        val file = File(BookEditsFixtures.tempDir("abook-pending"), "state-pending.json")
        PendingPushes(file).add("b1")
        PendingPushes(file).add("b2")
        PendingPushes(file).add("b1")
        assertEquals(setOf("b1", "b2"), PendingPushes(file).ids())
        PendingPushes(file).remove("b1")
        assertEquals(setOf("b2"), PendingPushes(file).ids())
    }

    @Test
    fun `cho nghe vuot do dai chuong khong duoc luu`() {
        assertTrue(PlacePolicy.fits(7.0, 7.0))
        assertTrue(PlacePolicy.fits(8.5, 7.0)) // độ dài trong gói lệch vài phần giây với file thật
        assertFalse(PlacePolicy.fits(812.4, 7.0)) // đồng hồ của cuốn trước
        assertTrue(PlacePolicy.fits(812.4, 0.0)) // chưa biết độ dài
    }

    @Test
    fun `giong rieng cua cuon theo ho so nghe, ben chon sau thang`() {
        val phone = JSONObject("""{"chapters":{},"bookmarks":[],"voice":"vieneu:Ái Hân","voiceAt":100.0,"_fieldRevs":{"voice":{"counter":2,"node":"phone"}}}""")
        val computer = JSONObject("""{"chapters":{},"bookmarks":[],"voice":"edge:vi-VN-NamMinhNeural","voiceAt":200.0,"_fieldRevs":{"voice":{"counter":3,"node":"computer"}}}""")
        assertEquals("edge:vi-VN-NamMinhNeural", Store.mergeStates(phone, computer).getString("voice"))
        val older = JSONObject(computer.toString()).put("voiceAt", 50.0).put("_fieldRevs", JSONObject("""{"voice":{"counter":1,"node":"computer"}}"""))
        assertEquals("vieneu:Ái Hân", Store.mergeStates(phone, older).getString("voice"))
    }
}
