package vn.abook.player.ui.data

import org.json.JSONObject
import vn.abook.player.LibraryTree
import vn.abook.player.Playback
import vn.abook.player.Store

/**
 * Nạp một cuốn vào trình phát ở CHỖ NGHE TIẾP (ListenLogic.resumePoint: gần hết chương thì sang chương kế, chưa nghe thì chương đầu chưa xong) -
 * cùng quy tắc với nút "Nghe" của bản WebView, không phải chỗ `last` thô như cây duyệt Android Auto.
 */
object PlayPlan {
    /** Hàm thuần: gói sách + trạng thái nghe -> lệnh nạp; null khi cuốn chưa có chương nghe được. */
    fun of(manifest: JSONObject, state: JSONObject?): LoadRequest? {
        val chapters = LibraryTree.chapters(manifest)
        if (chapters.isEmpty()) return null
        val listen = BookJson.state(state)
        val spot = ListenLogic.resumePoint(listen, manifest.optBoolean("complete", true), BookJson.chapters(manifest)) ?: return null
        return LoadRequest(
            id = manifest.getString("id"),
            title = manifest.optString("title"),
            narrator = manifest.optString("narrator").takeIf { it != "null" }.orEmpty(),
            chapters = chapters,
            startChapterId = spot.chapterId,
            startSeconds = spot.at,
            rate = listen.rate ?: 1.0,
        )
    }

    /** Nạp cuốn bắt đầu ở chương `chapterId`, giây `seconds` (chạm một chương ở trang sách); null khi chương ấy không nghe được. */
    fun at(manifest: JSONObject, state: JSONObject?, chapterId: Int, seconds: Double): LoadRequest? {
        val chapters = LibraryTree.chapters(manifest)
        if (chapters.none { it.id == chapterId }) return null
        return LoadRequest(
            id = manifest.getString("id"),
            title = manifest.optString("title"),
            narrator = manifest.optString("narrator").takeIf { it != "null" }.orEmpty(),
            chapters = chapters,
            startChapterId = chapterId,
            startSeconds = seconds.coerceAtLeast(0.0),
            rate = BookJson.state(state).rate ?: 1.0,
        )
    }

    /** Đọc Store (đĩa - luồng nền): cuốn đã tải hay cuốn nghe thẳng đã cất gói. */
    fun fromStore(id: String): LoadRequest? = Store.playableManifest(id)?.let { of(it, Store.state(id)) }

    /** Cuốn nghe gần nhất trên máy ([Playback.lastListened]) ở chỗ nghe tiếp của nó; null khi chưa nghe cuốn nào. Đọc Store - luồng nền. */
    fun fromLast(): LoadRequest? = Playback.lastListened()?.let { (manifest, _) -> of(manifest, Store.state(manifest.getString("id"))) }

    fun fromStoreAt(id: String, chapterId: Int, seconds: Double): LoadRequest? =
        Store.playableManifest(id)?.let { at(it, Store.state(id), chapterId, seconds) }
}
