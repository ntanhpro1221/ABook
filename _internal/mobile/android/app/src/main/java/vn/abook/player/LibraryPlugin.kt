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
import java.util.concurrent.Executors

/** Công tắc "Cho máy khác nghe thư viện này" (SharedPreferences "sync"). */
private const val SHARE_KEY = ShareService.SHARE_KEY

/** Số file tối đa trong một lần chọn nhiều file của "Thêm sách từ file…" (mỗi file được chép vào thư mục tạm của app trước khi xem trước). */
private const val PICK_SOURCE_LIMIT = 40
private const val HEAD_BYTES = 512 // đầu file đủ để thấy mục `mimetype` của gói (BookFileImport.looksLikeBookFile)

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
    // Nhập file sách (.abook / .abookproj): chép + băm + giải nén vài GB mất phút - không được chặn hàng `io` (tiến độ nghe, thư viện
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
     * [NetErrors.UNPAIRED] (nó đã bỏ ghép máy này). Lỗi mạng: câu tiếng Việt theo loại, mã là tên loại, chữ gốc trong `data.technical` (soát a68 lỗi 4, 5).
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

    /** Trang đầu đã dựng xong và đứng yên: màn chờ lúc mở app được mờ đi (MainActivity). */
    @PluginMethod
    fun appReady(call: PluginCall) {
        LaunchSplash.ready = true
        call.resolve()
    }

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
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true).putExtra(Intent.EXTRA_MIME_TYPES, MusicImport.MIME_TYPES)
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
                call.resolve(importMusic(uris.take(MusicImport.LIMIT)))
            } catch (error: Exception) {
                fail(call, error, "không nhập được nhạc")
            }
        }
    }

    /** Nhập từng bản vào kho ([MusicImport]), báo tiến độ "musicImport" {done, total}; trả đúng JSON của `my_music_import`. */
    private fun importMusic(uris: List<Uri>): JSObject =
        JSObject.fromJSONObject(MusicImport.run(context, uris) { done, total ->
            notifyListeners("musicImport", JSObject().put("done", done).put("total", total))
        }).put("picked", true)

    // ---- ghép nối --------------------------------------------------------------------------------------------

    /** Tìm máy tính đang bật đồng bộ trong cùng mạng Wi-Fi (UDP broadcast). */
    @PluginMethod
    fun discover(call: PluginCall) = background(call) {
        call.resolve(JSObject().put("computers", Devices.discover(context, call.getInt("timeoutMs") ?: 2500)))
    }

    @PluginMethod
    fun pair(call: PluginCall) = background(call) {
        val host = call.getString("host") ?: throw IllegalArgumentException("thiếu địa chỉ máy tính")
        val name = Devices.pair(context, host, call.getInt("port") ?: 47630, call.getString("code") ?: "", call.getString("device"))
        call.resolve(JSObject().put("name", name))
    }

    /** Đổi tên điện thoại này ở máy khác (soát a68 lỗi 16); rỗng = tên mặc định. Báo ngay máy tính chính và các máy đã ghép (máy tắt thì lần ghép sau). */
    @PluginMethod
    fun setDeviceName(call: PluginCall) = background(call) {
        call.resolve(JSObject().put("name", Devices.setDeviceName(context, call.getString("name") ?: "")))
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
        val devices = Devices.bluetoothDevices(context)
        val out = JSArray()
        for (index in 0 until devices.length()) out.put(JSObject.fromJSONObject(devices.getJSONObject(index)))
        call.resolve(JSObject().put("devices", out))
    }

    /** Ghép máy tính chính QUA BLUETOOTH: cùng mã 6 số, cùng /sync/v1/pair - đi qua đường hầm. */
    @PluginMethod
    fun pairBluetooth(call: PluginCall) = background(call) {
        val address = call.getString("address") ?: throw IllegalArgumentException("thiếu máy")
        call.resolve(JSObject().put("name", Devices.pairBluetooth(context, address, call.getString("code") ?: "", call.getString("device"))))
    }

    // ---- cho máy khác nghe thư viện này (mạng trạm bước 2 - LibraryServer) ------------------------------------------

    private fun shareView(): JSObject = JSObject.fromJSONObject(Devices.shareView(context))

    @PluginMethod
    fun shareStatus(call: PluginCall) = background(call) { call.resolve(shareView()) }

    /** Màn xuất hỏi riêng (không dựng cả trạng thái chia sẻ): có nhắc người dùng cho ABook chạy nền hay không. */
    @PluginMethod
    fun backgroundStatus(call: PluginCall) = call.resolve(JSObject.fromJSONObject(Devices.backgroundView(context)))

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
        call.resolve(JSObject.fromJSONObject(Devices.setShare(context, call.getBoolean("enabled") ?: false)))
    }

    @PluginMethod
    fun sharePair(call: PluginCall) = background(call) { call.resolve(JSObject.fromJSONObject(Devices.sharePair(context))) }

    @PluginMethod
    fun shareCancelPairing(call: PluginCall) = background(call) { call.resolve(JSObject.fromJSONObject(Devices.shareCancelPairing(context))) }

    @PluginMethod
    fun shareRevoke(call: PluginCall) = background(call) { call.resolve(JSObject.fromJSONObject(Devices.shareRevoke(context, call.getString("id") ?: ""))) }

    @PluginMethod
    fun connection(call: PluginCall) = call.resolve(JSObject.fromJSONObject(Devices.connection(context)))

    @PluginMethod
    fun unpair(call: PluginCall) {
        // Máy tính chính thu hồi mã của điện thoại này (soát a27 lỗi 5): báo trước khi quên địa chỉ - máy tính tắt thì chỉ chờ vài giây.
        Thread({
            Devices.unpair(context)
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

    /** Máy tính mở Studio được (Devices.studioComputers): máy tính chính rồi các máy tính ghép thêm - nút "Mở Studio" hỏi chọn khi có hơn một. */
    @PluginMethod
    fun studioComputers(call: PluginCall) = background(call) {
        val out = JSArray()
        val computers = Devices.studioComputers(context, call.getString("book"))
        for (index in 0 until computers.length()) out.put(JSObject.fromJSONObject(computers.getJSONObject(index)))
        call.resolve(JSObject().put("computers", out))
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
        call.resolve(JSObject.fromJSONObject(RemoteBooks.library(context)))
        RemoteBooks.reached(context)
    }

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
        RemoteBooks.fetchHolderEdits(context, id)
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

    /** Sách nghe thẳng của máy tính chính và thiết bị ghép ([RemoteBooks.streamable]); hỏi mạng nên có hàng riêng, không chặn hàng `io`. */
    @PluginMethod
    fun streamableBooks(call: PluginCall) = streaming(call) {
        val books = JSArray()
        val rows = RemoteBooks.streamable(context)
        for (index in 0 until rows.length()) books.put(JSObject.fromJSONObject(rows.getJSONObject(index)))
        call.resolve(JSObject().put("books", books))
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

    /** Sửa chưa gửi của các cuốn nghe thẳng của một thiết bị ghép - thứ bỏ ghép sẽ xoá (hộp xác nhận hỏi trước): từng cuốn, tổng, và
     *  `sendable` = thiết bị là máy tính nên "gửi trước" có nghĩa (điện thoại khác không nhận sửa); `cache` = cái bỏ ghép sẽ quên
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

    /** Bỏ ghép. Còn sửa chưa gửi thì từ chối, trừ khi `send` (gửi hết về máy ấy rồi mới gỡ; hỏng giữa chừng thì không gỡ) hay `discard` (người dùng chọn bỏ). */
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
            // Nhạc đọc lại lớp sửa; cuốn tải từ máy tính: phần sửa gửi về máy tính sau vài giây.
            Regex("/api/books/([A-Za-z0-9_-]+)").find(path)?.groupValues?.get(1)?.let { id -> BookActions.edited(context, id) }
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
        val project = BookSaves.asProject(id, call.getString("as"))
        val kept = if (call.getBoolean("ask", false) == true) null else BookSaves.remembered(context, id, project)
        if (kept != null) writeSavedBook(call, kept, direct = true) else askSaveLocation(call, id, project)
    }

    private fun askSaveLocation(call: PluginCall, id: String, project: Boolean) {
        startActivityForResult(call, BookSaves.askIntent(id, project), "savedBook")
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

    /** Ghi cuốn vào `uri` ([BookSaves.write]). `direct`: chỗ nhớ từ lần trước - ghi hỏng thì hỏi lại chỗ lưu thay vì báo lỗi; chỗ vừa chọn thì nhớ lại. */
    private fun writeSavedBook(call: PluginCall, uri: Uri, direct: Boolean) = io.execute {
        val id = call.getString("id")
        try {
            if (id == null) throw IllegalArgumentException("thiếu id")
            val written = BookSaves.write(context, id, uri, BookSaves.asProject(id, call.getString("as")), direct)
            call.resolve(JSObject().put("saved", true).put("name", written.name).put("size", written.size).put("edits", written.edits))
        } catch (error: Exception) {
            // Gói dựng hỏng (thiếu file nguồn...) thì chỗ lưu không có lỗi: giữ chỗ nhớ, báo đúng lý do thay vì hỏi chỗ khác rồi hỏng y hệt.
            if (id != null && BookSave.shouldChooseAnotherLocation(direct, error)) {
                BookSaves.forget(context, id)
                activity.runOnUiThread { askSaveLocation(call, id, BookSaves.asProject(id, call.getString("as"))) }
            } else fail(call, error, "không lưu được file")
        }
    }

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
        io.execute {
            val shared = try {
                BookActions.share(context, id, project)
            } catch (error: Exception) {
                fail(call, error, "không đóng được file sách để chia sẻ")
                return@execute
            }
            activity.runOnUiThread {
                try {
                    activity.startActivity(shared.chooser)
                    call.resolve(JSObject().put("shared", true).put("name", shared.name))
                } catch (error: Exception) {
                    fail(call, error, "không mở được bảng chia sẻ")
                }
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
            val (chooser, target) = try {
                Diagnostics.shareIntent(context)
            } catch (error: Exception) {
                fail(call, error, "không gom được nhật ký để gửi")
                return@execute
            }
            activity.runOnUiThread {
                try {
                    activity.startActivity(chooser)
                    AppLog.i("Diagnostics", "mở bảng chia sẻ nhật ký (${target.length()} byte)")
                    call.resolve(JSObject().put("shared", true).put("name", target.name))
                } catch (error: Exception) {
                    fail(call, error, "không mở được bảng chia sẻ")
                }
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
        try {
            ExportStart.requireBook(id)
        } catch (error: Mp3Export.Refused) {
            return call.reject(error.message)
        }
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
        // Sách không có gì để xuất: từ chối ngay, không bắt đầu việc nền.
        val started = ExportStart.mp3(context, id, tree, drawn, selected, call.getBoolean("music", false) == true)
        call.resolve(JSObject().put("started", true).put("run", started.run).put("folder", started.folder).put("chapters", started.chapters))
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
        val title = try {
            ExportStart.m4bTitle(id)
        } catch (error: Mp3Export.Refused) {
            return call.reject(error.message)
        }
        startActivityForResult(call, M4bExports.createIntent(title), "pickedM4bFile")
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
                val started = ExportStart.m4b(context, id, file, drawnCover(call.getString("cover")), call.getBoolean("music", false) == true)
                call.resolve(JSObject().put("started", true).put("run", started.run).put("name", started.name).put("chapters", started.chapters))
            } catch (error: Exception) {
                M4bExports.discard(context, file) // chưa bắt đầu việc nền (hay thiếu bookId): file rỗng vừa tạo không để lại
                throw error
            }
        }
    }

    // ---- "Xuất sách nói" của sách Nghe ngay (ListenExport, ListenExportWorker) ------------------------------------------

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
        background(call) { call.resolve(JSObject.fromJSONObject(ExportStart.audiobookPlan(context, id, voice, wanted))) }
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
            val title = ExportStart.audiobookTitle(id)
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
                val started = ExportStart.audiobook(context, id, voice, file, drawnCover(call.getString("cover")), call.getBoolean("music", false) == true)
                call.resolve(JSObject().put("started", true).put("run", started.run).put("name", started.name))
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
        call.resolve(JSObject().put("opened", ExportStart.openFile(context, uri)))
    }

    /**
     * "Mở thư mục" ở thông báo xuất xong: mở thư mục bản xuất bằng app Tệp của hệ thống. Chỉ nhận địa chỉ nằm trong thư mục người dùng đã
     * cấp cho ABook (không mở địa chỉ tuỳ ý); máy không có app nào mở được thư mục thì trả {opened: false} - giao diện nói đường đi bằng chữ.
     */
    @PluginMethod
    fun openFolder(call: PluginCall) {
        val uri = call.getString("uri")?.let(Uri::parse) ?: return call.reject("thiếu uri")
        call.resolve(JSObject().put("opened", ExportStart.openFolder(context, uri)))
    }

    /** Bìa tự vẽ gửi từ giao diện, cùng luật với máy tính (export._cover_file): chỉ data URL PNG, tối đa 4 MB. */
    private fun drawnCover(value: String?): ByteArray? {
        val match = Regex("data:image/png;base64,([A-Za-z0-9+/=]+)").matchEntire(value ?: return null) ?: return null
        val bytes = runCatching { android.util.Base64.decode(match.groupValues[1], android.util.Base64.DEFAULT) }.getOrNull() ?: return null
        return bytes.takeIf { it.size <= 4 * 1024 * 1024 && Id3Tag.Cover.of(it)?.mime == "image/png" }
    }

    // ---- hồ sơ nghe (độc lập với sách, app giữ liên kết - Store) -----------------------------------------------

    /** Trả danh sách hồ sơ mới, rồi báo máy tính ([ListeningRecords.Change.push]) ở luồng nền. */
    private fun resolveRecords(call: PluginCall, change: ListeningRecords.Change) {
        call.resolve(JSObject().put("records", change.records))
        io.execute { change.push() }
    }

    @PluginMethod
    fun createRecord(call: PluginCall) = background(call) {
        resolveRecords(call, ListeningRecords.create(context, call.getString("id")!!, call.getString("name") ?: ""))
    }

    @PluginMethod
    fun activateRecord(call: PluginCall) = background(call) {
        resolveRecords(call, ListeningRecords.activate(context, call.getString("id")!!, call.getString("record")!!))
    }

    @PluginMethod
    fun renameRecord(call: PluginCall) = background(call) {
        resolveRecords(call, ListeningRecords.rename(context, call.getString("id")!!, call.getString("record")!!, call.getString("name") ?: ""))
    }

    @PluginMethod
    fun moveRecord(call: PluginCall) = background(call) {
        resolveRecords(call, ListeningRecords.move(context, call.getString("id")!!, call.getString("record")!!, call.getString("book").orEmpty()))
    }

    @PluginMethod
    fun deleteRecord(call: PluginCall) = background(call) {
        resolveRecords(call, ListeningRecords.delete(context, call.getString("id")!!, call.getString("record")!!))
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
    private fun bookText(id: String, path: String): String? = BookActions.text(context, id, path)

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
        // Cuốn nằm chờ rồi mới xoá hẳn; `undo` là mã để "Hoàn tác" (không có khi xoá thẳng) - BookActions.delete.
        val undo = BookActions.delete(context, call.getString("id").orEmpty()) { io.execute(it) }
        call.resolve(JSObject().put("undo", undo ?: JSONObject.NULL))
    }

    @PluginMethod
    fun undoDelete(call: PluginCall) = background(call) {
        Store.undoBook(call.getString("token").orEmpty())
        call.resolve()
    }

    @PluginMethod
    fun storage(call: PluginCall) = background(call) { call.resolve(JSObject.fromJSONObject(Devices.storage())) }

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
