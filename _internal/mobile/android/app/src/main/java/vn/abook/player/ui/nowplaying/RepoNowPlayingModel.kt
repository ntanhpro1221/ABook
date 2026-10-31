package vn.abook.player.ui.nowplaying

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.State
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.music.MusicState
import vn.abook.player.ui.data.PrepareState
import vn.abook.player.ui.voice.VoiceState

/** Where Read-along text and the installed voices come from (off the main thread inside); real: [AndroidReadAlongSource]. */
interface ReadAlongSource {
    /** Paragraphs of one chapter. Throws a listener-readable message when the text is not on this device and cannot be fetched. */
    suspend fun paragraphs(bookId: String, chapter: PlayerChapter): List<ReadParagraph>
    suspend fun voices(): List<PlayerVoice>

    object None : ReadAlongSource {
        override suspend fun paragraphs(bookId: String, chapter: PlayerChapter): List<ReadParagraph> = emptyList()
        override suspend fun voices(): List<PlayerVoice> = emptyList()
    }
}

/**
 * The window's model on top of the ONE player source: [PlayerRepo] is the only `Playback` listener and the only owner of the clock, so what is here is
 * a mapping of its immutable snapshot (once per snapshot, never per tick), commands that go through the repo to the core, and the window's own extras
 * (installed voices, the "Về chỗ cũ" chip, Read-along text).
 */
@Stable
class RepoNowPlayingModel(
    private val repo: PlayerRepo,
    private val scope: CoroutineScope,
    private val source: ReadAlongSource = ReadAlongSource.None,
    override val music: MusicState? = null,
    override val voice: VoiceState? = null,
    private val options: () -> SleepOptions = { SleepOptions() },
    /** Thư viện lúc này: "Đã nghe hết ..." mời tập kế / cuốn khác, và hỏi khi máy khác đã nghe xa hơn. */
    private val books: StateFlow<List<ListenBook>> = MutableStateFlow(emptyList()),
    private val clockMs: () -> Long = System::currentTimeMillis,
    override val prepare: PrepareState? = null,
    private val night: vn.abook.player.ui.data.NightState? = null,
) : NowPlayingModel {
    override val hadNight: Boolean get() = night?.had == true

    @Immutable
    private data class Place(val bookId: String, val chapterId: Int, val ms: Long)

    @Immutable
    private data class Extras(val voices: List<PlayerVoice> = emptyList(), val place: Place? = null, val serial: Int = 0)

    private val extras = MutableStateFlow(Extras())
    override val state: StateFlow<NowPlayingState> =
        combine(repo.state, extras) { player, extra ->
            nowPlayingState(player, extra.voices, extra.place?.bookId == player.bookId && player.bookId.isNotEmpty(), extra.serial)
        }.stateIn(scope, SharingStarted.Eagerly, nowPlayingState(repo.state.value, emptyList(), false, 0))

    private val text = MutableStateFlow(ReadAlongState())
    override val readAlong = text.asStateFlow()

    override val position = object : PlayerPosition {
        override val milliseconds: State<Long> get() = repo.clock.positionMs
        override val sleepRemainingMs: State<Long> get() = repo.clock.sleepRemainingMs
        override fun sample() = repo.sampleClock()
    }

    private var textRequested = false
    private var textJob: Job? = null

    private val noteFlow = MutableStateFlow<PlayerNote?>(null)
    override val note: StateFlow<PlayerNote?> = noteFlow.asStateFlow()
    private var noteDo: (() -> Unit)? = null
    private var noteSerial = 0

    private fun say(text: String, action: String? = null, lifeMs: Long = 6_000, then: (() -> Unit)? = null) {
        noteDo = then
        noteFlow.value = PlayerNote(text, action, ++noteSerial, lifeMs)
    }

    override fun noteAction() {
        noteDo?.invoke()
        noteFlow.value = null
        noteDo = null
    }

    override fun dismissNote(serial: Int) {
        if (noteFlow.value?.serial == serial) { noteFlow.value = null; noteDo = null }
    }

    override fun endChoices(): PlayerEnd.Choices = PlayerEnd.choices(books.value, repo.state.value.bookId, extras.value.voices.isNotEmpty())
    override fun listen(bookId: String) = repo.playNow(bookId)
    override fun restart() {
        val first = repo.state.value.chapters.firstOrNull() ?: return
        repo.jumpTo(first.id, 0.0)
        repo.play()
    }

    /** Lúc cuốn này được nạp ở đây (mili giây): chỗ nghe thư viện ghi SAU đó là của máy khác. */
    private var loadedBook = ""
    private var loadedAt = 0L
    private var askedAt = ""
    private var continued = ""

    private fun checkElsewhere(list: List<ListenBook>) {
        val now = repo.state.value
        if (now.bookId.isEmpty() || now.bookId != loadedBook) return
        val last = list.firstOrNull { it.id == now.bookId }?.state?.last ?: return
        val key = "${now.bookId}:${last.at}"
        if (askedAt == key) return
        val here = repo.positionMs() / 1000.0
        if (!PlayerText.newerElsewhere(last.chapterId, last.seconds, last.at, loadedAt, now.chapterId, here)) return
        val chapter = now.chapters.firstOrNull { it.id == last.chapterId } ?: return
        askedAt = key
        say(PlayerText.elsewhereLine(chapter.title, last.seconds), PlayerText.ELSEWHERE_ACTION, lifeMs = 20_000) { repo.jumpTo(last.chapterId, last.seconds) }
    }

    /** Hết một PHẦN của cùng cuốn ("Làm tiếp cuốn này"): nghe nối sang phần sau, từ chỗ nghe tiếp của nó. Tập khác của một bộ thì chỉ mời (thông báo cuối). */
    private fun continueIntoNextPart() {
        val now = repo.state.value
        if (!now.ended || !now.whole || continued == now.bookId) return
        val part = PlayerEnd.continuingPart(PlayerEnd.nextVolume(books.value, now.bookId)) ?: return
        continued = now.bookId
        say(PlayerText.continueLine(part.title))
        repo.playNow(part.id)
    }

    init {
        scope.launch {
            repo.state.map { it.bookId }.distinctUntilChanged().collect { id -> loadedBook = id; loadedAt = clockMs(); askedAt = "" }
        }
        scope.launch { books.collect { list -> checkElsewhere(list) } }
        scope.launch { repo.state.map { it.ended }.distinctUntilChanged().collect { continueIntoNextPart() } }
        // Another book: the text on screen is the old one's. Read-along text itself is reloaded by the window (it keys on book + chapter).
        scope.launch {
            repo.state.map { it.bookId }.distinctUntilChanged().drop(1).collect { book -> text.value = ReadAlongState(bookId = book) }
        }
        // The engine pushes "state" when newly streamed words / durations arrive: refresh the open text. Clock ticks never reach here.
        scope.launch {
            repo.events.collect { kind -> if (textRequested && kind in TEXT_EVENTS) requestTextRefresh() }
        }
    }

    private fun rememberPlace() {
        val now = repo.state.value
        val chapter = now.chapterId ?: return
        extras.update { it.copy(place = Place(now.bookId, chapter, repo.positionMs()), serial = it.serial + 1) }
    }

    override fun toggle() = repo.toggle()
    override fun skip(seconds: Int) { rememberPlace(); repo.skip(seconds.toDouble()) }
    override fun seek(milliseconds: Long) { rememberPlace(); repo.seekTo(milliseconds.coerceAtLeast(0) / 1000.0) }
    override fun jump(chapterId: Int) { rememberPlace(); repo.jumpTo(chapterId, 0.0) }
    override fun next() { rememberPlace(); repo.next() }
    override fun previous() { rememberPlace(); repo.previous() }
    override fun setRate(rate: Double) { if (rate in PlayerLabels.rates) repo.setRate(rate) }

    override fun setSleep(kind: SleepKind, minutes: Int) {
        when (kind) {
            SleepKind.Off -> repo.setSleep("off")
            SleepKind.Chapter -> repo.setSleep("chapter")
            SleepKind.Minutes -> if (minutes in PlayerLabels.sleepMinutes) repo.setSleep("minutes", minutes)
        }
    }

    override val sleepOptions: SleepOptions get() = options()
    override fun extendSleep() = repo.extendSleep()

    override fun setVoice(id: String) {
        if (extras.value.voices.none { it.id == id && !it.online }) return
        repo.setVoice(id)
    }

    override suspend fun loadVoices() {
        val voices = source.voices()
        extras.update { it.copy(voices = voices) }
    }

    override fun setReadAlongActive(active: Boolean) {
        textRequested = active
        if (!active) textJob?.cancel()
    }

    override fun returnToPreviousPlace() {
        val place = extras.value.place ?: return
        extras.update { it.copy(place = null) }
        repo.jumpTo(place.chapterId, place.ms / 1000.0)
    }

    private fun requestTextRefresh() {
        textJob?.cancel()
        textJob = scope.launch { loadReadAlong() }
    }

    override suspend fun loadReadAlong() {
        textRequested = true
        val snapshot = state.value
        val chapter = snapshot.chapters.firstOrNull { it.id == snapshot.chapterId } ?: return
        val book = snapshot.bookId
        val same = text.value.bookId == book && text.value.chapterId == chapter.id
        if (!same || text.value.paragraphs.isEmpty()) text.value = ReadAlongState(book, chapter.id, loading = true)
        try {
            val paragraphs = source.paragraphs(book, chapter)
            val now = state.value
            if (now.bookId == book && now.chapterId == chapter.id) {
                text.value = ReadAlongState(book, chapter.id, paragraphs,
                    error = if (paragraphs.isEmpty()) "Chương chưa có chữ. Bạn thử lại sau." else "")
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            val now = state.value
            if (now.bookId == book && now.chapterId == chapter.id)
                text.value = ReadAlongState(book, chapter.id, error = error.message?.takeIf { it.startsWith("Bạn cần") } ?: "Chưa tải được chữ. Bạn thử lại.")
        }
    }

    private companion object {
        val TEXT_EVENTS = setOf("state", "chapter", "record")
    }
}

@androidx.compose.runtime.Composable
fun rememberRepoNowPlaying(
    repo: PlayerRepo,
    source: ReadAlongSource = ReadAlongSource.None,
    music: MusicState? = null,
    voice: VoiceState? = null,
    books: StateFlow<List<ListenBook>> = androidx.compose.runtime.remember { MutableStateFlow(emptyList()) },
    prepare: PrepareState? = null,
    night: vn.abook.player.ui.data.NightState? = null,
): RepoNowPlayingModel {
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    // Mức hẹn giờ do lõi giữ (SleepTimer); chỉ đọc khi tấm Hẹn giờ / lời báo cần.
    val options = { SleepOptions((vn.abook.player.SleepTimer.fadeMs / 1000).toInt(), vn.abook.player.SleepTimer.extendMinutes) }
    return androidx.compose.runtime.remember(repo, source, music, voice, books, prepare, night) { RepoNowPlayingModel(repo, scope, source, music, voice, options, books, prepare = prepare, night = night) }
}
