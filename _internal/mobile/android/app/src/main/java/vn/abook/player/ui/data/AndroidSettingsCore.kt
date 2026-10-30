package vn.abook.player.ui.data

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import org.json.JSONObject
import vn.abook.player.AppLog
import vn.abook.player.BuildConfig
import vn.abook.player.Diagnostics
import vn.abook.player.ListenPrefs
import vn.abook.player.MusicBed
import vn.abook.player.Playback
import vn.abook.player.Store
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.readaloud.VoiceSpeed

/**
 * Lõi thật của Cài đặt native: đọc / ghi ĐÚNG những chỗ lõi dùng - tuỳ chọn nghe ở [ListenPrefs] (`listen-prefs.json`, qua [ListenPrefs.apply]),
 * "Tự chọn nhạc nền" ở [MusicBed], giọng mặc định ở [ReadAloud] (`readaloud-voices.json`), tốc độ giọng ở [VoiceSpeed], nhật ký ở
 * [AppLog] / [Diagnostics]. Mọi hàm gọi ở luồng nền.
 */
class AndroidSettingsCore(context: Context) : SettingsCore {
    private val app = context.applicationContext
    override fun takeNotificationOffer(): Boolean {
        val prefs = app.getSharedPreferences("native_ui", Context.MODE_PRIVATE)
        if (prefs.getBoolean("notification_asked", false)) return false
        prefs.edit().putBoolean("notification_asked", true).apply()
        return true
    }
    override fun freshOldSaves(names: List<String>): Boolean {
        val prefs = app.getSharedPreferences("native_ui", Context.MODE_PRIVATE)
        val seen = prefs.getStringSet("old_saves_seen", emptySet()).orEmpty()
        val fresh = names.any { it !in seen }
        prefs.edit().putStringSet("old_saves_seen", names.toSet()).apply()
        return fresh
    }
    override fun oldSaves(): List<OldSave> {
        val dir = vn.abook.player.OldSaves.dir(app.filesDir)
        vn.abook.player.BookSave.recover(dir)
        return vn.abook.player.OldSaves.list(dir).map { OldSave(it.name, it.size, it.modified) }
    }
    override fun deleteOldSave(name: String) {
        check(vn.abook.player.OldSaves.delete(vn.abook.player.OldSaves.dir(app.filesDir), name)) { "Chưa xoá được" }
    }
    override fun exportOldSave(name: String, uri: String) {
        val sink = app.contentResolver.openOutputStream(android.net.Uri.parse(uri), "wt") ?: error("Chưa mở được file để ghi")
        sink.use { vn.abook.player.OldSaves.copyTo(vn.abook.player.OldSaves.dir(app.filesDir), name, it) }
    }
    override fun release(): AppRelease? {
        val prefs = app.getSharedPreferences("app-release", Context.MODE_PRIVATE)
        val cached = runCatching { JSONObject(prefs.getString("json", "")!!) }.getOrNull()
        if (System.currentTimeMillis() - prefs.getLong("at", 0) < 86_400_000) return cached?.let(AppRelease::parse)
        return runCatching {
            val connection = java.net.URL("https://api.github.com/repos/ntanhpro1221/ABook/releases/latest").openConnection() as java.net.HttpURLConnection
            try {
                connection.connectTimeout = 8000; connection.readTimeout = 8000
                connection.setRequestProperty("Accept", "application/vnd.github+json")
                check(connection.responseCode == 200)
                val json = connection.inputStream.bufferedReader().use { it.readText() }
                val release = AppRelease.parse(JSONObject(json))
                prefs.edit().putString("json", json).putLong("at", System.currentTimeMillis()).apply()
                release
            } finally { connection.disconnect() }
        }.getOrElse { cached?.let(AppRelease::parse) }
    }
    override fun tellRelease(version: String): Boolean {
        val prefs = app.getSharedPreferences("app-release", Context.MODE_PRIVATE)
        if (prefs.getString("told", "") == version) return false
        prefs.edit().putString("told", version).apply()
        return true
    }

    /** Lõi phát (và kho, giọng đọc, nhạc nền) đã dựng: `Playback.init` gọi lại được nhiều lần, các phần bên trong tự giữ lần đầu. */
    private fun ready() = Playback.init(app)

    override fun load(): JSONObject {
        Store.init(app)
        return ListenPrefs.stored().put("autoMusic", MusicBed.rememberedAuto(app))
    }

    override fun save(changes: JSONObject) {
        ready()
        ListenPrefs.apply(changes)
        if (changes.has("autoMusic")) MusicBed.chooseAuto(changes.getBoolean("autoMusic"))
    }

    override fun voices(): List<VoiceOption> {
        ready()
        return ReadAloud.voices(app).map {
            VoiceOption(it.optString("id"), it.optString("name"), it.optString("provider"), it.optBoolean("default"), it.optString("gender"))
        }
    }

    override fun defaultVoice(): String {
        ready()
        return ReadAloud.choices?.voiceFor("").orEmpty()
    }

    override fun chooseDefaultVoice(id: String) {
        ready()
        ReadAloud.chooseDefault(id)
    }

    override fun voiceSpeed(): JSONObject {
        VoiceSpeed.setup(app)
        return VoiceSpeed.status()
    }

    override fun setVoiceSpeed(choice: String): JSONObject {
        VoiceSpeed.setup(app)
        VoiceSpeed.setChoice(choice)
        return VoiceSpeed.status()
    }

    override fun cacheBytes(): Long {
        ready()
        return ReadAloud.cache().sizeBytes()
    }

    override fun clearCache(): Long {
        ready()
        // "Dọn bản đọc đã làm": "Làm trước" đang chạy dừng trước, không thì nó ghi lại đúng những đoạn vừa dọn.
        vn.abook.player.readaloud.PrepareAhead.cancel(app)
        ReadAloud.cache().clear()
        return ReadAloud.cache().sizeBytes()
    }

    override fun notificationsAllowed(): Boolean =
        Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(app, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    override fun logLines(): List<String> {
        val log = Diagnostics.collect(app, VIEW_LINES).optJSONArray("log") ?: return emptyList()
        return (0 until log.length()).map { log.optString(it) }
    }

    override fun clearLogs() {
        AppLog.clear()
        AppLog.i("Diagnostics", "người dùng xoá nhật ký")
    }

    override fun thirdParty(): String =
        runCatching { app.assets.open(THIRD_PARTY_ASSET).use { it.readBytes().toString(Charsets.UTF_8) } }.getOrDefault("")

    override val version: String get() = BuildConfig.VERSION_NAME

    companion object {
        /** Số dòng nhật ký của "Xem". */
        const val VIEW_LINES = 500

        /** docs/THIRD_PARTY.md gói vào asset lúc build (app/build.gradle, nativeThirdPartyAsset). */
        const val THIRD_PARTY_ASSET = "THIRD_PARTY.md"
    }
}
