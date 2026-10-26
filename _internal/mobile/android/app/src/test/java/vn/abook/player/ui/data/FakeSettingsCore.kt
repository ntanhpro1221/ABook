package vn.abook.player.ui.data

import org.json.JSONArray
import org.json.JSONObject

/** Lõi Cài đặt giả cho test: kho trong bộ nhớ, ghi lại mọi lần ghi để test so khoá / giá trị. */
class FakeSettingsCore(var stored: JSONObject = JSONObject()) : SettingsCore {
    val saved = ArrayList<JSONObject>()
    var default = "edge:vi-VN-HoaiMyNeural"
    var allowed = true
    var bytes = 12L * 1024 * 1024 + 300 * 1024
    var logsCleared = 0
    var thirdPartyText = "# Thành phần\n\nABook dùng:\n\n## Phông chữ\n\n- **Be Vietnam Pro** (OFL)\n\n## Ghi chú cho người bảo trì\n\n- không hiện\n"

    override fun load(): JSONObject = stored
    override fun save(changes: JSONObject) {
        saved += changes
    }

    /** Giọng tải về máy đã cài (test thêm vào để thấy danh sách giọng đọc lại). */
    var installed = emptyList<VoiceOption>()

    override fun voices() = installed + listOf(
        VoiceOption("edge:vi-VN-HoaiMyNeural", "Hoài My (Edge)", "edge", true),
        VoiceOption("edge:vi-VN-NamMinhNeural", "Nam Minh (Edge)", "edge", false),
        VoiceOption("supertonic:F1", "Supertonic F1 - giọng nữ trầm ấm đọc truyện dài", "supertonic", false),
        VoiceOption("device:vi-vn-x-gft-local", "Tiếng Việt (vi-vn-x-gft-local)", "device", false),
    )

    override fun defaultVoice() = default
    override fun chooseDefaultVoice(id: String) {
        default = id
    }

    override fun voiceSpeed(): JSONObject = JSONObject().put("choice", "auto").put(
        "voices",
        JSONArray().put(
            JSONObject().put("name", "Giọng Supertonic").put("tier", "fast").put("using", "quality").put("rtf", 1.3).put("fastBytes", 48L * 1024 * 1024),
        ),
    )

    override fun setVoiceSpeed(choice: String): JSONObject = voiceSpeed().put("choice", choice)
    override fun cacheBytes() = bytes
    override fun clearCache(): Long {
        bytes = 0
        return 0
    }

    override fun notificationsAllowed() = allowed
    override fun logLines() = List(30) { "09:${(10 + it)}:00 I Playback phát chương $it của một cuốn có tên rất dài để xem dòng xuống dòng" }
    override fun clearLogs() {
        logsCleared++
    }

    override fun thirdParty() = thirdPartyText
    override val version = "0.4.146"
}
