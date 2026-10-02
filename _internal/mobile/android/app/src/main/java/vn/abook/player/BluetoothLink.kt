package vn.abook.player

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothServerSocket
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Kết nối máy tính (hay điện thoại khác) qua Bluetooth - chủ sách 27-09: "stream Bluetooth để sau là vẫn phải làm đấy nhé".
 *
 * Mỗi máy nhận một cổng TCP cục bộ ổn định (127.0.0.1:47670-47701, theo địa chỉ Bluetooth): SyncLink, trình phát nghe thẳng,
 * điều khiển từ xa... dùng https://127.0.0.1:<cổng> như một máy tính trong mạng, và mọi kết nối vào cổng ấy đi qua MỘT kết
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

    /**
     * Gốc https qua đường hầm tới máy `address` (không chặn). Đường hầm chỉ chuyển byte: TLS đi nguyên vẹn tới máy kia, và vẫn
     * ghim đúng chứng chỉ của nó ([Pin.expected] tìm máy theo cổng cục bộ này).
     */
    fun base(context: Context, address: String): String = "https://127.0.0.1:${gateway(context, address).port}"

    /** Địa chỉ Bluetooth của máy mà cổng cục bộ `port` dẫn tới, hay null nếu không phải cổng của đường hầm nào. */
    @Synchronized
    fun addressOfPort(port: Int): String? = gateways.entries.firstOrNull { it.value.port == port }?.key

    @Synchronized
    private fun gateway(context: Context, address: String): Gateway =
        gateways.getOrPut(address) { Gateway(context.applicationContext, address) }

    fun lastError(address: String): String = synchronized(this) { gateways[address]?.lastError.orEmpty() }

    /** Thôi ghép máy `address` (hay "bt:<address>"): đóng cổng cục bộ và kết nối RFCOMM của nó. */
    fun forget(address: String) {
        val gateway = synchronized(this) { gateways.remove(address.removePrefix("bt:")) }
        gateway?.close()
    }
}

private class Gateway(private val context: Context, private val address: String) {
    companion object {
        const val RETRY_MILLIS = 10_000L // vừa hỏng (ngoài tầm, máy kia tắt Bluetooth): trả lỗi ngay, không quay số lại
        const val IDLE_MILLIS = 60_000L // không luồng nào mở ngần này thì đóng RFCOMM - mở lại khi cần
    }

    private val server = bind()
    val port: Int = server.localPort
    @Volatile var lastError = ""
    private var mux: BtMux? = null
    private var failedAt = 0L
    @Volatile private var lastUsed = System.currentTimeMillis()
    @Volatile private var closed = false
    // Mỗi kết nối cục bộ chờ đường hầm ở luồng riêng: một lần quay số RFCOMM chậm (vài giây khi máy kia ngoài tầm) không
    // làm các kết nối sau xếp hàng sau luồng accept.
    private val workers = Executors.newCachedThreadPool()

    init {
        Thread({ accept() }, "bt-gateway").apply { isDaemon = true }.start()
        Thread({ reap() }, "bt-gateway-idle").apply { isDaemon = true }.start()
    }

    /** Cổng ổn định theo địa chỉ: trình phát giữ URL qua các lần mở lại đường hầm. Bận thì để hệ thống chọn. */
    private fun bind(): ServerSocket {
        val stable = 47670 + (address.hashCode() and 31)
        return runCatching { ServerSocket(stable, 50, InetAddress.getByName("127.0.0.1")) }
            .getOrElse { ServerSocket(0, 50, InetAddress.getByName("127.0.0.1")) }
    }

    private fun accept() {
        while (!closed) {
            val client = try {
                server.accept()
            } catch (_: IOException) {
                return
            }
            workers.execute { carry(client) }
        }
    }

    private fun carry(client: Socket) {
        try {
            link().open(client)
            lastUsed = System.currentTimeMillis()
        } catch (error: IOException) {
            lastError = error.message ?: "không kết nối được qua Bluetooth"
            runCatching { client.close() }
        } catch (_: SecurityException) {
            lastError = "Chưa cho ABook dùng Bluetooth"
            runCatching { client.close() }
        } catch (error: Exception) { // địa chỉ hỏng, Bluetooth stack lỗi...: không được làm sập app
            lastError = "Không kết nối được qua Bluetooth: ${error.message ?: error.javaClass.simpleName}"
            runCatching { client.close() }
        }
    }

    @Synchronized
    @SuppressLint("MissingPermission")
    private fun link(): BtMux {
        if (closed) throw IOException("Đã thôi ghép máy này")
        mux?.takeIf { it.alive }?.let { return it }
        val now = System.currentTimeMillis()
        if (now - failedAt < RETRY_MILLIS) throw IOException(lastError.ifBlank { "Không kết nối được qua Bluetooth" })
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
            ?: throw IOException("Điện thoại này không có Bluetooth")
        if (!adapter.isEnabled) throw IOException("Bluetooth của điện thoại đang tắt")
        // cancelDiscovery đòi BLUETOOTH_SCAN trên Android 12+ (mình không dò tìm nên không xin quyền ấy): chỉ là tối ưu.
        runCatching { adapter.cancelDiscovery() }
        val socket = try {
            adapter.getRemoteDevice(address).createRfcommSocketToServiceRecord(BluetoothLink.SERVICE)
        } catch (error: IllegalArgumentException) {
            failedAt = now
            throw IOException("Địa chỉ Bluetooth không hợp lệ: $address", error)
        }
        try {
            socket.connect()
        } catch (error: IOException) {
            runCatching { socket.close() }
            failedAt = System.currentTimeMillis()
            lastError = "Không kết nối được qua Bluetooth - máy kia có bật ABook và Bluetooth không?"
            throw IOException(lastError, error)
        }
        val fresh = BtMux(socket.inputStream, socket.outputStream, { socket.close() })
        Thread({ fresh.run() }, "bt-link").apply { isDaemon = true }.start()
        lastError = ""
        failedAt = 0L
        lastUsed = System.currentTimeMillis()
        mux = fresh
        return fresh
    }

    /** Đóng RFCOMM khi không còn luồng nào mở đã IDLE_MILLIS: không giữ sóng Bluetooth (và pin) cho máy không ai dùng. */
    private fun reap() {
        while (!closed) {
            try {
                Thread.sleep(15_000)
            } catch (_: InterruptedException) {
                return
            }
            val current = synchronized(this) { mux }
            if (current != null && current.alive && current.openStreams == 0 &&
                System.currentTimeMillis() - lastUsed > IDLE_MILLIS
            ) {
                current.shutdown()
            } else if (current != null && current.openStreams > 0) {
                lastUsed = System.currentTimeMillis()
            }
        }
    }

    fun close() {
        closed = true
        runCatching { server.close() }
        synchronized(this) { mux }?.shutdown()
        workers.shutdownNow()
    }
}

/**
 * Điện thoại PHỤC VỤ qua Bluetooth (vai bên kia của BluetoothLink): khi "Cho máy khác nghe thư viện này" bật, nghe RFCOMM
 * cùng UUID dịch vụ ABook; mỗi máy kết nối là một BtMux nối vào LibraryServer của chính điện thoại - điện thoại khác (hay
 * máy tính) nghe thư viện này, đồng bộ chỗ nghe, điều khiển trình phát qua Bluetooth như qua Wi-Fi. Chỉ máy đã ghép
 * Bluetooth mới kết nối được (listenUsingRfcommWithServiceRecord là kênh có xác thực), rồi mới tới mã 6 số.
 *
 * Tắt Bluetooth thì thôi nghe và nói rõ; bật lại (ACTION_STATE_CHANGED) thì tự nghe lại khi chia sẻ còn bật.
 */
object BluetoothShare {
    private var server: BluetoothServerSocket? = null
    private val links = mutableSetOf<BtMux>()
    private var wanted = false
    private var appContext: Context? = null
    private var watching = false

    /** "" = chưa bật; "running"; hay lý do đọc được (tắt Bluetooth, chưa cho quyền...). */
    @Volatile
    var status = ""
        private set

    private val radio = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR)) {
                BluetoothAdapter.STATE_ON -> synchronized(this@BluetoothShare) { if (wanted) runCatching { start(context) } }
                BluetoothAdapter.STATE_TURNING_OFF, BluetoothAdapter.STATE_OFF -> dropListener("Bluetooth của điện thoại đang tắt")
            }
        }
    }

    @Synchronized
    @SuppressLint("MissingPermission")
    fun start(context: Context) {
        wanted = true
        appContext = context.applicationContext
        watch(context.applicationContext)
        if (server != null) return
        if (!BluetoothLink.permitted(context)) {
            status = "Chưa cho ABook dùng \"Thiết bị ở gần\" - bật trong phần Bluetooth"
            return
        }
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
        if (adapter == null) {
            status = "Điện thoại này không có Bluetooth"
            return
        }
        if (!adapter.isEnabled) {
            status = "Bluetooth của điện thoại đang tắt"
            return
        }
        val socket = try {
            adapter.listenUsingRfcommWithServiceRecord("ABook", BluetoothLink.SERVICE)
        } catch (error: IOException) {
            status = "Không mở được Bluetooth: ${error.message}"
            return
        } catch (_: SecurityException) {
            status = "Chưa cho ABook dùng Bluetooth"
            return
        }
        server = socket
        status = "running"
        Thread({ accept(socket) }, "bt-share").apply { isDaemon = true }.start()
    }

    /** Thử lại khi màn hình hỏi trạng thái (vừa cho quyền "Thiết bị ở gần", vừa bật Bluetooth). */
    @Synchronized
    fun retry() {
        val context = appContext ?: return
        if (wanted && server == null) runCatching { start(context) }
    }

    private fun watch(context: Context) {
        if (watching) return
        watching = true
        ContextCompat.registerReceiver(context, radio, IntentFilter(BluetoothAdapter.ACTION_STATE_CHANGED),
            ContextCompat.RECEIVER_NOT_EXPORTED)
    }

    private fun accept(socket: BluetoothServerSocket) {
        while (true) {
            val link = try {
                socket.accept()
            } catch (_: IOException) {
                // Tắt Bluetooth, hay stop(): bỏ socket hỏng để lần bật lại mở socket mới - không báo "đang chạy" mãi.
                dropListener("Bluetooth ngừng nghe - sẽ tự mở lại khi Bluetooth bật", socket)
                return
            }
            val mux = BtMux(link.inputStream, link.outputStream, { link.close() },
                dial = { Socket("127.0.0.1", LibraryServer.PORT) }, odd = false)
            synchronized(links) { links += mux }
            Thread({
                try {
                    mux.run()
                } finally {
                    synchronized(links) { links -= mux }
                }
            }, "bt-share-link").apply { isDaemon = true }.start()
        }
    }

    @Synchronized
    private fun dropListener(reason: String, only: BluetoothServerSocket? = null) {
        val current = server ?: return
        if (only != null && only !== current) return
        server = null
        runCatching { current.close() }
        if (wanted) status = reason
    }

    fun connections(): Int = synchronized(links) { links.size }

    @Synchronized
    fun stop() {
        wanted = false
        runCatching { server?.close() }
        server = null
        status = ""
        val all = synchronized(links) { links.toList() }
        all.forEach { it.shutdown() }
    }
}
