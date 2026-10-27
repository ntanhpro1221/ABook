package vn.abook.player.ui

import android.app.Activity
import android.content.Intent
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertSame
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import vn.abook.player.AbookApplication

/**
 * Application sống lâu hơn Activity: cửa ra hệ điều hành ([AbookApplication.exportLinks], [AbookApplication.deviceLinks]) Activity đặt vào đó giữ lambda bắt
 * chính Activity ấy - Activity đã huỷ (cả cây Compose) mà còn bị giữ thì rò bộ nhớ suốt lúc sách phát nền. Huỷ thì phải gỡ ra.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class NativeActivityLinksTest {
    @Test
    fun `paused but STARTED PiP activity keeps player attached and core clock ticking`() {
        val context = ApplicationProvider.getApplicationContext<AbookApplication>()
        val intent = Intent(context, NativeActivity::class.java).putExtra(NativeActivity.DEMO_BOOKS, 1)
        val controller = Robolectric.buildActivity(NativeActivity::class.java, intent).create()
        val core = vn.abook.player.ui.data.FakePlaybackCore(org.json.JSONObject())
        val repo = vn.abook.player.ui.data.PlayerRepo(
            core, kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined), kotlinx.coroutines.Dispatchers.Unconfined, { null }, { null },
        )
        NativeActivity::class.java.getDeclaredField("player").apply { isAccessible = true }.set(controller.get(), repo)
        NativeActivity::class.java.getDeclaredField("contentReady").apply { isAccessible = true }.setBoolean(controller.get(), true)
        controller.start()
        assertEquals(1, core.listeners.size)
        controller.resume()
        assertEquals(1, core.listeners.size)
        controller.pause()
        assertEquals(androidx.lifecycle.Lifecycle.State.STARTED, controller.get().lifecycle.currentState)
        assertEquals(1, core.listeners.size)
        core.emit(vn.abook.player.ui.data.playerSnapshot(position = 23.5, kind = "tick"))
        assertEquals(23_500L, repo.clock.positionMs.value)
        controller.stop()
        assertEquals(0, core.listeners.size)
        core.emit(vn.abook.player.ui.data.playerSnapshot(position = 25.0, kind = "tick"))
        assertEquals(23_500L, repo.clock.positionMs.value)
        controller.restart().start()
        assertEquals(1, core.listeners.size)
        controller.resume()
        assertEquals(1, core.listeners.size)
        controller.pause().stop().destroy()
        assertEquals(0, core.listeners.size)
    }

    @Test
    fun `first content delivered while paused in PiP still attaches the player`() {
        val context = ApplicationProvider.getApplicationContext<AbookApplication>()
        val intent = Intent(context, NativeActivity::class.java).putExtra(NativeActivity.DEMO_BOOKS, 1)
        val controller = Robolectric.buildActivity(NativeActivity::class.java, intent).create()
        val core = vn.abook.player.ui.data.FakePlaybackCore(org.json.JSONObject())
        val repo = vn.abook.player.ui.data.PlayerRepo(
            core, kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined), kotlinx.coroutines.Dispatchers.Unconfined, { null }, { null },
        )
        NativeActivity::class.java.getDeclaredField("player").apply { isAccessible = true }.set(controller.get(), repo)
        controller.start().resume().pause()
        assertEquals(0, core.listeners.size)
        NativeActivity::class.java.getDeclaredMethod("onFirstContent").apply { isAccessible = true }.invoke(controller.get())
        assertEquals(1, core.listeners.size)
        core.emit(vn.abook.player.ui.data.playerSnapshot(position = 30.0, kind = "tick"))
        assertEquals(30_000L, repo.clock.positionMs.value)
        controller.stop().destroy()
        assertEquals(0, core.listeners.size)
    }

    @Test
    fun `a destroyed activity is not kept by the application`() {
        val app = ApplicationProvider.getApplicationContext<AbookApplication>()
        val exportsBefore = app.exportLinks
        val devicesBefore = app.deviceLinks
        val controller = Robolectric.buildActivity(NativeActivity::class.java).setup()
        assertNotSame("Activity đang hiện đặt cửa ra của nó", exportsBefore, app.exportLinks)
        assertNotSame(devicesBefore, app.deviceLinks)
        controller.pause().stop().destroy()
        var answer: String? = "chưa trả lời"
        app.exportLinks.pickFolder { answer = it }
        assertNull("cửa ra của Activity đã huỷ không mở hộp hệ thống trên Activity chết", answer)
    }

    /**
     * Hộp chọn của hệ thống đang mở mà Activity bị huỷ (thiếu RAM, "Không giữ hoạt động"): Activity mới nhận câu trả lời - nơi hỏi (màn Xuất) vẫn đang đợi, không được treo mãi.
     */
    @Test
    fun `a folder picked after the activity was rebuilt still reaches who asked`() {
        val app = ApplicationProvider.getApplicationContext<AbookApplication>()
        val controller = Robolectric.buildActivity(NativeActivity::class.java).setup()
        var answer: String? = "chưa trả lời"
        app.exportLinks.pickFolder { answer = it }
        val launched = shadowOf(controller.get()).nextStartedActivityForResult
        controller.recreate()
        val rebuilt = controller.get()
        val tree = Intent().setData(Uri.parse("content://tree/Music"))
        val dispatch = Activity::class.java.getDeclaredMethod("onActivityResult", Int::class.java, Int::class.java, Intent::class.java).apply { isAccessible = true }
        dispatch.invoke(rebuilt, launched.requestCode, Activity.RESULT_OK, tree)
        assertEquals("content://tree/Music", answer)
    }

    @Test
    fun `a file made after the activity was rebuilt still reaches who asked`() {
        val app = ApplicationProvider.getApplicationContext<AbookApplication>()
        val controller = Robolectric.buildActivity(NativeActivity::class.java).setup()
        var answer: String? = "chưa trả lời"
        app.exportLinks.createFile("Truyện") { answer = it }
        val launched = shadowOf(controller.get()).nextStartedActivityForResult
        controller.recreate()
        val dispatch = Activity::class.java.getDeclaredMethod("onActivityResult", Int::class.java, Int::class.java, Intent::class.java).apply { isAccessible = true }
        dispatch.invoke(controller.get(), launched.requestCode, Activity.RESULT_OK, Intent().setData(Uri.parse("content://doc/Truyen.m4b")))
        assertEquals("content://doc/Truyen.m4b", answer)
    }
}
