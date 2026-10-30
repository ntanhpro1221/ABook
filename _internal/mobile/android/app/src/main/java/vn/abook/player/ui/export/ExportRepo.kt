package vn.abook.player.ui.export

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import vn.abook.player.BookMusic
import vn.abook.player.Devices
import vn.abook.player.ExportHistory
import vn.abook.player.ExportJobs
import vn.abook.player.ExportStart
import vn.abook.player.ListenExports
import vn.abook.player.M4bExports
import vn.abook.player.Mp3Export
import vn.abook.player.Mp3Exports
import vn.abook.player.Playback
import vn.abook.player.Store
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.listenerFlow
import vn.abook.player.ui.voice.VoiceText

/**
 * Nguồn thật của màn Xuất: gọi thẳng các lõi ([ExportStart], [Mp3Exports], [M4bExports], [ListenExports], [ExportHistory], [BookMusic]) - không qua
 * lớp trung gian nào. Tin của việc nền đến qua [vn.abook.player.ExportLive.listen].
 */
class ExportRepo(private val context: Context) : ExportSource {
    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) {
        Store.init(context)
        block()
    }

    private fun started(value: ExportStart.Started) = Started(value.run, value.folder, value.name, value.chapters)

    /** Bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật. */
    private fun drawn(book: ListenBook): ByteArray? = if (book.cover != null) null else runCatching { DrawnCover.png(book.title) }.getOrNull()

    override suspend fun music(bookId: String): ExportMusic = io { BookMusic.exportState(bookId).let { (available, enabled) -> ExportMusic(available, enabled) } }

    override suspend fun history(bookId: String): List<PastExport> = io {
        val records = ExportHistory.view(Store.bookDir(bookId))
        (0 until records.length()).mapNotNull { ExportJson.past(records.getJSONObject(it)) }
    }

    override suspend fun folder(): String? = io { Mp3Exports.remembered(context)?.let { Mp3Exports.treeName(context, it) } }

    override suspend fun voice(bookId: String): ExportVoice? = io {
        Playback.init(context)
        val chosen = ReadAloud.voiceForBook(bookId, "")
        val voices = ReadAloud.voices(context)
        val info = voices.firstOrNull { it.optString("id") == chosen } ?: voices.firstOrNull { it.optBoolean("default") } ?: voices.firstOrNull() ?: return@io null
        val provider = info.optString("provider")
        ExportVoice(info.optString("id"), if (provider == "device") "Giọng đọc của máy" else VoiceText.spokenName(info.optString("name")), provider, info.optBoolean("online"))
    }

    override suspend fun plan(bookId: String, voice: String, music: Boolean?): AudiobookPlan = io {
        Playback.init(context)
        ExportJson.plan(ExportStart.audiobookPlan(context, bookId, voice, music))
    }

    override suspend fun background(): BackgroundView? = io {
        val view = Devices.backgroundView(context)
        BackgroundView(view.optString("manufacturer"), view.optBoolean("backgroundAllowed"))
    }

    override suspend fun keepFolder(tree: String): String = io {
        val uri = Uri.parse(tree)
        Mp3Exports.remember(context, uri)
        Mp3Exports.treeName(context, uri) ?: throw ExportFailure("Chưa mở được thư mục đã chọn - chọn lại nơi lưu")
    }

    override suspend fun fileTitle(book: ListenBook, kind: ExportKind): String = io {
        when (kind) {
            ExportKind.Mp3 -> {
                ExportStart.requireBook(book.id)
                Mp3Export.plan(book.id).title
            }
            ExportKind.M4b -> ExportStart.m4bTitle(book.id)
            ExportKind.Audiobook -> ExportStart.audiobookTitle(book.id)
        }
    }

    override suspend fun startMp3(book: ListenBook, chapterIds: List<Int>?, music: Boolean): Started = io {
        val tree = Mp3Exports.remembered(context) ?: throw ExportFailure("Chọn thư mục để lưu trước")
        started(ExportStart.mp3(context, book.id, tree, drawn(book), chapterIds, music))
    }

    override suspend fun startM4b(book: ListenBook, file: String, music: Boolean): Started = io {
        started(ExportStart.m4b(context, book.id, Uri.parse(file), drawn(book), music))
    }

    override suspend fun startAudiobook(book: ListenBook, voice: String, file: String, music: Boolean): Started = io {
        started(ExportStart.audiobook(context, book.id, voice, Uri.parse(file), drawn(book), music))
    }

    override suspend fun cancel(kind: ExportKind, bookId: String) = io {
        when (kind) {
            ExportKind.Mp3 -> Mp3Exports.cancel(context, bookId)
            ExportKind.M4b -> M4bExports.cancel(context, bookId)
            ExportKind.Audiobook -> ListenExports.cancel(context, bookId)
        }
    }

    override suspend fun open(uri: String): Boolean = io { ExportStart.openFile(context, Uri.parse(uri)) }

    override suspend fun openFolder(uri: String): Boolean = io { ExportStart.openFolder(context, Uri.parse(uri)) }

    override fun events(): Flow<ExportEvent> = listenerFlow { send ->
        val stops = listOf(ExportKind.Mp3 to Mp3Exports.live, ExportKind.M4b to M4bExports.live, ExportKind.Audiobook to ListenExports.live).map { (kind, live) ->
            live.listen { json -> ExportJson.event(json, kind)?.let(send) }
        }
        ({ stops.forEach { it() } })
    }

    override suspend fun running(): List<ExportEvent> = io { ExportJobs.running(context).mapNotNull { ExportJson.event(it) } }
}
