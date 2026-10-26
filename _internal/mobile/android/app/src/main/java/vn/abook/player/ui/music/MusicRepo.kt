package vn.abook.player.ui.music

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.BookActions
import vn.abook.player.BookEdits
import vn.abook.player.DeviceMusic
import vn.abook.player.LocalStudio
import vn.abook.player.Playlists
import vn.abook.player.Store

/**
 * Nhạc nền với lõi: màn nhạc của cuốn và lần sửa đi qua [LocalStudio.bookMusic] / [LocalStudio.setBookMusic] (cùng lời đáp với WebView), menu danh sách phát qua
 * [LocalStudio.playlistsView] (cần mạng lần đầu: luồng nền); thêm nhạc không qua đây mà qua [vn.abook.player.ui.voice.MineImports] (một kho, một lượt với Nhạc của tôi). Sửa xong: nhạc đang phát đọc lại lớp
 * sửa, cuốn tải từ máy tính gửi phần sửa về ([BookActions.edited]).
 */
class MusicRepo(context: Context) : MusicSource {
    private val app = context.applicationContext

    private suspend fun <T> io(fallback: String, block: () -> T): T = withContext(Dispatchers.IO) {
        Store.init(app)
        // Bản WebView đặt hai thứ này ở LibraryPlugin.load; giao diện native không nạp plugin.
        if (LocalStudio.musicStore == null) LocalStudio.musicStore = DeviceMusic.store(app)
        if (LocalStudio.catalog == null) LocalStudio.catalog = DeviceMusic.catalog(app)
        try {
            block()
        } catch (error: BookEdits.EditsError) {
            throw MusicFailure(error.message ?: fallback)
        } catch (error: IllegalArgumentException) {
            throw MusicFailure(error.message ?: fallback)
        }
    }

    private fun textOnly(id: String): Boolean =
        (Store.manifest(id) ?: Store.streamManifest(id)?.let { Store.streamed(id, it) })?.let(Playlists::isTextBook) ?: false

    override suspend fun menu(): MusicMenu = io("Chưa tải được các danh sách nhạc") { MusicJson.menu(LocalStudio.playlistsView()) }

    override suspend fun book(id: String): BookMusic = io("Chưa đọc được nhạc nền của cuốn này") { MusicJson.book(LocalStudio.bookMusic(id), textOnly(id)) }

    private suspend fun put(id: String, body: JSONObject): BookMusic = io("Chưa đổi được nhạc nền") {
        val view = LocalStudio.setBookMusic(id, body)
        BookActions.edited(app, id)
        MusicJson.book(view, textOnly(id))
    }

    override suspend fun choose(id: String, playlist: String?): BookMusic = put(id, JSONObject().put("playlist", playlist ?: JSONObject.NULL))

    override suspend fun level(id: String, levelDb: Double): BookMusic = put(id, JSONObject().put("levelDb", levelDb))

    override suspend fun enable(id: String, enabled: Boolean): BookMusic = put(id, JSONObject().put("enabled", enabled))

    override suspend fun silence(id: String, key: String, silenced: Boolean): BookMusic = put(id, JSONObject().put("silence", JSONObject().put(key, silenced)))

    /** Như Sửa sách của web: chọn một bài cho đoạn đang im thì cho đoạn ấy có nhạc lại; null = về bài gốc. */
    override suspend fun pin(id: String, key: String, link: String?): BookMusic {
        val body = JSONObject().put("pins", JSONObject().put(key, link ?: JSONObject.NULL))
        if (link != null) body.put("silence", JSONObject().put(key, false))
        return put(id, body)
    }

    override suspend fun alternatives(id: String, key: String): List<MineTrack> =
        io("Chưa tìm được bài để đổi") { MusicJson.mine(LocalStudio.musicAlternatives(id, key)) }
}
