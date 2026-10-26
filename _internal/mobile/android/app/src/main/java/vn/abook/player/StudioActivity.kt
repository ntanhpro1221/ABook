package vn.abook.player

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.net.http.SslCertificate
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.AppCompatButton
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import org.json.JSONObject
import java.io.IOException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Studio từ xa: giao diện web mà máy tính phục vụ trên cổng đồng bộ (webui/remote_studio.py) - xem tiến độ, bắt đầu
 * hay dừng, "Việc cần duyệt", "Cần nghe lại", đặt bìa. Điện thoại không sản xuất, nhưng điều khiển được máy có sản xuất
 * (chủ sách 27-09).
 *
 * Mở bằng WebView riêng chứ không trong trang của app: trang app nạp từ https://localhost, không gọi được thẳng máy
 * tính (chứng chỉ tự ký). Ở đây cả trang là của máy tính, và mã thiết bị đã ghép đi vào cookie HttpOnly đúng như khi một trình
 * duyệt ghép bằng mã 6 số - không phải ghép lần hai. Chứng chỉ tự ký của máy tính chỉ được nhận khi trùng vân tay đã ghim lúc
 * ghép ([Pin]); khác là trang không mở, không có nút "tiếp tục". Máy tính chưa cho thiết bị này sửa thì trang tự nói bật ở đâu.
 *
 * Máy nào: Intent extra `computer` ([StudioLink.MAIN] = máy tính chính, hay mã một máy tính ghép thêm trong [Peers]); trang nào:
 * extra `path` ("/#/studio/<mã cuốn>..."). Máy ấy không trả lời (tắt, đổi mạng) - lúc mở hay giữa chừng - thì thay trang lỗi trắng
 * của WebView bằng màn chờ, tự hỏi lại theo nhịp của máy tính (StudioLink.Watch) và nạp lại đúng trang đang xem khi máy ấy về.
 */
class StudioActivity : AppCompatActivity() {
    private enum class Answer { UP, SILENT, MISMATCH, PIN, GONE }

    private lateinit var web: WebView
    private lateinit var trouble: LinearLayout
    private lateinit var troubleTitle: TextView
    private lateinit var troubleDetail: TextView
    private lateinit var retry: AppCompatButton
    private var computer = StudioLink.MAIN
    private var name = ""
    @Volatile private var base = ""
    private var wanted = "/#/studio"
    @Volatile private var lastUrl: String? = null
    private var showing: Answer? = null
    private var watch: StudioLink.Watch? = null
    @Volatile private var pendingAnswer = Answer.SILENT // câu trả lời làm lượt hỏi lại dừng
    @Volatile private var theirVersion = ""
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private val asking = AtomicBoolean(false)
    @Volatile private var lastAsked = 0L
    private var pendingFiles: ValueCallback<Array<Uri>>? = null
    private val pickOne = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        pendingFiles?.onReceiveValue(uri?.let { arrayOf(it) } ?: arrayOf())
        pendingFiles = null
    }
    private val pickMany = registerForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        pendingFiles?.onReceiveValue(uris.toTypedArray())
        pendingFiles = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        computer = intent.getStringExtra("computer").orEmpty()
        val link = StudioLink.link(this, computer)
        if (link == null) {
            finish()
            return
        }
        base = link.base
        name = StudioLink.name(this, computer)
        wanted = StudioLink.safePath(intent.getStringExtra("path"))
        web = WebView(this)
        val root = FrameLayout(this)
        root.addView(web, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        root.addView(troubleView(), FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        setContentView(root)
        // Android 15 vẽ tràn viền: trang web của máy tính không biết vùng an toàn, nên chừa chỗ cho thanh hệ thống.
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
        }
        CookieManager.getInstance().setAcceptCookie(true)
        admit(link)
        web.webViewClient = object : WebViewClient() {
            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                // Chứng chỉ tự ký của máy tính: nhận đúng khi vân tay trùng cái đã ghim; còn lại huỷ, không hỏi người dùng.
                val uri = Uri.parse(error.url)
                val pinned = Pin.expected(uri.host, if (uri.port > 0) uri.port else 443)
                val seen = certificateOf(error.certificate)?.let { Pin.fingerprint(it.encoded) }
                if (pinned != null && pinned.isNotEmpty() && seen == pinned) {
                    handler.proceed()
                } else {
                    handler.cancel()
                    pinChanged()
                }
            }

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url.toString()
                if (url.startsWith(base)) return false
                // Liên kết ra ngoài (nguồn ảnh bìa...) mở bằng trình duyệt, không kéo WebView này đi nơi khác.
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                return true
            }

            override fun doUpdateVisitedHistory(view: WebView, url: String?, isReload: Boolean) {
                // Trang dùng định tuyến #/...: đổi trang trong Studio không nạp lại, nhưng có vào lịch sử - nhớ để nạp lại đúng chỗ.
                if (url != null && url.startsWith(base)) lastUrl = url
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (!request.url.toString().startsWith(base) || error.errorCode == WebViewClient.ERROR_FAILED_SSL_HANDSHAKE) return
                // Trang chính không nạp được: không để trang lỗi trắng. Lời gọi của trang hỏng giữa chừng: hỏi máy ấy còn trả lời không.
                if (request.isForMainFrame) settle(Answer.SILENT) else check()
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            // "Đổi ảnh bìa" (một ảnh) và "Chọn các file TXT" khi tạo sách (nhiều file; trình quản lý file hay gắn .txt
            // là octet-stream, nên không lọc theo loại - trang tự bỏ file không phải .txt).
            override fun onShowFileChooser(
                view: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean {
                pendingFiles?.onReceiveValue(arrayOf())
                pendingFiles = callback
                val type = if (params.acceptTypes.any { it.startsWith("image") }) "image/*" else "*/*"
                if (params.mode == FileChooserParams.MODE_OPEN_MULTIPLE) pickMany.launch(type) else pickOne.launch(type)
                return true
            }
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (showing == null && web.canGoBack()) web.goBack() else finish()
            }
        })
        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl(base + wanted)
        check(force = true) // cùng lúc nạp trang: hai máy có cùng bản không
    }

    override fun onResume() {
        super.onResume()
        // Quay lại app sau một lúc: máy ấy có thể đã tắt trong lúc đó.
        if (::web.isInitialized && showing == null) check()
    }

    /** Mã thiết bị của máy ấy vào cookie HttpOnly của đúng gốc đang mở - không bao giờ trong đường trang. */
    private fun admit(link: Peers.Link) {
        CookieManager.getInstance().apply {
            setCookie(link.base, "abook_device=${link.token}; Path=/; HttpOnly; Secure; SameSite=Strict")
            flush()
        }
    }

    /** Màn chờ / màn lỗi nằm đè lên trang (ẩn khi trang bình thường): một dòng, một lời giải thích, Thử lại và Đóng. */
    private fun troubleView(): View {
        val density = resources.displayMetrics.density
        fun dp(value: Int) = (value * density).toInt()
        val background = TypedValue().also { theme.resolveAttribute(android.R.attr.colorBackground, it, true) }
        troubleTitle = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        }
        troubleDetail = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            gravity = Gravity.CENTER
            alpha = 0.75f
            setPadding(0, dp(8), 0, dp(20))
        }
        retry = AppCompatButton(this).apply {
            text = "Thử lại"
            setOnClickListener { check(force = true, retrying = true) }
        }
        val close = AppCompatButton(this).apply {
            text = "Đóng"
            setOnClickListener { finish() }
        }
        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            addView(retry, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { marginEnd = dp(12) })
            addView(close, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        }
        trouble = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(24), dp(24), dp(24), dp(24))
            setBackgroundColor(background.data)
            isClickable = true // không để chạm xuyên xuống trang phía dưới
            visibility = View.GONE
            addView(troubleTitle, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
            addView(troubleDetail, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
            addView(buttons, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        }
        return trouble
    }

    /**
     * Hỏi máy ấy ở nền (`/api/app`, cùng mã thiết bị) rồi theo câu trả lời. Không hỏi chồng nhau, và lỗi lặp lại của trang không
     * hỏi quá một lần mỗi vài giây - trừ `force` (lúc mở, nút Thử lại).
     */
    private fun check(force: Boolean = false, retrying: Boolean = false) {
        val now = System.currentTimeMillis()
        if (!force && (showing != null || now - lastAsked < 3000)) return
        if (!asking.compareAndSet(false, true)) return
        lastAsked = now
        if (retrying) watch?.stop()
        runCatching {
            worker.execute {
                val answer = try {
                    ask()
                } finally {
                    asking.set(false)
                }
                runOnUiThread { settle(answer, retrying) }
            }
        }.onFailure { asking.set(false) }
    }

    /** Máy ấy lúc này: trả lời (kể cả lỗi của chính nó - trang tự nói), không trả lời, khác bản, chứng chỉ đổi, hay đã bỏ ghép. */
    private fun ask(): Answer {
        val link = StudioLink.link(this, computer) ?: return Answer.GONE
        return try {
            val text = SyncLink.request(this, "GET", "/api/app", auth = false, root = link.base, token = link.token,
                readTimeoutMs = 4000, connectTimeoutMs = 2000)
            theirVersion = runCatching { JSONObject(text).optString("version") }.getOrDefault("")
            if (StudioLink.mismatched(theirVersion, ourVersion())) Answer.MISMATCH else Answer.UP
        } catch (error: Pin.ChangedException) {
            Answer.PIN
        } catch (error: IOException) {
            Answer.SILENT
        } catch (error: Exception) {
            Answer.UP
        }
    }

    private fun ourVersion(): String = runCatching { packageManager.getPackageInfo(packageName, 0).versionName }.getOrNull().orEmpty()

    private fun settle(answer: Answer, retrying: Boolean = false) {
        if (isFinishing || isDestroyed) return
        when (answer) {
            Answer.UP -> if (showing != null) back()
            Answer.SILENT -> silent(retrying)
            Answer.MISMATCH -> show(Answer.MISMATCH, StudioLink.MISMATCH, "Điện thoại này: ${ourVersion()} · ${StudioLink.called(name)}: $theirVersion")
            Answer.PIN -> pinChanged()
            Answer.GONE -> finish()
        }
    }

    /** Máy ấy không trả lời: màn chờ, và hỏi lại theo nhịp tới khi nó trả lời (hay quá lâu - còn nút Thử lại). */
    private fun silent(retrying: Boolean) {
        if (showing != Answer.SILENT) {
            web.stopLoading()
            show(Answer.SILENT, StudioLink.silentLine(name), "Máy tắt hay đổi mạng. Studio tự mở lại đúng trang đang xem khi máy ấy trả lời.")
        }
        if (watch?.stopped == false && !retrying) return
        watch = StudioLink.Watch(
            reachable = { ask().also { pendingAnswer = it } != Answer.SILENT },
            onBack = { runOnUiThread { settle(pendingAnswer) } },
            schedule = { ms, task -> runCatching { worker.schedule({ task() }, ms, TimeUnit.MILLISECONDS) } },
        ).start()
    }

    private fun show(kind: Answer, title: String, detail: String) {
        showing = kind
        troubleTitle.text = title
        troubleDetail.text = detail
        trouble.visibility = View.VISIBLE
    }

    /** Máy ấy trả lời lại: bỏ màn chờ, nạp lại trang đang xem - ở gốc mới nếu máy tính chính nối lại qua đường khác. */
    private fun back() {
        watch?.stop()
        showing = null
        trouble.visibility = View.GONE
        val link = StudioLink.link(this, computer) ?: return finish()
        val target = StudioLink.rebase(lastUrl, base, link.base, wanted)
        base = link.base
        admit(link)
        if (target == web.url) web.reload() else web.loadUrl(target)
    }

    /** Vân tay lệch: không có trang để hiện và không có nút "tiếp tục" - nói lý do rồi về màn trước, nơi cũng đang báo "ghép lại". */
    private fun pinChanged() {
        if (isFinishing) return
        Toast.makeText(this, Pin.CHANGED, Toast.LENGTH_LONG).show()
        finish()
    }

    /** Chứng chỉ X.509 của lỗi SSL: API 29+ có sẵn; máy cũ hơn lấy từ trạng thái đã lưu của SslCertificate. */
    private fun certificateOf(certificate: SslCertificate): X509Certificate? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) certificate.x509Certificate
        else runCatching {
            val state = SslCertificate.saveState(certificate)
            CertificateFactory.getInstance("X.509").generateCertificate(state.getByteArray("x509-certificate")?.inputStream()) as X509Certificate
        }.getOrNull()

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (::web.isInitialized) web.saveState(outState)
    }

    override fun onDestroy() {
        watch?.stop()
        worker.shutdownNow()
        if (::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
