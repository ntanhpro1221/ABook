package vn.ebookreader.player

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * Studio từ xa: giao diện web mà máy tính phục vụ trên cổng đồng bộ (webui/remote_studio.py) - xem tiến độ, bắt đầu
 * hay dừng, "Việc cần anh", "Cần nghe lại", đặt bìa. Điện thoại không sản xuất, nhưng điều khiển được máy có sản xuất
 * (chủ sách 27-09).
 *
 * Mở bằng WebView riêng chứ không trong trang của app: trang app nạp từ https://localhost, không gọi được http LAN
 * (mixed content). Ở đây cả trang là của máy tính, và mã thiết bị đã ghép đi vào cookie HttpOnly đúng như khi một trình
 * duyệt ghép bằng mã 6 số - không phải ghép lần hai. Máy tính chưa bật "Cho phép điều khiển sản xuất" thì trang tự
 * giải thích cách bật.
 */
class StudioActivity : AppCompatActivity() {
    private lateinit var web: WebView
    private var pendingFiles: ValueCallback<Array<Uri>>? = null
    private val pickImage = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        pendingFiles?.onReceiveValue(uri?.let { arrayOf(it) } ?: arrayOf())
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
            setCookie(base, "abook_device=${SyncLink.token(this@StudioActivity)}; Path=/; HttpOnly; SameSite=Strict")
            flush()
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url.toString()
                if (url.startsWith(base)) return false
                // Liên kết ra ngoài (nguồn ảnh bìa...) mở bằng trình duyệt, không kéo WebView này đi nơi khác.
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            // "Đổi ảnh bìa" trong Studio: chọn ảnh trong máy.
            override fun onShowFileChooser(
                view: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean {
                pendingFiles?.onReceiveValue(arrayOf())
                pendingFiles = callback
                pickImage.launch("image/*")
                return true
            }
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })
        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl("$base/#/studio")
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (::web.isInitialized) web.saveState(outState)
    }

    override fun onDestroy() {
        if (::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
