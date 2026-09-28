package vn.ebookreader.player

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Đường tới máy tính đã ghép (địa chỉ, cổng, mã thiết bị trong SharedPreferences "sync") - dùng chung cho thư viện
 * (LibraryPlugin: tải sách, đồng bộ chỗ nghe) và điều khiển từ xa (Remote).
 */
object SyncLink {
    fun prefs(context: Context): SharedPreferences = context.getSharedPreferences("sync", Context.MODE_PRIVATE)

    fun paired(context: Context): Boolean = !prefs(context).getString("token", "").isNullOrBlank()

    fun token(context: Context): String = prefs(context).getString("token", "") ?: ""

    fun base(context: Context): String {
        val prefs = prefs(context)
        return "http://${prefs.getString("host", "")}:${prefs.getInt("port", 47630)}"
    }

    /**
     * Máy giữ một cuốn: máy tính chính, hay thiết bị đã ghép (Peers) nếu gói của cuốn ghi `source` - kèm mã sách BÊN ẤY
     * (`remoteId`; sách của máy tính chính dùng đúng mã của nó).
     */
    fun linkFor(context: Context, bookId: String): Pair<Peers.Link, String> {
        val manifest = Store.playableManifest(bookId)
        val source = manifest?.optString("source").orEmpty()
        if (source.isNotEmpty()) {
            val link = Peers.link(context, source) ?: throw IllegalStateException("Thiết bị giữ cuốn này đã thôi ghép")
            return link to manifest!!.optString("remoteId", bookId)
        }
        return Peers.Link(base(context), token(context)) to bookId
    }

    /** Mã thiết bị cho một địa chỉ (trình phát nghe thẳng): thiết bị ghép có địa chỉ ấy, không thì máy tính chính. */
    fun tokenFor(context: Context, uri: android.net.Uri): String = Peers.tokenFor(context, uri) ?: token(context)

    fun request(
        context: Context,
        method: String,
        path: String,
        body: JSONObject? = null,
        auth: Boolean = true,
        root: String = base(context),
        readTimeoutMs: Int = 20_000,
        connectTimeoutMs: Int = 5000,
        token: String? = null,
    ): String {
        val connection = URL(root + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = connectTimeoutMs
        connection.readTimeout = readTimeoutMs
        if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
        else if (auth) connection.setRequestProperty("Authorization", "Bearer ${prefs(context).getString("token", "")}")
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.outputStream.use { it.write(body.toString().toByteArray()) }
        }
        val code = connection.responseCode
        val text = (if (code < 400) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
        connection.disconnect()
        if (code >= 400) {
            val message = runCatching { JSONObject(text).optString("error") }.getOrNull()
            throw IllegalStateException(message?.ifBlank { null } ?: "Máy tính trả lỗi $code")
        }
        return text
    }
}
