package vn.abook.player.ui

import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.data.ReleaseSigning

class ReleaseSigningTest {
    private val abc = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" // SHA-256("abc"), vector chuẩn FIPS 180-2

    @Test fun sha256IsLowercaseHexWithoutColons() {
        assertEquals(abc, ReleaseSigning.sha256Hex("abc".toByteArray()))
    }

    @Test fun aCertificateWhoseHashIsTheExpectedFingerprintIsRelease() {
        assertTrue(ReleaseSigning.isRelease(listOf("abc".toByteArray()), abc))
    }

    @Test fun anyOtherCertificateIsNotRelease() {
        assertFalse(ReleaseSigning.isRelease(listOf("debug certificate".toByteArray()), abc))
        assertFalse(ReleaseSigning.isRelease(listOf("abc".toByteArray(), "another".toByteArray()), abc))
        assertFalse(ReleaseSigning.isRelease(emptyList(), abc))
    }

    @Test fun theDebugKeyIsNotTheReleaseKey() {
        assertFalse(ReleaseSigning.isRelease(listOf("debug certificate".toByteArray())))
        assertTrue(Regex("[0-9a-f]{64}").matches(ReleaseSigning.RELEASE_SHA256))
    }
}
