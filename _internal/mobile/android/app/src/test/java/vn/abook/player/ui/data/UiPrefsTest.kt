package vn.abook.player.ui.data

import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.nowplaying.ReadLook

/** Dáng chữ của Đọc theo được nhớ giữa các lần mở; giá trị lạ trong file nhớ thì về mặc định. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class UiPrefsTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Test
    fun `reading look survives a restart`() {
        val prefs = UiPrefs(context)
        assertEquals(ReadLook(), prefs.readLook())
        prefs.setReadLook(ReadLook(size = 24, leading = 1.9, tapped = true))
        val again = UiPrefs(context).readLook()
        assertEquals(24, again.size)
        assertEquals(1.9, again.leading, 0.0)
        assertTrue(again.tapped)
    }

    @Test
    fun `a size outside the picker range falls back to the default`() {
        context.getSharedPreferences("native_ui", android.content.Context.MODE_PRIVATE).edit().putInt("read_size", 41).putFloat("read_leading", 3f).commit()
        assertEquals(ReadLook(), UiPrefs(context).readLook())
    }

    @Test
    fun `any size and spacing inside the picker range is kept`() {
        context.getSharedPreferences("native_ui", android.content.Context.MODE_PRIVATE).edit().putInt("read_size", 33).putFloat("read_leading", 1.85f).commit()
        assertEquals(ReadLook(size = 33, leading = 1.85), UiPrefs(context).readLook())
    }
}
