package vn.abook.player.net

import org.junit.rules.ExternalResource
import java.security.Provider
import java.security.Security
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocketFactory

/**
 * Trạng thái TLS của cả JVM như lúc mới khởi động, cho một bài thử chạy kết nối JDK thật; xong thì trả lại đúng cái đã có.
 *
 * Mọi suite chạy chung một JVM, mà ba thứ này là biến tĩnh của JDK nên sống qua các suite:
 * - Robolectric (AndroidTestEnvironment, mọi chế độ trừ ConscryptMode.OFF) đặt verifier mặc định và chèn Conscrypt đầu danh sách, không bao giờ gỡ.
 * - Pin.install đặt socket factory và verifier mặc định cho cả tiến trình.
 * Verifier mặc định đã bị thay thì HttpsClient của JDK không tự kiểm tên ở lớp TLS nữa: chứng chỉ sai tên thành IOException thay vì SSLException,
 * tuỳ suite nào chạy trước. Phải trả lại sau bài thử vì Pin chỉ cài một lần cho mỗi sandbox.
 */
class PristineJvmTls : ExternalResource() {
    private var verifier: HostnameVerifier? = null
    private var factory: SSLSocketFactory? = null
    private var displaced: List<IndexedValue<Provider>> = emptyList()

    override fun before() {
        verifier = HttpsURLConnection.getDefaultHostnameVerifier()
        factory = HttpsURLConnection.getDefaultSSLSocketFactory()
        displaced = Security.getProviders().withIndex().filter { it.value.name.contains("Conscrypt", ignoreCase = true) }
        displaced.forEach { Security.removeProvider(it.value.name) }
        HttpsURLConnection.setDefaultHostnameVerifier(jdkVerifier())
        HttpsURLConnection.setDefaultSSLSocketFactory(SSLContext.getInstance("TLS", "SunJSSE").apply { init(null, null, null) }.socketFactory)
    }

    override fun after() {
        displaced.forEach { Security.insertProviderAt(it.value, it.index + 1) }
        HttpsURLConnection.setDefaultHostnameVerifier(verifier)
        HttpsURLConnection.setDefaultSSLSocketFactory(factory)
    }

    private companion object {
        /** JDK chỉ nhận ra verifier mặc định qua đúng lớp riêng của nó (build.gradle mở javax.net.ssl cho việc này). */
        fun jdkVerifier(): HostnameVerifier =
            Class.forName("javax.net.ssl.HttpsURLConnection\$DefaultHostnameVerifier").getDeclaredConstructor()
                .apply { isAccessible = true }.newInstance() as HostnameVerifier
    }
}
