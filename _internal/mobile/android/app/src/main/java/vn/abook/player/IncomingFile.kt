package vn.abook.player

import android.content.Intent
import android.net.Uri
import android.os.Build

/** File app khác gửi tới ("Mở bằng ABook", chia sẻ tới ABook): một chỗ lấy địa chỉ ra khỏi Intent cho cả MainActivity (WebView) lẫn NativeActivity. */
object IncomingFile {
    /** Lời báo khi bạn chia sẻ chữ trần (vd một đường link): app nhận SEND text/plain cho file .txt nên chữ trần cũng tới đây. */
    const val TEXT_ONLY = "Bạn gửi file EPUB, Word, PDF hoặc TXT; chưa nhận đoạn chữ chia sẻ."

    /** Địa chỉ file của lệnh "Mở bằng" (VIEW) hay "Chia sẻ" (SEND); null khi Intent không mang file. */
    fun uri(intent: Intent?): Uri? = when (intent?.action) {
        Intent.ACTION_VIEW -> intent.data
        Intent.ACTION_SEND -> if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }
        else -> null
    }

    /** Chia sẻ chỉ có chữ, không có file. */
    fun textOnly(intent: Intent?): Boolean =
        intent?.action == Intent.ACTION_SEND && uri(intent) == null && intent.getStringExtra(Intent.EXTRA_TEXT) != null
}
