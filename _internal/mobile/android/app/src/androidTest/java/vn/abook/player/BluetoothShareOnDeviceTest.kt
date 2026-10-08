package vn.abook.player

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * "Cho máy khác nghe thư viện này" qua Bluetooth THẬT, không mở Activity: bật chia sẻ bằng ShareService.enable - cùng đường công
 * tắc trong app dùng (dịch vụ nền chống đóng băng + LibraryServer, kéo theo BluetoothShare.start) -, kiểm trạng thái "running",
 * rồi giữ sống để một máy tính ghép với điện thoại gọi vào (scripts/bt_desktop_probe.py <địa chỉ>). Chỉ chạy khi có tham số
 * `bt_real` - bài thử thường bỏ qua:
 *
 *     adb shell am instrument -w -e bt_real 1 [-e bt_seconds 360] -e class vn.abook.player.BluetoothShareOnDeviceTest \
 *         com.ngdtuanh.abook.test/androidx.test.runner.AndroidJUnitRunner
 *
 * Thêm `-e bt_pair 1` (in mã ghép 6 số ra logcat) và `-e bt_seed_mb 4` (dựng cuốn thử 4 MB để đo tải sách).
 * Không có dịch vụ nền thì ColorOS đóng băng tiến trình này khoảng 30 giây sau khi bắt đầu (app không ở trước màn hình); có nó thì
 * phải nối được suốt thời gian giữ sống - `-e bt_seconds 200` rồi gọi vào sau hơn 2 phút.
 * Dừng sớm: tạo file `files/bt_real.done` (adb shell run-as com.ngdtuanh.abook touch files/bt_real.done). Nhật ký ở logcat, tag `BtReal`.
 */
@RunWith(AndroidJUnit4::class)
class BluetoothShareOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val done = File(context.filesDir, "bt_real.done")

    @After
    fun tearDown() {
        runCatching { ShareService.disable(context) }
    }

    @Test
    fun theLibraryServesOverBluetoothUntilTheComputerCallsIn() {
        val arguments = InstrumentationRegistry.getArguments()
        assumeTrue("chạy tay với -e bt_real 1", arguments.getString("bt_real") == "1")
        val seconds = arguments.getString("bt_seconds")?.toIntOrNull() ?: 360
        done.delete()

        ShareService.enable(context)
        Log.i(TAG, "dịch vụ chia sẻ chạy=${shareServiceRunning()}")
        Log.i(TAG, "tên Bluetooth báo cho máy kia='${LibraryServer.bluetoothNameSource()}'")
        Log.i(TAG, "LibraryServer chạy=${LibraryServer.running()} cổng=${LibraryServer.PORT} vân tay=${LibraryServer.fingerprint}")
        Log.i(TAG, "BluetoothShare.status='${BluetoothShare.status}'")
        assertTrue(LibraryServer.lastError, LibraryServer.running())
        assertEquals("running", BluetoothShare.status)

        // `-e bt_pair 1`: mở mã ghép 6 số như màn "Thiết bị khác" và ghi vào logcat (không cần nhìn màn hình).
        // `-e bt_seed_mb N`: dựng một cuốn thử N MB (byte giả, sha1 trong logcat) để đo tải sách qua Bluetooth; xoá khi xong.
        val seeded = arguments.getString("bt_seed_mb")?.toIntOrNull()?.takeIf { it > 0 }?.let(::seedBook)
        if (arguments.getString("bt_pair") == "1") {
            Log.i(TAG, "mã ghép nối=${LibraryServer.startPairing().getString("code")}")
        }

        var last = -1
        var peak = 0
        val deadline = System.currentTimeMillis() + seconds * 1000L
        while (System.currentTimeMillis() < deadline && !done.exists()) {
            val now = BluetoothShare.connections()
            peak = maxOf(peak, now)
            if (now != last) {
                Log.i(TAG, "kết nối RFCOMM đang mở: $now (đỉnh $peak)")
                last = now
            }
            Thread.sleep(200)
        }
        Log.i(TAG, "hết giờ giữ sống; đỉnh kết nối $peak; status='${BluetoothShare.status}'")
        seeded?.deleteRecursively()
    }

    @Suppress("DEPRECATION") // getRunningServices vẫn trả đúng dịch vụ của chính app
    private fun shareServiceRunning(): Boolean {
        val manager = context.getSystemService(android.content.Context.ACTIVITY_SERVICE) as android.app.ActivityManager
        repeat(30) { // dịch vụ vào chế độ foreground bất đồng bộ, chờ tối đa 3 giây
            if (manager.getRunningServices(100).any { it.service.className == ShareService::class.java.name && it.foreground }) return true
            Thread.sleep(100)
        }
        return false
    }

    private fun seedBook(megabytes: Int): File {
        val dir = Store.bookDir(SEED_ID).apply { mkdirs() }
        val audio = File(dir, "audio/001.mp3").apply { parentFile!!.mkdirs() }
        val bytes = ByteArray(megabytes * 1024 * 1024).also { java.util.Random(7).nextBytes(it) }
        audio.writeBytes(bytes)
        val chapter = JSONObject().put("id", 1).put("title", "Chương thử").put("file", "audio/001.mp3")
            .put("size", bytes.size).put("duration", 60.0).put("available", true)
        File(dir, "book.json").writeText(JSONObject().put("id", SEED_ID).put("title", "Sách thử Bluetooth").put("duration", 60.0)
            .put("chaptersTotal", 1).put("complete", true).put("chapters", JSONArray().put(chapter)).toString())
        val sha1 = java.security.MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }
        Log.i(TAG, "cuốn thử ${SEED_ID}: ${bytes.size} byte, sha1=$sha1")
        return dir
    }

    private companion object {
        const val TAG = "BtReal"
        const val SEED_ID = "btreal0123456789abcdef01"
    }
}
