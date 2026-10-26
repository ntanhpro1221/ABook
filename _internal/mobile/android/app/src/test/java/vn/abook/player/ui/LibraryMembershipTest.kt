package vn.abook.player.ui

import androidx.test.core.app.ApplicationProvider
import android.content.Context
import android.os.Looper
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.Shadows.shadowOf
import vn.abook.player.BookActions
import vn.abook.player.Store
import vn.abook.player.ui.data.*
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class LibraryMembershipTest {
    @Test fun undoKeepsTheRealFilesAndExpiryActuallyDeletesThem() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        Store.init(context)
        val file = File(Store.bookDir("local"), "book.json").apply { parentFile!!.mkdirs(); writeText("{}") }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val deletes = UndoDelete(scope, { BookActions.deleteAfterUndo(context, it); null }, {})
        deletes.remove("local")
        assertTrue(file.isFile)
        deletes.undo()
        shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(28_000))
        assertTrue("Undo must preserve the original bytes", file.isFile)
        deletes.remove("local")
        shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(27_999))
        assertTrue(file.isFile)
        shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(1))
        assertFalse("Expiry must call the real Store deletion", file.exists())
        assertFalse(deletes.contains("local"))
        scope.cancel()
    }

    @Test fun authoritativeRemoteListDropsVanishedCacheButPreservesDownloadsAndOfflinePlayingBook() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        Store.init(context)
        fun put(id: String, downloaded: Boolean) {
            val manifest = JSONObject().put("id", id).put("title", id).put("chaptersAvailable", 1).put("chaptersTotal", 1)
                .put("chapters", JSONArray().put(JSONObject().put("id", 1).put("fullTitle", "Một").put("file", "audio/1.mp3").put("available", true).put("duration", 60)))
            File(Store.bookDir(id), if (downloaded) "book.json" else "stream.json").apply { parentFile.mkdirs(); writeText(manifest.toString()) }
        }
        put("downloaded", true); put("playing", false); put("vanished", false)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val repo = LibraryRepo(context, scope)
        repo.refresh()
        assertEquals(setOf("downloaded", "playing", "vanished"), (repo.state.value as LibraryState.Ready).books.map { it.id }.toSet())
        // The shared core retains the current streamed book with offline=true when a host times out.
        repo.acceptRemote(JSONArray().put(JSONObject().put("id", "playing").put("offline", true)))
        assertEquals(setOf("downloaded", "playing"), (repo.state.value as LibraryState.Ready).books.map { it.id }.toSet())
        repo.acceptRemote(JSONArray())
        assertEquals(listOf("downloaded"), (repo.state.value as LibraryState.Ready).books.map { it.id })
        // A successful later catalogue restores the cached book without migration or changing local downloads.
        repo.acceptRemote(JSONArray().put(JSONObject().put("id", "vanished")))
        assertEquals(setOf("downloaded", "vanished"), (repo.state.value as LibraryState.Ready).books.map { it.id }.toSet())
        scope.cancel()
    }
}
