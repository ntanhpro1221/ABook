package vn.abook.player

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.os.StatFs
import androidx.core.app.NotificationManagerCompat
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.WorkQuery
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit

/**
 * Bản chẩn đoán của điện thoại (a114): MỘT JSON gom mọi thứ người sửa lỗi cần mà không có adb - phiên bản app, máy, giờ, pin, mạng (CÓ hay KHÔNG
 * Wi-Fi / di động / VPN, không SSID, không địa chỉ IP), chỗ trống, quyền thông báo, miễn tối ưu pin, việc nền (tải / xuất), đang nghe cuốn nào,
 * dịch vụ chia sẻ, lý do tiến trình chết lần trước ([ExitReasons]), các file văng ([CrashLog]), đuôi nhật ký của app ([AppLog]) và đuôi logcat của
 * CHÍNH tiến trình (`logcat -d --pid=<pid>` không cần quyền READ_LOGS).
 *
 * Mỗi phần bọc try riêng ([assemble]): một phần lỗi thì thành `{"collectionFailed": true, "error": "..."}`, cả bản vẫn ra. Có tên cuốn đang nghe vì bản này chỉ đi
 * tới máy đã ghép (`GET /sync/v1/diagnostics`, [LibraryServer]) hay tới nơi người dùng tự chọn gửi; không có mã thiết bị, khoá, chữ của truyện.
 */
object Diagnostics {
    const val DEFAULT_LINES = 2000
    const val MAX_LINES = 20_000
    /** Trần cỡ cả bản (ký tự JSON): vượt thì bỏ logcat rồi cắt bớt đầu nhật ký ([fit]). */
    internal const val MAX_CHARS = 3_000_000
    private const val LOGCAT_LINES = 2000
    private const val WORK_LIMIT = 30

    /** `lines` từ người gọi (có thể thiếu / sai / âm / to) về khoảng 1..[MAX_LINES], mặc định [DEFAULT_LINES]. */
    fun clampLines(raw: Int?): Int = (raw ?: DEFAULT_LINES).coerceIn(1, MAX_LINES)

    /** `lines=N` trong chuỗi truy vấn (`a=1&lines=50`); không có / không phải số thì null. */
    internal fun linesOf(query: String): Int? =
        query.split('&').firstOrNull { it.startsWith("lines=") }?.removePrefix("lines=")?.toIntOrNull()

    /**
     * Ghép các phần: mỗi phần chạy trong try riêng. Ném (kể cả `Error` như thiếu lớp ở máy lạ) thì gắn collectionFailed và error.
     * Phần trả null thì bỏ khỏi bản.
     */
    internal fun assemble(parts: List<Pair<String, () -> Any?>>): JSONObject {
        val report = JSONObject().put("schema", 1)
        for ((name, build) in parts) {
            try {
                val value = build() ?: continue
                report.put(name, value)
            } catch (error: Throwable) {
                report.put(name, JSONObject().put("collectionFailed", true)
                    .put("error", "${error.javaClass.simpleName}: ${AppLog.scrub(error.message.orEmpty()).take(200)}"))
            }
        }
        return sanitize(report, bounded = true)
    }

    /** One common scrubber for every string, including object keys and nested errors. */
    internal fun sanitize(report: JSONObject, bounded: Boolean = false): JSONObject {
        var clipped = false
        fun text(value: String): String {
            val safe = AppLog.scrub(value)
            if (bounded && safe.length > 2000) { clipped = true; return safe.take(2000) }
            return safe
        }
        fun walk(value: Any?, depth: Int, logArray: Boolean = false): Any? {
            if (bounded && depth > 10) { clipped = true; return JSONObject.NULL }
            return when (value) {
                is String -> text(value)
                is JSONObject -> JSONObject().also { out ->
                    val keys = value.keys().asSequence().toList()
                    if (bounded && keys.size > 200) clipped = true
                    for (key in if (bounded) keys.take(200) else keys) {
                        val item = value.get(key)
                        val secret = key.matches(Regex("(?i)(?:key|api[_-]?key|token|secret|password|code|mật khẩu|mã ghép|host|hostname|address)"))
                        out.put(text(key), if (key.equals("addresses", true) || (secret && item is String)) "***" else walk(item, depth + 1,
                            logArray = depth == 0 && key in setOf("log", "logcat")))
                    }
                }
                is JSONArray -> JSONArray().also { out ->
                    val limit = if (logArray) MAX_LINES else 200
                    val start = if (bounded) (value.length() - limit).coerceAtLeast(0) else 0
                    if (start > 0) clipped = true
                    for (i in start until value.length()) out.put(walk(value.get(i), depth + 1))
                }
                else -> value
            }
        }
        val out = walk(report, 0) as JSONObject
        out.optJSONArray("logcat")?.let { raw ->
            out.put("logcat", JSONArray(filterLogcat((0 until raw.length()).map { raw.optString(it) })))
        }
        if (clipped) out.put("truncated", true)
        return out
    }

    /** Bound fields first, then enforce a final whole-document cap even without logs. */
    internal fun fit(report: JSONObject, maxChars: Int = MAX_CHARS): JSONObject {
        require(maxChars >= 2) // smallest JSON object is {}
        val out = sanitize(report, bounded = true)
        if (out.toString().length <= maxChars) return out
        out.remove("logcat")
        out.put("truncated", true)
        var log = out.optJSONArray("log")
        while (out.toString().length > maxChars && log != null && log.length() > 0) {
            val keep = log.length() / 2
            val shorter = JSONArray()
            for (index in log.length() - keep until log.length()) shorter.put(log.get(index))
            out.put("log", shorter)
            log = shorter
        }
        // Corrupt/massive metadata alone can exceed the budget. Remove largest sections until it fits.
        var size = out.toString().length
        if (size > maxChars) {
            val costs = out.keys().asSequence().filter { it != "truncated" && it != "schema" }
                .map { key -> key to (JSONObject().put(key, out.get(key)).toString().length - 2) }
                .sortedByDescending { it.second }.toList()
            for ((key, cost) in costs) {
                if (size <= maxChars) break
                size -= cost + if (out.length() > 1) 1 else 0
                out.remove(key)
            }
        }
        return if (out.toString().length <= maxChars) out else JSONObject()
    }

    /** Nhật ký đọc được (một dòng một mục) cho file chữ trong gói gửi đi: nhật ký của app rồi logcat của tiến trình. */
    internal fun logText(report: JSONObject): String {
        fun lines(key: String): List<String> = report.optJSONArray(key)?.let { array -> (0 until array.length()).map { array.optString(it) } } ?: emptyList()
        return buildString {
            append("=== Nhật ký của ABook ===\n").append(lines("log").joinToString("\n")).append("\n\n")
            append("=== logcat của tiến trình ===\n").append(lines("logcat").joinToString("\n")).append('\n')
        }
    }

    /** Gói .zip để người dùng tự gửi đi: `chan-doan.json` (JSON gọn để giữ trần) + `nhat-ky.txt`. Không gửi đi đâu - xem LibraryPlugin.shareDiagnostics. */
    internal fun bundle(report: JSONObject): ByteArray {
        val safe = fit(report)
        val out = java.io.ByteArrayOutputStream()
        java.util.zip.ZipOutputStream(out).use { zip ->
            zip.putNextEntry(java.util.zip.ZipEntry("chan-doan.json"))
            zip.write(safe.toString().toByteArray(Charsets.UTF_8))
            zip.closeEntry()
            zip.putNextEntry(java.util.zip.ZipEntry("nhat-ky.txt"))
            zip.write(logText(safe).toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        return out.toByteArray()
    }

    /** Tên file gói gửi đi: `abook-nhat-ky-<ngày-giờ>.zip`. */
    internal fun bundleName(now: Long): String = "abook-nhat-ky-" + SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date(now)) + ".zip"

    /** Cắt chuỗi dài, báo đã cắt bao nhiêu. */
    internal fun clip(text: String, max: Int): String = if (text.length <= max) text else text.take(max) + "\n… (cắt, còn ${text.length - max} ký tự)"

    internal fun iso(millis: Long, zone: TimeZone = TimeZone.getDefault()): String =
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).apply { timeZone = zone }.format(Date(millis))

    fun collect(context: Context, logLines: Int = DEFAULT_LINES): JSONObject {
        val app = context.applicationContext
        val lines = clampLines(logLines)
        return fit(assemble(listOf(
            "app" to { appInfo(app) },
            "device" to { JSONObject().put("sdk", Build.VERSION.SDK_INT).put("release", Build.VERSION.RELEASE)
                .put("manufacturer", Build.MANUFACTURER).put("model", Build.MODEL) },
            "time" to { val now = System.currentTimeMillis()
                JSONObject().put("epochMillis", now).put("iso", iso(now)).put("timezone", TimeZone.getDefault().id) },
            "battery" to { battery(app) },
            "network" to { network(app) },
            "storage" to { val stat = StatFs(app.filesDir.path)
                JSONObject().put("freeBytes", stat.availableBytes).put("totalBytes", stat.totalBytes) },
            "notifications" to { JSONObject().put("enabled", NotificationManagerCompat.from(app).areNotificationsEnabled()) },
            "power" to { power(app) },
            "playback" to { playback() },
            "work" to { work(app) },
            "share" to { share(app) },
            "dataRecovery" to { Store.dataDiagnostics() },
            "exitReasons" to { ExitReasons.read(app) },
            "crashes" to { JSONArray().also { array -> CrashLog.read(AppLog.folder()).forEach { (name, text) -> array.put(JSONObject().put("name", name).put("text", text)) } } },
            "log" to { JSONArray(AppLog.tail(lines)) },
            "logcat" to { logcat(minOf(lines, LOGCAT_LINES)) },
        )))
    }

    private fun appInfo(context: Context): JSONObject {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        val code = if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else @Suppress("DEPRECATION") info.versionCode.toLong()
        return JSONObject().put("package", context.packageName).put("versionName", info.versionName.orEmpty()).put("versionCode", code)
            .put("debug", (context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0)
            .put("pid", android.os.Process.myPid())
    }

    private fun battery(context: Context): JSONObject {
        val intent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        return JSONObject().put("percent", if (level < 0 || scale <= 0) JSONObject.NULL else level * 100 / scale)
            .put("charging", status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL)
    }

    /** Mạng hiện dùng: loại đường (có / không), đã kiểm có ra Internet, tính cước. Không SSID, không IP. */
    private fun network(context: Context): JSONObject {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = manager.activeNetwork?.let(manager::getNetworkCapabilities)
        fun has(transport: Int) = caps?.hasTransport(transport) == true
        return JSONObject().put("connected", caps != null).put("wifi", has(NetworkCapabilities.TRANSPORT_WIFI))
            .put("cellular", has(NetworkCapabilities.TRANSPORT_CELLULAR)).put("vpn", has(NetworkCapabilities.TRANSPORT_VPN))
            .put("ethernet", has(NetworkCapabilities.TRANSPORT_ETHERNET)).put("bluetooth", has(NetworkCapabilities.TRANSPORT_BLUETOOTH))
            .put("validated", caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true)
            .put("metered", manager.isActiveNetworkMetered)
    }

    private fun power(context: Context): JSONObject {
        val power = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        val activity = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        return JSONObject().put("ignoringBatteryOptimizations", power.isIgnoringBatteryOptimizations(context.packageName))
            .put("powerSave", power.isPowerSaveMode).put("deviceIdle", power.isDeviceIdleMode)
            .apply { if (Build.VERSION.SDK_INT >= 28) put("backgroundRestricted", activity.isBackgroundRestricted) }
    }

    /** Trình phát: cuốn / chương / vị trí / đang phát (cùng bản `Remote.snapshot` máy tính thấy). */
    private fun playback(): JSONObject {
        val state = Remote.snapshot()
        val out = JSONObject()
        for (key in listOf("bookId", "bookTitle", "chapterId", "chapterTitle", "position", "duration", "playing", "buffering", "rate", "error")) {
            if (state.has(key)) out.put(key, state.get(key))
        }
        return out
    }

    /** Việc nền của WorkManager (tải sách, xuất MP3 / M4B / sách nói, thông báo Studio): mã, trạng thái, lần chạy, lý do bị dừng, tiến độ. */
    private fun work(context: Context): JSONArray {
        val states = listOf(WorkInfo.State.RUNNING, WorkInfo.State.ENQUEUED, WorkInfo.State.BLOCKED, WorkInfo.State.FAILED, WorkInfo.State.CANCELLED)
        val infos = WorkManager.getInstance(context).getWorkInfos(WorkQuery.Builder.fromStates(states).build()).get(3, TimeUnit.SECONDS)
        val out = JSONArray()
        for (info in infos.take(WORK_LIMIT)) out.put(workEntry(info.id.toString(), info.state.name, info.tags, info.runAttemptCount, info.stopReason,
            info.progress.keyValueMap.entries.take(8).associate { it.key to it.value.toString().take(80) }))
        return out
    }

    /** Một mục việc nền (thuần: test JVM). Thẻ (tag) là tên lớp worker nên đủ để biết việc gì. */
    internal fun workEntry(id: String, state: String, tags: Set<String>, attempts: Int, stopReason: Int, progress: Map<String, String>): JSONObject {
        val live = if (state == "RUNNING") liveProgress(id) else emptyMap()
        return sanitize(JSONObject().put("id", id).put("state", state).put("tags", JSONArray(tags.sorted().map { it.substringAfterLast('.') }))
            .put("attempts", attempts).put("stopReason", stopReason).put("progress", JSONObject(progress + live)))
    }

    /** The very same sources that the four workers emit to; keyed by run, never by title/book alone. */
    private fun liveProgress(id: String): Map<String, String> {
        val sources = BookDownloads.diagnosticProgress() + Mp3Exports.live.running() + M4bExports.live.running() + ListenExports.live.running()
        val event = sources.firstOrNull { it.optString("run") == id } ?: return emptyMap()
        return listOf("done", "total", "percent", "phase", "chapter", "chapters").filter { event.has(it) }
            .associateWith { event.get(it).toString() }
    }

    internal fun share(context: Context): JSONObject = LibraryServer.diagnostics(context)

    /** Đuôi logcat của chính tiến trình này; lỗi (máy chặn) thì ném - [assemble] bỏ phần này. */
    private fun logcat(lines: Int): JSONArray {
        val process = Runtime.getRuntime().exec(arrayOf("logcat", "-v", "threadtime", "-d", "-t", lines.toString(), "--pid=${android.os.Process.myPid()}"))
        val out = java.util.Collections.synchronizedList(ArrayList<String>())
        val reader = Thread({ runCatching { process.inputStream.bufferedReader().useLines { it.forEach(out::add) } } }, "diag-logcat")
        reader.start()
        reader.join(4000)
        runCatching { process.destroy() }
        return JSONArray(filterLogcat(ArrayList(out).takeLast(lines)))
    }

    // Explicit media/system allowlist. Web/plugin payloads are never diagnostics logcat sources.
    private val allowedTags = Regex("(?:ExoPlayer[^: ]*|MediaCodec[^: ]*|CCodec[^: ]*|ACodec[^: ]*|AudioTrack|AudioSink|DefaultAudioSink|AndroidRuntime|WM-[^: ]+|StrictMode)")
    private val forbiddenTags = Regex("(?i)(?:Capacitor(?:/.*)?|Console|chromium|WebView.*)")
    private val threadtimeTag = Regex("""^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s+([^:]+):""")
    private val briefTag = Regex("""^[VDIWEF]/([^(:\s]+)\s*(?:\(\s*\d+\))?:""")

    internal fun filterLogcat(lines: List<String>): List<String> = lines.mapNotNull { line ->
        val tag = (threadtimeTag.find(line) ?: briefTag.find(line))?.groupValues?.get(1)?.trim() ?: return@mapNotNull null
        if (forbiddenTags.matches(tag) || !allowedTags.matches(tag)) null else AppLog.clean(line)
    }
}
