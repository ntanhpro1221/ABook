package vn.abook.player

import java.io.File
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import java.util.concurrent.atomic.AtomicInteger
import org.json.JSONObject
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue

class StoreInitTest {
    private lateinit var fixture: ColdStoreFixture
    @Before fun prepare() { fixture = ColdStoreFixture() }
    @After fun restore() { fixture.restore() }

    private fun concurrentInit(init: () -> Unit, secondInit: () -> Unit = init) {
        val calls = AtomicInteger()
        val recovering = CountDownLatch(1)
        val release = CountDownLatch(1)
        val secondStarted = CountDownLatch(1)
        val recover = Store.initRecovery
        Store.initRecovery = { dir ->
            calls.incrementAndGet()
            recovering.countDown()
            check(release.await(5, TimeUnit.SECONDS))
            recover(dir)
        }
        val workers = Executors.newFixedThreadPool(2)
        try {
            val first = workers.submit { init() }
            assertTrue(recovering.await(5, TimeUnit.SECONDS))
            val second = workers.submit { secondStarted.countDown(); secondInit() }
            assertTrue(secondStarted.await(5, TimeUnit.SECONDS))
            val early = runCatching { second.get(300, TimeUnit.MILLISECONDS) }
            val rootDuringRecovery = fixture.field(Store::class.java, "root")
            val contextDuringRecovery = fixture.field(LibraryServer::class.java, "appContext")
            release.countDown()
            first.get(5, TimeUnit.SECONDS)
            second.get(5, TimeUnit.SECONDS)
            assertTrue("second init must wait for recovery", early.exceptionOrNull() is TimeoutException)
            assertEquals("root is published only after recovery", null, rootDuringRecovery)
            assertEquals("server context is published only after recovery", null, contextDuringRecovery)
            assertEquals(1, calls.get())
            assertEquals(File(fixture.directory, "library").canonicalFile, Store.root.canonicalFile)
        } finally {
            release.countDown()
            workers.shutdown()
            assertTrue(workers.awaitTermination(10, TimeUnit.SECONDS))
        }
    }

    @Test fun parallel_store_init_recovers_once_and_waits_for_publication() {
        concurrentInit({ Store.init(fixture.context) })
    }

    @Test fun parallel_server_init_recovers_once_and_publishes_together() {
        concurrentInit({ LibraryServer.init(fixture.context) })
        assertSame(fixture.context, fixture.field(LibraryServer::class.java, "appContext"))
        assertSame(fixture.context, fixture.field(Remote::class.java, "context"))
        assertFalse(LibraryServer.running())
    }

    @Test fun store_rejects_a_different_directory_without_recovery_or_files() {
        Store.init(fixture.context)
        val otherDir = File(fixture.directory, "other")
        var recoveries = 0
        Store.initRecovery = { recoveries++; emptyList() }
        Store.init(fixture.contextFor(otherDir))
        assertEquals(File(fixture.directory, "library").canonicalFile, Store.root.canonicalFile)
        assertEquals(0, recoveries)
        assertFalse(otherDir.exists())
        // LibraryServer's first init must also reject a directory different from the already open Store.
        LibraryServer.init(fixture.contextFor(otherDir))
        assertEquals(null, fixture.field(LibraryServer::class.java, "appContext"))
        assertEquals(null, fixture.field(LibraryServer::class.java, "devicesFile"))
        assertEquals(null, fixture.field(Remote::class.java, "context"))
        assertFalse(otherDir.exists())
    }

    @Test fun server_rejects_a_different_directory_and_keeps_all_of_the_first_context() {
        LibraryServer.init(fixture.context)
        val otherDir = File(fixture.directory, "other")
        LibraryServer.init(fixture.contextFor(otherDir))
        assertSame(fixture.context, fixture.field(LibraryServer::class.java, "appContext"))
        assertSame(fixture.context, fixture.field(Remote::class.java, "context"))
        assertEquals(File(fixture.directory, "share.json"), fixture.field(LibraryServer::class.java, "devicesFile"))
        assertEquals(File(fixture.directory, "library").canonicalFile, Store.root.canonicalFile)
        assertFalse(otherDir.exists())
        assertFalse(LibraryServer.running())
    }

    @Test fun parallel_different_directories_keep_only_the_first_store_and_server() {
        val other = File(fixture.directory, "other")
        concurrentInit({ LibraryServer.init(fixture.context) }, { LibraryServer.init(fixture.contextFor(other)) })
        assertSame(fixture.context, fixture.field(LibraryServer::class.java, "appContext"))
        assertSame(fixture.context, fixture.field(Remote::class.java, "context"))
        assertEquals(File(fixture.directory, "share.json"), fixture.field(LibraryServer::class.java, "devicesFile"))
        assertFalse(other.exists())
    }

    @Test fun failed_recovery_publishes_nothing_and_only_the_same_directory_can_retry() {
        val recover = Store.initRecovery
        Store.initRecovery = { throw java.io.IOException("recovery interrupted") }
        assertTrue(runCatching { LibraryServer.init(fixture.context) }.isFailure)
        assertEquals(null, fixture.field(Store::class.java, "root"))
        assertEquals(null, fixture.field(LibraryServer::class.java, "appContext"))
        assertEquals(null, fixture.field(LibraryServer::class.java, "devicesFile"))
        assertEquals(null, fixture.field(Remote::class.java, "context"))
        Store.initRecovery = recover
        val other = File(fixture.directory, "other")
        assertFalse(LibraryServer.init(fixture.contextFor(other)))
        assertFalse(other.exists())
        assertTrue(LibraryServer.init(fixture.context))
        assertSame(fixture.context, fixture.field(LibraryServer::class.java, "appContext"))
    }

    @Test fun warm_init_keeps_a_live_socket_and_the_original_context() {
        LibraryServer.init(fixture.context)
        val devices = File(fixture.directory, "share.json").apply { writeText("{\"devices\":{}}") }
        val before = fixture.files()
        ServerSocket().use { socket ->
            LibraryServer::class.java.getDeclaredField("server").apply { isAccessible = true }.set(null, socket)
            val alias = fixture.contextFor(File(fixture.directory, "./"))
            assertTrue(LibraryServer.init(alias))
            assertSame(socket, fixture.field(LibraryServer::class.java, "server"))
            assertTrue(LibraryServer.running())
            assertSame(fixture.context, fixture.field(LibraryServer::class.java, "appContext"))
            assertSame(fixture.context, fixture.field(Remote::class.java, "context"))
            assertEquals(before, fixture.files())
            assertEquals("{\"devices\":{}}", devices.readText())
        }
    }

    @Test fun reopening_recovers_staging_and_rekey_before_publishing_the_root() {
        val root = File(fixture.directory, "library").apply { mkdirs() }
        val staging = File(root, "books/.old.123.old").apply { mkdirs() }
        File(staging, "book.json").writeText(JSONObject().put("id", "old").put("title", "Recovered").toString())
        File(root, "rekey_journal.json").writeText(JSONObject().put("old", JSONObject().put("to", "new").put("adopt", false)).toString())
        assertTrue(Store.init(fixture.context))
        assertFalse(staging.exists())
        assertFalse(File(root, "books/old").exists())
        assertEquals("new", Store.rawManifest("new")!!.getString("id"))
        assertEquals("Recovered", Store.rawManifest("new")!!.getString("title"))
        assertEquals(0, JSONObject(File(root, "rekey_journal.json").readText()).length())
    }
}
