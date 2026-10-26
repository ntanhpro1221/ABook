package vn.abook.player.ui.export

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import vn.abook.player.ui.data.ListenBook

/** Nguồn Xuất giả: kho trong bộ nhớ, ghi lại mọi việc màn đã bảo lõi làm để test so lời gọi. */
class FakeExportSource : ExportSource {
    var music = ExportMusic()
    var history = emptyList<PastExport>()
    var folder: String? = null
    var voice: ExportVoice? = ExportVoice("edge:vi-VN-HoaiMyNeural", "Hoài My", "edge", online = true)
    var plan = AudiobookPlan(chapters = 12, audioSeconds = 8 * 3600, secondsEstimate = 2 * 3600 + 600, readyChapters = 0, readySeconds = 0, bytes = 900L * 1024 * 1024, rereads = 0, music = ExportMusic())
    var planError: String? = null
    var background: BackgroundView? = BackgroundView("OPPO", allowed = true)

    val keptFolders = ArrayList<String>()
    val titles = ArrayList<Pair<String, ExportKind>>()
    var titleError: String? = null

    /** Mỗi lần bắt đầu: kiểu, chương, tuỳ chọn. */
    data class Start(val kind: ExportKind, val bookId: String, val chapterIds: List<Int>?, val music: Boolean, val file: String?, val voice: String?)

    val starts = ArrayList<Start>()
    var startError: String? = null
    var startGate: CompletableDeferred<Unit>? = null
    var run = "run-1"
    val plans = ArrayList<Triple<String, String, Boolean?>>()
    val cancels = ArrayList<Pair<ExportKind, String>>()
    val opened = ArrayList<String>()
    val openedFolders = ArrayList<String>()
    var openWorks = true
    val events = MutableSharedFlow<ExportEvent>(extraBufferCapacity = 64)
    var live = emptyList<ExportEvent>()

    override suspend fun music(bookId: String) = music
    override suspend fun history(bookId: String) = history
    override suspend fun folder() = folder
    override suspend fun voice(bookId: String) = voice
    override suspend fun background() = background

    override suspend fun plan(bookId: String, voice: String, music: Boolean?): AudiobookPlan {
        plans += Triple(bookId, voice, music)
        planError?.let { throw ExportFailure(it) }
        return plan
    }

    override suspend fun keepFolder(tree: String): String {
        keptFolders += tree
        folder = tree.substringAfterLast('/')
        return folder!!
    }

    override suspend fun fileTitle(book: ListenBook, kind: ExportKind): String {
        titles += book.id to kind
        titleError?.let { throw ExportFailure(it) }
        return book.title
    }

    private suspend fun start(start: Start, chapters: Int?, name: String?, folder: String?): Started {
        startGate?.await()
        startError?.let { throw ExportFailure(it) }
        starts += start
        return Started(run, folder = folder, name = name, chapters = chapters)
    }

    override suspend fun startMp3(book: ListenBook, chapterIds: List<Int>?, music: Boolean) =
        start(Start(ExportKind.Mp3, book.id, chapterIds, music, null, null), chapterIds?.size ?: book.chaptersAvailable, null, "Music/${book.title}")

    override suspend fun startM4b(book: ListenBook, file: String, music: Boolean) =
        start(Start(ExportKind.M4b, book.id, null, music, file, null), book.chaptersAvailable, "${book.title}.m4b", null)

    override suspend fun startAudiobook(book: ListenBook, voice: String, file: String, music: Boolean) =
        start(Start(ExportKind.Audiobook, book.id, null, music, file, voice), null, "${book.title}.m4b", null)

    override suspend fun cancel(kind: ExportKind, bookId: String) {
        cancels += kind to bookId
    }

    override suspend fun open(uri: String): Boolean {
        opened += uri
        return openWorks
    }

    override suspend fun openFolder(uri: String): Boolean {
        openedFolders += uri
        return openWorks
    }

    override fun events(): Flow<ExportEvent> = events

    override suspend fun running() = live
}
