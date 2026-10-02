package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.Base64
import javax.net.ssl.SSLHandshakeException

/**
 * Ghim chứng chỉ (Pin): vân tay tính ở đây phải TRÙNG vân tay webui/tls.py tính trên cùng chứng chỉ - hai bên so với nhau
 * qua lời đáp ghép nối - và chỉ đúng vân tay ấy mới qua được.
 */
class PinTest {
    // Chứng chỉ tự ký do tls.generate() của máy tính sinh (ECDSA P-256); vân tay do tls.fingerprint() tính.
    private val der = Base64.getDecoder().decode("MIIBbDCCARGgAwIBAgIQQtsXy341ikso5HxWaYgiTzAKBggqhkjOPQQDAjAQMQ4wDAYDVQQDDAVBQm9vazAeFw0yNjEwMDEwNzQ3MDFaFw00NjA5MjcwNzQ3MDFaMBAxDjAMBgNVBAMMBUFCb29rMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEhbAOSP4+ZUuo4PdbQ8mT/fchWK3ZSMpYr7w1STXOLxvtp5eZJ0DuQA7mKxBpZ4GqAaYnOTqd9XZ+MYJbihndzaNNMEswDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCB4AwEwYDVR0lBAwwCgYIKwYBBQUHAwEwFgYDVR0RBA8wDYILYWJvb2subG9jYWwwCgYIKoZIzj0EAwIDSQAwRgIhAMXF56mkEcJZXI99B92R0Lxibl89JlIIEwVZjQ1Kb3eLAiEAxoDo4nHCcSPlMyHyBrwChimz7/zIPDxa+3bxeTWyIow=")
    private val fingerprint = "7414dc673adf95d62f9e114a0cf1ce8d3413704348c755f9f152071bb911d08f"
    private val certificate = CertificateFactory.getInstance("X.509").generateCertificate(der.inputStream()) as X509Certificate

    @Test
    fun theFingerprintMatchesTheOneThePythonSideComputes() {
        assertEquals(fingerprint, Pin.fingerprint(der))
        assertEquals(fingerprint, Pin.fingerprint(certificate.encoded))
        assertEquals("7414 DC67 3ADF 95D6 2F9E 114A 0CF1 CE8D 3413 7043 48C7 55F9 F152 071B B911 D08F", Pin.display(fingerprint))
    }

    @Test
    fun onlyTheExactCertificatePasses() {
        Pin.check(arrayOf(certificate), fingerprint)
        Pin.check(arrayOf(certificate), fingerprint.uppercase())
        assertThrows(CertificateException::class.java) { Pin.check(arrayOf(certificate), "0".repeat(64)) }
        assertThrows(CertificateException::class.java) { Pin.check(arrayOf(certificate), "") }
        assertThrows(CertificateException::class.java) { Pin.check(emptyArray(), fingerprint) }
        assertThrows(CertificateException::class.java) { Pin.check(null, fingerprint) }
    }

    @Test
    fun aCertificateProblemIsToldApartFromALostConnection() {
        val changed = SSLHandshakeException("handshake").apply { initCause(CertificateException(Pin.CHANGED)) }
        assertTrue(Pin.isCertificateProblem(changed))
        assertFalse(Pin.isCertificateProblem(SSLHandshakeException("connection closed")))
        val error = assertThrows(IllegalStateException::class.java) { Pin.guard { throw changed } }
        assertEquals(Pin.CHANGED, error.message)
        assertTrue("giao diện nhận ra qua kiểu này, mã Pin.CODE", error is Pin.ChangedException)
        // Trình phát Media3 bọc lỗi chứng chỉ vài lớp (PlaybackException > HttpDataSourceException > SSLException).
        assertTrue(Pin.isCertificateProblem(java.io.IOException("playback", changed)))
        assertFalse(Pin.isCertificateProblem(java.io.IOException("playback", java.net.SocketTimeoutException())))
        // Đứt mạng giữa lúc bắt tay vẫn là IOException thường - SyncLink còn thử đường Bluetooth.
        assertThrows(SSLHandshakeException::class.java) { Pin.guard { throw SSLHandshakeException("connection closed") } }
    }
}
