package vn.abook.player

import android.os.Handler
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Soát a77 #9: tốc độ đổi từ controller ngoài (xe, đồng hồ, Android Auto) phải được lưu vào sách và báo giao diện; tốc độ đổi từ chính app thì không lưu / báo hai lần. */
class ExternalRateTest {
    private val voice = FakeExo()
    private val events = mutableListOf<JSONObject>()
    private val listener: (JSONObject) -> Unit = { events += it }
    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun storedRate() = Store.state("rate-book").optDouble("rate", 1.0)
    private fun stamp() = Store.state("rate-book").optDouble("rateAt", 0.0)

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("external-rate"))
        Playback.player = voice.player
        field("bookId").set(Playback, "rate-book")
        field("knownSpeed").setFloat(Playback, 1f)
        Playback.addListener(listener)
    }

    @After fun cleanup() {
        Playback.removeListener(listener)
        field("bookId").set(Playback, "")
        Playback.player = null
        Handler.reset()
    }

    @Test fun aRateChosenByAnExternalControllerIsStoredAndReported() {
        voice.speed = 1.5f // controller đã đổi: ExoPlayer báo onPlaybackParametersChanged
        Playback.onRateChanged(1.5f)
        assertEquals(1.5, storedRate(), 0.0001)
        val reported = events.single { it.optString("kind") == "rateChanged" }
        assertEquals(1.5, reported.getDouble("rate"), 0.0001)
    }

    @Test fun theAppsOwnSetRateIsNotStoredOrReportedTwice() {
        Playback.setRate(1.25)
        val stampAfterOwn = stamp()
        val before = events.size
        Playback.onRateChanged(1.25f) // ExoPlayer gọi lại sau chính lệnh setRate của app
        assertEquals(before, events.size)
        assertEquals(stampAfterOwn, stamp(), 0.0)
        assertTrue(events.none { it.optString("kind") == "rateChanged" })
        assertEquals(1.25, storedRate(), 0.0001)
    }

    @Test fun anUnchangedRateCallbackDoesNothing() {
        Playback.onRateChanged(1.0f)
        assertTrue(events.none { it.optString("kind") == "rateChanged" })
    }
}
