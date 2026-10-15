package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Test

/** `vieneu_engine.keep_lone_o`: sea-g2p's second normalisation must not turn the "o" syllable of a name (`Names.loneSyllable`) into the letter "ô"; same cases as test_readaloud_sounds.py. */
class KeepLoneOTest {
    @Test
    fun aLoneOThatTheSecondPassSpelledAsTheLetterIsGivenBack() {
        assertEquals("a o, b", SeaG2p.keepLoneO("a o, b", "a ô, b"))
        assertEquals("hẳn là o xu ki xan", SeaG2p.keepLoneO("hẳn là o xu ki xan", "hẳn là ô xu ki xan"))
    }

    @Test
    fun aChunkWhoseWordCountChangedIsLeftAlone() {
        assertEquals("a ô b c", SeaG2p.keepLoneO("a o b", "a ô b c"))
        assertEquals("tôi ô một", SeaG2p.keepLoneO("tôi x một", "tôi ô một"))
    }
}
