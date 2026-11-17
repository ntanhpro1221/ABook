package vn.abook.player.ui.addbook

import android.net.Uri
import android.content.ContentProvider
import android.content.ContentValues
import android.content.pm.ProviderInfo
import android.database.Cursor
import android.database.MatrixCursor
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Before
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver
import org.json.JSONObject
import vn.abook.player.BookFileImport
import vn.abook.player.BookDocumentWriter
import vn.abook.player.BookImports
import vn.abook.player.ImportJob
import vn.abook.player.ImportJobState
import vn.abook.player.ImportJobs
import vn.abook.player.ImportStopped
import vn.abook.player.BookVolumes
import vn.abook.player.Store
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ImportRepoFileTest {
    private val context get() = ApplicationProvider.getApplicationContext<vn.abook.player.AbookApplication>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

    // Robolectric không chạy việc của WorkManager: file sách đi cùng lõi nền nhưng ngay trên luồng gọi.
    @Before fun inline() { BookImports.inline = true }
    @After fun close() { BookImports.inline = false; scope.cancel() }

    /** Gói .abook hợp lệ dựng từ fixture book_edits/base (không có chữ truyện thật). */
    private fun fixtureBook(name: String): File {
        val base = File("../../../tests/fixtures/book_edits/base")
        assertTrue(base.isDirectory)
        val book = JSONObject(File(base, "book.json").readText())
        val names = listOf("book.json") + book.getJSONObject("package").getJSONObject("files").keys().asSequence().toList()
        val file = File(context.cacheDir, name)
        ZipOutputStream(file.outputStream()).use { zip ->
            val mime = BookFileImport.MIMETYPE.toByteArray()
            zip.putNextEntry(ZipEntry("mimetype").apply {
                method = ZipEntry.STORED; size = mime.size.toLong(); compressedSize = size
                crc = java.util.zip.CRC32().apply { update(mime) }.value
            })
            zip.write(mime); zip.closeEntry()
            names.forEach { entry -> zip.putNextEntry(ZipEntry(entry)); zip.write(if (entry == "book.json") BookVolumes.nested(JSONObject(File(base, entry).readText()).apply { getJSONObject("package").put("version", 6) }).toString().toByteArray() else File(base, entry).readBytes()); zip.closeEntry() }
        }
        return file
    }

    private fun waitFor(queue: ImportQueue, phase: String, what: (ImportState) -> Boolean): ImportState = runBlocking {
        try {
            withTimeout(30_000) { queue.state.first(what) }
        } catch (error: TimeoutCancellationException) {
            throw AssertionError("Timed out waiting for $phase; current import state: ${queue.state.value}", error)
        }
    }
    private fun stageOf(queue: ImportQueue, index: Int) = queue.state.value.items.getOrNull(index)?.stage
    private fun ended(stage: ImportStage?) = stage == ImportStage.Error || stage == ImportStage.Added || stage == ImportStage.Existing

    @Test fun androidExportsKeepPackageMetadataAsAnObjectAndImportAgain() {
        Store.init(context)
        val original = BookFileImport.importFile(fixtureBook("export-source.abook"))
        for (project in listOf(false, true)) {
            val exported = File(context.cacheDir, if (project) "roundtrip.abookproj" else "roundtrip.abook")
            exported.outputStream().use { BookDocumentWriter.write(Store.bookDir(original.id), it, asProject = project) }
            ZipFile(exported).use { zip ->
                val book = JSONObject(zip.getInputStream(zip.getEntry("book.json")).bufferedReader().use { it.readText() })
                assertEquals("abook", book.getJSONObject("package").getString("format"))
            }
            assertEquals(original.id, BookFileImport.importFile(exported).id)
        }
    }

    @Test fun aCompletedImportKeepsItsSourceUntilTheDependentCleanupAndCanReplayBeforeThen() {
        val inbox = requireNotNull(BookImports.inbox(context)).apply { mkdirs() }
        val source = fixtureBook("cleanup-source.abook").copyTo(File(inbox, "cleanup-source.abook"), overwrite = true)
        val job = ImportJob("cleanup-replay", Uri.fromFile(source).toString(), source.name, owned = true)
        fun runAgain() = ImportJobs().run(job, { sink -> BookImports.importOne(context, job, sink) }, {})
        val first = runAgain()
        assertEquals(ImportJobState.Done, first.state)
        assertTrue(source.isFile)
        // Process death before WorkManager records success: source still exists and the same request is safe to repeat.
        val replay = runAgain()
        assertEquals(ImportJobState.Done, replay.state)
        assertEquals(first.bookId, replay.bookId)
        assertTrue(source.isFile)
        BookImports.cleanup(context, BookImports.completion(replay.copy(how = "conflict")))
        assertTrue(source.isFile)
        BookImports.cleanup(context, BookImports.completion(replay.copy(state = ImportJobState.Failed)))
        assertTrue(source.isFile)
        BookImports.cleanup(context, BookImports.completion(replay))
        assertFalse(source.exists())
        BookImports.cleanup(context, BookImports.completion(replay))
    }

    @Test fun stoppingDuringExtractionOrBeforePublicationKeepsTheSourceAndRemovesStaging() {
        Store.init(context)
        val source = fixtureBook("stopped-source.abook")
        val before = File(Store.root, "books").listFiles().orEmpty().filter { it.name.endsWith(".part") }.toSet()
        var chunks = 0
        try {
            BookFileImport.importFile(source, separate = true, progress = {
                chunks++
                if (chunks == 2) throw ImportStopped()
            })
            fail("stop was swallowed")
        } catch (_: ImportStopped) {
            assertEquals(2, chunks)
            assertTrue(source.isFile)
            assertEquals(before, File(Store.root, "books").listFiles().orEmpty().filter { it.name.endsWith(".part") }.toSet())
        }
        val published = File(Store.root, "books").listFiles().orEmpty().toSet()
        var checkpoints = 0
        try {
            BookFileImport.importFile(source, separate = true, checkpoint = {
                if (++checkpoints == 2) throw ImportStopped()
            })
            fail("publication stop was swallowed")
        } catch (_: ImportStopped) {
            assertEquals(2, checkpoints)
            assertTrue(source.isFile)
            assertEquals(published, File(Store.root, "books").listFiles().orEmpty().toSet())
        }
        assertNotNull(BookFileImport.importFile(source, separate = true).id)
    }

    /**
     * Bản bench 15-11: sau một file .abook hỏng, thêm TXT báo "Chưa thêm được sách. Đây không phải file sách của app.". Mỗi lượt có trạng thái riêng (bản tạm,
     * kiểu file, đường dẫn, lời lỗi): lượt hỏng trước không bao giờ đổi kết quả của lượt sau - theo cả hai chiều.
     */
    @Test fun aBrokenBookFileThenAValidTxtStillAdds() {
        Store.init(context)
        val broken = File(context.cacheDir, "Sach_lon.abook").apply { writeBytes(ByteArray(64 * 1024)) }
        val txt = File(context.cacheDir, "Sach_thu.txt").apply { writeBytes(File("../../../tests/fixtures/import/whole.txt").readBytes()) }
        val queue = ImportQueue(ImportRepo(context), scope)
        queue.enqueue(listOf(Uri.fromFile(broken).toString()))
        waitFor(queue, "broken .abook to finish") { ended(it.items.getOrNull(0)?.stage) && it.currentId == null }
        assertEquals(ImportStage.Error, stageOf(queue, 0))
        assertEquals("Chưa mở được file sách. Đây không phải file sách của app.", queue.state.value.items[0].problem)
        queue.enqueue(listOf(Uri.fromFile(txt).toString()))
        val review = waitFor(queue, "valid TXT preview after broken .abook") { it.items.getOrNull(1)?.stage == ImportStage.Review && it.preview != null && !it.busy }
        assertNull(review.packageReview)
        assertEquals("", review.problem)
        queue.add()
        val done = waitFor(queue, "valid TXT to finish adding after broken .abook") {
            ended(it.items.getOrNull(1)?.stage) || (!it.busy && it.problem.isNotBlank())
        }
        // Cùng file đã thêm ở test khác (Store dùng chung trong JVM test) thì "Đã có trong thư viện" - cũng là thành công; lỗi mới là sai.
        assertTrue(done.problem + done.items[1].problem, done.items[1].stage == ImportStage.Added || done.items[1].stage == ImportStage.Existing)
        val id = requireNotNull(done.items[1].bookId)
        assertNotNull(Store.manifest(id))
    }

    @Test fun aBrokenTxtThenAValidBookFileStillAdds() {
        Store.init(context)
        val broken = File(context.cacheDir, "Sach_hong.txt").apply { writeBytes("Noi dung.".toByteArray() + byteArrayOf(0x81.toByte())) }
        val book = fixtureBook("Sach_tot.abook")
        val queue = ImportQueue(ImportRepo(context), scope)
        queue.enqueue(listOf(Uri.fromFile(broken).toString()))
        waitFor(queue, "broken TXT to finish") { ended(it.items.getOrNull(0)?.stage) && it.currentId == null }
        assertEquals(ImportStage.Error, stageOf(queue, 0))
        queue.enqueue(listOf(Uri.fromFile(book).toString()))
        val done = waitFor(queue, "valid .abook to finish after broken TXT") { ended(it.items.getOrNull(1)?.stage) && it.currentId == null }
        assertTrue(done.items[1].problem, done.items[1].stage == ImportStage.Added || done.items[1].stage == ImportStage.Existing)
        assertNotNull(Store.manifest(requireNotNull(done.items[1].bookId)))
        assertNull(done.preview)
        assertEquals("", done.problem)
    }

    @Test fun viewStyleFileAndContentUrisApplyCoverAndScriptUpdatesAndKeepListening() = runBlocking {
        val provider = PackageProvider()
        provider.attachInfo(context, ProviderInfo().apply { authority = "metaupd-package" })
        ShadowContentResolver.registerProviderInternal("metaupd-package", provider)
        val repo = ImportRepo(context)
        for (contentUri in listOf(false, true)) {
            val base = File("../../../tests/fixtures/book_edits/base")
            val book = JSONObject(File(base, "book.json").readText())
            val content = book.getJSONObject("package").getJSONObject("files").keys().asSequence()
                .associateWith { File(base, it).readBytes() }.toMutableMap()
            // Independent books for the two VIEW URI schemes.
            val audio = content.keys.first { it.startsWith("chapters/") }
            content[audio] = content.getValue(audio) + contentUri.toString().toByteArray()
            suspend fun prepare(): PreparedImport {
                val files = JSONObject()
                for ((name, bytes) in content) files.put(name, JSONObject().put("size", bytes.size)
                    .put("sha256", java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }))
                book.getJSONObject("package").put("files", files).put("version", 6)
                val file = File(context.cacheDir, "Bản cập nhật.abook")
                ZipOutputStream(file.outputStream()).use { zip ->
                    val mime = BookFileImport.MIMETYPE.toByteArray()
                    zip.putNextEntry(ZipEntry("mimetype").apply {
                        method = ZipEntry.STORED; size = mime.size.toLong(); compressedSize = size
                        crc = java.util.zip.CRC32().apply { update(mime) }.value
                    })
                    zip.write(mime); zip.closeEntry()
                    for ((name, bytes) in content + ("book.json" to BookVolumes.nested(book).toString().toByteArray())) {
                        zip.putNextEntry(ZipEntry(name)); zip.write(bytes); zip.closeEntry()
                    }
                }
                provider.file = file
                val uri = if (contentUri) Uri.parse("content://metaupd-package/book") else Uri.fromFile(file)
                return repo.prepare(ImportItem(1, uri.toString()))
            }
            val first = prepare()
            val id = requireNotNull(first.bookId)
            Store.progress(id, 1, 4.5, 120.0)
            Store.setRate(id, 1.25)
            Store.setChapterDone(id, 1, true)
            val state = Store.state(id).toString()
            val cover = "new base cover".toByteArray()
            content["cover.jpg"] = cover
            book.put("cover", JSONObject().put("file", "cover.jpg").put("width", 12).put("height", 24))
            val covered = prepare()
            assertEquals(id, covered.bookId)
            assertFalse(covered.existing)
            assertEquals("Đã cập nhật “${Store.manifest(id)!!.getString("title")}”", covered.notice)
            assertArrayEquals(cover, File(Store.bookDir(id), "cover.jpg").readBytes())
            val script = "{\"text\":\"script-only update\"}".toByteArray()
            content["scripts/1.json"] = script
            val scripted = prepare()
            assertEquals(id, scripted.bookId)
            assertFalse(scripted.existing)
            assertArrayEquals(script, File(Store.bookDir(id), "scripts/1.json").readBytes())
            assertTrue(prepare().existing)
            assertEquals(state, Store.state(id).toString())
        }
    }

    class PackageProvider : ContentProvider() {
        lateinit var file: File
        override fun onCreate() = true
        override fun getType(uri: Uri) = BookFileImport.MIMETYPE
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor =
            MatrixCursor(projection ?: arrayOf(OpenableColumns.DISPLAY_NAME)).apply {
                addRow(columnNames.map<String, Any> { if (it == OpenableColumns.SIZE) file.length() else file.name }.toTypedArray())
            }
        override fun openFile(uri: Uri, mode: String) = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0
    }
    @Test fun fileUriKeepsItsVietnameseNameAndExtensionWithoutAProvider() = runBlocking {
        val file = File(context.cacheDir, "Sách của bạn.abook")
        assertEquals(file.name, ImportRepo(context).describe(ImportItem(1, Uri.fromFile(file).toString())))
    }
    @Test fun anActualFixturePackageCanBeOpenedFromAFileUri() = runBlocking {
        val file = fixtureBook("Sách thử.abook")
        val prepared = ImportRepo(context).prepare(ImportItem(1,Uri.fromFile(file).toString()))
        assertEquals(file.name, prepared.name)
        assertNotNull(prepared.bookId)
        assertNull(prepared.preview)
    }
}
