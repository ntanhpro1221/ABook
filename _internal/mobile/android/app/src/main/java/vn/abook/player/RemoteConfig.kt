package vn.abook.player

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.InputStream

/**
 * Cấu hình từ xa trên điện thoại - bản Kotlin của `abook/webui/remote_config.py`: những gì có thể đổi sau khi app đã phát hành (chỗ đặt
 * danh mục nhạc...) KHÔNG ghi cứng trong app. App chỉ ghi cứng hai ĐỊA CHỈ KHỞI ĐỘNG (cùng hai địa chỉ của máy tính) trỏ tới
 * `remote-config.json` + chữ ký `remote-config.json.sig`. Cấu hình có quyền bảo app lấy dữ liệu ở chỗ khác, nên:
 * - chỉ nhận file có chữ ký Ed25519 đúng khoá của ABook ([Signatures]);
 * - không nhận bản cũ hơn bản đang giữ (`issued`);
 * - tải hỏng / chữ ký sai / mất mạng: dùng bản tốt gần nhất đã cất, chưa có thì [DEFAULTS] đóng sẵn trong app.
 * Mọi lời gọi chặn (mạng) - chạy ở luồng nền, không bao giờ ở luồng giao diện. Bản tốt cất ở `dir` (cả byte gốc lẫn `.sig`).
 *
 * `open(url)` như của [MusicCatalog] (http(s) hay đường dẫn file cho test JVM).
 */
class RemoteConfig(
    private val dir: File,
    private val sources: List<String> = BOOTSTRAP,
    private val publicKey: ByteArray = PUBLIC_KEY,
    private val open: (String) -> InputStream = MusicCatalog.Companion::openUrl,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private val lock = Any()
    private var value: JSONObject? = null
    private var checked = 0L

    private fun accept(raw: ByteArray, signature: ByteArray): JSONObject? {
        if (!Signatures.verifyBase64(publicKey, raw, signature)) return null
        val parsed = try {
            JSONObject(String(raw, Charsets.UTF_8))
        } catch (_: JSONException) {
            return null
        }
        if (parsed.optString("format") != FORMAT) return null
        val version = parsed.opt("version") as? Int ?: return null
        if (version > FORMAT_VERSION) return null // định dạng mới hơn app: giữ bản cũ, bản app mới sẽ đọc được
        if (parsed.opt("issued") !is String) return null
        return parsed
    }

    private fun cached(): JSONObject? = try {
        accept(File(dir, "remote-config.json").readBytes(), File(dir, "remote-config.json.sig").readBytes())
    } catch (_: java.io.IOException) {
        null
    }

    /** Cấu hình hiện hành; làm mới (mạng) khi quá [REFRESH_MS] kể từ lần kiểm trước hay khi `refresh`. */
    fun get(refresh: Boolean = false): JSONObject = synchronized(lock) {
        value?.takeIf { !refresh && clock() - checked < REFRESH_MS }?.let { return it }
        var current = value ?: cached() ?: DEFAULTS
        for (source in sources) {
            val raw: ByteArray
            val signature: ByteArray
            try {
                raw = open(source).use { it.readBytes() }
                signature = open("$source.sig").use { it.readBytes() }
            } catch (_: java.io.IOException) {
                continue
            }
            val fetched = accept(raw, signature) ?: continue
            if (fetched.getString("issued") < current.optString("issued")) continue // bản cũ hơn bản đang giữ - có thể là file cũ bị dựng lại
            Store.writeAtomic(File(dir, "remote-config.json"), raw)
            Store.writeAtomic(File(dir, "remote-config.json.sig"), signature)
            current = fetched
            break
        }
        value = current
        checked = clock()
        current
    }

    /** Địa chỉ các danh mục nhạc (https/http) theo cấu hình; không có địa chỉ nào dùng được thì địa chỉ mặc định đóng kèm. */
    fun musicCatalogs(): List<String> {
        val list = get().optJSONObject("music")?.optJSONArray("catalogs")
        val catalogs = (0 until (list?.length() ?: 0)).mapNotNull { (list!!.opt(it) as? String)?.takeIf { url -> url.startsWith("http://") || url.startsWith("https://") } }
        return catalogs.ifEmpty { listOf(MusicCatalog.DEFAULT_SOURCE) }
    }

    companion object {
        const val FORMAT = "abook-remote-config"
        const val FORMAT_VERSION = 1
        const val REFRESH_MS = 6L * 3600 * 1000

        /** Khoá công khai của ABook (`remote_config.PUBLIC_KEY`): kiểm cấu hình từ xa và mục lục danh mục nhạc. */
        val PUBLIC_KEY: ByteArray = "1486a17adc7729ca8a23dd8bd11f5b7d59eb4424f3948bb8e9ddf2333ee18e22".chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        val BOOTSTRAP = listOf(
            "https://cdn.jsdelivr.net/gh/ntanhpro1221/ABook@main/remote-config/remote-config.json",
            "https://raw.githubusercontent.com/ntanhpro1221/ABook/main/remote-config/remote-config.json",
        )

        /** Bản đóng sẵn trong app (`remote_config.DEFAULTS`): `issued` rỗng nên bản có chữ ký nào cũng mới hơn. */
        val DEFAULTS: JSONObject
            get() = JSONObject().put("format", FORMAT).put("version", FORMAT_VERSION).put("issued", "").put(
                "music", JSONObject().put("catalogs", JSONArray().put(MusicCatalog.DEFAULT_SOURCE)).put("openverse", "https://api.openverse.org/v1/"),
            )
    }
}
