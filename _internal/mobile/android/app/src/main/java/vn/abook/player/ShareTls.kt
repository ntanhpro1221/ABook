package vn.abook.player

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.math.BigInteger
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.cert.X509Certificate
import java.security.spec.ECGenParameterSpec
import java.util.Date
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.security.auth.x500.X500Principal

/**
 * Danh tính TLS của điện thoại khi nó PHỤC VỤ thư viện cho máy khác (LibraryServer): một khoá ECDSA P-256 trong
 * AndroidKeyStore (khoá không bao giờ rời chip), sinh MỘT lần; chứng chỉ tự ký do chính KeyStore lập. Vân tay SHA-256 của
 * nó đi trong lời đáp ghép nối - máy kia ghim lại, như máy tính (webui/tls.py). Gỡ app / xoá dữ liệu thì khoá mất: sinh mới,
 * máy đã ghép phải ghép lại.
 */
object ShareTls {
    private const val ALIAS = "abook-share-tls"
    private const val YEARS = 20L

    class Identity(val context: SSLContext, val fingerprint: String)

    @Synchronized
    fun identity(): Identity {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (!store.containsAlias(ALIAS)) {
            val now = System.currentTimeMillis()
            val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
                .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                // TLS ký bằng SHA-256 (hay SHA-384/512 tuỳ máy kia); NONE cho đường Conscrypt ký sẵn bản băm.
                .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA1, KeyProperties.DIGEST_SHA256,
                    KeyProperties.DIGEST_SHA384, KeyProperties.DIGEST_SHA512)
                .setCertificateSubject(X500Principal("CN=ABook"))
                .setCertificateSerialNumber(BigInteger.valueOf(now))
                .setCertificateNotBefore(Date(now - 24 * 3600 * 1000L))
                .setCertificateNotAfter(Date(now + YEARS * 365 * 24 * 3600 * 1000L))
                .build()
            KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
                .apply { initialize(spec) }.generateKeyPair()
        }
        val certificate = store.getCertificate(ALIAS) as X509Certificate
        val keys = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm()).apply { init(store, null) }
        val context = SSLContext.getInstance("TLS").apply { init(keys.keyManagers, null, null) }
        return Identity(context, Pin.fingerprint(certificate.encoded))
    }
}
