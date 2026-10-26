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
import vn.abook.player.ui.voice.VoiceFailure
import vn.abook.player.ui.voice.VoiceSource
import vn.abook.player.ui.voice.VoiceText

/**
 * Nhạc nền với lõi: màn nhạc của cuốn và lần sửa đi qua [LocalStudio.bookMusic] / [LocalStudio.setBookMusic] (cùng lời đáp với WebView), menu danh sách phát qua
 * [LocalStudio.playlistsView] (cần mạng lần đầu: luồng nền), thêm nhạc qua [VoiceSource.importMusic] (một kho với Nhạc của tôi). Sửa xong: nhạc đang phát đọc lại lớp
 * sửa, cuốn tải từ máy tính gửi phần sửa về ([BookActions.edited]).
 */
class MusicRepo(context: Context, private val voice: VoiceSource) : MusicSource {
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

    override suspend fun importMine(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImported {
        val result = try {
            voice.importMusic(uris, progress)
        } catch (error: VoiceFailure) {
            throw MusicFailure(error.message ?: "Chưa thêm được nhạc")
        }
        return MusicImported(VoiceText.imported(result), result.failed, result.added + result.existing > 0)
    }
}
