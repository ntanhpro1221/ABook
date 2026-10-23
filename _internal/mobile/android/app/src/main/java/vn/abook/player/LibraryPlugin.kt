package vn.abook.player

import android.Manifest
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import androidx.activity.result.ActivityResult
import androidx.core.view.WindowCompat
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.readaloud.VoiceSpeed
import java.io.File
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.net.URL
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit

/** Công tắc "Cho máy khác nghe thư viện này" (SharedPreferences "sync"). */
private const val SHARE_KEY = ShareService.SHARE_KEY

/** Số file tối đa trong một lần chọn nhiều file của "Thêm sách từ file…" (mỗi file được chép vào thư mục tạm của app trước khi xem trước). */
private const val PICK_SOURCE_LIMIT = 40
private const val HEAD_BYTES = 512 // đầu file đủ để thấy mục `mimetype` của gói (BookFileImport.looksLikeBookFile)

/** Số file tối đa trong một lượt nhập "Nhạc của tôi" (server.MY_MUSIC_IMPORT_LIMIT). */
private const val MY_MUSIC_IMPORT_LIMIT = 500
private const val STREAM_PARALLEL = 4 // số gói sách nghe thẳng lấy cùng lúc (streamableBooks)
private const val STREAM_BUDGET_MS = 12_000L // hết chừng này thì cuốn còn lại dùng gói đã cất, lượt hỏi sau lấy tiếp

/**
 * Thư viện trên điện thoại + đồng bộ với máy tính qua Wi-Fi (abook/webui/sync.py).
 *
 * Mọi mạng đi qua đây (native) chứ không qua fetch của WebView: trang chạy ở https://localhost, không ghim được chứng chỉ
 * tự ký của máy tính (Pin.kt), và tải hàng trăm MB audio thì nên làm ở luồng nền, ghi thẳng ra file.
 */
@CapacitorPlugin(
    name = "EbookLibrary",
    permissions = [
        Permission(strings = [Manifest.permission.POST_NOTIFICATIONS], alias = "notifications"),
        Permission(strings = [Manifest.permission.BLUETOOTH_CONNECT], alias = "bluetooth"),
    ],
)
class LibraryPlugin : Plugin() {
    private val io = Executors.newSingleThreadExecutor()
    // Trình phát máy khác (mạng trạm bước 4): hỏi mạng tới vài giây, không được chặn hàng `io` của thư viện.
    private val remotes = Executors.newCachedThreadPool()
    private val downloads = Executors.newSingleThreadExecutor()
    // Danh sách sách nghe thẳng hỏi máy tính và thiết bị ghép, chậm tới hàng chục giây khi mạng chập chờn: không được chặn hàng `io` (thư viện đã tải,
    // trang sách, chỗ nghe xếp hàng sau nó - soát a101 F2).
    private val streams = Executors.newSingleThreadExecutor()
    // Nhập nhạc của tôi: giải mã từng bản để đo độ to nên lâu - không được chặn hàng `io` của thư viện.
    private val musicImports = Executors.newSingleThreadExecutor()
    // Nhập file sách (.abook / .abookproj): chép + băm + giải nén vài GB mất phút - không được chặn hàng `io` (tiến độ nghe, thư viện, dấu trang
    // xếp hàng sau nó; app bị giết giữa chừng thì mất chỗ nghe). Một luồng riêng: hai lần nhập không giải nén chồng nhau.
    private val bookImports = Executors.newSingleThreadExecutor()
    private val prefs by lazy { SyncLink.prefs(context) }

    override fun load() {
        val musicStore = DeviceMusic.store(context)
        LocalStudio.musicStore = musicStore
        VoiceLabels.labels = VoiceLabels.load(context)
        LocalStudio.catalog = DeviceMusic.catalog(context)
        // Bộ phân tích nhạc: "Gói nhạc" (model + thư viện ONNX Runtime) tải khi người dùng bấm (không bao giờ tự tải); đã có từ lần trước thì cắm luôn, ở luồng nền.
        val abi = OrtRuntime.deviceAbi()
        val runtime = SharedRuntime.of(context)
        val student = MusicStudentSetup(File(context.filesDir, MusicStudentSetup.FOLDER), musicStore, { AndroidMusicStudent.open(it, runtime.dir, context.cacheDir) },
            runtime, files = MusicStudentSetup.PACKAGE + OrtRuntime.parts(abi), supported = abi != null, metered = { AndroidMusicStudent.metered(context) })
        LocalStudio.student = student
        musicImports.execute { runCatching { student.attachIfPresent() } }
        // Gửi phần sửa về máy tính xong: lấy lại sách từ máy ấy (không báo "Đã tải xong") và báo giao diện làm mới.
        EditsSync.refresh = { id -> refreshAfterPush(id) }
        EditsSync.changed = { id -> notifyListeners("editsSync", JSObject().put("bookId", id)) }
        ShareService.changed = { notifyListeners("shareChanged", JSObject()) }
        Mp3Exports.events = { event -> notifyListeners("mp3Export", JSObject.fromJSONObject(event)) }
        M4bExports.events = { event -> notifyListeners("m4bExport", JSObject.fromJSONObject(event)) }
        ListenExports.events = { event -> notifyListeners("audiobookExport", JSObject.fromJSONObject(event)) }
        BookDownloads.events = { event -> notifyListeners("download", JSObject.fromJSONObject(event)) }
        io.execute { runCatching { BookDownloads.restore(context) } } // lượt tải WorkManager còn giữ từ lần trước: tính là đang tải
        Playback.init(context)
        PhoneCast.init(context)
        TextImports.codec = AndroidCoverCodec
        TextImports.sweep() // thư mục tạm của lần "Thêm sách từ file…" bị bỏ dở lần trước
        bookImports.execute { runCatching { BookFileImport.sweepCache(context.cacheDir) } } // bản chép tạm `import-*.abook` của lần nhập bị giết giữa chừng
        io.execute { BookShare.sweep(context.cacheDir) } // file đã gửi qua "Chia sẻ…" lần trước: app nhận đã đọc xong từ lâu
        io.execute { runCatching { Store.sweepTrash(everything = true) } } // cuốn "Xoá khỏi điện thoại" còn nằm chờ Hoàn tác từ lần trước: nút ấy đã mất, xoá hẳn
        io.execute { runCatching { ListenExports.sweep(context) } } // chương tạm của "Xuất sách nói" cho cuốn đã xoá, hay bỏ dở quá 7 ngày
        // Đã bật "Cho máy khác nghe thư viện này" từ lần trước: mở lại máy chủ cùng app (LibraryServer).
        if (prefs.getBoolean(SHARE_KEY, false)) io.execute { runCatching { ShareService.enable(context) } }
    }

    private fun background(call: PluginCall, block: () -> Unit) = io.execute {
        try {
            block()
        } catch (error: Exception) {
            fail(call, error)
        }
    }

    private fun streaming(call: PluginCall, block: () -> Unit) = streams.execute {
        try {
            block()
        } catch (error: Exception) {
            fail(call, error)
        }
    }

    /**
     * Từ chối lời gọi; chứng chỉ máy kia đổi thì kèm mã [Pin.CODE] để giao diện hiện câu "ghép lại" thay vì "không kết nối được". Máy kia trả 401: mã
     * [NetErrors.UNPAIRED] (nó đã thôi ghép máy này). Lỗi mạng: câu tiếng Việt theo loại, mã là tên loại, chữ gốc trong `data.technical` (soát a68 lỗi 4, 5).
     */
    private fun fail(call: PluginCall, error: Exception, fallback: String = error.javaClass.simpleName) {
        val (message, technical) = describe(error, fallback)
        when {
            error is Pin.ChangedException -> call.reject(message, Pin.CODE)
            NetErrors.unpaired(error) -> call.reject(message, NetErrors.UNPAIRED)
            technical != null -> call.reject(message, NetErrors.kind(error)?.name, null, JSObject().put("technical", technical))
            else -> call.reject(message)
        }
    }

    /** Lời cho người nghe + chữ gốc (chỉ khi là lỗi mạng đã dịch thành câu) - dùng chung cho lời gọi bị từ chối và sự kiện "download". */
    private fun describe(error: Exception, fallback: String = error.javaClass.simpleName): Pair<String, String?> = BookDownloads.describe(error, fallback)

    // Large options (the drawn cover of an export) wait in memory while a system picker is open - see HeldCallFields.
    private val held = HeldCallFields()

    override fun startActivityForResult(call: PluginCall, intent: Intent, callbackName: String) {
        held.take(call.methodName, call.data)
        super.startActivityForResult(call, intent, callbackName)
    }

    /** First thing in every @ActivityCallback: the call gets back the options [startActivityForResult] held. */
    private fun answered(call: PluginCall?) {
        if (call != null) held.putBack(call.methodName, call.data)
    }

    @PluginMethod
    fun info(call: PluginCall) = call.resolve(JSObject().put("root", Store.root.absolutePath))

    // ---- mở file sách (.abook) -------------------------------------------------------------------------------

    /**
     * Nhập một file sách (BookFileImport) ở luồng nền rồi báo "import" lên giao diện: mở từ trình quản lý file, Zalo,
     * Drive (MainActivity) hay nút "Nhập sách". Sự kiện được GIỮ tới khi giao diện nghe: mở app lạnh bằng file thì
     * việc nhập có thể xong trước khi trang web kịp gắn listener.
     */
    fun importFrom(uri: Uri, allowOlder: Boolean = false) = bookImports.execute {
        val event = try {
            val imported = BookFileImport.import(context, uri, allowOlder)
            JSObject().put("bookId", imported.id).put("title", imported.title).put("keptEdits", imported.keptEdits)
                .put("brokenMusic", imported.brokenMusic)
                .put("how", imported.how).put("source", uri.toString())
        } catch (error: BookFileImport.Refused) {
            JSObject().put("error", error.message)
        } catch (error: Exception) {
            JSObject().put("error", "Không mở được file sách: ${error.message ?: error.javaClass.simpleName}")
        }
        notifyListeners("import", event, true)
    }

    @PluginMethod
    fun confirmOlderImport(call: PluginCall) {
        val source = call.getString("source") ?: return call.reject("thiếu file nguồn")
        importFrom(Uri.parse(source), true)
        call.resolve()
    }

    @PluginMethod
    fun exportHistory(call: PluginCall) = background(call) {
        val id = call.getString("bookId") ?: throw IllegalArgumentException("thiếu bookId")
        call.resolve(JSObject().put("exports", ExportHistory.view(Store.bookDir(id))))
    }

    /**
     * File app khác gửi tới ("Mở bằng ABook", chia sẻ tới ABook - MainActivity): EPUB / DOCX / PDF / TXT vào bước xem trước của "Thêm sách
     * từ file…" (chép vào thư mục tạm như bộ chọn, giao diện nghe sự kiện `textPicked` - android/imports.ts); còn lại là file sách,
     * đi [importFrom] như trước.
     */
    fun openFrom(uri: Uri, mime: String?) = io.execute {
        val type = mime ?: runCatching { context.contentResolver.getType(uri) }.getOrNull()
        val shown = displayName(uri) ?: uri.lastPathSegment
        val name = TextImports.incomingName(type, shown)
        if (name == null) {
            // Chia sẻ qua kiểu chung (octet-stream, zip): kiểm tên / đầu file trước khi nhập, file lạ thì nói rõ (soát a99 V6).
            val refusal = TextImports.refuseShared(type, shown) {
                runCatching { context.contentResolver.openInputStream(uri)?.use { input -> ByteArray(HEAD_BYTES).let { buffer -> buffer.copyOf(maxOf(0, input.read(buffer))) } } }.getOrNull()
            }
            if (refusal != null) {
                notifyListeners("import", JSObject().put("error", refusal), true)
                return@execute
            }
            importFrom(uri)
            return@execute
        }
        val event = try {
            val staged = stageDocument(uri, name)
            JSObject().put("ref", staged.ref).put("name", staged.name).also { reply -> staged.pdf?.let { reply.put("pdf", it.absolutePath) } }
        } catch (error: Exception) {
            JSObject().put("error", error.message ?: "Không đọc được file này")
        }
        notifyListeners("textPicked", event, true)
    }

    /** Nút "Nhập sách": chọn file bằng bộ chọn của hệ thống (mọi loại - trình quản lý file không biết đuôi .abook). */
    @PluginMethod
    fun pickBook(call: PluginCall) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
        startActivityForResult(call, intent, "pickedBook")
    }

    @ActivityCallback
    private fun pickedBook(call: PluginCall?, result: ActivityResult) {
        answered(call)
        val uri = result.data?.data
        if (uri == null) {
            call?.resolve(JSObject().put("picked", false))
            return
        }
        // Một nút nhận mọi loại file: file chữ (EPUB / DOCX / PDF / TXT) vào bước xem trước, file sách vào Thư viện.
        openFrom(uri, null)
        call?.resolve(JSObject().put("picked", true))
    }

    // ---- "Thêm sách từ file…": EPUB / DOCX / PDF / thư mục TXT thành sách chỉ có chữ (TextImports, docs/LISTEN_ANYTHING.md) -----------------

    /** Bộ chọn file (hay thư mục TXT) của hệ thống; thứ chọn được chép vào thư mục tạm của app, trả `ref` để xem trước và thêm.
     *  `multiple` (chỉ với file): chọn được nhiều file một lúc, trả `items` - mỗi file một `{ref, name, pdf?}`, `{book: true, name}` (file sách .abook đã mở),
     *  hay `{name, error}` (không chép được: một file hỏng không làm hỏng cả lượt). */
    @PluginMethod
    fun pickSource(call: PluginCall) {
        val intent = if (call.getString("kind") == "folder") Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
        else Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
            .apply { if (call.getBoolean("multiple") == true) putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true) }
        startActivityForResult(call, intent, "pickedSource")
    }

    @ActivityCallback
    private fun pickedSource(call: PluginCall?, result: ActivityResult) {
        answered(call)
        if (call == null) return
        val uris = ArrayList<Uri>()
        result.data?.clipData?.let { clip -> for (index in 0 until clip.itemCount) uris.add(clip.getItemAt(index).uri) }
        result.data?.data?.let { if (it !in uris) uris.add(it) }
        if (uris.isEmpty()) {
            call.resolve(JSObject().put("picked", false))
            return
        }
        val folder = call.getString("kind") == "folder"
        val multiple = !folder && call.getBoolean("multiple") == true
        io.execute {
            try {
                if (multiple) {
                    val items = JSArray()
                    for (uri in uris.take(PICK_SOURCE_LIMIT)) {
                        items.put(
                            try {
                                stagedSource(uri, false)
                            } catch (error: Exception) {
                                JSObject().put("name", displayName(uri) ?: uri.lastPathSegment ?: "file").put("error", error.message ?: "Không đọc được file này")
                            },
                        )
                    }
                    call.resolve(JSObject().put("picked", true).put("items", items))
                } else {
                    call.resolve(stagedSource(uris[0], folder).put("picked", true))
                }
            } catch (error: Exception) {
                fail(call, error, "không đọc được thứ đã chọn")
            }
        }
    }

    /** Một thứ đã chọn thành JSON cho giao diện: `{ref, name, pdf?}` (đã chép vào thư mục tạm), hay `{book: true, name}` khi là file sách .abook (người dùng chỉ có
     *  một nút "Thêm sách từ file…": mở như "Mở file sách"). Ném lỗi khi không chép được. */
    private fun stagedSource(uri: Uri, folder: Boolean): JSObject {
        val shown = displayName(uri) ?: uri.lastPathSegment
        if (!folder && TextImports.isAppBookFile(runCatching { context.contentResolver.getType(uri) }.getOrNull(), shown)) {
            importFrom(uri)
            return JSObject().put("name", shown ?: "Sách").put("book", true)
        }
        val staged = if (folder) stageTree(uri) else stageDocument(uri)
        val reply = JSObject().put("ref", staged.ref).put("name", staged.name)
        staged.pdf?.let { reply.put("pdf", it.absolutePath) }
        return reply
    }

    private fun displayName(uri: Uri): String? = runCatching {
        context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
    }.getOrNull()

    private fun stageDocument(uri: Uri, name: String? = null): TextImports.Staged =
        TextImports.stageFile(name ?: displayName(uri) ?: uri.lastPathSegment ?: "sach") { context.contentResolver.openInputStream(uri) }

    /** Thư mục TXT: chỉ các file nằm ngay trong thư mục (như Studio), không quét thư mục con. */
    private fun stageTree(tree: Uri): TextImports.Staged {
        val treeId = android.provider.DocumentsContract.getTreeDocumentId(tree)
        val folderName = displayName(android.provider.DocumentsContract.buildDocumentUriUsingTree(tree, treeId)) ?: "Sách"
        val children = android.provider.DocumentsContract.buildChildDocumentsUriUsingTree(tree, treeId)
        val files = ArrayList<Pair<String, () -> java.io.InputStream?>>()
        context.contentResolver.query(
            children,
            arrayOf(android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID, android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE),
            null, null, null,
        )?.use { cursor ->
            while (cursor.moveToNext()) {
                if (cursor.getString(2) == android.provider.DocumentsContract.Document.MIME_TYPE_DIR) continue
                val document = android.provider.DocumentsContract.buildDocumentUriUsingTree(tree, cursor.getString(0))
                files.add(cursor.getString(1) to { context.contentResolver.openInputStream(document) })
            }
        }
        return TextImports.stageFolder(folderName, files)
    }

    /** Đọc thứ đã chọn bằng luật nhập sách (BookImport.kt) và trả danh sách chương; PDF kèm `pages` (các dòng từng trang) do pdf.js lấy trong WebView. */
    @PluginMethod
    fun previewImport(call: PluginCall) = background(call) {
        val ref = call.getString("ref") ?: throw IllegalArgumentException("thiếu ref")
        val pages = TextImports.pagesOf(call.getArray("pages"))
        call.resolve(JSObject.fromJSONObject(TextImports.preview(ref, pages, call.getString("title") ?: "", call.getString("author") ?: "",
            call.getBoolean("splitChapters") ?: false, BookImport.footnoteChoiceFromJson(call.getObject("footnotes")))))
    }

    /** Nhập thành sách chỉ có chữ trong thư viện; trả {id, how, chapters}. */
    @PluginMethod
    fun createImport(call: PluginCall) = background(call) {
        val ref = call.getString("ref") ?: throw IllegalArgumentException("thiếu ref")
        val separate = call.getBoolean("separate") ?: false
        val picks = TextImports.picksOf(call.getArray("chapters"))
        call.resolve(JSObject.fromJSONObject(TextImports.create(ref, call.getString("title") ?: "", context.cacheDir, separate, picks)))
    }

    @PluginMethod
    fun discardImport(call: PluginCall) = background(call) {
        TextImports.discard(call.getString("ref") ?: "")
        call.resolve()
    }

    // ---- "Nhạc của tôi" (MusicStore, docs/MUSIC_IMPORT.md) -------------------------------------------------------------

    /** Nút "Nhập nhạc của tôi…": bộ chọn file của hệ thống, chọn được nhiều bản một lúc; chọn xong thì nhập từng bản vào kho. */
    @PluginMethod
    fun pickMusic(call: PluginCall) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true).putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("audio/*", "application/ogg"))
        startActivityForResult(call, intent, "pickedMusic")
    }

    @ActivityCallback
    private fun pickedMusic(call: PluginCall?, result: ActivityResult) {
        answered(call)
        if (call == null) return
        val uris = ArrayList<Uri>()
        result.data?.clipData?.let { clip -> for (index in 0 until clip.itemCount) uris.add(clip.getItemAt(index).uri) }
        result.data?.data?.let { if (it !in uris) uris.add(it) }
        if (uris.isEmpty()) {
            call.resolve(JSObject().put("picked", false))
            return
        }
        musicImports.execute {
            try {
                call.resolve(importMusic(uris.take(MY_MUSIC_IMPORT_LIMIT)))
            } catch (error: Exception) {
                fail(call, error, "không nhập được nhạc")
            }
        }
    }

    /** Nhập từng bản (một bản hỏng không làm hỏng cả lượt), báo tiến độ "musicImport" {done, total}; trả đúng JSON của `my_music_import`. */
    private fun importMusic(uris: List<Uri>): JSObject {
        val store = LocalStudio.musicStore ?: throw IllegalStateException("Kho nhạc chưa sẵn sàng")
        val added = ArrayList<JSONObject>()
        val existing = ArrayList<JSONObject>()
        val failed = ArrayList<String>()
        for ((index, uri) in uris.withIndex()) {
            val name = runCatching {
                context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                }
            }.getOrNull() ?: uri.lastPathSegment ?: "nhạc"
            try {
                val (track, duplicate) = store.importStream(name) { context.contentResolver.openInputStream(uri) }
                (if (duplicate) existing else added).add(track)
            } catch (error: MusicStore.ImportError) {
                failed.add(error.message.orEmpty())
            } catch (error: Exception) {
                failed.add("“$name”: không nhập được (${error.message ?: error.javaClass.simpleName}).")
            }
            notifyListeners("musicImport", JSObject().put("done", index + 1).put("total", uris.size))
        }
        if (added.isNotEmpty()) Playback.onMain { MusicBed.refreshMine() }
        return JSObject.fromJSONObject(LocalStudio.importAnswer(added, existing, failed)).put("picked", true)
    }

    // ---- ghép nối --------------------------------------------------------------------------------------------

    private fun base(): String = SyncLink.base(context)

    private fun request(method: String, path: String, body: JSONObject? = null, auth: Boolean = true, root: String = base()): String =
        SyncLink.request(context, method, path, body, auth, root)

    /** Tìm máy tính đang bật đồng bộ trong cùng mạng Wi-Fi (UDP broadcast). */
    @PluginMethod
    fun discover(call: PluginCall) = background(call) {
        val found = JSArray()
        val seen = mutableSetOf<String>()
        val own = LibraryServer.addresses().toSet() + "127.0.0.1"
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.soTimeout = 400
            val probe = "ABOOK_DISCOVER".toByteArray()
            val deadline = System.currentTimeMillis() + (call.getInt("timeoutMs") ?: 2500)
            var sent = 0
            while (System.currentTimeMillis() < deadline) {
                if (sent < 3) {
                    runCatching { socket.send(DatagramPacket(probe, probe.size, InetAddress.getByName("255.255.255.255"), 47631)) }
                    sent += 1
                }
                val buffer = ByteArray(4096)
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    socket.receive(packet)
                    val reply = JSONObject(String(packet.data, 0, packet.length))
                    val host = packet.address.hostAddress ?: continue
                    // Chính điện thoại này (đang cho máy khác nghe thư viện - LibraryServer) cũng trả lời: bỏ.
                    if (host in own && reply.optInt("port") == LibraryServer.PORT) continue
                    val address = PeerAddresses.discoveryEndpoint(host, reply.opt("port")) ?: continue
                    val port = PeerAddresses.split(address).second
                    if (reply.optString("app") == "abook" && seen.add(address)) {
                        PeerRouting.discovered(context, host, port, reply.optString("fingerprint"))
                        found.put(JSObject().put("host", host).put("port", port).put("name", reply.optString("name"))
                            .put("kind", reply.optString("kind", "computer")))
                    }
                } catch (_: SocketTimeoutException) {
                } catch (_: org.json.JSONException) {
                    // A malformed UDP responder must not discard the remaining discoveries.
                }
            }
        }
        call.resolve(JSObject().put("computers", found))
    }

    @PluginMethod
    fun pair(call: PluginCall) = background(call) {
        val host = call.getString("host") ?: throw IllegalArgumentException("thiếu địa chỉ máy tính")
        val port = call.getInt("port") ?: 47630
        SyncLink.refuseSelf(host, port)
        val device = call.getString("device") ?: DeviceName.of(context)
        val body = JSONObject().put("code", call.getString("code") ?: "").put("device", device)
        val (reply, fingerprint) = SyncLink.pair(context, "https://${PeerAddresses.endpoint(host, port)}", body)
        SyncLink.saveRoutes(prefs.edit().putString("host", host).putInt("port", port).putString("token", reply.getString("token"))
            .putString("fingerprint", fingerprint).putString("name", reply.optString("name")), reply, host, port, fingerprint,
            PeerRouting.main(context).takeIf { it.optString("fingerprint").equals(fingerprint, true) }).commit()
        // Ô địa chỉ nhớ máy đã ghép lần trước (soát a68 lỗi 20): ngoài "sync" vì thôi ghép xoá sạch "sync" - ghép lại là lúc cần nó nhất.
        context.getSharedPreferences("abook_self", Context.MODE_PRIVATE).edit().putString("lastAddress", "$host:$port").apply()
        Remote.ensure()
        call.resolve(JSObject().put("name", reply.optString("name")))
    }

    /** Đổi tên điện thoại này ở máy khác (soát a68 lỗi 16); rỗng = tên mặc định. Báo ngay máy tính chính và các máy đã ghép (máy tắt thì lần ghép sau). */
    @PluginMethod
    fun setDeviceName(call: PluginCall) = background(call) {
        val name = DeviceName.set(context, call.getString("name") ?: "")
        val body = JSONObject().put("name", name)
        if (SyncLink.paired(context)) runCatching { SyncLink.request(context, "POST", "/sync/v1/name", body, readTimeoutMs = 5000, connectTimeoutMs = 2000) }
        for (key in Peers.all(context).keys()) runCatching { Peers.request(context, key, "POST", "/sync/v1/name", body, readTimeoutMs = 5000, connectTimeoutMs = 2000) }
        call.resolve(JSObject().put("name", name))
    }

    // ---- qua Bluetooth (BluetoothLink, BtMux) -------------------------------------------------------------------------

    /** Máy đã ghép Bluetooth với điện thoại. Android 12+: xin quyền "Thiết bị ở gần" lần đầu. */
    @PluginMethod
    fun bluetoothDevices(call: PluginCall) {
        if (!BluetoothLink.permitted(context)) {
            requestPermissionForAlias("bluetooth", call, "bluetoothDevicesAfterPermission")
            return
        }
        bluetoothDevicesAfterPermission(call)
    }

    /** Quyền "Thiết bị ở gần" lúc này, trước khi xin (giao diện giải thích trước, hay chỉ tới Cài đặt khi đã bị từ chối hẳn): "granted",
     *  "prompt", "prompt-with-rationale" (đã từ chối một lần), "denied" (từ chối hẳn - hộp xin của Android không hiện nữa). Android < 12 không cần. */
    @PluginMethod
    fun bluetoothPermission(call: PluginCall) {
        val state = if (BluetoothLink.permitted(context)) "granted" else getPermissionState("bluetooth")?.toString() ?: "prompt"
        call.resolve(JSObject().put("state", state))
    }

    @PermissionCallback
    private fun bluetoothDevicesAfterPermission(call: PluginCall) = background(call) {
        if (!BluetoothLink.permitted(context)) throw IllegalStateException("Cần cho ABook dùng \"Thiết bị ở gần\" để kết nối qua Bluetooth")
        val out = JSArray()
        val devices = BluetoothLink.devices(context)
        for (index in 0 until devices.length()) out.put(JSObject.fromJSONObject(devices.getJSONObject(index)))
        call.resolve(JSObject().put("devices", out))
    }

    /** Ghép máy tính chính QUA BLUETOOTH: cùng mã 6 số, cùng /sync/v1/pair - đi qua đường hầm. */
    @PluginMethod
    fun pairBluetooth(call: PluginCall) = background(call) {
        val address = call.getString("address") ?: throw IllegalArgumentException("thiếu máy")
        val device = call.getString("device") ?: DeviceName.of(context)
        val body = JSONObject().put("code", call.getString("code") ?: "").put("device", device)
        val root = BluetoothLink.base(context, address)
        val (reply, fingerprint) = try {
            SyncLink.pair(context, root, body)
        } catch (error: Exception) {
            val reason = BluetoothLink.lastError(address)
            throw IllegalStateException(reason.ifBlank { error.message ?: "không kết nối được qua Bluetooth" })
        }
        SyncLink.saveRoutes(prefs.edit().putString("host", "bt:$address").putInt("port", 0).putString("token", reply.getString("token"))
            .putString("fingerprint", fingerprint).putString("name", reply.optString("name")), reply, "bt:$address", 0, fingerprint,
            PeerRouting.main(context).takeIf { it.optString("fingerprint").equals(fingerprint, true) }).commit()
        Remote.ensure()
        call.resolve(JSObject().put("name", reply.optString("name")))
    }

    // ---- cho máy khác nghe thư viện này (mạng trạm bước 2 - LibraryServer) ------------------------------------------

    private fun shareView(): JSObject {
        LibraryServer.init(context)
        // Màn hình hỏi trạng thái sau khi người dùng vừa cho quyền "Thiết bị ở gần" hay vừa bật Bluetooth: thử nghe lại.
        if (LibraryServer.running()) BluetoothShare.retry()
        val devices = JSArray()
        val list = LibraryServer.devices()
        for (index in 0 until list.length()) devices.put(JSObject.fromJSONObject(list.getJSONObject(index)))
        val pairing = LibraryServer.pairingCode()
        return JSObject().put("running", LibraryServer.running()).put("name", LibraryServer.name())
            .put("port", LibraryServer.PORT).put("addresses", JSArray(LibraryServer.addresses()))
            .put("pairing", if (pairing != null) JSObject.fromJSONObject(pairing) else JSONObject.NULL)
            .put("blocked", LibraryServer.blocked).put("devices", devices).put("error", LibraryServer.lastError)
            .put("fingerprint", if (LibraryServer.fingerprint.isEmpty()) "" else Pin.display(LibraryServer.fingerprint))
            .put("bluetooth", JSObject().put("status", BluetoothShare.status).put("connections", BluetoothShare.connections()))
            .also { backgroundView(it) }
    }

    /**
     * Hãng máy (chọn lời chỉ đường cho chạy nền: OPPO, Xiaomi, Samsung...) và ABook đã được miễn tối ưu pin chưa. Máy hãng cho app "ngủ"
     * khi ở nền; bật "Cho phép hoạt động dưới nền" thì ABook vào danh sách miễn và cờ này thành true. Chỉ đọc - app không tự xin miễn.
     */
    private fun backgroundView(into: JSObject = JSObject()): JSObject =
        into.put("manufacturer", Build.MANUFACTURER.orEmpty())
            .put("backgroundAllowed", context.getSystemService(PowerManager::class.java)?.isIgnoringBatteryOptimizations(context.packageName) ?: false)

    @PluginMethod
    fun shareStatus(call: PluginCall) = background(call) { call.resolve(shareView()) }

    /** Màn xuất hỏi riêng (không dựng cả trạng thái chia sẻ): có nhắc người dùng cho ABook chạy nền hay không. */
    @PluginMethod
    fun backgroundStatus(call: PluginCall) = call.resolve(backgroundView())

    /**
     * Trang thông tin ứng dụng của ABook trong Cài đặt Android - nơi người dùng cho ABook chạy nền (máy hãng cho app "ngủ" khi
     * ở nền, máy tính phải chờ). Chỉ dùng intent công khai; không mở trang riêng của hãng (không có tài liệu, đổi theo bản).
     */
    @PluginMethod
    fun openAppSettings(call: PluginCall) {
        val intent = Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { context.startActivity(intent) }
            .onSuccess { call.resolve() }
            .onFailure { call.reject("Không mở được cài đặt của ABook") }
    }

    /** Giao diện của app lúc này (systemBars): sáng/tối + màu thân app. */
    private var bars: Pair<Boolean, Int?>? = null

    /**
     * Thanh trạng thái + thanh điều hướng theo giao diện của APP chứ không theo sáng/tối của máy (app sáng trên máy tối và ngược lại; đổi
     * khi đang mở thì Activity không dựng lại - uiMode trong configChanges): màu biểu tượng + dải nền sau thanh (nền của decorView) khớp thân app.
     */
    @PluginMethod
    fun systemBars(call: PluginCall) {
        val color = runCatching { Color.parseColor(call.getString("color") ?: "") }.getOrNull()
        bars = (call.getBoolean("dark") ?: false) to color
        activity.runOnUiThread {
            applyBars()
            call.resolve()
        }
    }

    private fun applyBars() {
        val (dark, color) = bars ?: return
        val window = activity.window
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !dark
            isAppearanceLightNavigationBars = !dark
        }
        if (color != null) window.decorView.setBackgroundColor(color)
    }

    override fun handleOnConfigurationChanged(newConfig: Configuration) {
        super.handleOnConfigurationChanged(newConfig)
        // SystemBars của Capacitor đặt lại theo máy mỗi lần cấu hình đổi (xoay, máy chuyển sáng/tối): đặt lại theo app, sau nó.
        bridge.executeOnMainThread { applyBars() }
    }

    @PluginMethod
    fun setShare(call: PluginCall) {
        // Bật chia sẻ chạy một dịch vụ nền có thông báo thường trực (ShareService) để Android không đóng băng app khi tắt màn hình:
        // Android 13+ xin quyền thông báo trước. Bị từ chối thì chia sẻ vẫn bật (dịch vụ vẫn chạy, chỉ không hiện trong ngăn thông báo).
        if ((call.getBoolean("enabled") ?: false) && Build.VERSION.SDK_INT >= 33 && !StudioAlerts.permitted(context)) {
            requestPermissionForAlias("notifications", call, "setShareAfterPermission")
        } else {
            setShareNow(call)
        }
    }

    @PermissionCallback
    private fun setShareAfterPermission(call: PluginCall) = setShareNow(call)

    private fun setShareNow(call: PluginCall) = background(call) {
        if (call.getBoolean("enabled") ?: false) ShareService.turnOn(context) else ShareService.turnOff(context)
        call.resolve(shareView())
    }

    @PluginMethod
    fun sharePair(call: PluginCall) = background(call) {
        if (!LibraryServer.running()) ShareService.enable(context)
        LibraryServer.startPairing()
        call.resolve(shareView())
    }

    @PluginMethod
    fun shareCancelPairing(call: PluginCall) = background(call) {
        LibraryServer.cancelPairing()
        call.resolve(shareView())
    }

    @PluginMethod
    fun shareRevoke(call: PluginCall) = background(call) {
        LibraryServer.revoke(call.getString("id") ?: "")
        call.resolve(shareView())
    }

    @PluginMethod
    fun connection(call: PluginCall) {
        val paired = !prefs.getString("token", "").isNullOrBlank()
        call.resolve(
            JSObject().put("paired", paired).put("host", prefs.getString("host", "")).put("port", prefs.getInt("port", 47630))
                .put("name", prefs.getString("name", "")).put("fingerprint", prefs.getString("fingerprint", "") ?: "")
                .put("connectedVia", prefs.getString("connectedVia", ""))
                .put("lastAddress", context.getSharedPreferences("abook_self", Context.MODE_PRIVATE).getString("lastAddress", "") ?: "")
                .put("deviceName", DeviceName.of(context)),
        )
    }

    @PluginMethod
    fun unpair(call: PluginCall) {
        // Máy tính chính thu hồi mã của điện thoại này (soát a27 lỗi 5): báo trước khi quên địa chỉ - máy tính tắt thì chỉ chờ vài giây.
        Thread({
            runCatching { SyncLink.tellUnpaired(context, SyncLink.base(context), SyncLink.token(context)) }
            prefs.getString("host", null)?.takeIf { it.startsWith("bt:") }?.let { BluetoothLink.forget(it) }
            prefs.edit().clear().apply()
            call.resolve()
        }, "sync-unpair").start()
    }

    /** Thông báo Studio (StudioAlerts.kt): công tắc, và Android có cho app đăng thông báo không. */
    @PluginMethod
    fun studioAlerts(call: PluginCall) {
        call.resolve(JSObject().put("enabled", StudioAlerts.enabled(context)).put("permitted", StudioAlerts.permitted(context)))
    }

    @PluginMethod
    fun setStudioAlerts(call: PluginCall) {
        val on = call.getBoolean("enabled") ?: false
        // Android 13+: bật mà chưa có quyền thông báo thì xin trước; người dùng từ chối thì công tắc vẫn lưu, màn hình
        // nói rõ "chưa cho phép thông báo".
        if (on && Build.VERSION.SDK_INT >= 33 && !StudioAlerts.permitted(context)) {
            requestPermissionForAlias("notifications", call, "studioAlertsAfterPermission")
        } else {
            studioAlertsAfterPermission(call)
        }
    }

    @PermissionCallback
    private fun studioAlertsAfterPermission(call: PluginCall) {
        StudioAlerts.setEnabled(context, call.getBoolean("enabled") ?: false)
        studioAlerts(call)
    }

    /** Máy tính mở Studio được (StudioLink.computers): máy tính chính rồi các máy tính ghép thêm - nút "Mở Studio" hỏi chọn khi có hơn một. */
    @PluginMethod
    fun studioComputers(call: PluginCall) = background(call) {
        val out = JSArray()
        // `book` (mã cuốn trên điện thoại này): máy tính GIỮ cuốn ấy - "Mở Studio" ở trang sách đi thẳng tới máy ấy (openStudio), nên chip phải xét quyền của
        // chính máy ấy chứ không của cả danh sách (`holdsBook`).
        val holder = call.getString("book")?.let { StudioLink.bookTarget(it)?.first }
        for (computer in StudioLink.computers(context)) {
            // Máy tính chỉ cho điện thoại này nghe: nút "Mở Studio" nói thẳng thay vì mở một trang Studio đóng (`listenOnly`). Không hỏi được = coi như mở được.
            val listenOnly = StudioLink.link(context, computer.key)?.let { link ->
                runCatching {
                    StudioLink.listenOnly(SyncLink.request(context, "GET", "/api/app", auth = false, root = link.base, token = link.token,
                        readTimeoutMs = 3000, connectTimeoutMs = 2000))
                }.getOrDefault(false)
            } ?: false
            out.put(JSObject().put("key", computer.key).put("name", computer.name).put("listenOnly", listenOnly).apply { if (computer.key == holder) put("holdsBook", true) })
        }
        call.resolve(JSObject().put("computers", out))
    }

    /**
     * Studio từ xa (StudioActivity.kt): trang Studio của một máy tính đã ghép, mang sẵn mã thiết bị. `book`: mã cuốn trên điện thoại này -
     * mở thẳng cuốn ấy trong Studio của máy tính giữ nó (StudioLink.bookTarget); không thì `computer` (mã máy, "" = máy tính chính) ở
     * danh sách dự án. Chỉ mã máy và đường trang đi qua Intent, không bao giờ mã thiết bị.
     */
    @PluginMethod
    fun openStudio(call: PluginCall) = background(call) {
        val book = call.getString("book")
        val (computer, path) = if (book != null) {
            val (key, remote) = StudioLink.bookTarget(book) ?: throw IllegalStateException("Cuốn này không làm trên máy tính nào đã ghép")
            key to StudioLink.bookPath(remote)
        } else {
            (call.getString("computer") ?: StudioLink.MAIN) to StudioLink.bookPath(null)
        }
        if (!StudioLink.known(computer, SyncLink.paired(context), Peers.all(context))) throw IllegalStateException("Chưa ghép với máy tính nào")
        activity.startActivity(Intent(activity, StudioActivity::class.java).putExtra("computer", computer).putExtra("path", path))
        call.resolve()
    }

    /**
     * Mở trang (hay file APK) của bản phát hành mới bằng trình duyệt của máy: điện thoại không tự cập nhật như app Windows,
     * nên Cài đặt báo có bản mới và mời tải (updates.ts). Chỉ mở đường của chính ABook trên GitHub - không phải cửa mở mọi
     * địa chỉ cho trang web trong app.
     */
    @PluginMethod
    fun openRelease(call: PluginCall) {
        val url = call.getString("url").orEmpty()
        if (!url.startsWith("https://github.com/ntanhpro1221/ABook/")) {
            call.reject("Chỉ mở trang phát hành của ABook")
            return
        }
        runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
            .onSuccess { call.resolve() }
            .onFailure { call.reject("Không mở được trình duyệt: ${it.message}") }
    }

    @PluginMethod
    fun remoteLibrary(call: PluginCall) = background(call) {
        val reply = JSONObject(request("GET", "/sync/v1/library"))
        val books = reply.getJSONArray("books")
        matchImported(listed(books))
        for (index in 0 until books.length()) {
            val book = books.getJSONObject(index)
            runCatching { refreshMetadata(book.getString("id"), book) }
            val local = Store.rawManifest(book.getString("id"))
            book.put("downloaded", local != null)
            book.put("localChapters", local?.optInt("chaptersAvailable") ?: 0)
            book.put("localCoverVersion", local?.optJSONObject("cover")?.optLong("version") ?: 0L)
            book.put("localWordsVersion", local?.optString("wordsVersion") ?: "")
            book.put("localAudioVersion", local?.optString("audioVersion") ?: "")
            book.put("localMetaVersion", local?.optString("metaVersion") ?: "")
            // Cỡ khi tải về, hiện trước khi bấm Tải (soát a68 lỗi 7): máy tính gửi kèm (`bytes`); máy tính đời trước thì lấy từ gói sách đã cất
            // cho nghe thẳng nếu còn đúng - không hỏi máy tính từng cuốn (thư viện vài chục cuốn thành vài chục lượt mạng).
            if (local == null && !book.has("bytes")) {
                Store.streamManifest(book.getString("id"))?.takeIf { it.optInt("chaptersAvailable") == book.optInt("chaptersAvailable") }
                    ?.let { book.put("bytes", DownloadSpace.bookBytes(it)) }
            }
        }
        call.resolve(JSObject().put("name", reply.optString("name")).put("books", books))
        EditsSync.scheduleAllPending(context) // tới được máy tính: gửi nốt phần sửa còn tồn
        StateSync.flushPending(context) // chỗ nghe ghi trong lúc mất kết nối (soát a68 lỗi 9)
    }

    private fun matchImported(listed: Set<String>? = null) = BookDownloads.matchImported(context, listed)

    private fun listed(books: JSONArray): Set<String> =
        (0 until books.length()).mapNotNull { books.optJSONObject(it)?.optString("id")?.takeIf(String::isNotEmpty) }.toSet()

    // ---- tải sách --------------------------------------------------------------------------------------------

    /**
     * Tải (hoặc cập nhật) một cuốn: chỉ tải file mới/đổi; book.json ghi CUỐI để sách chỉ hiện khi đã đủ file. Việc chạy ở nền (BookDownloads - WorkManager, dịch vụ
     * nền, tiếp tục sau khi tiến trình bị giết): lời gọi trả về ngay khi việc đã xếp hàng, tiến độ / xong / huỷ / lỗi đến qua sự kiện "download".
     */
    @PluginMethod
    fun download(call: PluginCall) = background(call) {
        val id = call.getString("bookId") ?: throw IllegalArgumentException("thiếu bookId")
        // Sách của thiết bị ghép (Peers): `source` = mã thiết bị ở đây, `remoteId` = mã sách bên ấy.
        val source = call.getString("source")?.takeIf { it.isNotEmpty() }
        BookDownloads.start(context, id, source, call.getString("remoteId"))
        call.resolve(JSObject().put("bookId", id))
    }

    /**
     * Phần mô tả của cuốn ĐÃ TẢI đổi ở máy giữ sách (tên, tác giả, người đọc, liên kết bộ, tên chương - `metaVersion`): lấy gói mới và sửa book.json tại
     * chỗ, giữ nguyên audio và lớp sửa của máy này (StreamRefresh.withMetadata). Không mạng / máy kia lỗi thì thôi, lần sau thử lại. Cuốn đang tải
     * thì để lượt tải ghi book.json mới (soát a97 V1).
     */
    private fun refreshMetadata(id: String, entry: JSONObject, source: String? = null, remoteId: String? = null) {
        if (BookDownloads.isActive(context, id)) return
        val local = Store.rawManifest(id) ?: return
        if (!StreamRefresh.metadataStale(local, entry)) return
        val remote = remoteId ?: id
        val fresh = JSONObject(
            if (source != null) Peers.request(context, source, "GET", "/sync/v1/books/$remote/manifest")
            else SyncLink.request(context, "GET", "/sync/v1/books/$id/manifest"),
        )
        PeerPaths.checkManifest(fresh)
        if (fresh.optString("id") != remote) return
        if (source != null) Peers.localizeSeries(fresh, source)
        Store.rewriteManifest(id) { StreamRefresh.withMetadata(it, fresh) }
    }

    /** Nút Huỷ khi đang tải một cuốn (soát a68 lỗi 7): dừng thật ở khối kế; phần đã về giữ lại để lần Tải sau tải tiếp. */
    @PluginMethod
    fun cancelDownload(call: PluginCall) = background(call) {
        val id = call.getString("bookId") ?: throw IllegalArgumentException("thiếu bookId")
        BookDownloads.cancel(context, id)
        call.resolve()
    }

    /** Máy giữ sách vừa nhận phần sửa: cuốn đã tải thì tải lại (file đổi), cuốn nghe thẳng thì chỉ lấy lại gói sách và bìa - không tải cả cuốn. */
    private fun refreshAfterPush(id: String) {
        val (peer, remote) = Store.editDestination(id) ?: return
        if (Store.rawManifest(id) != null) {
            BookDownloads.downloadBook(context, id, peer, remote, announce = false)
            return
        }
        val manifest = Streaming.fetchManifest(context, id, peer, remote)
        if (manifest.optJSONObject("cover") != null) Streaming.fetchSmall(context, id, "cover.jpg")
        fetchHolderEdits(id)
    }

    /**
     * The readings, skipped lines and pending speakers the holder set ([BookEdits.HOLDER_FILE], webui/package_share.py `shared_edits`):
     * fetched again when the library entry's `listenerEdits` stamp changes, dropped when the holder has none (review a70: edits made on the
     * computer never reached the phone).
     */
    private fun syncHolderEdits(id: String, entry: JSONObject) {
        val stamp = entry.optString("listenerEdits")
        val file = File(Store.bookDir(id), BookEdits.HOLDER_FILE)
        if (stamp.isEmpty()) {
            if (file.isFile && file.delete()) ReadAloud.readingsChanged(id)
            return
        }
        if (BookEdits.holderEdits(Store.bookDir(id))?.optString("stamp") != stamp) fetchHolderEdits(id)
    }

    private fun fetchHolderEdits(id: String) {
        if (Streaming.fetchSmall(context, id, BookEdits.HOLDER_FILE) != null) ReadAloud.readingsChanged(id)
    }

    // ---- sách trên máy ---------------------------------------------------------------------------------------

    @PluginMethod
    fun localBooks(call: PluginCall) = background(call) {
        val books = JSArray()
        Store.books().forEach { manifest ->
            val id = manifest.getString("id")
            books.put(JSObject.fromJSONObject(manifest).put("state", JSObject.fromJSONObject(Store.state(id)))
                .put("bytes", Store.bookBytes(Store.bookDir(id)))
                // Lúc sách về điện thoại (cho "Mới thêm" ở thư viện): book.json ghi một lần lúc tải / mở file.
                .put("addedAt", File(Store.bookDir(id), "book.json").lastModified() / 1000.0))
        }
        Store.saveSizes()
        call.resolve(JSObject().put("books", books).put("notices", Store.dataNotices()))
    }

    /**
     * Sách trên máy tính CHƯA tải mà nghe thẳng được (Streaming). Gói sách chỉ lấy lại khi máy tính có thêm chương, đổi
     * tên hay đổi bìa, còn lại dùng bản đã cất. Máy tính không trả lời thì không liệt kê sách của nó: những cuốn ấy không nằm trên
     * điện thoại, hiện ra mà bấm không nghe được thì chỉ làm người nghe bối rối - TRỪ cuốn đang nằm trong trình phát (`offline`): máy tắt hay
     * mất mạng không phải thôi ghép, trình phát không được tưởng cuốn đã rời Thư viện mà đóng giữa câu (soát a68 lỗi 3). Chỉ khi máy kia trả 401
     * (đã thôi ghép điện thoại này) cuốn mới thật sự rời đi.
     */
    @PluginMethod
    fun streamableBooks(call: PluginCall) = streaming(call) {
        val books = JSArray()
        var computerAnswered = true
        // Thiết bị ghép khác trả lời độc lập với máy tính: hỏi cùng lúc, không nối đuôi (mỗi bên đã có hạn chờ riêng).
        val peersAsk = FutureTask { Peers.libraries(context) }
        Thread(peersAsk, "abook-peer-libraries").apply { isDaemon = true }.start()
        val reply = if (SyncLink.paired(context)) {
            try {
                JSONObject(SyncLink.request(context, "GET", "/sync/v1/library", readTimeoutMs = 10_000, connectTimeoutMs = 1500))
            } catch (error: Exception) {
                computerAnswered = NetErrors.unpaired(error) // 401: máy tính trả lời - nó đã thôi ghép; không giữ cuốn nào của nó
                null
            }
        } else null
        val remote = reply?.optJSONArray("books") ?: JSONArray()
        if (reply != null) {
            matchImported(listed(remote))
            StateSync.flushPending(context) // chỗ nghe ghi trong lúc mất kết nối về máy tính ngay khi nối lại (soát a68 lỗi 9)
        }
        val peers = try {
            peersAsk.get()
        } catch (error: ExecutionException) {
            throw error.cause as? Exception ?: error
        }
        // Mọi cuốn của máy tính rồi của từng thiết bị ghép xếp thành MỘT danh sách việc: gói sách lấy song song có giới hạn, chung một trần
        // thời gian (STREAM_BUDGET_MS). Hết trần thì cuốn còn lại dùng gói đã cất, lượt hỏi sau lấy tiếp.
        class Job(val entry: JSONObject, val source: String?, val sourceName: String?)
        val jobs = ArrayList<Job>()
        for (index in 0 until remote.length()) jobs.add(Job(remote.getJSONObject(index), null, null))
        val peerLists = (0 until peers.length()).map { peers.getJSONObject(it) }
        for (peer in peerLists) {
            val list = peer.optJSONArray("books") ?: continue
            for (item in 0 until list.length()) jobs.add(Job(list.getJSONObject(item), peer.getString("key"), peer.optString("name")))
        }
        val rows = Bounded.map(jobs, STREAM_PARALLEL, STREAM_BUDGET_MS) { job, expired ->
            streamedRow(job.entry, job.source, job.sourceName) { !expired() }
        }
        var next = 0
        if (reply == null && !computerAnswered) keepPlaying(books) { it.optString("source").isEmpty() }
        repeat(remote.length()) { rows[next++]?.let(books::put) }
        // Thiết bị ghép (điện thoại khác, máy tính khác): cùng cách, gói ghi nguồn - thiết bị không trả lời thì bỏ qua (trừ cuốn đang phát, như trên).
        for (peer in peerLists) {
            if (peer.has("error") && !peer.optBoolean("unpaired")) keepPlaying(books) { it.optString("source") == peer.optString("key") }
            repeat(peer.optJSONArray("books")?.length() ?: 0) { rows[next++]?.let(books::put) }
        }
        call.resolve(JSObject().put("books", books))
    }

    /**
     * Dòng của một cuốn nghe thẳng trong thư viện, hay null khi không có gì để hiện: cuốn đã tải về thì chỉ làm mới mô tả / phần sửa của nó; cuốn chưa
     * tải mà chưa có gói sách (cũng không lấy được) thì bỏ. `source` / `sourceName`: thiết bị ghép giữ cuốn (null = máy tính chính). `network` sai (hết
     * trần thời gian của lượt) thì không hỏi mạng: dùng gói đã cất.
     */
    private fun streamedRow(entry: JSONObject, source: String?, sourceName: String?, network: () -> Boolean): JSObject? {
        val id = entry.getString("id")
        val remoteId = if (source != null) entry.getString("remoteId") else null
        if (Store.rawManifest(id) != null) {
            if (network()) runCatching { refreshMetadata(id, entry, source, remoteId) }
            if (network()) runCatching { syncHolderEdits(id, entry) }
            return null
        }
        val cached = Store.streamManifest(id)
        val stale = StreamRefresh.stale(cached, entry)
        val manifest = (if (stale && network()) runCatching { Streaming.fetchManifest(context, id, source, remoteId) }.getOrNull() else null) ?: cached ?: return null
        if (manifest.optJSONObject("cover") != null && (stale || !Store.file(id, "cover.jpg").isFile) && network()) {
            runCatching { Streaming.fetchSmall(context, id, "cover.jpg") }
        }
        if (network()) runCatching { syncHolderEdits(id, entry) }
        val row = JSObject.fromJSONObject(Store.streamed(id, manifest)).put("state", JSObject.fromJSONObject(Store.state(id))).put("streamed", true)
        if (sourceName != null) row.put("sourceName", sourceName)
        return row
    }

    /** Cuốn nghe thẳng đang nằm trong trình phát mà máy giữ nó không trả lời: vẫn ở danh sách (gói đã cất), đánh dấu `offline`. */
    private fun keepPlaying(books: JSArray, ownedBy: (JSONObject) -> Boolean) {
        val id = Playback.bookId.takeIf { it.isNotEmpty() } ?: return
        if (Store.rawManifest(id) != null) return
        val manifest = Store.streamManifest(id)?.takeIf(ownedBy) ?: return
        books.put(JSObject.fromJSONObject(Store.streamed(id, manifest)).put("state", JSObject.fromJSONObject(Store.state(id))).put("streamed", true)
            .put("offline", true))
    }

    // ---- thiết bị ghép khác (Peers: điện thoại khác, máy tính khác - mạng trạm bước 2) -----------------------------

    @PluginMethod
    fun peers(call: PluginCall) = background(call) {
        val out = JSArray()
        val all = Peers.all(context)
        for (key in all.keys()) {
            val peer = all.getJSONObject(key)
            out.put(JSObject().put("key", key).put("name", peer.optString("name")).put("host", peer.optString("host"))
                .put("port", peer.optInt("port", 47630)))
        }
        call.resolve(JSObject().put("peers", out))
    }

    @PluginMethod
    fun peerPair(call: PluginCall) = background(call) {
        val host = call.getString("host") ?: throw IllegalArgumentException("thiếu địa chỉ")
        val reply = Peers.pair(context, host, call.getInt("port") ?: 47630, call.getString("code") ?: "")
        call.resolve(JSObject.fromJSONObject(reply))
    }

    @PluginMethod
    fun peerPairBluetooth(call: PluginCall) = background(call) {
        val address = call.getString("address") ?: throw IllegalArgumentException("thiếu máy")
        call.resolve(JSObject.fromJSONObject(Peers.pairBluetooth(context, address, call.getString("code") ?: "")))
    }

    /** Sửa chưa gửi của các cuốn nghe thẳng của một thiết bị ghép - thứ thôi ghép sẽ xoá (hộp xác nhận hỏi trước): từng cuốn, tổng, và
     *  `sendable` = thiết bị là máy tính nên "gửi trước" có nghĩa (điện thoại khác không nhận sửa); `cache` = cái thôi ghép sẽ quên
     *  (số cuốn nghe thẳng, byte của chúng, số cuốn đang có chỗ nghe - chỗ nghe giữ lại, [Peers.forget]). */
    @PluginMethod
    fun peerUnsent(call: PluginCall) = background(call) {
        val key = call.getString("key") ?: ""
        val unsent = Peers.unsent(key)
        val books = JSArray()
        for (book in unsent.books) books.put(JSObject().put("id", book.id).put("title", book.title).put("changes", book.changes))
        val cache = Peers.cached(key)
        call.resolve(JSObject().put("books", books).put("changes", unsent.changes).put("sendable", Peers.kindOf(context, key) == "computer")
            .put("cache", JSObject().put("books", cache.books).put("bytes", cache.bytes).put("places", cache.places)))
    }

    /** Thôi ghép. Còn sửa chưa gửi thì từ chối, trừ khi `send` (gửi hết về máy ấy rồi mới gỡ; hỏng giữa chừng thì không gỡ) hay `discard` (người dùng chọn bỏ). */
    @PluginMethod
    fun peerForget(call: PluginCall) = background(call) {
        val key = call.getString("key") ?: ""
        if (call.getBoolean("send") == true) Peers.sendUnsent(key) { EditsSync.pushNow(context, it) }
        Peers.forget(context, key, discard = call.getBoolean("discard") ?: false)
        call.resolve()
    }

    /** Trình phát của máy tính chính và mọi thiết bị ghép lúc này (RemotePlayers). */
    @PluginMethod
    fun remotePlayers(call: PluginCall) = remotes.execute {
        try {
            val out = JSArray()
            val players = RemotePlayers.all(context)
            for (index in 0 until players.length()) out.put(JSObject.fromJSONObject(players.getJSONObject(index)))
            call.resolve(JSObject().put("players", out))
        } catch (error: Exception) {
            fail(call, error)
        }
    }

    /** "Tìm lại" ở nút "Phát trên…": điện thoại tìm loa / TV của nó ngay, không đợi nhịp 30 giây (DlnaPlayers.scan). */
    @PluginMethod
    fun scanPlayers(call: PluginCall) {
        runCatching { PhoneCast.players.scan() }
        call.resolve()
    }

    @PluginMethod
    fun remoteCommand(call: PluginCall) = remotes.execute {
        try {
            val device = call.getString("device") ?: throw IllegalArgumentException("thiếu máy")
            val command = call.getObject("command") ?: throw IllegalArgumentException("thiếu lệnh")
            call.resolve(JSObject.fromJSONObject(RemotePlayers.command(context, device, JSONObject(command.toString()))))
        } catch (error: Exception) {
            fail(call, error)
        }
    }

    @PluginMethod
    fun peerLibraries(call: PluginCall) = background(call) {
        val out = JSArray()
        val peers = Peers.libraries(context)
        for (index in 0 until peers.length()) out.put(JSObject.fromJSONObject(peers.getJSONObject(index)))
        call.resolve(JSObject().put("peers", out))
    }

    @PluginMethod
    fun book(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: throw IllegalArgumentException("thiếu id")
        val local = Store.manifest(id)
        val manifest = local ?: Store.streamed(id, openStreamed(id))
        call.resolve(JSObject.fromJSONObject(manifest).put("state", JSObject.fromJSONObject(Store.state(id))).put("streamed", local == null)
            .put("records", Store.records(id)))
    }

    // ---- sửa sách ngay trên điện thoại (docs/EDITING.md: LocalStudio, BookEdits, BookDocumentWriter) -----------------

    /**
     * Điện thoại không có máy chủ giao diện nên giao diện gọi thẳng đây thay cho `fetch("/api/books/<mã>/...")`: trả
     * {status, body} đúng như máy chủ của máy tính (LocalStudio). Sửa xong (khác GET) thì nhạc đang phát đọc lại lớp sửa.
     */
    @PluginMethod
    fun studio(call: PluginCall) = background(call) {
        val method = call.getString("method") ?: "GET"
        val path = call.getString("path") ?: throw IllegalArgumentException("thiếu đường dẫn")
        val body = call.getObject("body")?.let { JSONObject(it.toString()) }
        if (method.uppercase() == "GET" && !fetchStreamedScript(path)) {
            // Chữ chương chưa về máy mà máy giữ sách không trả lời: nói đúng thế, không phải "không có chương này" (soát a27 lỗi 12).
            val error = JSONObject().put("error", "Máy giữ sách chưa trả lời nên chưa lấy được chữ chương — bạn kiểm tra kết nối.")
            call.resolve(JSObject().put("status", 503).put("body", JSObject.fromJSONObject(error)))
            return@background
        }
        val (status, reply) = LocalStudio.handle(method, path, body)
        if (status == 200 && method.uppercase() != "GET") {
            Regex("/api/books/([A-Za-z0-9_-]+)").find(path)?.groupValues?.get(1)?.let { id ->
                MusicBed.invalidate(id)
                EditsSync.schedule(context, id) // cuốn tải từ máy tính: phần sửa gửi về máy tính sau vài giây
            }
        }
        val answer = JSObject().put("status", status)
        call.resolve(if (reply is JSONObject) answer.put("body", JSObject.fromJSONObject(reply)) else answer.put("body", JSONObject.NULL))
    }

    /** `GET /api/books/<mã>/chapters/<n>/script` của cuốn nghe thẳng: chữ đọc theo của chương chưa về máy thì lấy từ máy giữ sách trước (như [readText]).
     *  false: cần lấy mà máy giữ sách không trả lời. */
    private fun fetchStreamedScript(path: String): Boolean {
        val match = Regex("/api/books/([A-Za-z0-9_-]+)/chapters/([0-9]+)/script").matchEntire(path.substringBefore('?')) ?: return true
        val id = match.groupValues[1]
        val script = Streaming.missingScript(id, match.groupValues[2].toLong()) ?: return true
        return Streaming.fetchSmall(context, id, script) != null
    }

    /**
     * "Gửi về máy tính": gửi ngay phần sửa của một cuốn tải từ máy tính (EditsSync). Trả `editsSync` mới của cuốn ({pending, last});
     * không tới được máy tính hay máy tính không nhận thì từ chối với câu nói lý do - phần sửa vẫn nằm trên máy này.
     */
    @PluginMethod
    fun sendEdits(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: throw IllegalArgumentException("thiếu id")
        call.resolve(JSObject.fromJSONObject(EditsSync.pushNow(context, id)))
    }

    /** Điện thoại làm được gì (EditingCapabilities, ui/src/shared/capabilities.ts): không có Studio, không có xưởng; `link` theo cuốn. */
    @PluginMethod
    fun capabilities(call: PluginCall) = background(call) {
        val id = call.getString("id")
        call.resolve(JSObject.fromJSONObject(if (id != null) Store.capabilitiesOf(id) else Store.capabilities(link = false)))
    }

    /**
     * "Lưu" / "Lưu thành…": ghi cuốn - kèm thay đổi của người nghe nếu có (file phiên bản 4) - bằng BookDocumentWriter. `as` "abook" hay
     * "abookproj" (cuốn nhập từ file dự án giữ xưởng của nó; cuốn từ file `.abook` thành file chờ dựng xưởng); không nói thì giữ đúng loại
     * file cuốn đã đến. Lần đầu hỏi chỗ lưu bằng hộp thoại "tạo file" của hệ thống (người dùng chọn chỗ và tên) rồi NHỚ chỗ ấy: "Lưu" những lần
     * sau ghi thẳng vào đó, không hỏi lại (như máy tính). `ask: true` ("Lưu thành…") luôn hỏi; chỗ nhớ không ghi được nữa (file bị xoá, mất
     * quyền) cũng hỏi lại. File gốc người dùng mở sách ra không bao giờ bị ghi đè - chỗ nhớ chỉ là file do chính "Lưu" đã tạo. Trả
     * {saved: true, name, size, edits}, hay {saved: false} khi huỷ.
     */
    @PluginMethod
    fun saveBook(call: PluginCall) {
        val id = call.getString("id") ?: return call.reject("thiếu id")
        val manifest = Store.rawManifest(id) ?: return call.reject("Không tìm thấy sách này trong thư viện")
        if (Store.isComputerBook(id) || manifest.optJSONObject("package") == null) {
            return call.reject("Sách này lấy từ máy tính khác - muốn lưu thành file thì lưu ở máy ấy")
        }
        val project = savesAsProject(call, id)
        val kept = if (call.getBoolean("ask", false) == true) null else rememberedSave(id, project)
        if (kept != null) writeSavedBook(call, kept, direct = true) else askSaveLocation(call, id, project)
    }

    private fun askSaveLocation(call: PluginCall, id: String, project: Boolean) {
        val title = Store.manifest(id)?.optString("title").orEmpty()
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType(if (project) BookFileImport.PROJECT_MIMETYPE else BookFileImport.MIMETYPE)
            .putExtra(Intent.EXTRA_TITLE, BookDocumentWriter.defaultName(title, project))
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        startActivityForResult(call, intent, "savedBook")
    }

    /** "Lưu" giữ loại file cuốn đã đến (có `project.json` = file dự án); "Lưu thành…" chọn `as`. */
    private fun savesAsProject(call: PluginCall, id: String): Boolean =
        (call.getString("as") ?: if (ProjectDocument.kept(Store.bookDir(id)) != null) "abookproj" else "abook") == "abookproj"

    private fun savePlaces() = context.getSharedPreferences("book_saves", Context.MODE_PRIVATE)

    /** Chỗ "Lưu" đã ghi lần trước của cuốn này, cùng loại file và còn quyền ghi; không thì null (hỏi lại). */
    private fun rememberedSave(id: String, project: Boolean): Uri? {
        val (kind, address) = savePlaces().getString(id, null)?.split("|", limit = 2)?.takeIf { it.size == 2 } ?: return null
        if ((kind == "abookproj") != project) return null
        val uri = Uri.parse(address)
        return uri.takeIf { context.contentResolver.persistedUriPermissions.any { grant -> grant.uri == it && grant.isWritePermission } }
    }

    private fun rememberSave(id: String, project: Boolean, uri: Uri) {
        val kept = runCatching { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION) }
        if (kept.isSuccess) savePlaces().edit().putString(id, "${if (project) "abookproj" else "abook"}|$uri").apply()
    }

    @ActivityCallback
    private fun savedBook(call: PluginCall?, result: ActivityResult) {
        answered(call)
        val uri = result.data?.data
        if (call == null) return
        if (uri == null) {
            call.resolve(JSObject().put("saved", false))
            return
        }
        writeSavedBook(call, uri, direct = false)
    }

    /** Ghi cuốn vào `uri`. `direct`: chỗ nhớ từ lần trước - ghi hỏng thì hỏi lại chỗ lưu thay vì báo lỗi; chỗ vừa chọn thì nhớ lại. */
    private fun writeSavedBook(call: PluginCall, uri: Uri, direct: Boolean) = io.execute {
        val id = call.getString("id")
        try {
            if (id == null) throw IllegalArgumentException("thiếu id")
            val project = savesAsProject(call, id)
            val snapshot = ExportHistory.snapshot(Store.bookDir(id))
            // Gói dựng và kiểm trong file tạm trước, đích chỉ bị mở (và cắt) sau đó; chép hỏng giữa chừng thì bản lưu trước được trả lại (BookSave, soát a99 C2).
            // Bản cũ không giữ được thì dừng trước khi ghi đè; trả lại cũng hỏng thì bản cũ nằm ở filesDir/ban-luu-cu (bền, không như cache); thiếu chỗ thì báo sớm.
            val written = BookSave.save(Store.bookDir(id), File(context.cacheDir, "save"), project,
                previous = { context.contentResolver.openInputStream(uri) ?: throw BookSave.DestinationUnavailable() },
                open = { context.contentResolver.openOutputStream(uri, "wt") ?: throw BookSave.DestinationUnavailable() },
                keepDir = OldSaves.dir(context.filesDir), keepName = Store.manifest(id)?.optString("title").orEmpty(),
                previousSize = savedSize(uri), destination = uri.toString())
            ExportHistory.remember(Store.bookDir(id), if (project) "abookproj" else "abook", uri.toString(), snapshot)
            BookEdits.markSaved(Store.bookDir(id)) // "Save (N changes)" counts again from here
            if (!direct) rememberSave(id, project, uri)
            val name = runCatching {
                context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                }
            }.getOrNull() ?: ""
            call.resolve(JSObject().put("saved", true).put("name", name).put("size", written.size).put("edits", written.edits))
        } catch (error: Exception) {
            // Gói dựng hỏng (thiếu file nguồn...) thì chỗ lưu không có lỗi: giữ chỗ nhớ, báo đúng lý do thay vì hỏi chỗ khác rồi hỏng y hệt.
            if (id != null && BookSave.shouldChooseAnotherLocation(direct, error)) {
                savePlaces().edit().remove(id).apply()
                activity.runOnUiThread { askSaveLocation(call, id, savesAsProject(call, id)) }
            } else fail(call, error, "không lưu được file")
        }
    }

    /** Cỡ file đang nằm ở `uri` (0 = không biết) - để BookSave tính chỗ trống cho cả bản cũ. */
    private fun savedSize(uri: Uri): Long = runCatching {
        context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else 0L
        }
    }.getOrNull() ?: 0L

    /** Bản lưu cũ [BookSave] giữ lại khi lần lưu hỏng giữa chừng mà bản trước chưa trả lại được: tên, cỡ, lúc giữ (giây) - mới nhất đứng đầu. */
    @PluginMethod
    fun listOldSaves(call: PluginCall) = background(call) {
        BookSave.recover(OldSaves.dir(context.filesDir))
        val files = JSONArray()
        OldSaves.list(OldSaves.dir(context.filesDir)).forEach { files.put(JSONObject().put("name", it.name).put("size", it.size).put("modified", it.modified / 1000.0)) }
        call.resolve(JSObject().put("files", files))
    }

    /** "Lưu ra…": hộp chọn chỗ lưu của hệ thống, rồi chép bản lưu cũ `name` ra đó theo khối (không giữ cả file trong bộ nhớ). */
    @PluginMethod
    fun exportOldSave(call: PluginCall) {
        val name = call.getString("name") ?: return call.reject("thiếu tên")
        try {
            OldSaves.resolve(OldSaves.dir(context.filesDir), name)
        } catch (error: IllegalArgumentException) {
            return call.reject(error.message ?: "Không thấy bản lưu cũ này")
        }
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType(OldSaves.mimeOf(name)).putExtra(Intent.EXTRA_TITLE, name)
        startActivityForResult(call, intent, "exportedOldSave")
    }

    @ActivityCallback
    private fun exportedOldSave(call: PluginCall?, result: ActivityResult) {
        answered(call)
        val uri = result.data?.data
        if (call == null) return
        val name = call.getString("name")
        if (uri == null || name == null) return call.resolve(JSObject().put("saved", false))
        io.execute {
            try {
                val sink = context.contentResolver.openOutputStream(uri, "wt") ?: throw IllegalStateException("Không ghi được vào chỗ đã chọn")
                sink.use { OldSaves.copyTo(OldSaves.dir(context.filesDir), name, it) }
                call.resolve(JSObject().put("saved", true))
            } catch (error: Exception) {
                fail(call, error, "không lưu được file")
            }
        }
    }

    /** "Xoá…" (đã xác nhận trong app): bản lưu cũ biến mất, không lấy lại được. */
    @PluginMethod
    fun deleteOldSave(call: PluginCall) = background(call) {
        val deleted = OldSaves.delete(OldSaves.dir(context.filesDir), call.getString("name") ?: throw IllegalArgumentException("thiếu tên"))
        call.resolve(JSObject().put("deleted", deleted))
    }

    /**
     * "Chia sẻ…": đóng cuốn (kèm thay đổi của người nghe, như "Lưu thành…") thành file trong `cacheDir/share` ([BookShare]) rồi mở bảng
     * chia sẻ của hệ thống (Zalo, Drive, email…). `as` không nói: sách nghe `.abook` - thứ người nhận mở được để nghe ngay. Trả
     * {shared: true, name} khi bảng chia sẻ đã mở (người dùng gửi cho ai hay đóng bảng thì app không biết).
     */
    @PluginMethod
    fun shareBook(call: PluginCall) {
        val id = call.getString("id") ?: return call.reject("thiếu id")
        val manifest = Store.rawManifest(id) ?: return call.reject("Không tìm thấy sách này trong thư viện")
        if (Store.isComputerBook(id) || manifest.optJSONObject("package") == null) {
            return call.reject("Sách này lấy từ máy tính khác - muốn gửi file sách thì gửi từ máy ấy")
        }
        val project = call.getString("as") == "abookproj"
        val title = Store.manifest(id)?.optString("title").orEmpty()
        io.execute {
            val file = BookShare.target(context.cacheDir, title, project)
            try {
                file.parentFile?.mkdirs()
                val snapshot = ExportHistory.snapshot(Store.bookDir(id))
                file.outputStream().use { BookDocumentWriter.write(Store.bookDir(id), it, project) }
                ExportHistory.remember(Store.bookDir(id), if (project) "abookproj" else "abook", file.name, snapshot)
                val uri = androidx.core.content.FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
                val mime = BookShare.mimeType(project)
                val send = Intent(Intent.ACTION_SEND).setType(mime)
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_TITLE, file.name)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                send.clipData = android.content.ClipData.newUri(context.contentResolver, file.name, uri)
                val chooser = Intent.createChooser(send, "Chia sẻ “${title.ifBlank { file.nameWithoutExtension }}”")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                activity.runOnUiThread {
                    try {
                        activity.startActivity(chooser)
                        call.resolve(JSObject().put("shared", true).put("name", file.name))
                    } catch (error: Exception) {
                        fail(call, error, "không mở được bảng chia sẻ")
                    }
                }
            } catch (error: Exception) {
                file.parentFile?.deleteRecursively()
                fail(call, error, "không đóng được file sách để chia sẻ")
            }
        }
    }

    // ---- Chẩn đoán (Diagnostics, AppLog): xem / gửi / xoá nhật ký ----------------------------------------------------------------

    /** "Xem nhật ký": cả bản chẩn đoán (`lines` dòng nhật ký cuối, mặc định 500) cho màn Cài đặt → Chẩn đoán. */
    @PluginMethod
    fun diagnostics(call: PluginCall) {
        val lines = Diagnostics.clampLines(call.getInt("lines") ?: 500)
        remotes.execute {
            try {
                call.resolve(JSObject(Diagnostics.collect(context, lines).toString()))
            } catch (error: Exception) {
                fail(call, error, "không đọc được nhật ký")
            }
        }
    }

    /**
     * "Gửi nhật ký": ghi gói .zip (`chan-doan.json` + `nhat-ky.txt`) vào `cacheDir/share` rồi mở bảng chia sẻ của hệ thống - NGƯỜI DÙNG tự chọn gửi
     * cho ai, app không gửi đi đâu. Trong gói có tên cuốn đang nghe, không có mã thiết bị, mật khẩu hay chữ truyện. Trả {shared: true, name}.
     */
    @PluginMethod
    fun shareDiagnostics(call: PluginCall) {
        remotes.execute {
            var file: File? = null
            try {
                val report = Diagnostics.collect(context, Diagnostics.DEFAULT_LINES)
                val target = File(File(BookShare.dir(context.cacheDir), java.lang.Long.toHexString(System.nanoTime())), Diagnostics.bundleName(System.currentTimeMillis()))
                file = target
                target.parentFile?.mkdirs()
                target.writeBytes(Diagnostics.bundle(report))
                val uri = androidx.core.content.FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", target)
                val send = Intent(Intent.ACTION_SEND).setType("application/zip")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_TITLE, target.name)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                send.clipData = android.content.ClipData.newUri(context.contentResolver, target.name, uri)
                val chooser = Intent.createChooser(send, "Gửi nhật ký của ABook").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                activity.runOnUiThread {
                    try {
                        activity.startActivity(chooser)
                        AppLog.i("Diagnostics", "mở bảng chia sẻ nhật ký (${target.length()} byte)")
                        call.resolve(JSObject().put("shared", true).put("name", target.name))
                    } catch (error: Exception) {
                        fail(call, error, "không mở được bảng chia sẻ")
                    }
                }
            } catch (error: Exception) {
                file?.parentFile?.deleteRecursively()
                fail(call, error, "không gom được nhật ký để gửi")
            }
        }
    }

    /** "Xoá nhật ký": bỏ nhật ký của app và các file văng (lý do tiến trình chết do hệ thống giữ, không xoá được). */
    @PluginMethod
    fun clearDiagnostics(call: PluginCall) {
        AppLog.clear()
        AppLog.i("Diagnostics", "người dùng xoá nhật ký")
        call.resolve(JSObject().put("cleared", true))
    }

    // ---- "Xuất MP3 để nghe ở app khác" (Mp3Export, Mp3ExportWorker) ------------------------------------------------

    /**
     * Xuất cuốn `bookId` thành thư mục MP3 như máy tính. Lần đầu (hay `pick`, hay thư mục cũ không còn ghi được) hỏi chỗ lưu bằng bộ
     * chọn thư mục của hệ thống, rồi nhớ lại. `cover`: data URL PNG bìa giao diện tự vẽ, dùng khi sách không có bìa thật. `music`: ô "Kèm nhạc nền" (mỗi
     * chương ra file .m4a đã trộn nhạc vì máy không có bộ mã hoá MP3 - [Mp3Export.runMixed]). Trả
     * {started, run, folder, chapters} - tiến độ và kết quả đến qua sự kiện "mp3Export" mang `run` - hay {started: false} khi huỷ chọn.
     */
    @PluginMethod
    fun exportMp3(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        if (Store.manifest(id) == null) return call.reject("Sách này chưa tải về điện thoại")
        val tree = if (call.getBoolean("pick", false) == true) null else Mp3Exports.remembered(context)
        if (tree == null) startActivityForResult(call, Mp3Exports.pickIntent(context), "pickedExportFolder") else startMp3Export(call, tree)
    }

    @ActivityCallback
    private fun pickedExportFolder(call: PluginCall?, result: ActivityResult) {
        answered(call)
        if (call == null) return
        val tree = result.data?.data ?: return call.resolve(JSObject().put("started", false))
        try {
            Mp3Exports.remember(context, tree)
        } catch (error: Exception) {
            return fail(call, error, "không giữ được quyền ghi thư mục đã chọn")
        }
        startMp3Export(call, tree)
    }

    private fun startMp3Export(call: PluginCall, tree: Uri) = background(call) {
        val id = call.getString("bookId") ?: throw IllegalArgumentException("thiếu bookId")
        val drawn = drawnCover(call.getString("cover"))
        val selected = call.getArray("chapterIds")?.let { array -> (0 until array.length()).map { array.getInt(it) } }
        val plan = Mp3Export.plan(id, drawn, selected) // sách không có gì để xuất: từ chối ngay, không bắt đầu việc nền
        val treeName = Mp3Exports.treeName(context, tree) ?: throw Mp3Export.Refused("Không mở được thư mục đã chọn - chọn lại nơi lưu")
        val coverFile = drawn?.let { bytes ->
            File(context.cacheDir, "mp3-export").apply { mkdirs() }.let { File(it, "${java.util.UUID.randomUUID()}.png") }.also { it.writeBytes(bytes) }
        }
        val run = Mp3Exports.start(context, id, tree, coverFile, selected, call.getBoolean("music", false) == true)
        call.resolve(JSObject().put("started", true).put("run", run).put("folder", "$treeName/${Mp3Export.folderName(plan.title)}")
            .put("chapters", plan.chapters.size))
    }

    // ---- "Xuất M4B cho app sách nói" (M4bExport, M4bExportWorker) ---------------------------------------------------

    /**
     * Xuất cuốn `bookId` thành MỘT file `.m4b` có mục lục chương như máy tính. Hỏi tên và chỗ lưu bằng hộp thoại "tạo file" của hệ thống
     * (mỗi lần - khác xuất MP3 không nhớ chỗ: đây là một file, người dùng đặt tên). `cover`: data URL PNG bìa giao diện tự vẽ, dùng khi
     * sách không có bìa thật. Sách chưa có chương nào nghe được thì từ chối ngay, trước khi hỏi chỗ lưu. Trả {started, run, name, chapters}
     * - tiến độ và kết quả đến qua sự kiện "m4bExport" mang `run` - hay {started: false} khi huỷ chọn.
     */
    @PluginMethod
    fun exportM4b(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        if (Store.manifest(id) == null) return call.reject("Sách này chưa tải về điện thoại")
        val plan = try {
            Mp3Export.plan(id)
        } catch (error: Mp3Export.Refused) {
            return call.reject(error.message)
        }
        startActivityForResult(call, M4bExports.createIntent(plan.title), "pickedM4bFile")
    }

    /**
     * Ô "Kèm nhạc nền" của hộp xuất cuốn `bookId` (`packaged_state` của máy tính): {available: có mốc nhạc ở ít nhất một chương, enabled: mặc định của ô theo
     * công tắc Nhạc nền của cuốn}.
     */
    @PluginMethod
    fun m4bMusicState(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        background(call) {
            val (available, enabled) = BookMusic.exportState(id)
            call.resolve(JSObject().put("available", available).put("enabled", enabled))
        }
    }

    /** Dừng lượt xuất M4B của cuốn `bookId` (nút "Dừng" trong app; thông báo của hệ thống có nút riêng). File dở bị xoá. */
    @PluginMethod
    fun cancelM4bExport(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        background(call) {
            M4bExports.cancel(context, id)
            call.resolve()
        }
    }

    @ActivityCallback
    private fun pickedM4bFile(call: PluginCall?, result: ActivityResult) {
        answered(call)
        if (call == null) return
        val file = result.data?.data ?: return call.resolve(JSObject().put("started", false))
        background(call) {
            try {
                val id = call.getString("bookId") ?: throw IllegalArgumentException("thiếu bookId")
                val drawn = drawnCover(call.getString("cover"))
                val plan = Mp3Export.plan(id, drawn)
                M4bExports.remember(context, file)
                val coverFile = drawn?.let { bytes ->
                    File(context.cacheDir, "m4b-export").apply { mkdirs() }.let { File(it, "${java.util.UUID.randomUUID()}.png") }.also { it.writeBytes(bytes) }
                }
                val run = M4bExports.start(context, id, file, coverFile, call.getBoolean("music", false) == true)
                call.resolve(JSObject().put("started", true).put("run", run).put("name", M4bExport.fileName(plan.title)).put("chapters", plan.chapters.size))
            } catch (error: Exception) {
                M4bExports.discard(context, file) // chưa bắt đầu việc nền: file rỗng vừa tạo không để lại
                throw error
            }
        }
    }

    // ---- "Xuất sách nói" của sách Nghe ngay (ListenExport, ListenExportWorker) ------------------------------------------

    private fun readingOf(id: String, voice: String) = ListenExport.Reading(voice, ReadAloud.originNow(id), ReadAloud.readingsOf(id))

    /**
     * Cho hộp "Xuất sách nói": số chương, số chữ, giờ nghe (từ clip đã có + phần chưa có ước theo tốc độ đo), ước thời gian máy làm (giọng đã đo tốc độ), phần đã có sẵn
     * (chương đã ghép + clip trong bộ đệm) và chỗ trống cần. Đọc chữ nên chạy ở luồng nền.
     * `music`: ô "Kèm nhạc nền" (thiếu = mặc định theo cuốn); kết quả thêm `music` {available, enabled} và `rereads` (đoạn phải đọc lại vì đổi nhạc).
     */
    @PluginMethod
    fun audiobookPlan(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val voice = call.getString("voice") ?: return call.reject("thiếu voice")
        val wanted = call.getBoolean("music")
        background(call) {
            val chapters = ListenExport.chapters(id)
            val speed = runCatching { ReadAloud.speeds().secondsPerChar(voice) }.getOrNull()
            val (available, enabled) = BookMusic.exportState(id)
            val (music, extra) = if (available && (wanted ?: enabled)) ExportMusic.listenPlan(context, id, chapters) else emptyMap<Int, MusicExport.ChapterMusic>() to 0L
            val reading = readingOf(id, voice)
            val cache = ReadAloud.cache()
            val plan = ListenExport.plan(chapters, reading, ListenExport.workFolder(ListenExports.workRoot(context), id), speed,
                music = { MusicExport.audible(music, it) }, cachedMs = { text -> cache.durationMs(VoiceSpeed.quality(voice), text, reading.origin, reading.readings) }, extra = extra)
            call.resolve(JSObject.fromJSONObject(plan.toJson().put("music", JSONObject().put("available", available).put("enabled", enabled))))
        }
    }

    /**
     * Xuất sách chỉ có chữ `bookId` thành MỘT file `.m4b` có mục lục chương, đọc bằng giọng `voice`, chạy nền. Hỏi tên và chỗ lưu bằng hộp thoại "tạo file" của hệ thống (mỗi lần).
     * `cover`: bìa tự vẽ (data URL PNG) khi sách không có bìa thật. Sách chưa có chương nào đọc được thì từ chối ngay, trước khi hỏi chỗ lưu. Trả {started, run, name, chapters}
     * - tiến độ và kết quả đến qua sự kiện "audiobookExport" mang `run` - hay {started: false} khi huỷ chọn.
     */
    @PluginMethod
    fun exportAudiobook(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        if (call.getString("voice").isNullOrEmpty()) return call.reject("thiếu voice")
        background(call) {
            val book = Store.manifest(id) ?: throw Mp3Export.Refused("Sách này chưa tải về điện thoại")
            if (ListenExport.chapters(id).isEmpty()) throw Mp3Export.Refused("Sách chưa có chương nào có chữ để đọc")
            val title = book.optString("title").ifEmpty { id }
            activity.runOnUiThread { startActivityForResult(call, M4bExports.createIntent(title), "pickedAudiobookFile") }
        }
    }

    @ActivityCallback
    private fun pickedAudiobookFile(call: PluginCall?, result: ActivityResult) {
        answered(call)
        if (call == null) return
        val file = result.data?.data ?: return call.resolve(JSObject().put("started", false))
        background(call) {
            try {
                val id = call.getString("bookId") ?: throw IllegalArgumentException("thiếu bookId")
                val voice = call.getString("voice") ?: throw IllegalArgumentException("thiếu voice")
                val title = Store.manifest(id)?.optString("title").orEmpty().ifEmpty { id }
                val drawn = drawnCover(call.getString("cover"))
                M4bExports.remember(context, file)
                val coverFile = drawn?.let { bytes ->
                    File(context.cacheDir, "audiobook-export").apply { mkdirs() }.let { File(it, "${java.util.UUID.randomUUID()}.png") }.also { it.writeBytes(bytes) }
                }
                val run = ListenExports.start(context, id, voice, file, coverFile, call.getBoolean("music", false) == true)
                call.resolve(JSObject().put("started", true).put("run", run).put("name", M4bExport.fileName(title)))
            } catch (error: Exception) {
                M4bExports.discard(context, file) // chưa bắt đầu việc nền: file rỗng vừa tạo không để lại
                throw error
            }
        }
    }

    /** Dừng lượt xuất sách nói của cuốn `bookId` (file dở bị xoá, phần đã đọc xong giữ để xuất lại làm tiếp). */
    @PluginMethod
    fun cancelAudiobookExport(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        background(call) {
            ListenExports.cancel(context, id)
            call.resolve()
        }
    }

    /**
     * Các lượt xuất (MP3, M4B, sách nói) đang chạy, tin cuối của từng lượt kèm `kind` ("mp3" | "m4b" | "audiobook"): giao diện vừa mở lại (hay
     * tải lại) hiện lại thông báo tiến độ và nhận tiếp tin xong / lỗi của lượt ấy. Có cả lượt WorkManager còn giữ mà tiến trình này chưa có tin nào.
     */
    @PluginMethod
    fun exportJobs(call: PluginCall) = background(call) {
        call.resolve(JSObject().put("jobs", JSONArray(ExportJobs.running(context))))
    }

    /** Mở file vừa xuất bằng app nghe sách nói của máy (nút "Mở" ở thông báo xong). Chỉ địa chỉ `content:` của nơi lưu người dùng chọn, không phải của chính app. */
    @PluginMethod
    fun openFile(call: PluginCall) {
        val uri = call.getString("uri")?.let(Uri::parse) ?: return call.reject("thiếu uri")
        val allowed = uri.scheme == "content" && uri.authority != "${context.packageName}.fileprovider"
        call.resolve(JSObject().put("opened", allowed && ListenExports.open(context, uri)))
    }

    /**
     * "Mở thư mục" ở thông báo xuất xong: mở thư mục bản xuất bằng app Tệp của hệ thống. Chỉ nhận địa chỉ nằm trong thư mục người dùng đã
     * cấp cho ABook (không mở địa chỉ tuỳ ý); máy không có app nào mở được thư mục thì trả {opened: false} - giao diện nói đường đi bằng chữ.
     */
    @PluginMethod
    fun openFolder(call: PluginCall) {
        val uri = call.getString("uri")?.let(Uri::parse) ?: return call.reject("thiếu uri")
        val allowed = uri.scheme == "content" && context.contentResolver.persistedUriPermissions.any { uri.toString().startsWith(it.uri.toString()) }
        if (!allowed) return call.resolve(JSObject().put("opened", false))
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, android.provider.DocumentsContract.Document.MIME_TYPE_DIR)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        call.resolve(JSObject().put("opened", runCatching { context.startActivity(intent) }.isSuccess))
    }

    /** Bìa tự vẽ gửi từ giao diện, cùng luật với máy tính (export._cover_file): chỉ data URL PNG, tối đa 4 MB. */
    private fun drawnCover(value: String?): ByteArray? {
        val match = Regex("data:image/png;base64,([A-Za-z0-9+/=]+)").matchEntire(value ?: return null) ?: return null
        val bytes = runCatching { android.util.Base64.decode(match.groupValues[1], android.util.Base64.DEFAULT) }.getOrNull() ?: return null
        return bytes.takeIf { it.size <= 4 * 1024 * 1024 && Id3Tag.Cover.of(it)?.mime == "image/png" }
    }

    // ---- hồ sơ nghe (độc lập với sách, app giữ liên kết - Store) -----------------------------------------------

    /** Trả danh sách hồ sơ mới, rồi báo máy tính: hồ sơ vừa rời trước (`left` - chỗ nghe cuối của nó, lưu lúc đổi, chưa
     *  tới máy tính: điện thoại chỉ đẩy hồ sơ đang dùng), rồi hồ sơ đang dùng (lựa chọn, tên, bia mộ). `first`: cuốn đẩy
     *  trước tiên (cuốn vừa nhận hồ sơ chuyển tới - máy tính gắn lại hồ sơ theo lần chuyển ấy trước khi nghe cuốn cũ). */
    private fun resolveRecords(call: PluginCall, records: JSONArray, left: String? = null, first: String? = null) {
        call.resolve(JSObject().put("records", records))
        val id = call.getString("id") ?: return
        io.execute {
            if (first != null) runCatching { pushState(first) }
            if (left != null && left != Store.knownActiveRecord(id) && Store.hasRecord(left)) {
                runCatching { StateSync.pushNow(context, id, left) }
            }
            runCatching { pushState(id) }
        }
    }

    /** Đổi hồ sơ của một cuốn: cuốn đang nạp trong trình phát thì qua Playback trên luồng chính (trình phát theo sang
     *  hồ sơ mới), cuốn khác thì đổi thẳng. */
    private fun switching(id: String, change: () -> JSONArray): JSONArray {
        if (Playback.bookId != id) return change()
        val task = FutureTask { Playback.switchRecord(id, change) }
        Playback.onMain { task.run() }
        return try {
            task.get(10, TimeUnit.SECONDS)
        } catch (error: ExecutionException) {
            throw error.cause ?: error
        }
    }

    @PluginMethod
    fun createRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val left = Store.knownActiveRecord(id)
        resolveRecords(call, switching(id) { Store.createRecord(id, call.getString("name") ?: "") }, left)
    }

    @PluginMethod
    fun activateRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val left = Store.knownActiveRecord(id)
        val record = call.getString("record")!!
        // Hồ sơ máy giữ sách báo trong danh sách mà điện thoại chưa có trạng thái (mới hiện ra ở bộ chọn): lấy trạng thái của đúng mã
        // ấy trước khi nạp - đẩy hồ sơ rỗng, lời đáp mang trạng thái đã gộp (Store.applySync). Không với tới máy giữ sách thì chọn như cũ.
        if (Store.hasRecord(record) && !Store.hasState(record)) runCatching { StateSync.pushNow(context, id, record) }
        resolveRecords(call, switching(id) { Store.activateRecord(id, record) }, left)
    }

    @PluginMethod
    fun renameRecord(call: PluginCall) = background(call) {
        resolveRecords(call, Store.renameRecord(call.getString("id")!!, call.getString("record")!!, call.getString("name") ?: ""))
    }

    @PluginMethod
    fun moveRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val to = call.getString("book").orEmpty()
        val change = { Store.moveRecord(id, call.getString("record")!!, to) }
        // Cuốn nhận đang nạp trong trình phát: cũng qua Playback - lưu chỗ của hồ sơ đang dùng ở đó trước, rồi theo sang hồ
        // sơ vừa chuyển tới (không thì lần lưu kế ghi chỗ của cuốn ấy đè lên hồ sơ vừa tới).
        resolveRecords(call, if (Playback.bookId == to) switching(to, change) else switching(id, change), first = to)
    }

    @PluginMethod
    fun deleteRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        resolveRecords(call, switching(id) { Store.deleteRecord(id, call.getString("record")!!) })
    }

    /** Mở một cuốn chưa tải: gói sách mới nhất từ máy tính (mạng lỗi thì bản đã cất), bìa ngay; dàn nhân vật và câu mẫu
     *  lấy ở luồng nền để màn sách hiện ra không phải chờ chúng. */
    private fun openStreamed(id: String): JSONObject {
        // Sách của thiết bị ghép chưa từng mở thư viện của nó ở đây (chưa có stream.json): mã `p<key>_<mã bên ấy>` nói
        // nguồn - "Nghe ở đây" từ thanh trình phát của máy kia đi thẳng tới đó thay vì hỏi nhầm máy tính chính.
        val peer = Peers.sourceOf(context, id)
        val previous = Store.streamManifest(id)
        val manifest = runCatching { Streaming.fetchManifest(context, id, peer?.first, peer?.second) }.getOrNull()
            ?: Store.streamManifest(id)
            ?: throw IllegalStateException("Cuốn này nằm trên máy tính - kết nối cùng mạng với máy tính để nghe")
        if (StreamRefresh.coverNeeded(previous, manifest, Store.file(id, "cover.jpg").isFile)) Streaming.fetchSmall(context, id, "cover.jpg")
        downloads.execute {
            if (StreamRefresh.castNeeded(Store.bookDir(id), manifest) && Streaming.fetchSmall(context, id, "cast.json") != null) {
                StreamRefresh.castFetched(Store.bookDir(id), manifest)
            }
            val samples = manifest.optJSONArray("samples") ?: JSONArray()
            for (index in 0 until samples.length()) {
                val sample = samples.getString(index)
                if (!Store.file(id, sample).isFile) Streaming.fetchSmall(context, id, sample)
            }
        }
        return manifest
    }

    /** Văn bản trong gói (chương để đọc theo, dàn nhân vật). Sách nghe thẳng thì lấy từ máy tính lần đầu rồi cất lại. */
    @PluginMethod
    fun readText(call: PluginCall) = background(call) {
        call.resolve(JSObject().put("text", bookText(call.getString("id") ?: "", call.getString("path") ?: "") ?: ""))
    }

    /**
     * Văn bản của NHIỀU file trong gói một lần (ô "Tìm trong sách": mỗi chương một file, sách 2000 chương đi qua cầu hàng trăm lượt nếu hỏi từng file):
     * `texts` theo thứ tự `paths`, null cho file không có. Chữ quá nhiều thì trả phần đầu (TextBatch) - bên hỏi xin lại phần còn lại.
     */
    @PluginMethod
    fun readTexts(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: ""
        val paths = call.getArray("paths")?.toList<String>() ?: emptyList()
        val texts = JSArray()
        TextBatch.read(paths) { path -> bookText(id, path) }.forEach { texts.put(it ?: JSONObject.NULL) }
        call.resolve(JSObject().put("texts", texts))
    }

    /** Một file văn bản của gói như người nghe thấy (lớp sửa phủ lên); sách nghe thẳng chưa có file thì lấy từ máy tính. null khi không có. */
    private fun bookText(id: String, path: String): String? {
        val file = Store.file(id, path)
        val fromPeer = !Store.streamManifest(id)?.optString("source").isNullOrEmpty()
        if (!file.isFile && Store.rawManifest(id) == null && (fromPeer || SyncLink.paired(context))) Streaming.fetchSmall(context, id, path)
        return Store.readText(id, path)
    }

    /**
     * Mốc nhạc nền THEO CẢNH của một chương sách chỉ có chữ (đường N0, [DeviceScenes]): `{cues: [{start, end, link, key, sibling?, tail?, steps?, firstSegment?}], scene,
     * estSeconds, scenes: [...], pending?}` - cùng hình với tuyến `music/cues` của máy tính khi sách đang "Theo cảnh". Dựng ở luồng nền riêng (lời gọi chờ tối đa 2 giây,
     * quá thì `pending` true: hỏi lại sau); không chiếm luồng `io` chung.
     */
    @PluginMethod
    fun musicSceneCues(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        val chapterId = call.getInt("chapterId") ?: return call.reject("thiếu chapterId")
        DeviceScenes.request(context, id, chapterId) { result, error ->
            if (result != null) call.resolve(JSObject.fromJSONObject(result)) else fail(call, error ?: IllegalStateException("không dựng được nhạc nền"))
        }
    }

    @PluginMethod
    fun path(call: PluginCall) {
        val file = Store.file(call.getString("id") ?: "", call.getString("path") ?: "")
        call.resolve(JSObject().put("path", file.absolutePath).put("exists", file.isFile))
    }

    @PluginMethod
    fun deleteBook(call: PluginCall) = background(call) {
        // Thiếu mã thì từ chối (Store.deletableBookDir) - trước đây `?: ""` biến thành xoá CẢ thư mục sách.
        // Cuốn đang có lượt tải chạy thì không dời thư mục dưới chân nó (màn Tải sách tắt nút Xoá; đây là lớp chặn cuối, soát a97 V6).
        require(!BookDownloads.isActive(context, call.getString("id").orEmpty())) { "Đang tải cuốn này - huỷ tải rồi mới xoá được." }
        // Cuốn nằm chờ UNDO_SECONDS giây (TrashPending) rồi mới xoá hẳn; `undo` là mã để "Hoàn tác" (không có khi xoá thẳng).
        val undo = Store.holdBook(call.getString("id").orEmpty())
        // Chương tạm của "Xuất sách nói" bỏ dở đi theo sách khi sách bị xoá hẳn (ListenExports.sweep - cuốn đang xuất không bị đụng).
        if (undo != null) {
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(
                { io.execute { runCatching { Store.sweepTrash() }; runCatching { ListenExports.sweep(context) } } }, (TrashPending.UNDO_SECONDS + 1) * 1000L,
            )
        } else {
            io.execute { runCatching { ListenExports.sweep(context) } }
        }
        call.resolve(JSObject().put("undo", undo ?: JSONObject.NULL))
    }

    @PluginMethod
    fun undoDelete(call: PluginCall) = background(call) {
        Store.undoBook(call.getString("token").orEmpty())
        call.resolve()
    }

    @PluginMethod
    fun storage(call: PluginCall) = background(call) {
        val sizes = Store.bookSizes()
        val books = JSArray()
        // `title`: tên trong gói sách của thư mục (đã tải hay nghe thẳng) - thư mục tải dở chưa có gói nào thì không có, giao diện lấy tên từ danh sách máy tính.
        for ((id, bytes) in sizes) {
            val title = (Store.rawManifest(id) ?: Store.streamManifest(id))?.optString("title").orEmpty()
            books.put(JSObject().put("id", id).put("bytes", bytes).apply { if (title.isNotEmpty()) put("title", title) })
        }
        call.resolve(JSObject().put("bytes", sizes.values.sum()).put("free", Store.root.usableSpace).put("books", books))
    }

    // ---- trạng thái nghe -------------------------------------------------------------------------------------

    private fun resolveState(call: PluginCall, state: JSONObject) {
        call.resolve(JSObject.fromJSONObject(state))
        val id = call.getString("id") ?: return
        // `record`: hồ sơ màn đã chốt - gửi đúng nó, không phải hồ sơ đang dùng lúc này.
        io.execute { runCatching { StateSync.pushNow(context, id, call.getString("record")) } }
    }

    @PluginMethod
    fun progress(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val seconds = call.getDouble("seconds")!!
        val duration = call.getDouble("duration") ?: 0.0
        // Chỗ vượt độ dài chương là của thứ khác: không lưu (PlacePolicy, soát a68 lỗi 2).
        if (!PlacePolicy.fits(seconds, duration)) return@background call.resolve(JSObject.fromJSONObject(Store.state(id)))
        resolveState(call, Store.progress(id, call.getInt("chapterId")!!, seconds, duration, call.getObject("anchor")))
    }

    @PluginMethod
    fun saveReading(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val record = call.getString("record") ?: Store.activeRecord(id)
        val state = Store.saveReading(id, call.getInt("chapterId")!!, call.getInt("index")!!,
            call.getDouble("at") ?: System.currentTimeMillis() / 1000.0, call.getObject("anchor"), record, call.getObject("rev"))
        call.resolve(JSObject.fromJSONObject(state))
        runCatching { StateSync.pushNow(context, id, record) }
    }

    @PluginMethod
    fun setChapterDone(call: PluginCall) = background(call) {
        resolveState(call, Store.setChapterDone(call.getString("id")!!, call.getInt("chapterId")!!, call.getBoolean("done") ?: true, call.getString("record")))
    }

    @PluginMethod
    fun setFinished(call: PluginCall) = background(call) {
        resolveState(call, Store.setFinished(call.getString("id")!!, call.getBoolean("finished") ?: true, call.getString("record")))
    }

    @PluginMethod
    fun setRate(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val record = call.getString("record")
        if (record != null && !Store.holds(id, record)) return@background call.reject(RECORD_GONE)
        Store.setRate(id, call.getDouble("rate") ?: 1.0, record)
        call.resolve()
    }

    /** Giọng Nghe ngay người nghe chọn riêng cho cuốn: lưu và báo máy giữ sách ngay (soát a68 lỗi 8) - máy kia có giọng ấy thì đọc tiếp bằng nó. */
    @PluginMethod
    fun setVoice(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val record = call.getString("record")
        if (record != null && !Store.holds(id, record)) return@background call.reject(RECORD_GONE)
        Store.setVoice(id, call.getString("voice") ?: "", record)
        call.resolve()
        runCatching { StateSync.pushNow(context, id, record) }
    }

    @PluginMethod
    fun addBookmark(call: PluginCall) = background(call) {
        val mark = Store.addBookmark(call.getString("id")!!, call.getInt("chapterId")!!, call.getDouble("seconds") ?: 0.0, call.getString("note") ?: "",
            call.getInt("index"), call.getString("quote") ?: "", call.getDouble("createdAt"), call.getString("record"), call.getObject("anchor"))
        call.resolve(JSObject.fromJSONObject(mark))
        // Bookmarks reach the computer like the listening position does (a70: a bookmark set in the reader never left the phone).
        runCatching { StateSync.pushNow(context, call.getString("id")!!, call.getString("record")) }
    }

    @PluginMethod
    fun restoreBookmark(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val mark = Store.restoreBookmark(id, call.getObject("mark")!!)
        call.resolve(JSObject.fromJSONObject(mark))
        runCatching { pushState(id) }
    }

    @PluginMethod
    fun updateBookmark(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val record = call.getString("record")
        Store.updateBookmark(id, call.getString("markId")!!, call.getString("note") ?: "", record)
        call.resolve()
        runCatching { StateSync.pushNow(context, id, record) }
    }

    @PluginMethod
    fun deleteBookmark(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val record = call.getString("record")
        Store.deleteBookmark(id, call.getString("markId")!!, record)
        call.resolve()
        runCatching { StateSync.pushNow(context, id, record) }
    }

    /**
     * Gửi hồ sơ nghe đang dùng của cuốn lên máy tính (kèm mã, tên hồ sơ, lúc chọn nó), nhận bản đã gộp của ĐÚNG hồ sơ ấy
     * cùng lựa chọn hồ sơ bên kia - bên chọn sau thắng (Store.applySync). Im lặng nếu không có mạng.
     */
    private fun pushState(id: String) = StateSync.pushNow(context, id)

    /** Tốc độ / giọng gửi kèm hồ sơ đã bị xoá hay chuyển sang sách khác: báo rõ, không ghi sang hồ sơ khác (soát a105 F7). */
    private val RECORD_GONE = Store.RECORD_GONE

    @PluginMethod
    fun syncState(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: throw IllegalArgumentException("thiếu id")
        pushState(id)
        call.resolve(JSObject.fromJSONObject(Store.state(id)))
    }
}
