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

    /**
     * Chữ đọc theo (`scripts/<n>.json`) đã cất: gói đổi (thêm một chương) thì chỉ bỏ chữ của chương thật sự đổi (mã SHA-256 audio, tên file
     * hay chương biến mất); chương không đổi giữ chữ - máy tính tắt sau đó thì "Đọc theo" của chương đã nghe vẫn mở được. Chữ căn theo
     * giọng (`wordsVersion`) đổi thì chữ của mọi chương đều đổi: bỏ cả thư mục.
     */
    fun invalidateScripts(folder: File, previous: JSONObject?, manifest: JSONObject) {
        if (previous == null) return
        if (previous.optString("wordsVersion") != manifest.optString("wordsVersion")) {
            File(folder, "scripts").deleteRecursively()
            return
        }
        val fresh = HashMap<String, Pair<String, String>>()
        manifest.optJSONArray("chapters")?.let { list ->
            for (i in 0 until list.length()) {
                val chapter = list.optJSONObject(i) ?: continue
                fresh[chapter.opt("id").toString()] = chapter.optString("script") to chapter.optString("sha256")
            }
        }
        val old = previous.optJSONArray("chapters") ?: return
        for (i in 0 until old.length()) {
            val chapter = old.optJSONObject(i) ?: continue
            val script = chapter.optString("script")
            if (!script.startsWith("scripts/") || script.contains("..")) continue
            if (fresh[chapter.opt("id").toString()] != script to chapter.optString("sha256")) File(folder, script).delete()
        }
    }

    private const val CAST_STAMP = "cast.version"

    /** Dàn nhân vật đã cất không bị xoá trước khi có bản mới: cần tải khi chưa có hay khi nó được tải từ gói phiên bản khác. */
    fun castNeeded(folder: File, manifest: JSONObject): Boolean =
        !File(folder, "cast.json").isFile || runCatching { File(folder, CAST_STAMP).readText() }.getOrNull() != manifest.optString("version")

    /** Ghi nhận `cast.json` vừa tải xong từ gói `manifest` (lần tải lỗi thì không ghi: lần mở sau tải lại, bản cũ vẫn dùng được). */
    fun castFetched(folder: File, manifest: JSONObject) {
        runCatching { File(folder, CAST_STAMP).writeText(manifest.optString("version")) }
    }

    /** Bìa là bộ đệm: gỡ ảnh cũ khi đổi mô tả, để mạng lỗi thì lần mở sau vẫn xin lại. Không đụng bìa người nghe sửa. */
    fun invalidateCover(folder: File, previous: JSONObject?, manifest: JSONObject) {
        if (coverChanged(previous, manifest)) File(folder, "cover.jpg").delete()
    }
}
