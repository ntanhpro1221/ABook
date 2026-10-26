package vn.abook.player.ui.nowplaying

import android.content.Context
import android.media.AudioManager
import android.os.SystemClock
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableLongStateOf
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.ChapterText
import vn.abook.player.MusicBed
import vn.abook.player.Playback
import vn.abook.player.Playlists
import vn.abook.player.SleepTimer
import vn.abook.player.Store
import vn.abook.player.readaloud.ReadAloud

/** Temporary direct adapter. Replace with PlayerRepo at merge; the screen only knows NowPlayingModel. */
@Stable
class PlaybackNowPlayingModel(private val context: Context, private val scope: CoroutineScope) : NowPlayingModel {
    private val metadata = MutableStateFlow(NowPlayingState())
    override val state = metadata.asStateFlow()
    private val text = MutableStateFlow(ReadAlongState())
    override val readAlong = text.asStateFlow()
    private val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var attached = false
    private var coverJob: Job? = null
    private var textJob: Job? = null
    private var textRequested = false
    private var returnPlace: Pair<Int, Long>? = null
    private var cover: CoverRef? = null
    private var chapters = emptyList<PlayerChapter>()
    private var queue: List<Playback.Chapter>? = null
    private var currentBook = ""
    override val position = object : PlayerPosition {
        override val milliseconds = mutableLongStateOf(0)
        override val realtimeMs = mutableLongStateOf(SystemClock.elapsedRealtime())
        override fun sample() {
            milliseconds.longValue = Playback.positionMs
            realtimeMs.longValue = SystemClock.elapsedRealtime()
        }
    }

    private val listener: (JSONObject) -> Unit = { event ->
        position.sample()
        if (event.optString("kind") != "tick") refresh(event)
        // ReadAloud emits state when newly streamed words/durations arrive. Never reload on clock ticks.
        if (textRequested && event.optString("kind") in listOf("state", "chapter", "record")) requestTextRefresh()
    }

    suspend fun attach() {
        withContext(Dispatchers.IO) { Playback.init(context) }
        if (attached) return
        attached = true
        Playback.addListener(listener)
        refresh(Playback.state())
        position.sample()
    }

    fun detach() {
        Playback.removeListener(listener)
        attached = false
        coverJob?.cancel()
        textJob?.cancel()
    }

    private fun refresh(event: JSONObject) {
        val book = event.optString("bookId")
        if (book != currentBook) {
            currentBook = book
            cover = null
            returnPlace = null
            text.value = ReadAlongState(bookId = book)
            coverJob?.cancel()
            if (book.isNotEmpty()) coverJob = scope.launch {
                val loaded = withContext(Dispatchers.IO) {
                    Store.coverFile(book)?.takeIf { it.isFile }?.let { CoverRef(it.path, it.lastModified()) }
                }
                if (book == currentBook) { cover = loaded; refresh(Playback.state()) }
            }
        }
        if (queue !== Playback.chapters) {
            queue = Playback.chapters
            chapters = Playback.chapters.map { PlayerChapter(it.id, it.title, (it.duration * 1000).toLong(), it.text) }
        }
        val old = metadata.value
        val mapped = mapPlaybackState(event, chapters, cover, SystemClock.elapsedRealtime())
        // Only sleep events re-anchor its monotonic clock. Other metadata events don't invalidate it.
        metadata.value = mapped.copy(
            sleep = if (event.optString("kind") == "sleep" || old.bookId != book) mapped.sleep else old.sleep,
            musicEnabled = Playlists.autoEnabled,
            volume = audio.getStreamVolume(AudioManager.STREAM_MUSIC), maxVolume = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC),
            returnAvailable = returnPlace != null, voices = old.voices, voiceId = ReadAloud.voiceId,
        )
    }

    private fun rememberPlace() {
        Playback.currentChapter?.let { returnPlace = it.id to Playback.positionMs }
        metadata.value = metadata.value.copy(returnAvailable = returnPlace != null)
    }
    override fun toggle() { Playback.toggle() }
    override fun skip(seconds: Int) { rememberPlace(); Playback.skip(seconds.toDouble()) }
    override fun seek(milliseconds: Long) { rememberPlace(); Playback.seekTo(milliseconds.coerceAtLeast(0) / 1000.0) }
    override fun jump(chapterId: Int) { rememberPlace(); Playback.jumpTo(chapterId, 0.0) }
    override fun next() { rememberPlace(); Playback.next() }
    override fun previous() { rememberPlace(); Playback.previous() }
    override fun setRate(rate: Double) { if (rate in PlayerLabels.rates) Playback.setRate(rate) }
    override fun setSleep(kind: SleepKind, minutes: Int) {
        when (kind) {
            SleepKind.Off -> SleepTimer.cancel()
            SleepKind.Chapter -> SleepTimer.setEndOfChapter()
            SleepKind.Minutes -> if (minutes in PlayerLabels.sleepMinutes) SleepTimer.setMinutes(minutes)
        }
    }
    override fun setMusic(enabled: Boolean) {
        // This is the core's automatic scene music toggle (same as PlayerPlugin.configure.autoMusic).
        if (enabled != Playlists.autoEnabled) MusicBed.invalidate(Playback.bookId)
        Playlists.autoEnabled = enabled
        MusicBed.rememberAuto(enabled)
        metadata.value = metadata.value.copy(musicEnabled = enabled)
    }
    override fun setVolume(value: Int) {
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, value.coerceIn(0, state.value.maxVolume), 0)
        metadata.value = metadata.value.copy(volume = audio.getStreamVolume(AudioManager.STREAM_MUSIC))
    }
    override fun setVoice(id: String) {
        if (id !in state.value.voices.map { it.id }) return
        ReadAloud.chooseFor(Playback.bookId, id, Playback.recordId)
        metadata.value = metadata.value.copy(voiceId = id)
    }
    override suspend fun loadVoices() {
        // Online voices remain configured by the existing consent/settings flow; this picker exposes installed voices.
        val voices = withContext(Dispatchers.IO) {
            ReadAloud.voices(context).filter { !it.optBoolean("online") }.map { PlayerVoice(it.optString("id"), it.optString("name")) }
        }
        metadata.value = metadata.value.copy(voices = voices)
    }
    override fun setReadAlongActive(active: Boolean) {
        textRequested = active
        if (!active) textJob?.cancel()
    }
    override fun returnToPreviousPlace() {
        val place = returnPlace ?: return
        returnPlace = null
        Playback.jumpTo(place.first, place.second / 1000.0)
        metadata.value = metadata.value.copy(returnAvailable = false)
    }

    private fun requestTextRefresh() {
        textJob?.cancel()
        textJob = scope.launch { loadReadAlong() }
    }
    override suspend fun loadReadAlong() {
        textRequested = true
        val snapshot = state.value
        val chapter = chapters.firstOrNull { it.id == snapshot.chapterId } ?: return
        val book = snapshot.bookId
        val same = text.value.bookId == book && text.value.chapterId == chapter.id
        if (!same || text.value.paragraphs.isEmpty()) text.value = ReadAlongState(book, chapter.id, loading = true)
        try {
            val paragraphs = if (chapter.textPath.isNotEmpty()) {
                // Active chapter: use the engine's exact loaded paragraphs and virtual timeline, including live tail clips.
                val active = ReadAloud.script(book, chapter.id)
                withContext(Dispatchers.Default) { ReadAlongLookup.parse(active) }
            } else withContext(Dispatchers.IO) {
                val raw = ChapterText.read(context, book, "scripts/${chapter.id}.json")
                    ?: error("Bạn cần tải chữ của chương.")
                ReadAlongLookup.parse(JSONObject(raw))
            }
            if (state.value.bookId == book && state.value.chapterId == chapter.id) {
                text.value = ReadAlongState(book, chapter.id, paragraphs,
                    error = if (paragraphs.isEmpty()) "Chương chưa có chữ. Bạn thử lại sau." else "")
            }
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (error: Exception) {
            if (state.value.bookId == book && state.value.chapterId == chapter.id)
                text.value = ReadAlongState(book, chapter.id, error = "Chưa tải được chữ. Bạn thử lại.")
        }
    }
}
