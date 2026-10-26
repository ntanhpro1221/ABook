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
import vn.abook.player.Store
import vn.abook.player.ui.data.*
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class LibraryMembershipTest {
    private fun awaitTrue(what: String, condition: () -> Boolean) {
        val until = System.currentTimeMillis() + 5_000
        while (!condition()) {
            shadowOf(Looper.getMainLooper()).idle()
            check(System.currentTimeMillis() < until) { "hết giờ chờ: $what" }
            Thread.sleep(10)
        }
    }

    private fun book(id: String): File = File(Store.bookDir(id), "book.json").apply { parentFile!!.mkdirs(); writeText("{}") }

    @Test fun deletingMovesTheBookToTheWaitingPlaceAtOnceAndUndoBringsItBack() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        Store.init(context)
        val file = book("local")
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val repo = LibraryRepo(context, scope)
        assertNull(repo.delete("local"))
        assertFalse("cuốn nằm chờ ngay, không đợi hết hạn Hoàn tác (như bản WebView: bền qua tắt app)", file.exists())
        assertTrue(repo.deletions.contains("local"))
        repo.deletions.undo()
        awaitTrue("cuốn về chỗ cũ") { file.isFile && !repo.deletions.contains("local") }
        assertEquals("Đã khôi phục “”", repo.deletions.notice.value)
        scope.cancel()
    }

    @Test fun aBookStillWaitingWhenTheProcessDiedIsGoneForGoodNextTime() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        Store.init(context)
        val file = book("local")
        val waiting = File(Store.bookDir("local").parentFile!!.parentFile, ".trash-pending")
        val first = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val repo = LibraryRepo(context, first)
        assertNull(repo.delete("local"))
        assertTrue(waiting.isDirectory)
        first.cancel() // tiến trình chết trước hạn Hoàn tác: nút Hoàn tác mất cùng nó
        val second = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        LibraryRepo(context, second)
        awaitTrue("chỗ chờ được dọn") { !waiting.exists() }
        assertFalse(file.exists())
        second.cancel()
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
