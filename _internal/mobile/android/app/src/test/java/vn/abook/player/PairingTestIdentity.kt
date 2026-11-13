package vn.abook.player

/** Synthetic TLS identity for route-level tests; real pairing must present the verified fingerprint too. */
internal class PairingTestIdentity : AutoCloseable {
    private val field = LibraryServer::class.java.getDeclaredField("fingerprint").apply { isAccessible = true }
    private val previous = LibraryServer.fingerprint
    val fingerprint = "0123456789abcdef".repeat(4)
    init { field.set(LibraryServer, fingerprint) }
    override fun close() { field.set(LibraryServer, previous) }
}
