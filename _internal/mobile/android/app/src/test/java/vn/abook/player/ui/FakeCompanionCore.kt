package vn.abook.player.ui

import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.ui.devices.*

class FakeCompanionCore : CompanionCore {
    var rows = JSONArray().put(JSONObject().put("device", "main").put("kind", "computer").put("name", "Máy tính phòng khách")
        .put("localBookId", "b1").put("known", true).put("age", 2.0)
        .put("state", JSONObject().put("bookId", "b1").put("chapterId", 1).put("chapterTitle", "Chương 1 · Ngày trở về")
            .put("playing", true).put("position", 60.0).put("duration", 600.0).put("rate", 1.25)))
    var noticeState = StudioNoticeState()
    var fail = false
    val commands = mutableListOf<Pair<String, JSONObject>>()
    override suspend fun players() = rows
    override suspend fun command(device: String, command: JSONObject) {
        if (fail) error("offline")
        commands += device to JSONObject(command.toString())
    }
    override suspend fun notices() = noticeState
    override suspend fun setNotices(enabled: Boolean): StudioNoticeState {
        noticeState = noticeState.copy(enabled = enabled)
        return noticeState
    }
}
