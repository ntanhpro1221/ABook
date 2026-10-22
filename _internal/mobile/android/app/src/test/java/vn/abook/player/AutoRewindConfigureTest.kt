package vn.abook.player

import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Soát a77 #7: `configure` chỉ có giọng / giọng mặc định / đồng ý giọng mạng (không mang `autoRewind`) không được bật lại "Tự lùi" mà bạn đã tắt. */
class AutoRewindConfigureTest {
    private fun rewinding() = Playback::class.java.getDeclaredField("autoRewind").also { it.isAccessible = true }.getBoolean(Playback)

    @After fun restore() = Playback.configure(true)

    @Test fun aConfigureWithoutTheFieldLeavesTheSettingAlone() {
        Playback.configure(false) // bạn đã tắt tự lùi
        Playback.configure(null) // đổi giọng: payload không có autoRewind
        assertFalse(rewinding())
        Playback.configure(true)
        Playback.configure(null)
        assertTrue(rewinding())
    }
}
