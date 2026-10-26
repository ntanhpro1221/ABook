package vn.abook.player.ui.export

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.data.ListenBook

/**
 * Việc của màn Xuất với nguồn giả: tuỳ chọn, bắt đầu từng kiểu (MP3 / M4B / sách nói) với đúng thứ gửi cho lõi, tiến độ, Dừng, kết quả (xong, dừng, lỗi),
 * nối lại lượt đang chạy khi tiến trình dựng lại, và việc không bắt đầu được. Phạm vi chạy ngay (Unconfined) nên sau mỗi lời gọi trạng thái đã xong.
 */
class ExportStateTest {
    private val source = FakeExportSource()
    private var pickAnswer: String? = "content://tree/Music"
    private var picks = 0
    private var createAnswer: String? = "content://doc/Truyen.m4b"
    private val createTitles = ArrayList<String>()
    private var shareWorks = true
    private val shared = ArrayList<Pair<String, String>>()
    private var settings = 0

    private val book = ListenBook("b1", "Truyện thử", chaptersTotal = 12, chaptersAvailable = 12, duration = 8 * 3600.0)
    private val text = ListenBook("t1", "Sách chữ", chaptersTotal = 12, textOnly = true)

    private fun state() = ExportState(
        source, CoroutineScope(Dispatchers.Unconfined),
        ExportLinks(
            pickFolder = { result -> picks++; result(pickAnswer) },
            createFile = { title, result -> createTitles += title; result(createAnswer) },
            share = { uri, name -> shared += uri to name; shareWorks },
            openAppSettings = { settings++ },
        ),
    )

    private fun event(kind: ExportKind = ExportKind.Mp3, run: String = "run-1", bookId: String = "b1", block: ExportEvent.() -> ExportEvent = { this }) =
        ExportEvent(kind, bookId, run).block()

    private fun ExportState.phase(id: String = "b1") = ui(id).value.phase

    // ---- mở ----

    @Test
    fun `opening reads the options of the book`() {
        source.music = ExportMusic(available = true, enabled = true)
        source.folder = "Music"
        source.history = listOf(PastExport(ExportKind.Mp3, "x", listOf(2, 5)))
        val exports = state()
        exports.open(book)
        val ui = exports.ui("b1").value
        assertTrue(ui.loaded)
        assertTrue(ui.music.available)
        assertTrue("ô nhạc theo mặc định của cuốn", ui.withMusic)
        assertEquals("Music", ui.folder)
        assertEquals(listOf(2, 5), ui.changedChapters)
        assertTrue(ui.askScope)
        assertEquals(ExportPhase.Idle, ui.phase)
    }

    @Test
    fun `a text only book only has m4b, a voice and a plan`() {
        val exports = state()
        exports.open(text)
        val ui = exports.ui("t1").value
        assertEquals(ExportFormat.M4b, ui.format)
        assertEquals("Hoài My", ui.voice?.caption)
        assertEquals(12, ui.plan?.chapters)
        assertEquals(listOf(Triple("t1", "edge:vi-VN-HoaiMyNeural", null as Boolean?)), source.plans)
    }

    @Test
    fun `changing the music box asks for a new plan with that choice`() {
        source.plan = source.plan.copy(music = ExportMusic(available = true, enabled = true))
        val exports = state()
        exports.open(text)
        assertTrue(exports.ui("t1").value.withMusic)
        exports.setMusic(text, false)
        assertFalse(exports.ui("t1").value.withMusic)
        assertEquals(false, source.plans.last().third)
        exports.setMusic(text, true)
        assertNull("bằng mặc định của cuốn thì lượt ước đầu đã đúng", source.plans.last().third)
    }

    @Test
    fun `a plan that cannot be made is said in words`() {
        source.planError = "Sách chưa có chương nào có chữ để đọc"
        val exports = state()
        exports.open(text)
        assertEquals("Sách chưa có chương nào có chữ để đọc", exports.ui("t1").value.planError)
        assertNull(exports.ui("t1").value.plan)
    }

    // ---- bắt đầu ----

    @Test
    fun `mp3 goes into the remembered folder without asking`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        assertEquals(0, picks)
        assertEquals(listOf(FakeExportSource.Start(ExportKind.Mp3, "b1", null, false, null, null)), source.starts)
        val phase = exports.phase() as ExportPhase.Running
        assertEquals(ExportKind.Mp3, phase.kind)
        assertEquals("run-1", phase.run)
        assertEquals("Music/Truyện thử", phase.folder)
        assertEquals("Đang xuất", exports.hint("b1").value?.substringBefore(" ·"))
    }

    @Test
    fun `mp3 without a folder asks for one first and keeps it`() {
        val exports = state()
        exports.open(book)
        exports.start(book)
        assertEquals(1, picks)
        assertEquals(listOf("content://tree/Music"), source.keptFolders)
        assertEquals("Music", exports.ui("b1").value.folder)
        assertTrue(exports.phase() is ExportPhase.Running)
    }

    @Test
    fun `cancelling the folder picker starts nothing`() {
        pickAnswer = null
        val exports = state()
        exports.open(book)
        exports.start(book)
        assertEquals(ExportPhase.Idle, exports.phase())
        assertTrue(source.starts.isEmpty())
        assertEquals("", exports.ui("b1").value.problem)
    }

    @Test
    fun `choosing the folder from its row keeps it for next time`() {
        val exports = state()
        exports.open(book)
        exports.chooseFolder("b1")
        assertEquals("Music", exports.ui("b1").value.folder)
        assertEquals(ExportPhase.Idle, exports.phase())
    }

    @Test
    fun `only the changed chapters when asked, the whole book otherwise`() {
        source.folder = "Music"
        source.history = listOf(PastExport(ExportKind.Mp3, "x", listOf(5, 2)), PastExport(ExportKind.M4b, "y", listOf(9)))
        val exports = state()
        exports.open(book)
        exports.start(book)
        assertEquals(listOf(2, 5), source.starts.single().chapterIds)
        val again = state()
        again.open(book)
        again.setOnlyChanged("b1", false)
        source.starts.clear()
        again.start(book)
        assertNull(source.starts.single().chapterIds)
    }

    @Test
    fun `m4b asks the system for a file named after the book`() {
        val exports = state()
        exports.open(book)
        exports.setFormat("b1", ExportFormat.M4b)
        exports.start(book)
        assertEquals(listOf("Truyện thử"), createTitles)
        assertEquals(listOf(FakeExportSource.Start(ExportKind.M4b, "b1", null, false, "content://doc/Truyen.m4b", null)), source.starts)
        assertEquals(ExportKind.M4b, (exports.phase() as ExportPhase.Running).kind)
    }

    @Test
    fun `music is sent only when the book has it and the box is on`() {
        source.music = ExportMusic(available = true, enabled = true)
        val exports = state()
        exports.open(book)
        exports.setFormat("b1", ExportFormat.M4b)
        exports.start(book)
        assertTrue(source.starts.single().music)
        val off = state()
        off.open(book)
        off.setFormat("b1", ExportFormat.M4b)
        off.setMusic(book, false)
        source.starts.clear()
        off.start(book)
        assertFalse(source.starts.single().music)
    }

    @Test
    fun `an audiobook reads with the chosen voice into the file the system made`() {
        val exports = state()
        exports.open(text)
        exports.start(text)
        val start = source.starts.single()
        assertEquals(ExportKind.Audiobook, start.kind)
        assertEquals("edge:vi-VN-HoaiMyNeural", start.voice)
        assertEquals("content://doc/Truyen.m4b", start.file)
        assertEquals(ExportKind.Audiobook, (exports.phase("t1") as ExportPhase.Running).kind)
    }

    @Test
    fun `cancelling the file dialog starts nothing`() {
        createAnswer = null
        val exports = state()
        exports.open(book)
        exports.setFormat("b1", ExportFormat.M4b)
        exports.start(book)
        assertEquals(ExportPhase.Idle, exports.phase())
        assertTrue(source.starts.isEmpty())
    }

    @Test
    fun `a book with nothing to export is refused before any dialog`() {
        source.titleError = "Sách này chưa có chương nghe được"
        val exports = state()
        exports.open(book)
        exports.setFormat("b1", ExportFormat.M4b)
        exports.start(book)
        assertTrue(createTitles.isEmpty())
        assertEquals(ExportPhase.Idle, exports.phase())
        assertEquals("Sách này chưa có chương nghe được", exports.ui("b1").value.problem)
    }

    @Test
    fun `a start the core refuses stays on the options with the reason`() {
        source.folder = "Music"
        source.startError = "Không mở được thư mục đã chọn - chọn lại nơi lưu"
        val exports = state()
        exports.open(book)
        exports.start(book)
        assertEquals(ExportPhase.Idle, exports.phase())
        assertEquals("Không mở được thư mục đã chọn - chọn lại nơi lưu", exports.ui("b1").value.problem)
    }

    @Test
    fun `pressing start twice starts once`() {
        source.folder = "Music"
        source.startGate = CompletableDeferred()
        val exports = state()
        exports.open(book)
        exports.start(book)
        assertEquals(ExportPhase.Starting, exports.phase())
        exports.start(book)
        source.startGate!!.complete(Unit)
        assertEquals(1, source.starts.size)
    }

    @Test
    fun `a run that ends before the start returns keeps its result`() {
        // Việc nền hỏng ngay (mất quyền ghi thư mục): tin lỗi tới luồng chính trước lời đáp của lõi - màn không được kẹt ở "Đang xuất".
        source.folder = "Music"
        source.startGate = CompletableDeferred()
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(error = "Không ghi được vào thư mục đã chọn") })
        source.startGate!!.complete(Unit)
        assertEquals(ExportPhase.Failed(ExportKind.Mp3, "Không ghi được vào thư mục đã chọn"), exports.phase())
        assertEquals("Không xuất được", exports.hint("b1").value)
    }

    @Test
    fun `coming back while the core is still starting the run shows it running`() {
        source.folder = "Music"
        source.startGate = CompletableDeferred()
        val exports = state()
        exports.open(book)
        exports.start(book)
        exports.leave("b1")
        exports.open(book)
        source.startGate!!.complete(Unit)
        assertEquals("run-1", (exports.phase() as ExportPhase.Running).run)
    }

    @Test
    fun `a text only book says its chapters from the plan, not from a count it does not have`() {
        // Sách chỉ có chữ: chưa chương nào có audio nên chaptersAvailable / chaptersTotal có thể là 0; số chương đọc là của bản ước.
        val bare = ListenBook("t2", "Sách chữ", textOnly = true)
        val exports = state()
        exports.open(bare)
        exports.start(bare)
        assertEquals("Chương 1/12 · 0%", exports.progress("t2").value.text)
    }

    @Test
    fun `asking for a hint starts nothing that lives on`() {
        val job = kotlinx.coroutines.Job()
        val exports = ExportState(source, CoroutineScope(job + Dispatchers.Unconfined))
        val before = job.children.count()
        repeat(20) { exports.hint("b$it") }
        assertEquals("mỗi cuốn từng mở menu không giữ thêm việc nào chạy mãi", before, job.children.count())
    }

    @Test
    fun `the hint follows the phase and the progress of a book nobody is watching`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        val hint = exports.hint("b1")
        assertNull(hint.value)
        exports.start(book)
        assertEquals("Đang xuất", hint.value)
        source.events.tryEmit(event { copy(done = 6, total = 12) })
        assertEquals("Đang xuất · 50%", hint.value)
        source.events.tryEmit(event { copy(finished = true, files = 12, chaptersTotal = 12) })
        assertEquals("Đã xuất xong", hint.value)
        exports.leave("b1")
        assertNull(hint.value)
    }

    // ---- tiến độ, kết quả ----

    @Test
    fun `progress events move the bar and the words`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(done = 3, total = 12) })
        assertEquals("3/12 chương", exports.progress("b1").value.text)
        assertEquals(0.25f, exports.progress("b1").value.fraction!!, 0.001f)
        assertEquals("Đang xuất · 25%", exports.hint("b1").value)
    }

    @Test
    fun `a finished run offers the result and refreshes the past exports`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.history = listOf(PastExport(ExportKind.Mp3, "x", emptyList()))
        source.events.tryEmit(event { copy(finished = true, files = 12, chaptersTotal = 12, folder = "Music/Truyện thử", uri = "content://tree/Music/doc") })
        val done = exports.phase() as ExportPhase.Done
        assertEquals("Đã xuất 12 chương", done.result.title)
        assertEquals("content://tree/Music/doc", done.result.uri)
        assertEquals(1, exports.ui("b1").value.history.size)
        assertEquals("Đã xuất xong", exports.hint("b1").value)
    }

    @Test
    fun `a stopped run says what is left`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(stopped = true, files = 4) })
        val stopped = exports.phase() as ExportPhase.Stopped
        assertEquals("4 chương đã ghi", stopped.note)
    }

    @Test
    fun `an error from the worker is shown with its words`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(error = "Hết chỗ trống trên điện thoại hoặc ở nơi lưu - dọn bớt rồi xuất lại") })
        assertEquals(ExportPhase.Failed(ExportKind.Mp3, "Hết chỗ trống trên điện thoại hoặc ở nơi lưu - dọn bớt rồi xuất lại"), exports.phase())
        assertEquals("Không xuất được", exports.hint("b1").value)
    }

    @Test
    fun `try again after a failure starts the same options again`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(error = "Lỗi") })
        source.run = "run-2"
        exports.start(book)
        assertEquals(2, source.starts.size)
        assertEquals("run-2", (exports.phase() as ExportPhase.Running).run)
    }

    // ---- Dừng ----

    @Test
    fun `stop reaches the core for the kind that is running and waits for it to say`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        exports.stop(book)
        assertEquals(listOf(ExportKind.Mp3 to "b1"), source.cancels)
        assertTrue((exports.phase() as ExportPhase.Running).stopping)
        assertEquals("Đang dừng", exports.progress("b1").value.text)
        // Tin tiến độ muộn không đè lên "Đang dừng".
        source.events.tryEmit(event { copy(done = 5, total = 12) })
        assertEquals("Đang dừng", exports.progress("b1").value.text)
        exports.stop(book)
        assertEquals("bấm lần hai không dừng hai lần", 1, source.cancels.size)
        source.events.tryEmit(event { copy(stopped = true, files = 5) })
        assertTrue(exports.phase() is ExportPhase.Stopped)
    }

    // ---- rời màn, quay lại ----

    @Test
    fun `leaving the screen does not stop the run, and coming back shows it`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(done = 6, total = 12) })
        exports.leave("b1")
        assertTrue(exports.phase() is ExportPhase.Running)
        exports.open(book)
        assertTrue(exports.phase() is ExportPhase.Running)
        assertEquals("6/12 chương", exports.progress("b1").value.text)
    }

    @Test
    fun `a run that finished while away shows its result, and leaving after seeing it clears it`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        exports.leave("b1")
        source.events.tryEmit(event { copy(finished = true, files = 12, chaptersTotal = 12) })
        exports.open(book)
        assertTrue(exports.phase() is ExportPhase.Done)
        exports.leave("b1")
        assertEquals(ExportPhase.Idle, exports.phase())
        assertNull(exports.hint("b1").value)
    }

    @Test
    fun `a process that comes back mid run picks the run up again`() {
        source.live = listOf(event(ExportKind.M4b, "run-9") { copy(done = 4, total = 12, percent = 33) })
        val exports = state()
        val phase = exports.phase() as ExportPhase.Running
        assertEquals("run-9", phase.run)
        assertEquals(ExportKind.M4b, phase.kind)
        assertEquals("4/12 chương · 33%", exports.progress("b1").value.text)
    }

    @Test
    fun `a rejoined mp3 run keeps its folder`() {
        source.live = listOf(event(ExportKind.Mp3, "run-9") { copy(folder = "Music/Truyện thử") })
        val exports = state()
        assertEquals("Music/Truyện thử", (exports.phase() as ExportPhase.Running).folder)
    }

    @Test
    fun `late news of a finished run and news of an older run are ignored`() {
        source.folder = "Music"
        val exports = state()
        exports.open(book)
        exports.start(book)
        source.events.tryEmit(event { copy(finished = true, files = 12, chaptersTotal = 12) })
        exports.leave("b1")
        source.events.tryEmit(event { copy(done = 3, total = 12) })
        assertEquals("tin muộn của lượt đã xong không dựng lại tiến độ", ExportPhase.Idle, exports.phase())
        source.run = "run-2"
        exports.start(book)
        source.events.tryEmit(event(run = "run-0") { copy(stopped = true) })
        assertEquals("run-2", (exports.phase() as ExportPhase.Running).run)
    }

    // ---- kết quả: mở, gửi ----

    @Test
    fun `open and share reach the system, and a failure is said at the spot`() {
        val exports = state()
        exports.open(book)
        exports.openFile("b1", "content://doc/a.m4b")
        assertEquals(listOf("content://doc/a.m4b"), source.opened)
        assertEquals("", exports.ui("b1").value.problem)
        source.openWorks = false
        exports.openFile("b1", "content://doc/a.m4b")
        assertEquals("Không mở được từ đây - mở file bằng app Tệp", exports.ui("b1").value.problem)
        exports.openFolder("b1", "content://tree/Music")
        assertEquals("Máy không mở được thư mục - mở app Tệp rồi vào thư mục đã chọn", exports.ui("b1").value.problem)
        exports.openFolder("b1", "content://tree/Music", "Music/Sách")
        assertEquals("Máy không mở được thư mục - mở app Tệp rồi vào Music/Sách", exports.ui("b1").value.problem)
        exports.share("b1", "content://doc/a.m4b", "Truyện thử")
        assertEquals(listOf("content://doc/a.m4b" to "Truyện thử"), shared)
        shareWorks = false
        exports.share("b1", "content://doc/a.m4b", "Truyện thử")
        assertEquals("Không gửi được từ đây - mở file bằng app Tệp", exports.ui("b1").value.problem)
    }

    @Test
    fun `the background note opens the app settings of ABook`() {
        source.background = BackgroundView("OPPO", allowed = false)
        val exports = state()
        exports.open(book)
        assertEquals(false, exports.ui("b1").value.background?.allowed)
        exports.openBackgroundSettings()
        assertEquals(1, settings)
        source.background = BackgroundView("OPPO", allowed = true)
        exports.refreshBackground("b1")
        assertEquals(true, exports.ui("b1").value.background?.allowed)
        assertNotNull(exports.ui("b1").value.background)
    }
}
