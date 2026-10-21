package vn.abook.player.readaloud

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** ONNX Runtime threads spin between ops only on the charger (dev/spin: 12-37 % faster on the OPPO, the same bytes, more battery). */
class SpinPolicyTest {
    @Test
    fun onlyAPhoneOnTheChargerSpins() {
        assertTrue(SpinPolicy.spinning(charging = true))
        assertFalse(SpinPolicy.spinning(charging = false))
    }
}
