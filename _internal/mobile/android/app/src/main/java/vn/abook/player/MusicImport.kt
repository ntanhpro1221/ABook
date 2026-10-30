package vn.abook.player

import android.content.Context
import android.net.Uri
import org.json.JSONObject

/**
 * Nhập nhạc vào "Nhạc của tôi" (MusicStore): một chỗ cho giao diện (hộp chọn file của màn Nhạc của tôi). Nhập từng bản - một
 * bản hỏng không làm hỏng cả lượt -, báo tiến độ (xong, tổng) sau mỗi bản; trả đúng JSON của `my_music_import` ([LocalStudio.importAnswer]). Chạy ở luồng nền.
 */
object MusicImport {
    /** Số file tối đa trong một lượt nhập (server.MY_MUSIC_IMPORT_LIMIT). */
    const val LIMIT = 500

    /** Loại file hộp chọn nhạc của hệ thống cho chọn. */
    val MIME_TYPES = arrayOf("audio/*", "application/ogg")

    fun run(context: Context, uris: List<Uri>, progress: (done: Int, total: Int) -> Unit): JSONObject {
        val store = LocalStudio.musicStore ?: throw IllegalStateException("Kho nhạc chưa sẵn sàng")
        val added = ArrayList<JSONObject>()
        val existing = ArrayList<JSONObject>()
        val failed = ArrayList<String>()
        for ((index, uri) in uris.withIndex()) {
            val name = runCatching {
                context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                }
            }.getOrNull() ?: uri.lastPathSegment ?: "nhạc"
            try {
                val (track, duplicate) = store.importStream(name) { context.contentResolver.openInputStream(uri) }
                (if (duplicate) existing else added).add(track)
            } catch (error: MusicStore.ImportError) {
                failed.add(error.message.orEmpty())
            } catch (error: Exception) {
                failed.add("“$name”: không thêm được (${error.message ?: error.javaClass.simpleName}).")
            }
            progress(index + 1, uris.size)
        }
        if (added.isNotEmpty()) Playback.onMain { MusicBed.refreshMine() }
        return LocalStudio.importAnswer(added, existing, failed)
    }
}
