package vn.abook.player.ui

import android.net.Uri
import android.os.Looper
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import vn.abook.player.AbookApplication
import vn.abook.player.BookFileImport
import vn.abook.player.BookFiles
import vn.abook.player.LibraryTree
import vn.abook.player.FakeExo
import vn.abook.player.PackageFixtures
import vn.abook.player.Playback
import vn.abook.player.Store
import vn.abook.player.ui.addbook.ImportItem
import vn.abook.player.ui.addbook.ImportRepo
import vn.abook.player.ui.data.PlaybackCore
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.LoadRequest
import java.io.File
import java.nio.file.Files

/**
 * Chỗ nghe sau khi THAY sách đang mở (lỗi ngoài đời: "Thay bằng file này" xong, trình phát và bảng chương vẫn giữ độ dài cũ tới khi app bị giết): sách nạp vào trình phát,
 * file thay qua đúng đường của app ([ImportRepo.replace] -> [BookFileImport]), rồi trạng thái của [PlayerRepo] phải có độ dài mới ngay, cùng chương, cùng giây,
 * đang phát vẫn phát, đang dừng vẫn dừng.
 */
// Paket ui (không phải vn.abook.player): Robolectric chạy TRƯỚC FastConnectTest trong cùng JVM làm hỏng TLS của JDK (Conscrypt chèn lên đầu), nên test Robolectric không được xếp trước gói net.
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ReplaceRefreshesPlayerTest {
    private val context get() = ApplicationProvider.getApplicationContext<AbookApplication>()
    private val exo = FakeExo()
    private lateinit var work: File
    private var booksBefore: Set<String> = emptySet()

    /** Thư mục sách của Store dùng chung trong cả JVM test: cuốn do test này nhập phải đi theo test, không để test khác thấy. */
    private fun booksDir() = Store.bookDir("probe").parentFile!!
    private val oldLengths = listOf(60.0, 120.0, 180.0)
    private val newLengths = listOf(62.5, 123.0, 180.0)

    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setUp() {
        Store.init(context)
        booksBefore = booksDir().list()?.toSet() ?: emptySet()
        work = Files.createTempDirectory("replace-refresh").toFile()
        field("appContext").set(Playback, context)
        Playback.player = exo.player
    }

    @After fun tearDown() {
        booksDir().listFiles()?.filter { it.name !in booksBefore }?.forEach { it.deleteRecursively() }
        work.deleteRecursively()
        field("bookId").set(Playback, "")
        field("chapters").set(Playback, emptyList<Playback.Chapter>())
        field("savedPlace").set(Playback, null)
        Playback.player = null
    }

    /** Một lần đóng gói của cùng một cuốn: `lengths` = độ dài từng chương trong book.json, `tag` đổi byte audio (cỡ khác nhau), `at` = giờ đóng gói. */
    private fun revision(name: String, lengths: List<Double>, tag: String, at: String): File {
        val chapters = JSONArray()
        val content = HashMap<String, ByteArray>()
        lengths.forEachIndexed { index, seconds ->
            chapters.put(PackageFixtures.chapter(index + 1, 0, "chapters/${index + 1}.mp3", seconds))
            content["chapters/${index + 1}.mp3"] = (tag + "-audio-".repeat(index + 1)).toByteArray()
            content["scripts/${index + 1}.json"] = "{}".toByteArray()
        }
        val book = JSONObject().put("title", "Your Story").put("sourceFingerprint", "same-source").put("audioUpdatedAt", at)
            .put("chaptersAvailable", lengths.size).put("chaptersTotal", lengths.size).put("chapters", chapters)
        return PackageFixtures.abook(work, name, 1, content, book, at)
    }

    /** Lõi phát chỉ-đọc cho [PlayerRepo]: đọc thẳng [Playback] (lệnh không cần ở đây). */
    private val core = object : PlaybackCore {
        override fun addListener(listener: (JSONObject) -> Unit) = Playback.addListener(listener)
        override fun removeListener(listener: (JSONObject) -> Unit) = Playback.removeListener(listener)
        override fun snapshot(): JSONObject = Playback.state()
        override fun play() = Playback.play()
        override fun pause() = Playback.pause()
        override fun close() = Playback.closeBook()
        override fun toggle() = Playback.toggle()
        override fun skip(deltaSeconds: Double) = Playback.skip(deltaSeconds)
        override fun seekTo(seconds: Double) = Playback.seekTo(seconds)
        override fun next() = Playback.next()
        override fun previous() = Playback.previous()
        override fun setRate(rate: Double) = Playback.setRate(rate)
        override fun jumpTo(chapterId: Int, seconds: Double) = Playback.jumpTo(chapterId, seconds)
        override fun positionMs(): Long = Playback.positionMs
        override fun chapters(): List<Playback.Chapter> = Playback.chapters
        override fun setSleep(mode: String, minutes: Int) = Unit
        override fun voiceId(): String = ""
        override fun setVoice(voiceId: String) = Unit
        override fun load(request: LoadRequest) = Unit
    }

    private fun repo() = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }

    /** Thay qua đúng đường của app (nhập chạy ở luồng IO); việc làm mới trình phát chạy ở luồng chính nên chờ hàng đợi chính xong. */
    private fun replaceWith(file: File) = runBlocking { ImportRepo(context).replace(ImportItem(1, Uri.fromFile(file).toString())) }
        .also { shadowOf(Looper.getMainLooper()).idle() }

    private fun load(id: String, chapter: Int, seconds: Double, playing: Boolean) {
        val manifest = Store.manifest(id)!!
        Playback.load(id, "Your Story", "", LibraryTree.chapters(manifest), chapter, seconds, 1.0, autoplay = playing)
    }

    private fun sheetLengths(repo: PlayerRepo) = repo.state.value.chapters.map { it.durationMs }

    @Test fun replacingThePlayingBookShowsTheNewLengthsAtTheSamePlaceAndKeepsPlaying() {
        val first = BookFileImport.importFile(revision("old.abook", oldLengths, "old", "2026-10-21T00:00:00Z"))
        load(first.id, chapter = 2, seconds = 100.0, playing = true)
        val repo = repo()
        assertEquals(oldLengths.map { Math.round(it * 1000) }, sheetLengths(repo))
        exo.position = 100_000
        assertTrue(exo.playWhenReady)
        val loads = exo.calls.count { it == "setMediaItems" }

        val replaced = replaceWith(revision("new.abook", newLengths, "newer", "2026-10-22T00:00:00Z"))

        assertEquals(first.id, replaced.bookId)
        assertEquals("the chapter sheet follows the new book without a restart", newLengths.map { Math.round(it * 1000) }, sheetLengths(repo))
        assertEquals("same chapter", 2, repo.state.value.chapterId)
        assertEquals("the open chapter now measures the new length", 123_000L, repo.state.value.durationMs)
        assertEquals("the player was given the new files", loads + 1, exo.calls.count { it == "setMediaItems" })
        assertEquals("same second", 100_000L, exo.position)
        assertEquals("same chapter in the queue", "2", exo.items[exo.index].mediaId)
        assertTrue("it was playing and still wants to", exo.playWhenReady)
        val stamp = (exo.items[1].localConfiguration!!.tag as Playback.BookTag).stamp
        assertEquals(Playback.fileStamp(first.id, "chapters/2.mp3"), stamp)
    }

    @Test fun aPausedBookStaysPausedAfterTheReplacement() {
        val first = BookFileImport.importFile(revision("old.abook", oldLengths, "old", "2026-10-21T00:00:00Z"))
        load(first.id, chapter = 3, seconds = 12.0, playing = false)
        val repo = repo()
        exo.position = 12_000
        assertFalse(exo.playWhenReady)

        replaceWith(revision("new.abook", newLengths, "newer", "2026-10-22T00:00:00Z"))

        assertEquals(newLengths.map { Math.round(it * 1000) }, sheetLengths(repo))
        assertEquals(3, repo.state.value.chapterId)
        assertEquals(12_000L, exo.position)
        assertFalse("never auto-plays", exo.playWhenReady)
        assertFalse(exo.calls.contains("play"))
    }

    @Test fun anotherBookBeingReplacedLeavesThePlayerAlone() {
        val first = BookFileImport.importFile(revision("old.abook", oldLengths, "old", "2026-10-21T00:00:00Z"))
        load(first.id, chapter = 1, seconds = 5.0, playing = true)
        val before = exo.calls.count { it == "setMediaItems" }
        BookFiles.changed("some-other-book")
        assertEquals(before, exo.calls.count { it == "setMediaItems" })
    }

    @Test fun anImportThatChangesNoFileDoesNotRestartTheOpenChapter() {
        val old = revision("old.abook", oldLengths, "old", "2026-10-21T00:00:00Z")
        val first = BookFileImport.importFile(old)
        load(first.id, chapter = 2, seconds = 30.0, playing = true)
        val loads = exo.calls.count { it == "setMediaItems" }
        BookFileImport.importFile(old)
        BookFiles.changed(first.id)
        assertEquals("same files: the open chapter is not re-prepared", loads, exo.calls.count { it == "setMediaItems" })
    }

    @Test fun aNewChapterJoinsTheQueueWithoutRestartingTheOpenOne() {
        val first = BookFileImport.importFile(revision("old.abook", oldLengths, "old", "2026-10-21T00:00:00Z"))
        load(first.id, chapter = 2, seconds = 30.0, playing = true)
        val loads = exo.calls.count { it == "setMediaItems" }
        val more = Store.manifest(first.id)!!
        val chapters = more.getJSONArray("chapters")
        chapters.put(JSONObject(chapters.getJSONObject(2).toString()).put("id", 4).put("fullTitle", "Chương 4").put("file", "chapters/3.mp3"))
        Playback.refreshQueue(first.id, LibraryTree.chapters(more))
        assertEquals(4, Playback.chapters.size)
        assertEquals(loads, exo.calls.count { it == "setMediaItems" })
        assertEquals(4, exo.items.size)
    }
}
