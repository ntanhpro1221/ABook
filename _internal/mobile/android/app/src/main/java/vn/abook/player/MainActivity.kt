package vn.abook.player

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import com.getcapacitor.BridgeActivity
import vn.abook.player.readaloud.ReadAloudPlugin

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        registerPlugin(PlayerPlugin::class.java)
        registerPlugin(LibraryPlugin::class.java)
        registerPlugin(ReadAloudPlugin::class.java)
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) open(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        open(intent)
    }

    /** "Mở bằng ABook" / chia sẻ một file tới app: file sách nhập vào thư viện, EPUB / DOCX / PDF / TXT mở bước xem trước của
     *  "Thêm sách từ file…" (LibraryPlugin.openFrom). */
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
        if (uri == null) {
            // Chia sẻ chữ trần (vd một đường link) cũng tới đây vì app nhận SEND text/plain cho file .txt: nói rõ thay vì im lặng.
            if (intent?.action == Intent.ACTION_SEND && intent.getStringExtra(Intent.EXTRA_TEXT) != null) {
                Toast.makeText(this, "ABook chỉ nhận file truyện (EPUB, Word, PDF, TXT) - đoạn chữ được chia sẻ không phải file.",
                    Toast.LENGTH_LONG).show()
            }
            return
        }
        val plugin = bridge?.getPlugin("EbookLibrary")?.instance as? LibraryPlugin ?: return
        plugin.openFrom(uri, intent?.type)
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
