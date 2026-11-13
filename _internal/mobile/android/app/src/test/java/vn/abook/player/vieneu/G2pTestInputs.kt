package vn.abook.player.vieneu

import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue

/** Local runs may omit the host frontend; release parity must execute every case. */
internal object G2pTestInputs {
    fun requireOrSkip(message: String, available: Boolean) {
        if (System.getenv("ABOOK_REQUIRE_G2P_PARITY") == "1") assertTrue(message, available)
        else assumeTrue(message, available)
    }
}
