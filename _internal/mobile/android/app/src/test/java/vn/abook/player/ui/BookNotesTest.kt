package vn.abook.player.ui

import android.os.Looper
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.BookNotes
import java.time.Duration

/** Lời báo ngắn của trang sách (web: toast): lời mới thay lời cũ, có nút thì ở lâu hơn, bấm nút thì khép rồi mới chạy việc. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BookNotesTest {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val notes = BookNotes(scope)

    @After fun stop() = scope.cancel()

    private fun advance(ms: Long) = shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms))

    @Test fun aPlainNoteShowsThenGoesAwayAfterFiveSeconds() {
        notes.say("Đã đổi tên hồ sơ")
        assertTrue(notes.visible.value)
        assertEquals("Đã đổi tên hồ sơ", notes.note.value.text)
        assertNull(notes.note.value.actionLabel)
        advance(4_900)
        assertTrue(notes.visible.value)
        advance(200)
        assertFalse(notes.visible.value)
        assertEquals("the line stays while the bar slides out", "Đã đổi tên hồ sơ", notes.note.value.text)
    }

    @Test fun aNoteWithAButtonStaysLongEnoughToPress() {
        notes.say("Đang nghe lại từ đầu", "Quay lại chỗ cũ") {}
        advance(7_900)
        assertTrue("the web toast keeps 8 seconds when it has an action", notes.visible.value)
        advance(200)
        assertFalse(notes.visible.value)
    }

    @Test fun pressingTheButtonClosesTheBarAndRunsTheActionOnce() {
        var ran = 0
        notes.say("Đã ghi: An là nhân vật nữ", "Hoàn tác") { ran++ }
        notes.act()
        assertEquals(1, ran)
        assertFalse(notes.visible.value)
        notes.act()
        assertEquals("a second press finds nothing to run", 1, ran)
    }

    @Test fun aNewNoteReplacesTheOldOneAndItsButton() {
        var first = 0
        notes.say("Một", "Hoàn tác") { first++ }
        advance(3_000)
        notes.say("Hai")
        assertEquals("Hai", notes.note.value.text)
        assertNull(notes.note.value.actionLabel)
        notes.act()
        assertEquals("the old button no longer does anything", 0, first)
        notes.say("Ba")
        advance(4_000)
        assertTrue("the old timer must not close the new note early", notes.visible.value)
    }

    @Test fun dismissingClosesWithoutRunningTheAction() {
        var ran = 0
        notes.say("Một", "Hoàn tác") { ran++ }
        notes.dismiss()
        assertFalse(notes.visible.value)
        assertEquals(0, ran)
    }
}
