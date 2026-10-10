package vn.abook.player

import android.content.Context
import java.net.Socket
import java.security.MessageDigest
import java.security.KeyStore
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLEngine
import javax.net.ssl.SSLException
import javax.net.ssl.SSLSocket
import javax.net.ssl.TrustManager
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509ExtendedTrustManager
import javax.net.ssl.X509TrustManager

/**
 * Ghim chứng chỉ TLS của máy đã ghép ("tin ở lần ghép đầu", webui/tls.py bên máy tính).
 *
 * Cổng đồng bộ của máy tính và `LibraryServer` của điện thoại khác đều nói TLS với MỘT chứng chỉ tự ký. Lúc ghép, điện thoại
 * này nhận chứng chỉ ấy ([SyncLink.pair]), đối chiếu với vân tay máy kia tự báo trong lời đáp, rồi ghi vân tay SHA-256 cùng thiết
 * bị (`fingerprint` trong SharedPreferences "sync" hay "peers"). Từ đó mọi kết nối tới địa chỉ của thiết bị ấy - SyncLink,
 * tải sách, và cả trình phát Media3 (DefaultHttpDataSource, đi qua HttpsURLConnection) - chỉ nhận ĐÚNG chứng chỉ có vân tay đó.
 * Vân tay đổi là lỗi [CHANGED] bảo ghép lại; không bao giờ rơi về HTTP, và không tự nhận chứng chỉ mới.
 *
 * Làm bằng MỘT SSLSocketFactory + HostnameVerifier mặc định của HttpsURLConnection ([install]): địa chỉ nào không phải của thiết
 * bị đã ghép (GitHub kiểm bản cập nhật...) vẫn đi đường kiểm chuỗi tin cậy của hệ thống như thường.
 */
object Pin {
    // Cùng nghĩa với webui/remote_books.py `_open`: bấm Thôi ghép rồi ghép lại; máy kia không cài lại thì đừng ghép lại.
    const val CHANGED = "Chứng chỉ bảo mật của máy kia đã khác lúc ghép (máy kia cài lại ABook?) - bấm Thôi ghép rồi ghép lại. " +
        "Nếu máy kia không cài lại gì thì đừng ghép lại: có thể có ai chen vào mạng"

    /** SHA-256 của chứng chỉ DER, 64 ký tự hex thường - cùng dạng với webui/tls.py `fingerprint`. */
    fun fingerprint(der: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(der).joinToString("") { "%02x".format(it) }

    /** Vân tay để người dùng nhìn: nhóm 4 ký tự, hoa - như `tls.display`. */
    fun display(fingerprint: String): String = fingerprint.chunked(4).joinToString(" ").uppercase()

    /** Phần thuần (test được): chứng chỉ đầu chuỗi phải có đúng vân tay `expected`; rỗng thì không bao giờ khớp. */
    fun check(chain: Array<out X509Certificate>?, expected: String) {
        val leaf = chain?.firstOrNull() ?: throw CertificateException("Máy kia không đưa chứng chỉ")
        if (expected.isEmpty() || fingerprint(leaf.encoded) != expected.lowercase()) throw CertificateException(CHANGED)
    }

    /** Mã lỗi Capacitor cho [ChangedException]: giao diện thấy mã này thì hiện nguyên câu [CHANGED] thay vì "không kết nối được". */
    const val CODE = "PIN_CHANGED"

    /** Lỗi chứng chỉ đã đổi lời cho người nghe (không phải IOException: không phải "mất mạng"). */
    class ChangedException(cause: Throwable) : IllegalStateException(CHANGED, cause)

    /** `error` hay một nguyên nhân của nó là lỗi chứng chỉ (không phải đứt mạng): lúc ấy nói [CHANGED] thay vì chữ của SSL.
     *  Không đòi `error` là SSLException: lỗi của trình phát Media3 (PlaybackException) bọc nó vài lớp. */
    fun isCertificateProblem(error: Throwable): Boolean =
        generateSequence(error) { it.cause }.any { it is CertificateException }

    /** Chạy `block`; lỗi chứng chỉ thành [ChangedException] có chữ đọc được. */
    fun <T> guard(block: () -> T): T = try {
        block()
    } catch (error: SSLException) {
        if (isCertificateProblem(error)) throw ChangedException(error) else throw error
    }

    // ---- vân tay mong đợi của một địa chỉ ----------------------------------------------------------------------------

    @Volatile private var appContext: Context? = null
    private var installed = false

    /**
     * Vân tay phải gặp ở `host:port`, hay null khi đó không phải thiết bị đã ghép (đi đường kiểm của hệ thống). Chuỗi rỗng =
     * thiết bị đã ghép mà không có vân tay - không chứng chỉ nào khớp.
     */
    fun expected(host: String?, port: Int): String? {
        val context = appContext ?: return null
        if (host == null) return null
        val main = SyncLink.prefs(context)
        val (lan, bluetooth) = SyncLink.routes(main)
        val mainPrint = main.getString("fingerprint", "").orEmpty()
        if ("$host:$port" in lan) return mainPrint
        // Đường hầm Bluetooth: kết nối vào cổng cục bộ 127.0.0.1:<cổng> của máy nào thì đúng chứng chỉ của máy ấy.
        val tunnel = if (host == "127.0.0.1") BluetoothLink.addressOfPort(port) else null
        if (tunnel != null && tunnel == bluetooth) return mainPrint
        val peers = Peers.all(context)
        for (key in peers.keys()) {
            val peer = peers.getJSONObject(key)
            val at = peer.optString("host")
            val here = if (tunnel != null) at == "bt:$tunnel" else at == host && peer.optInt("port", 47630) == port
            if (here) return peer.optString("fingerprint")
        }
        return null
    }

    /** Cài một lần cho cả tiến trình: gọi từ mọi nơi sắp mở kết nối tới thiết bị đã ghép (idempotent). */
    @Synchronized
    fun install(context: Context) {
        appContext = context.applicationContext
        if (installed) return
        val factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply { init(null as KeyStore?) }
        val system = factory.trustManagers.filterIsInstance<X509TrustManager>().first()
        val sslContext = SSLContext.getInstance("TLS").apply { init(null, arrayOf<TrustManager>(PinningTrust(system)), null) }
        HttpsURLConnection.setDefaultSSLSocketFactory(sslContext.socketFactory)
        val original = HttpsURLConnection.getDefaultHostnameVerifier()
        // Tên máy không kiểm với chứng chỉ tự ký: vân tay đã thay cho cả chuỗi tin cậy lẫn tên (PinningTrust).
        HttpsURLConnection.setDefaultHostnameVerifier { host, session ->
            if (expected(host, session.peerPort) != null) true else original.verify(host, session)
        }
        installed = true
    }

    private class PinningTrust(private val system: X509TrustManager) : X509ExtendedTrustManager() {
        private fun expectedFor(socket: Socket?): String? {
            if (socket == null) return null
            val named = (socket as? SSLSocket)?.handshakeSession?.peerHost
            return expected(named, socket.port) ?: expected(socket.inetAddress?.hostAddress, socket.port)
        }

        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?, socket: Socket?) {
            val pinned = expectedFor(socket)
            if (pinned != null) check(chain, pinned) else system.checkServerTrusted(chain, authType)
        }

        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?, engine: SSLEngine?) {
            val pinned = expected(engine?.peerHost, engine?.peerPort ?: -1)
            if (pinned != null) check(chain, pinned) else system.checkServerTrusted(chain, authType)
        }

        // Không có socket/engine để biết đang nối tới đâu: chỉ chứng chỉ do CA tin cậy - chứng chỉ tự ký không qua được.
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
            system.checkServerTrusted(chain, authType)
        }


        // Phía này không bao giờ là máy chủ có kiểm chứng chỉ khách.
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?, socket: Socket?) {
            throw CertificateException("client")
        }

        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?, engine: SSLEngine?) {
            throw CertificateException("client")
        }

        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {
            throw CertificateException("client")
        }

        override fun getAcceptedIssuers(): Array<X509Certificate> = system.acceptedIssuers
    }

    // ---- lần ghép đầu -----------------------------------------------------------------------------------------------

    /** Chỉ cho yêu cầu GHÉP: nhận chứng chỉ nào cũng được (chưa có vân tay để đối chiếu), vân tay đọc lại sau đó từ kết nối. */
    fun firstUse(connection: HttpsURLConnection) {
        val trustAll = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }
        connection.sslSocketFactory = SSLContext.getInstance("TLS").apply { init(null, arrayOf<TrustManager>(trustAll), null) }.socketFactory
        connection.hostnameVerifier = javax.net.ssl.HostnameVerifier { _, _ -> true }
    }

    /** Vân tay chứng chỉ máy kia đã đưa ra trong kết nối này (sau khi đã nhận trả lời). */
    fun peerFingerprint(connection: HttpsURLConnection): String =
        (connection.serverCertificates.firstOrNull() as? X509Certificate)?.let { fingerprint(it.encoded) } ?: ""
}
