package vn.abook.player.ui.export

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import vn.abook.player.ui.data.ListenBook
import java.util.concurrent.ConcurrentHashMap
import kotlin.coroutines.resume

/** Màn Xuất của MỘT cuốn: mọi thứ màn cần vẽ. Đổi hiếm (đổi tuỳ chọn, đổi pha) - tiến độ chạy theo nhịp ở [ExportState.progress]. */
@Immutable
data class ExportUi(
    val loaded: Boolean = false,
    val format: ExportFormat = ExportFormat.Mp3,
    val music: ExportMusic = ExportMusic(),
    /** Ô "Kèm nhạc nền" người dùng chọn (chỉ có nghĩa khi [music] có sẵn). */
    val withMusic: Boolean = false,
    val history: List<PastExport> = emptyList(),
    /** MP3 mà có chương đã đổi từ lần xuất trước: chỉ xuất các chương ấy (mặc định) hay cả cuốn. */
    val onlyChanged: Boolean = true,
    /** Tên thư mục MP3 đã nhớ; null = chưa chọn. */
    val folder: String? = null,
    val voice: ExportVoice? = null,
    val voiceChecked: Boolean = false,
    val plan: AudiobookPlan? = null,
    val planError: String = "",
    val background: BackgroundView? = null,
    /** Câu lỗi tại chỗ của việc vừa bấm (chưa bắt đầu được, không mở được kết quả). */
    val problem: String = "",
    val phase: ExportPhase = ExportPhase.Idle,
) {
    /** Các chương MP3 đã đổi từ lần xuất trước (gộp mọi bản MP3 của cuốn). */
    val changedChapters: List<Int> get() = history.filter { it.kind == ExportKind.Mp3 }.flatMap { it.changed }.distinct().sorted()

    /** Hỏi "cả cuốn hay chỉ chương đã đổi" khi nào: MP3 và có chương đã đổi. */
    val askScope: Boolean get() = format == ExportFormat.Mp3 && changedChapters.isNotEmpty()

    /** Ô nhạc hiện ra khi cuốn có kế hoạch nhạc. */
    val musicOn: Boolean get() = music.available && withMusic
}

/**
 * Trạng thái sống của màn Xuất, một holder cho cả tiến trình: việc xuất chạy ở WorkManager nên sống lâu hơn màn, và holder này nghe tin của nó từ lúc dựng
 * (rời màn rồi quay lại vẫn thấy tiến độ; xong lúc bạn đi vắng thì quay lại thấy kết quả). Màn chỉ vẽ [ui] / [progress] và gọi hàm ở đây; mọi việc với lõi đi
 * qua [ExportSource]. Tiến độ là luồng riêng để màn đọc nó ở lá, không dựng lại cả trang mỗi nhịp.
 */
@Stable
class ExportState(
    private val source: ExportSource,
    private val scope: CoroutineScope,
    private val links: ExportLinks = ExportLinks(),
) {
    private val uis = ConcurrentHashMap<String, MutableStateFlow<ExportUi>>()
    private val progresses = ConcurrentHashMap<String, MutableStateFlow<ExportProgress>>()
    private val hints = ConcurrentHashMap<String, MutableStateFlow<String?>>()
    private val plans = ConcurrentHashMap<String, Job>()

    /** Mã các lượt đã báo xong / dừng / lỗi (vài chục lượt gần nhất): tin muộn của chúng, hay bản chụp việc đang chạy cũ, không dựng lại thanh tiến độ. */
    private val ended = object : LinkedHashSet<String>() {
        override fun add(element: String): Boolean = super.add(element).also { if (size > 64) remove(first()) }
    }

    init {
        scope.launch { source.events().collect(::onEvent) }
        scope.launch { runCatching { source.running() }.getOrDefault(emptyList()).forEach(::onEvent) }
    }

    private fun flow(bookId: String) = uis.getOrPut(bookId) { MutableStateFlow(ExportUi()) }
    private fun progressFlow(bookId: String) = progresses.getOrPut(bookId) { MutableStateFlow(ExportProgress()) }

    fun ui(bookId: String): StateFlow<ExportUi> = flow(bookId)

    /** Tiến độ của lượt đang chạy; đọc ở lá (dòng chữ) và trong pha vẽ (thanh). */
    fun progress(bookId: String): StateFlow<ExportProgress> = progressFlow(bookId)

    /** Dòng phụ của hàng xuất trong menu của cuốn: "Đang xuất · 27%", "Đã xuất xong"; null khi không có gì để nói. */
    fun hint(bookId: String): StateFlow<String?> = hints.getOrPut(bookId) { MutableStateFlow(hintOf(bookId)) }

    private fun hintOf(bookId: String) = ExportText.menuHint(flow(bookId).value.phase, progressFlow(bookId).value.fraction)

    /** Dòng phụ nối lại mỗi khi pha hay tiến độ đổi (đổi ở [edit] / [setProgress]): không giữ việc nào chạy mãi cho mỗi cuốn từng mở menu. */
    private fun refreshHint(bookId: String) {
        hints[bookId]?.value = hintOf(bookId)
    }

    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Result.failure(error)
    }

    private fun message(error: Throwable?) = error?.message?.takeIf { it.isNotBlank() } ?: "Bạn hãy thử lại."

    private fun edit(bookId: String, change: (ExportUi) -> ExportUi) {
        flow(bookId).update(change)
        refreshHint(bookId)
    }

    private fun setProgress(bookId: String, value: ExportProgress) {
        progressFlow(bookId).value = value
        refreshHint(bookId)
    }

    // ---- tin của lõi ----------------------------------------------------------------------------------------------------

    private fun onEvent(event: ExportEvent) {
        if (event.bookId.isEmpty()) return
        if (event.ended) ended.add(event.run) else if (event.run in ended) return
        val phase = flow(event.bookId).value.phase
        // Lượt cũ (bị thay bằng lượt mới) báo muộn: không đè lên lượt mới.
        if (phase is ExportPhase.Running && phase.run != event.run) return
        when {
            event.finished -> finish(event, ExportPhase.Done(ExportText.finished(event)))
            event.stopped -> finish(event, ExportPhase.Stopped(event.kind, ExportText.stoppedNote(event)))
            event.error != null -> finish(event, ExportPhase.Failed(event.kind, event.error))
            else -> {
                val running = phase as? ExportPhase.Running
                if (running == null || !running.stopping) setProgress(event.bookId, ExportText.progress(event))
                if (running == null) edit(event.bookId) { it.copy(phase = ExportPhase.Running(event.kind, event.run, folder = event.folder), problem = "") }
                else if (running.folder == null && event.folder != null) edit(event.bookId) { it.copy(phase = running.copy(folder = event.folder)) }
            }
        }
    }

    private fun finish(event: ExportEvent, phase: ExportPhase) {
        edit(event.bookId) { it.copy(phase = phase, problem = "") }
        scope.launch { loadHistory(event.bookId) }
    }

    // ---- mở màn ---------------------------------------------------------------------------------------------------------

    /** Vào màn: đọc tuỳ chọn của cuốn (nền, không chặn). Lần mở trước còn dang dở ở bước hỏi chỗ lưu thì coi như bỏ. */
    fun open(book: ListenBook, format: ExportFormat? = null) {
        edit(book.id) {
            val fresh = if (it.phase is ExportPhase.Starting) it.copy(phase = ExportPhase.Idle) else it
            // Vào từ hàng "Xuất MP3" / "Xuất M4B" của menu thì dạng file đã chọn sẵn.
            if (format != null && !book.textOnly && fresh.phase is ExportPhase.Idle) fresh.copy(format = format) else fresh
        }
        scope.launch { load(book) }
    }

    private suspend fun load(book: ListenBook) {
        coroutineScope {
            val history = async { attempt { source.history(book.id) } }
            val folder = async { attempt { source.folder() } }
            val background = async { attempt { source.background() } }
            val music = async { if (book.textOnly) null else attempt { source.music(book.id) } }
            val voice = async { if (book.textOnly) attempt { source.voice(book.id) } else null }
            val picked = voice.await()?.getOrNull()
            val state = music.await()?.getOrNull()
            val past = history.await()
            val tree = folder.await()
            val view = background.await().getOrNull()
            edit(book.id) {
                it.copy(
                    loaded = true, history = past.getOrDefault(it.history), folder = tree.getOrDefault(it.folder),
                    background = view, voice = picked ?: it.voice, voiceChecked = it.voiceChecked || book.textOnly,
                    music = state ?: it.music, withMusic = if (it.loaded) it.withMusic else state?.enabled ?: false,
                    // Sách chỉ có chữ chỉ có M4B: MP3 không có chỗ nào để chọn.
                    format = if (book.textOnly) ExportFormat.M4b else it.format,
                )
            }
        }
        if (book.textOnly) loadPlan(book)
    }

    private suspend fun loadHistory(bookId: String) {
        attempt { source.history(bookId) }.onSuccess { list -> edit(bookId) { it.copy(history = list) } }
    }

    /** Ước của sách nói theo giọng và ô nhạc hiện tại (chạy lại mỗi khi đổi ô nhạc; lượt cũ bị bỏ). */
    private fun loadPlan(book: ListenBook) {
        plans.remove(book.id)?.cancel()
        val ui = flow(book.id).value
        val voice = ui.voice ?: return
        edit(book.id) { it.copy(planError = "") }
        plans[book.id] = scope.launch {
            // Khác mặc định của cuốn thì hỏi ước theo lựa chọn ấy; bằng mặc định thì lượt ước đầu (máy tự theo công tắc) đã đúng.
            val asked = if (ui.plan != null && ui.withMusic != ui.music.enabled) ui.withMusic else null
            attempt { source.plan(book.id, voice.id, asked) }
                .onSuccess { plan ->
                    edit(book.id) {
                        it.copy(plan = plan, planError = "", music = plan.music, withMusic = if (it.plan == null) plan.music.enabled else it.withMusic && plan.music.available)
                    }
                }
                .onFailure { error -> edit(book.id) { it.copy(plan = null, planError = message(error)) } }
        }
    }

    /** Quay lại từ Cài đặt Android: đọc lại việc ABook đã được chạy nền chưa. */
    fun refreshBackground(bookId: String) {
        scope.launch { attempt { source.background() }.onSuccess { view -> edit(bookId) { it.copy(background = view) } } }
    }

    /** Rời màn: kết quả (xong, dừng, lỗi) đã xem rồi thì lần sau vào là tuỳ chọn mới; việc đang chạy thì sống tiếp. */
    fun leave(bookId: String) {
        edit(bookId) { if (it.phase is ExportPhase.Done || it.phase is ExportPhase.Stopped || it.phase is ExportPhase.Failed) it.copy(phase = ExportPhase.Idle, problem = "") else it.copy(problem = "") }
    }

    // ---- tuỳ chọn -------------------------------------------------------------------------------------------------------

    fun setFormat(bookId: String, format: ExportFormat) = edit(bookId) { it.copy(format = format, problem = "") }

    fun setOnlyChanged(bookId: String, only: Boolean) = edit(bookId) { it.copy(onlyChanged = only) }

    fun setMusic(book: ListenBook, on: Boolean) {
        edit(book.id) { it.copy(withMusic = on) }
        if (book.textOnly) loadPlan(book)
    }

    /** Chạm hàng "Nơi lưu" của MP3: bộ chọn thư mục của hệ thống; chọn xong thì nhớ cho các lần sau. */
    fun chooseFolder(bookId: String) {
        links.pickFolder { tree -> if (tree != null) scope.launch { keepFolder(bookId, tree) } }
    }

    private suspend fun keepFolder(bookId: String, tree: String): Boolean {
        val result = attempt { source.keepFolder(tree) }
        result.onSuccess { name -> edit(bookId) { it.copy(folder = name, problem = "") } }
        result.onFailure { error -> edit(bookId) { it.copy(problem = message(error)) } }
        return result.isSuccess
    }

    fun openBackgroundSettings() = links.openAppSettings()

    // ---- bắt đầu, dừng --------------------------------------------------------------------------------------------------

    private suspend fun pick(): String? = suspendCancellableCoroutine { wait -> links.pickFolder { wait.resume(it) } }

    private suspend fun create(title: String): String? = suspendCancellableCoroutine { wait -> links.createFile(title) { wait.resume(it) } }

    /**
     * Bắt đầu xuất theo tuỳ chọn hiện tại. MP3: thư mục đã nhớ (chưa có thì hỏi trước); M4B và sách nói: hệ thống hỏi tên và chỗ lưu file (mỗi lần).
     * Không bắt đầu được (sách chưa có gì để xuất, không ghi được chỗ đã chọn) thì ở lại tuỳ chọn kèm câu lỗi tại chỗ; huỷ ở bộ chọn thì không có gì xảy ra.
     */
    fun start(book: ListenBook) {
        val now = flow(book.id).value
        if (now.phase !is ExportPhase.Idle && now.phase !is ExportPhase.Stopped && now.phase !is ExportPhase.Failed) return
        edit(book.id) { it.copy(phase = ExportPhase.Starting, problem = "") }
        scope.launch {
            try {
                val started = begin(book, now)
                if (started == null) {
                    edit(book.id) { it.copy(phase = ExportPhase.Idle) }
                    return@launch
                }
                val kind = now.format.kind(book.textOnly)
                // Tin của lượt có thể tới trước lời đáp này: đã chạy (Running) hay đã xong / dừng / lỗi thì giữ đúng điều tin ấy nói. Idle: bạn vừa
                // vào lại màn ([open] bỏ bước hỏi chỗ lưu) trong lúc lõi đang nhận việc.
                val phase = flow(book.id).value.phase
                if ((phase is ExportPhase.Starting || phase is ExportPhase.Idle) && started.run !in ended) {
                    // Sách chỉ có chữ không có số chương nghe được: số chương đọc là của bản ước.
                    val chapters = started.chapters ?: now.plan?.chapters?.takeIf { it > 0 } ?: book.chaptersAvailable.takeIf { it > 0 } ?: book.chaptersTotal
                    setProgress(book.id, ExportText.starting(kind, chapters))
                    edit(book.id) { it.copy(phase = ExportPhase.Running(kind, started.run, folder = started.folder), problem = "") }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                edit(book.id) { it.copy(phase = ExportPhase.Idle, problem = message(error)) }
                if (now.format == ExportFormat.Mp3 && !book.textOnly) attempt { source.folder() }.onSuccess { name -> edit(book.id) { it.copy(folder = name) } }
            }
        }
    }

    /** Một lượt bắt đầu; null = bạn huỷ ở bộ chọn của hệ thống. */
    private suspend fun begin(book: ListenBook, ui: ExportUi): Started? {
        val music = ui.musicOn
        return when {
            book.textOnly -> {
                val voice = ui.voice ?: throw ExportFailure("Máy chưa có giọng đọc nào - tải giọng ở Cài đặt rồi quay lại.")
                val file = create(source.fileTitle(book, ExportKind.Audiobook)) ?: return null
                source.startAudiobook(book, voice.id, file, music)
            }
            ui.format == ExportFormat.M4b -> {
                val file = create(source.fileTitle(book, ExportKind.M4b)) ?: return null
                source.startM4b(book, file, music)
            }
            else -> {
                source.fileTitle(book, ExportKind.Mp3) // sách không có gì để xuất thì từ chối TRƯỚC khi hỏi thư mục
                if (ui.folder == null) {
                    val tree = pick() ?: return null
                    if (!keepFolder(book.id, tree)) return null
                }
                source.startMp3(book, ui.changedChapters.takeIf { ui.askScope && ui.onlyChanged }, music)
            }
        }
    }

    /** "Dừng": lõi dừng ở chỗ an toàn kế rồi báo; lúc chờ, màn nói "Đang dừng". */
    fun stop(book: ListenBook) {
        val running = flow(book.id).value.phase as? ExportPhase.Running ?: return
        if (running.stopping) return
        edit(book.id) { it.copy(phase = running.copy(stopping = true)) }
        setProgress(book.id, ExportProgress("Đang dừng", "Đang dừng", progressFlow(book.id).value.fraction))
        scope.launch {
            attempt { source.cancel(running.kind, book.id) }.onFailure { error ->
                edit(book.id) { it.copy(phase = running.copy(stopping = false), problem = message(error)) }
            }
        }
    }

    // ---- kết quả --------------------------------------------------------------------------------------------------------

    /** "Mở": file M4B / sách nói bằng app nghe sách nói của máy. */
    fun openFile(bookId: String, uri: String) {
        scope.launch {
            if (!source.open(uri)) edit(bookId) { it.copy(problem = "Chưa mở được từ đây - mở file bằng app Tệp") }
        }
    }

    /** "Mở thư mục": thư mục MP3 bằng app Tệp. */
    fun openFolder(bookId: String, uri: String, folder: String? = null) {
        scope.launch {
            if (!source.openFolder(uri)) edit(bookId) { it.copy(problem = ExportText.noFolderOpener(folder)) }
        }
    }

    /** "Gửi": bảng chia sẻ của hệ thống với file vừa xuất. */
    fun share(bookId: String, uri: String, name: String) {
        if (!links.share(uri, name)) edit(bookId) { it.copy(problem = "Chưa gửi được từ đây - mở file bằng app Tệp") }
    }
}
