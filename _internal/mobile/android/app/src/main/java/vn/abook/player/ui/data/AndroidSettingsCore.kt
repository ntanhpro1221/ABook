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
 * Lõi thật của Cài đặt native: đọc / ghi ĐÚNG những chỗ bản WebView dùng - tuỳ chọn nghe ở [ListenPrefs] (`listen-prefs.json`, qua [ListenPrefs.apply] như
 * `PlayerPlugin.configure`), "Tự chọn nhạc nền" ở [MusicBed], giọng mặc định ở [ReadAloud] (`readaloud-voices.json`), tốc độ giọng ở [VoiceSpeed], nhật ký ở
 * [AppLog] / [Diagnostics]. Không qua plugin. Mọi hàm gọi ở luồng nền.
 */
class AndroidSettingsCore(context: Context) : SettingsCore {
    private val app = context.applicationContext

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
            VoiceOption(it.optString("id"), it.optString("name"), it.optString("provider"), it.optBoolean("default"))
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
        // Như "Dọn bản đọc đã làm" của bản WebView (ReadAloudPlugin.cacheClear): "Làm trước" đang chạy dừng trước, không thì nó ghi lại đúng những đoạn vừa dọn.
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
        /** Số dòng nhật ký của "Xem" (như `VIEW_LINES` của bản WebView). */
        const val VIEW_LINES = 500

        /** docs/THIRD_PARTY.md gói vào asset của bản -PnativeUi (app/build.gradle). */
        const val THIRD_PARTY_ASSET = "THIRD_PARTY.md"
    }
}
