package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import java.io.File

class PeerPathsTest {
    @Test fun canonical_paths_cannot_follow_a_link_out_of_the_book() {
        val root = BookEditsFixtures.tempDir("peer-link")
        val dir = File(root, "book").apply { mkdirs() }
        val outside = File(root, "outside").apply { mkdirs() }
        try {
            java.nio.file.Files.createSymbolicLink(File(dir, "scripts").toPath(), outside.toPath())
        } catch (error: Exception) { org.junit.Assume.assumeNoException("symlinks unavailable", error) }
        assertTrue(runCatching { Store.contained(dir, "scripts/1.json") }.isFailure)
    }

    @Test fun containment_rejects_siblings_root_and_unsafe_components() {
        val root = BookEditsFixtures.tempDir("peer-contained")
        val dir = File(root, "abc").apply { mkdirs() }
        assertEquals(File(dir, "scripts/1.json").canonicalFile, Store.contained(dir, "scripts/1.json"))
        for (name in listOf("../abc-2/probe.wav", "../abcdef/probe.wav", ".", "", "scripts/../1.json", "scripts/CON.json", "C:/x", "scripts/a:stream", "/outside", "scripts/CON .json", "scripts/CONIN$", "scripts/CONOUT$")) {
            assertTrue("accepted relative name: $name", runCatching { Store.contained(dir, name) }.isFailure)
        }
    }

    @Test fun book_ids_are_single_safe_components_even_after_peer_prefixing() {
        val root = BookEditsFixtures.tempDir("peer-paths")
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        for (id in listOf("x/../../outside", "../outside", "/outside", "C:\\outside", "..", "", "CON", "abc.", "abc ")) {
            assertTrue("accepted book id: $id", runCatching { Store.bookDir(id) }.isFailure)
            assertTrue("accepted peer book id: $id", runCatching { Store.bookDir(Peers.localId("peer1234", id)) }.isFailure)
        }
        assertEquals(File(root, "books/ppeer1234_book-1").canonicalFile, Store.bookDir(Peers.localId("peer1234", "book-1")))
        assertFalse(File(root, "books").exists())
    }
}
