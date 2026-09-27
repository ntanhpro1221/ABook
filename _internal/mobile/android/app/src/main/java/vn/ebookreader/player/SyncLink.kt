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

    fun base(context: Context): String {
        val prefs = prefs(context)
        return "http://${prefs.getString("host", "")}:${prefs.getInt("port", 47630)}"
    }

    fun request(
        context: Context,
        method: String,
        path: String,
        body: JSONObject? = null,
        auth: Boolean = true,
        root: String = base(context),
        readTimeoutMs: Int = 20_000,
    ): String {
        val connection = URL(root + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 5000
        connection.readTimeout = readTimeoutMs
        if (auth) connection.setRequestProperty("Authorization", "Bearer ${prefs(context).getString("token", "")}")
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
