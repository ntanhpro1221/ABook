package vn.abook.player

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.net.http.SslCertificate
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate

/**
 * Studio từ xa: giao diện web mà máy tính phục vụ trên cổng đồng bộ (webui/remote_studio.py) - xem tiến độ, bắt đầu
 * hay dừng, "Việc cần duyệt", "Cần nghe lại", đặt bìa. Điện thoại không sản xuất, nhưng điều khiển được máy có sản xuất
 * (chủ sách 27-09).
 *
 * Mở bằng WebView riêng chứ không trong trang của app: trang app nạp từ https://localhost, không gọi được thẳng máy
 * tính (chứng chỉ tự ký). Ở đây cả trang là của máy tính, và mã thiết bị đã ghép đi vào cookie HttpOnly đúng như khi một trình
 * duyệt ghép bằng mã 6 số - không phải ghép lần hai. Chứng chỉ tự ký của máy tính chỉ được nhận khi trùng vân tay đã ghim lúc
 * ghép ([Pin]); khác là trang không mở, không có nút "tiếp tục". Máy tính chưa bật "Cho phép điều khiển sản xuất" thì trang tự
 * giải thích cách bật.
 */
class StudioActivity : AppCompatActivity() {
    private lateinit var web: WebView
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
        val base = SyncLink.base(this)
        if (!SyncLink.paired(this)) {
            finish()
            return
        }
        web = WebView(this)
        setContentView(web)
        // Android 15 vẽ tràn viền: trang web của máy tính không biết vùng an toàn, nên chừa chỗ cho thanh hệ thống.
        ViewCompat.setOnApplyWindowInsetsListener(web) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
        }
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setCookie(base, "abook_device=${SyncLink.token(this@StudioActivity)}; Path=/; HttpOnly; Secure; SameSite=Strict")
            flush()
        }
        web.webViewClient = object : WebViewClient() {
            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                // Chứng chỉ tự ký của máy tính: nhận đúng khi vân tay trùng cái đã ghim; còn lại huỷ, không hỏi người dùng.
                val uri = Uri.parse(error.url)
                val pinned = Pin.expected(uri.host, if (uri.port > 0) uri.port else 443)
                val seen = certificateOf(error.certificate)?.let { Pin.fingerprint(it.encoded) }
                if (pinned != null && pinned.isNotEmpty() && seen == pinned) {
                    handler.proceed()
                } else {
                    // Không có trang để hiện (WebView để trắng): nói lý do rồi về màn trước, nơi cũng đang báo "ghép lại".
                    handler.cancel()
                    if (!isFinishing) {
                        Toast.makeText(this@StudioActivity, Pin.CHANGED, Toast.LENGTH_LONG).show()
                        finish()
                    }
                }
            }

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url.toString()
                if (url.startsWith(base)) return false
                // Liên kết ra ngoài (nguồn ảnh bìa...) mở bằng trình duyệt, không kéo WebView này đi nơi khác.
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                return true
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
                if (web.canGoBack()) web.goBack() else finish()
            }
        })
        // Thông báo Studio (StudioAlerts.kt) mở thẳng đúng cuốn, đúng tab: "/#/studio/<mã>?tab=work".
        val path = intent.getStringExtra("path")?.takeIf { it.startsWith("/#/studio") } ?: "/#/studio"
        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl(base + path)
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
        if (::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
