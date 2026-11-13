package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Reading process-level service state must not construct Android Media3 objects. */
class PlaybackServiceInitTest {
    @Test fun preferencesCanInspectServiceStateWithoutInitializingMediaCommands() {
        assertNull(PlaybackService.instance)
        assertEquals(125_000L, PlaybackService.foregroundGraceMs(flipEnabled = false, shakeEnabled = false))
    }
}
