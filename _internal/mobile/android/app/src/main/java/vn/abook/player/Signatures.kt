package vn.abook.player

import com.google.crypto.tink.subtle.Ed25519Verify
import java.security.GeneralSecurityException

/**
 * Kiểm chữ ký Ed25519 - bản Kotlin của `abook/webui/ed25519_verify.py`. Thư viện Tink (không tự viết mật mã): minSdk 24 chưa có Ed25519 trong
 * `java.security` (từ API 33). Chỉ KIỂM, không ký (ký ở máy dev: scripts/sign_remote_config.py, LLM_Train/music/sign_catalog.py).
 */
object Signatures {
    /** True khi `signature` (64 byte) là chữ ký Ed25519 hợp lệ của `message` theo `publicKey` (32 byte). Sai kiểu / sai độ dài thì false, không ném lỗi. */
    fun verify(publicKey: ByteArray, message: ByteArray, signature: ByteArray): Boolean = try {
        Ed25519Verify(publicKey).verify(signature, message)
        true
    } catch (_: GeneralSecurityException) {
        false
    } catch (_: IllegalArgumentException) {
        false
    }

    /** Như [verify], nhưng chữ ký ở dạng file `.sig` (base64 chặt, có thể kèm xuống dòng cuối) - `ed25519_verify.verify_base64`. */
    fun verifyBase64(publicKey: ByteArray, message: ByteArray, signatureText: ByteArray): Boolean {
        val signature = Covers.base64(String(signatureText, Charsets.US_ASCII).trim()) ?: return false
        return verify(publicKey, message, signature)
    }
}
