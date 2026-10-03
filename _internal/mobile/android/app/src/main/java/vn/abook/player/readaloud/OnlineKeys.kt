package vn.abook.player.readaloud

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Khoá của người dùng cho giọng trực tuyến dùng khoá riêng (OnlineVoices.kt) - bản điện thoại của `abook/readaloud/keys.py`.
 *
 * Khoá được niêm bằng AES-GCM với một khoá nằm trong Android Keystore ([KeystoreBox]; app không có androidx.security nên không dùng
 * EncryptedSharedPreferences - thêm thư viện chỉ để làm đúng việc này là thừa), rồi mới ghi vào SharedPreferences: file sao lưu hay máy đã root đọc được
 * preferences cũng không có khoá thật. Giao diện chỉ thấy bản che ([mask]). Không ghi log khoá.
 *
 * Mỗi nhà cung cấp một mục JSON: `key` (đã niêm), `region` (Azure), `valid` (lần kiểm tra gần nhất được và chưa bị từ chối sau đó), `voices` ([[mã, tên, giới], ...]).
 */
class OnlineKeys(private val store: Store, private val box: SecretBox) {
    /** Chỗ ghi (SharedPreferences trên máy; bài thử dùng bảng trong bộ nhớ). */
    interface Store {
        fun get(name: String): String?
        fun put(name: String, value: String?)
    }

    interface SecretBox {
        fun seal(plain: String): String
        /** null khi không mở được (khoá Keystore mất sau khi xoá dữ liệu / đổi máy). */
        fun open(sealed: String): String?
    }

    data class VoiceRow(val code: String, val name: String, val gender: String)

    data class Entry(val key: String, val region: String, val valid: Boolean, val voices: List<VoiceRow>)

    companion object {
        const val MASK = "••••"

        fun mask(key: String): String = if (key.length >= 12) MASK + key.takeLast(4) else if (key.isNotEmpty()) MASK else ""

        /** Trên máy: SharedPreferences riêng + Android Keystore. */
        fun onDevice(context: Context): OnlineKeys {
            val prefs = context.getSharedPreferences("readaloud-online-keys", Context.MODE_PRIVATE)
            return OnlineKeys(object : Store {
                override fun get(name: String) = prefs.getString(name, null)
                override fun put(name: String, value: String?) {
                    prefs.edit().apply { if (value == null) remove(name) else putString(name, value) }.apply()
                }
            }, KeystoreBox())
        }
    }

    @Synchronized
    fun get(provider: String): Entry? {
        val json = store.get(provider)?.let { runCatching { JSONObject(it) }.getOrNull() } ?: return null
        val key = box.open(json.optString("key")) ?: return null
        val rows = json.optJSONArray("voices") ?: JSONArray()
        val voices = (0 until rows.length()).mapNotNull { i ->
            rows.optJSONArray(i)?.let { VoiceRow(it.optString(0), it.optString(1), it.optString(2)) }?.takeIf { it.code.isNotEmpty() }
        }
        return Entry(key, json.optString("region"), json.optBoolean("valid"), voices)
    }

    private fun write(provider: String, entry: Entry) {
        val voices = JSONArray()
        entry.voices.forEach { voices.put(JSONArray().put(it.code).put(it.name).put(it.gender)) }
        store.put(provider, JSONObject().put("key", box.seal(entry.key)).put("region", entry.region).put("valid", entry.valid).put("voices", voices).toString())
    }

    /** Lưu khoá mới (phải kiểm tra lại: `valid` false, bỏ danh sách giọng cũ). `key` rỗng = giữ khoá đã lưu, chỉ đổi vùng. */
    @Synchronized
    fun put(provider: String, key: String, region: String) {
        val value = key.trim().ifEmpty { get(provider)?.key ?: throw IllegalArgumentException("Thiếu khóa") }
        write(provider, Entry(value, region.trim().lowercase(), false, emptyList()))
    }

    @Synchronized
    fun mark(provider: String, valid: Boolean, voices: List<VoiceRow>? = null) {
        val entry = get(provider) ?: return
        write(provider, entry.copy(valid = valid, voices = voices ?: entry.voices))
    }

    @Synchronized
    fun remove(provider: String) = store.put(provider, null)

    /** Những gì giao diện được thấy. */
    fun public(provider: String): JSONObject {
        val entry = get(provider)
        return JSONObject().put("hasKey", entry != null).put("masked", mask(entry?.key ?: "")).put("region", entry?.region ?: "")
            .put("valid", entry?.valid ?: false).put("voices", entry?.voices?.size ?: 0)
    }
}

/** AES-256-GCM với khoá sinh trong Android Keystore (không bao giờ ra khỏi phần cứng / tiến trình hệ thống). Bản niêm = base64(iv 12 byte + bản mã). */
class KeystoreBox(private val alias: String = "abook-online-voice-keys") : OnlineKeys.SecretBox {
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build(),
        )
        return generator.generateKey()
    }

    override fun seal(plain: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        return Base64.encodeToString(cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
    }

    override fun open(sealed: String): String? = runCatching {
        val bytes = Base64.decode(sealed, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes, 0, 12))
        String(cipher.doFinal(bytes, 12, bytes.size - 12), Charsets.UTF_8)
    }.getOrNull()
}
