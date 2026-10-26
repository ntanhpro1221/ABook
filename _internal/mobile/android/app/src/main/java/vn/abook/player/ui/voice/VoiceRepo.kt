package vn.abook.player.ui.voice

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.DeviceMusic
import vn.abook.player.LocalStudio
import vn.abook.player.MusicBed
import vn.abook.player.MusicImport
import vn.abook.player.Playback
import vn.abook.player.readaloud.OnlineVoices
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.readaloud.SupertonicVoices
import vn.abook.player.readaloud.VoiceException
import vn.abook.player.vieneu.VieneuVoices
import vn.abook.player.vieneu.VoiceModule

/**
 * Nguồn thật của Giọng đọc: gọi thẳng các lõi - cùng những hàm mà `ReadAloudPlugin` / `LibraryPlugin` chuyển tiếp cho bản WebView ([VoiceModule], [OnlineVoices],
 * [ReadAloud], [vn.abook.player.MusicStore]), không qua cầu Capacitor. Khóa chỉ đi xuống [OnlineVoices.saveKey], không ghi log, không trả lại.
 */
class VoiceRepo(context: Context) : VoiceSource {
    private val app = context.applicationContext

    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) {
        Playback.init(app)
        block()
    }

    private fun core(kind: ModuleKind): VoiceModule = when (kind) {
        ModuleKind.Vieneu -> VieneuVoices.module(app)
        ModuleKind.Supertonic -> SupertonicVoices.module(app)
    }

    private fun status(kind: ModuleKind) = ModuleJson.status(core(kind).status())

    /** Lỗi của lõi thành lời cho người nghe: câu của lõi đã là tiếng Việt, lỗi lạ thì nói chung. */
    private inline fun <T> guard(fallback: String, block: () -> T): T = try {
        block()
    } catch (error: VoiceFailure) {
        throw error
    } catch (error: IllegalArgumentException) {
        throw VoiceFailure(error.message ?: fallback)
    } catch (error: VoiceException) {
        throw VoiceFailure(error.message ?: fallback)
    } catch (error: Exception) {
        throw VoiceFailure(fallback)
    }

    override suspend fun module(kind: ModuleKind): ModuleStatus = io { status(kind) }

    override suspend fun start(kind: ModuleKind, choices: List<String>?): ModuleStatus = io {
        guard("Chưa tải được ${kind.title.replaceFirstChar { it.lowercase() }}") {
            core(kind).start(choices)
            status(kind)
        }
    }

    override suspend fun cancel(kind: ModuleKind): ModuleStatus = io {
        core(kind).cancel()
        status(kind)
    }

    override suspend fun measure(kind: ModuleKind): ModuleStatus = io {
        core(kind).measureAgain()
        status(kind)
    }

    override suspend fun remove(kind: ModuleKind, choice: String): ModuleStatus = io {
        guard("Chưa gỡ được ${kind.title.replaceFirstChar { it.lowercase() }}") {
            core(kind).remove(choice)
            // Cuốn đang đọc bằng giọng vừa gỡ thì đọc tiếp bằng giọng mặc định, không chờ lần nạp kế.
            Playback.onMain { ReadAloud.voicesChanged() }
            status(kind)
        }
    }

    override suspend fun switchVoices(fromPrefix: String, toPrefix: String, fallback: String) = io {
        val target = ReadAloud.voices(app).map { it.optString("id") }.firstOrNull { it.startsWith(toPrefix) } ?: fallback
        ReadAloud.switchVoices(fromPrefix, target)
    }

    override suspend fun providers(): List<KeyProvider> = io {
        val rows = OnlineVoices.describe(app)
        (0 until rows.length()).map { KeyJson.provider(rows.getJSONObject(it)) }
    }

    override suspend fun saveKey(provider: String, key: String, region: String): KeyProvider = io {
        guard("Chưa lưu được khóa") { KeyJson.provider(OnlineVoices.saveKey(app, provider, key, region)) }
    }

    override suspend fun removeKey(provider: String): KeyProvider = io {
        guard("Chưa xoá được khóa") { KeyJson.provider(OnlineVoices.removeKey(app, provider)) }
    }

    override suspend fun checkKey(provider: String): KeyResult = io {
        guard("Chưa kiểm tra được khóa") { KeyJson.check(OnlineVoices.checkKey(app, provider)) }
    }

    override suspend fun consents(): Set<String> = io { ReadAloud.onlineConsents().toSet() }

    override suspend fun allow(provider: String) = io { ReadAloud.grantOnline(provider) }

    override suspend fun sample(voice: String, text: String): String = io {
        guard("Chưa nghe thử được giọng này") { ReadAloud.readExactly(voice, text, null, emptyMap()).file.absolutePath }
    }

    /** Kho "Nhạc của tôi" của máy này; bản WebView đặt nó ở LibraryPlugin.load, bản native đặt ở đây (MỘT kho: [DeviceMusic.store]). */
    private fun store() = DeviceMusic.store(app).also { if (LocalStudio.musicStore == null) LocalStudio.musicStore = it }

    override suspend fun tracks(): List<MusicTrack> = io { MusicJson.tracks(org.json.JSONArray(store().entries())) }

    override suspend fun importMusic(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImportResult = io {
        store()
        guard("Chưa thêm được nhạc") { MusicJson.imported(MusicImport.run(app, uris.take(MusicImport.LIMIT).map(Uri::parse), progress)) }
    }

    override suspend fun removeTrack(link: String): List<MusicTrack> = io {
        val digest = link.removePrefix("local:")
        if (!store().remove(digest)) throw VoiceFailure("Bài này không còn trong Nhạc của tôi")
        Playback.onMain { MusicBed.refreshMine() }
        MusicJson.tracks(org.json.JSONArray(store().entries()))
    }
}
