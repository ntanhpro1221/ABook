package vn.abook.player.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.Description
import org.junit.runner.RunWith
import org.junit.runners.Suite
import org.junit.runners.model.Statement
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import vn.abook.player.Pin
import java.security.Security
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext

/** Để lại đúng thứ một suite Robolectric thật để lại trong JVM: Conscrypt đứng đầu, verifier và factory không còn của JDK. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class LeavesTlsStateBehind {
    @Test fun leaves() {
        Pin.install(RuntimeEnvironment.getApplication())
        assertEquals("Conscrypt", Security.getProviders().first().name)
    }
}

/** Thứ tự cố định: FastConnectTest chạy ngay sau một suite để lại trạng thái, phải cho cùng kết quả như chạy một mình. */
@RunWith(Suite::class)
@Suite.SuiteClasses(LeavesTlsStateBehind::class, FastConnectTest::class)
class FastConnectAfterRobolectricTest

class JvmTlsIsolationTest {
    private val leaked = HostnameVerifier { _, _ -> true }

    private fun isJdkVerifier(verifier: HostnameVerifier) =
        verifier.javaClass.name == "javax.net.ssl.HttpsURLConnection\$DefaultHostnameVerifier"

    @Test fun theBodySeesAFreshJvmAndTheLeftoversComeBackAfterwards() {
        val conscrypt = Class.forName("org.conscrypt.Conscrypt").getMethod("newProvider").invoke(null) as java.security.Provider
        val startVerifier = HttpsURLConnection.getDefaultHostnameVerifier()
        val startFactory = HttpsURLConnection.getDefaultSSLSocketFactory()
        val startConscrypt = Security.getProviders().withIndex().filter { it.value.name == conscrypt.name }
        startConscrypt.forEach { Security.removeProvider(it.value.name) }
        Security.insertProviderAt(conscrypt, 1)
        val leakedFactory = SSLContext.getInstance("TLS", conscrypt).apply { init(null, null, null) }.socketFactory
        HttpsURLConnection.setDefaultHostnameVerifier(leaked)
        HttpsURLConnection.setDefaultSSLSocketFactory(leakedFactory)
        val leakedOrder = Security.getProviders().map { it.name }
        var ran = false
        try {
            PristineJvmTls().apply(object : Statement() {
                override fun evaluate() {
                    ran = true
                    assertNull(Security.getProvider(conscrypt.name))
                    assertEquals("SunJSSE", SSLContext.getInstance("TLS").provider.name)
                    assertTrue(isJdkVerifier(HttpsURLConnection.getDefaultHostnameVerifier()))
                    assertTrue(HttpsURLConnection.getDefaultSSLSocketFactory().javaClass.name.startsWith("sun.security.ssl."))
                }
            }, Description.EMPTY).evaluate()
            assertTrue(ran)
            assertEquals(leakedOrder, Security.getProviders().map { it.name })
            assertNotNull(Security.getProvider(conscrypt.name))
            assertSame(leaked, HttpsURLConnection.getDefaultHostnameVerifier())
            assertSame(leakedFactory, HttpsURLConnection.getDefaultSSLSocketFactory())
        } finally {
            Security.removeProvider(conscrypt.name)
            startConscrypt.forEach { Security.insertProviderAt(it.value, it.index + 1) }
            HttpsURLConnection.setDefaultHostnameVerifier(startVerifier)
            HttpsURLConnection.setDefaultSSLSocketFactory(startFactory)
        }
    }
}
