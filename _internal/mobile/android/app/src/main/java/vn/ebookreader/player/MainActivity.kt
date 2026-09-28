package vn.ebookreader.player

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        registerPlugin(PlayerPlugin::class.java)
        registerPlugin(LibraryPlugin::class.java)
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) open(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        open(intent)
    }

    /** "Mở bằng ABook" / chia sẻ một file sách tới app: nhập vào thư viện (LibraryPlugin.importFrom). */
    private fun open(intent: Intent?) {
        val uri: Uri? = when (intent?.action) {
            Intent.ACTION_VIEW -> intent.data
            Intent.ACTION_SEND -> if (Build.VERSION.SDK_INT >= 33) {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(Intent.EXTRA_STREAM)
            }
            else -> null
        }
        if (uri == null) return
        val plugin = bridge?.getPlugin("EbookLibrary")?.instance as? LibraryPlugin ?: return
        plugin.importFrom(uri)
    }

    // Mở app là máy tính thấy điện thoại (để "Phát trên điện thoại" được cả khi chưa nghe gì) - Remote.
    override fun onResume() {
        super.onResume()
        Playback.init(this)
        Remote.foreground = true
        StudioAlerts.checkSoon(this)  // mở app là hỏi máy tính ngay, không đợi lượt 15 phút
    }

    override fun onPause() {
        Remote.foreground = false
        super.onPause()
    }
}
