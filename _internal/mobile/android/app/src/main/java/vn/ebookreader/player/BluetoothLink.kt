package vn.ebookreader.player

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.util.UUID

/**
 * Kết nối máy tính (hay điện thoại khác) qua Bluetooth - chủ sách 27-09: "stream Bluetooth để sau là vẫn phải làm đấy nhé".
 *
 * Mỗi máy nhận một cổng TCP cục bộ ổn định (127.0.0.1:47670-47701, theo địa chỉ Bluetooth): SyncLink, trình phát nghe thẳng,
 * điều khiển từ xa... dùng http://127.0.0.1:<cổng> như một máy tính trong mạng, và mọi kết nối vào cổng ấy đi qua MỘT kết
 * nối RFCOMM (BtMux - cùng giao thức với webui/bluetooth.py của máy tính). RFCOMM chỉ mở khi có kết nối đầu tiên và mở lại
 * khi đứt, nên gọi `base` không bao giờ chặn luồng giao diện. Chỉ máy đã ghép Bluetooth (Cài đặt Android) mới dùng được -
 * rồi mới tới mã 6 số của app.
 */
object BluetoothLink {
    val SERVICE: UUID = UUID.fromString("a1f667fe-352a-49b7-9b91-a5463677cac0")
    private val gateways = HashMap<String, Gateway>()

    fun permitted(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            context.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED

    /** Máy tính và điện thoại đã ghép Bluetooth với máy này (bỏ tai nghe, loa, đồng hồ...); `abook` = đã thấy dịch vụ ABook. */
    @SuppressLint("MissingPermission")
    fun devices(context: Context): JSONArray {
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
            ?: throw IllegalStateException("Điện thoại này không có Bluetooth")
        if (!adapter.isEnabled) throw IllegalStateException("Bluetooth của điện thoại đang tắt - bật lên rồi thử lại")
        val out = JSONArray()
        for (device in adapter.bondedDevices) {
            val major = device.bluetoothClass?.majorDeviceClass
            val abook = device.uuids?.any { it.uuid == SERVICE } == true
            if (!abook && major != BluetoothClass.Device.Major.COMPUTER && major != BluetoothClass.Device.Major.PHONE) continue
            out.put(JSONObject().put("address", device.address).put("name", device.name ?: device.address)
                .put("kind", if (major == BluetoothClass.Device.Major.PHONE) "phone" else "computer").put("abook", abook))
        }
        return out
    }

    /** Gốc http qua đường hầm tới máy `address` (không chặn). */
    fun base(context: Context, address: String): String = "http://127.0.0.1:${gateway(context, address).port}"

    @Synchronized
    private fun gateway(context: Context, address: String): Gateway =
        gateways.getOrPut(address) { Gateway(context.applicationContext, address) }

    fun lastError(address: String): String = synchronized(this) { gateways[address]?.lastError.orEmpty() }
}

private class Gateway(private val context: Context, private val address: String) {
    private val server = bind()
    val port: Int = server.localPort
    @Volatile var lastError = ""
    private var mux: BtMux? = null

    init {
        Thread({ accept() }, "bt-gateway").apply { isDaemon = true }.start()
    }

    /** Cổng ổn định theo địa chỉ: trình phát giữ URL qua các lần mở lại đường hầm. Bận thì để hệ thống chọn. */
    private fun bind(): ServerSocket {
        val stable = 47670 + (address.hashCode() and 31)
        return runCatching { ServerSocket(stable, 50, InetAddress.getByName("127.0.0.1")) }
            .getOrElse { ServerSocket(0, 50, InetAddress.getByName("127.0.0.1")) }
    }

    private fun accept() {
        while (true) {
            val client = try {
                server.accept()
            } catch (_: IOException) {
                return
            }
            try {
                link().open(client)
            } catch (error: IOException) {
                lastError = error.message ?: "không kết nối được qua Bluetooth"
                runCatching { client.close() }
            } catch (error: SecurityException) {
                lastError = "Chưa cho ABook dùng Bluetooth"
                runCatching { client.close() }
            }
        }
    }

    @Synchronized
    @SuppressLint("MissingPermission")
    private fun link(): BtMux {
        mux?.takeIf { it.alive }?.let { return it }
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
            ?: throw IOException("Điện thoại này không có Bluetooth")
        if (!adapter.isEnabled) throw IOException("Bluetooth của điện thoại đang tắt")
        adapter.cancelDiscovery()
        val socket = adapter.getRemoteDevice(address).createRfcommSocketToServiceRecord(BluetoothLink.SERVICE)
        try {
            socket.connect()
        } catch (error: IOException) {
            runCatching { socket.close() }
            throw IOException("Không kết nối được qua Bluetooth - máy kia có bật ABook và Bluetooth không?", error)
        }
        val fresh = BtMux(socket.inputStream, socket.outputStream, { socket.close() })
        Thread({ fresh.run() }, "bt-link").apply { isDaemon = true }.start()
        lastError = ""
        mux = fresh
        return fresh
    }
}
