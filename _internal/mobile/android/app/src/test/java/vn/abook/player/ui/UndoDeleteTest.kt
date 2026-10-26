package vn.abook.player.ui

import android.os.Looper
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.runBlocking
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
import vn.abook.player.ui.data.UndoDelete
import java.time.Duration

/**
 * "Xoá khỏi điện thoại" có Hoàn tác làm như bản WebView (`shared/trashUndo.ts`): cuốn vào chỗ chờ NGAY (không đợi hết hạn - tiến trình chết giữa chừng thì cuốn
 * không quay lại), chữ y như web, hạn 28 giây mỗi cuốn, Hoàn tác trả cũ trước.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class UndoDeleteTest {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val held = ArrayList<String>()
    private val restored = ArrayList<String>()
    private val removed = ArrayList<String>()
    private var changes = 0
    private var holdError: String? = null
    private var restoreError: String? = null
    private var straight = false

    private val deletes = UndoDelete(
        scope,
        hold = { id ->
            holdError?.let { throw IllegalStateException(it) }
            held += id
            if (straight) null else "token-$id"
        },
        restore = { token ->
            restoreError?.let { throw IllegalStateException(it) }
            restored += token
        },
        changed = { changes++ },
        removed = { removed += it },
    )

    @After fun stop() = scope.cancel()

    private fun advance(ms: Long) = shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms))

    @Test fun theBookGoesToTheWaitingPlaceAtOnceNotAfterTheWindow() = runBlocking {
        assertNull(deletes.remove("b1", "Dế Mèn"))
        assertEquals("cuốn nằm chờ ngay lúc bấm xoá", listOf("b1"), held)
        assertEquals(listOf("b1"), removed)
        assertTrue(deletes.contains("b1"))
        assertEquals(listOf("b1"), deletes.undoable.value)
        assertTrue(deletes.showing.value)
        assertEquals("Đã xoá “Dế Mèn” khỏi điện thoại", deletes.message.value)
    }

    @Test fun undoReturnsTheBooksOldestFirstAndSaysSoLikeTheWeb() = runBlocking {
        deletes.remove("b1", "Dế Mèn")
        deletes.remove("b2", "Tắt đèn")
        assertEquals("Đã bỏ 2 cuốn", deletes.message.value)
        deletes.undo()
        assertEquals(listOf("token-b1", "token-b2"), restored)
        assertFalse(deletes.contains("b1") || deletes.contains("b2"))
        assertTrue(deletes.undoable.value.isEmpty())
        assertFalse(deletes.showing.value)
        assertEquals("Đã khôi phục “Tắt đèn”", deletes.notice.value)
        assertTrue("danh sách đọc lại", changes >= 2)
        advance(30_000)
        assertEquals("lời báo tự tắt", "", deletes.notice.value)
    }

    @Test fun eachBookHasItsOwnWindowOfTwentyEightSeconds() = runBlocking {
        deletes.remove("b1", "Dế Mèn")
        advance(10_000)
        deletes.remove("b2", "Tắt đèn")
        advance(17_999)
        assertEquals(listOf("b1", "b2"), deletes.undoable.value)
        advance(1)
        assertEquals("b1 hết hạn lúc 28 giây", listOf("b2"), deletes.undoable.value)
        assertFalse(deletes.contains("b1"))
        assertEquals("Đã xoá “Tắt đèn” khỏi điện thoại", deletes.message.value)
        assertTrue(deletes.showing.value)
        advance(10_000)
        assertTrue(deletes.undoable.value.isEmpty())
        assertFalse(deletes.showing.value)
        deletes.undo()
        assertTrue("hết hạn thì không hoàn tác được nữa", restored.isEmpty())
    }

    @Test fun aBookDeletedStraightIsOnlySaidNotUndoable() = runBlocking {
        straight = true
        assertNull(deletes.remove("b1", "Dế Mèn"))
        assertEquals("Đã xoá “Dế Mèn” khỏi điện thoại", deletes.notice.value)
        assertTrue(deletes.undoable.value.isEmpty())
        assertFalse(deletes.showing.value)
        assertFalse(deletes.contains("b1"))
    }

    @Test fun aDeleteTheCoreRefusesBringsTheBookBackAndSaysWhy() = runBlocking {
        holdError = "Đang tải cuốn này - huỷ tải rồi mới xoá được."
        assertEquals("Đang tải cuốn này - huỷ tải rồi mới xoá được.", deletes.remove("b1", "Dế Mèn"))
        assertFalse(deletes.contains("b1"))
        assertTrue(deletes.undoable.value.isEmpty())
        assertFalse(deletes.showing.value)
        assertTrue("danh sách đọc lại để cuốn hiện lại", changes >= 2)
    }

    @Test fun anUndoThatFailsSaysWhyAndKeepsTheBookWaiting() = runBlocking {
        deletes.remove("b1", "Dế Mèn")
        restoreError = "Chỗ cũ đã có sách cùng mã nên chưa hoàn tác được."
        deletes.undo()
        assertEquals("Chưa hoàn tác được - Chỗ cũ đã có sách cùng mã nên chưa hoàn tác được.", deletes.problem.value)
        assertEquals(listOf("b1"), deletes.undoable.value)
        assertTrue(deletes.contains("b1"))
        assertTrue(deletes.showing.value)
        restoreError = null
        deletes.undo()
        assertEquals(listOf("token-b1"), restored)
        assertFalse(deletes.contains("b1"))
    }

    @Test fun dismissDoesNotUndoAndTheNextRemovalDoesNotBringTheOldBookBack() = runBlocking {
        deletes.remove("b1", "A")
        deletes.dismiss()
        assertFalse(deletes.showing.value)
        assertTrue("cuốn vẫn nằm chờ tới hết hạn", deletes.contains("b1"))
        deletes.remove("b2", "B")
        deletes.undo()
        assertEquals(listOf("token-b2"), restored)
        assertTrue(deletes.contains("b1"))
        advance(28_000)
        assertFalse("hết hạn thì thôi ẩn", deletes.contains("b1"))
    }

    @Test fun aPartialDownloadIsNamedAsSuch() = runBlocking {
        deletes.remove("b1", "Dế Mèn", partial = true)
        assertEquals("Đã xoá phần đã tải của “Dế Mèn”", deletes.message.value)
        assertEquals("Đã xoá khỏi điện thoại", UndoDelete.removedText(1, "", false))
    }
}
