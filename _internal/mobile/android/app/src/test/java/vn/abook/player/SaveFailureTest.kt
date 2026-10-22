package vn.abook.player

import android.os.Handler
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/** Soát a77 #4: bộ nhớ đầy / ghi hỏng lúc lưu chỗ nghe không được làm văng bộ phát; checkpoint cũ còn nguyên, báo bạn một lần, nhịp sau thử lại. */
class SaveFailureTest {
    private val voice = FakeExo()
    private lateinit var root: File
    private val events = mutableListOf<JSONObject>()
    private val listener: (JSONObject) -> Unit = { events += it }

    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setup() {
        Handler.reset()
        root = BookEditsFixtures.tempDir("save-failure")
        BookEditsFixtures.useStoreRoot(root)
        voice.item = MediaItem.Builder().setMediaId("1").setTag(Playback.BookTag("save-book")).build()
        voice.duration = 3_600_000
        voice.position = 1_800_000
        voice.state = Player.STATE_READY
        Playback.player = voice.player
        field("bookId").set(Playback, "save-book")
        field("chapters").set(Playback, listOf(Playback.Chapter(1, "Một", "1.mp3", 3600.0)))
        field("savedPlace").set(Playback, null)
        field("saveFailing").setBoolean(Playback, false)
        Playback.addListener(listener)
        Store.progress("save-book", 1, 1800.0, 3600.0)
    }

    @After fun cleanup() {
        Playback.removeListener(listener)
        field("bookId").set(Playback, "")
        field("chapters").set(Playback, emptyList<Playback.Chapter>())
        field("savedPlace").set(Playback, null)
        Playback.player = null
        Handler.reset()
    }

    private fun stateFile() = File(root, "state/${Store.activeRecord("save-book")}.json")

    @Test fun aFailedWriteKeepsTheOldCheckpointReportsOnceAndRetriesOnTheNextBeat() {
        val file = stateFile()
        val old = file.readText()
        // Chỗ ghi bị chặn (như bộ nhớ đầy: ghi/đổi tên hỏng): Store.progress ném lỗi.
        file.delete()
        file.mkdirs()
        voice.position = 2_000_000
        Playback.saveNow() // không được ném ra ngoài: ném ở đây là văng cả bộ phát
        Playback.saveNow() // lần hỏng thứ hai, vẫn không báo lại
        val failures = events.filter { it.optString("kind") == "saveFailed" }
        assertEquals("báo đúng một lần", 1, failures.size)
        // Nhịp sau thử lại: chỗ ghi thông lại thì lưu được và gỡ lời báo.
        file.delete()
        file.writeText(old)
        Playback.saveNow()
        assertEquals(2000.0, Store.state("save-book").getJSONObject("last").getDouble("seconds"), 0.001)
        assertTrue(events.none { it.optString("kind") == "saveFailed" && it !== failures.single() })
        // Hỏng lần nữa sau khi đã khoẻ lại là chuyện mới: báo lại.
        file.delete()
        file.mkdirs()
        voice.position = 2_100_000
        Playback.saveNow()
        assertEquals(2, events.count { it.optString("kind") == "saveFailed" })
        file.delete()
    }

    @Test fun theStateSaysWhatToTellTheListenerInVietnamese() {
        stateFile().let { it.delete(); it.mkdirs() }
        voice.position = 2_000_000
        Playback.saveNow()
        val failed = events.single { it.optString("kind") == "saveFailed" }
        assertTrue(failed.optString("saveError").contains("bạn"))
        assertTrue(failed.optString("saveError").contains("chỗ"))
        stateFile().delete()
    }
}
