package vn.abook.player

import org.json.JSONObject
import java.io.File

/** Quyết định làm mới sách nghe thẳng, dùng chung cho máy tính chính và thiết bị ghép. */
internal object StreamRefresh {
    fun stale(cached: JSONObject?, entry: JSONObject): Boolean = cached == null ||
        cached.optInt("chaptersAvailable") != entry.optInt("chaptersAvailable") ||
        cached.optString("title") != entry.optString("title") ||
        cached.optString("author") != entry.optString("author") || !StrictJson.equal(listedCover(cached), listedCover(entry))

    // /library chỉ có màu và phiên bản; manifest có thêm kích thước/tên file, không đem các trường ấy so với danh sách.
    private fun listedCover(value: JSONObject): JSONObject? = value.optJSONObject("cover")?.let {
        JSONObject().put("version", it.optLong("version")).put("color", it.opt("color") ?: JSONObject.NULL)
    }

    fun coverChanged(previous: JSONObject?, manifest: JSONObject): Boolean =
        !StrictJson.equal(previous?.optJSONObject("cover"), manifest.optJSONObject("cover"))

    fun coverNeeded(previous: JSONObject?, manifest: JSONObject, exists: Boolean): Boolean =
        manifest.optJSONObject("cover") != null && (coverChanged(previous, manifest) || !exists)

    /** Bìa là bộ đệm: gỡ ảnh cũ khi đổi mô tả, để mạng lỗi thì lần mở sau vẫn xin lại. Không đụng bìa người nghe sửa. */
    fun invalidateCover(folder: File, previous: JSONObject?, manifest: JSONObject) {
        if (coverChanged(previous, manifest)) File(folder, "cover.jpg").delete()
    }
}
