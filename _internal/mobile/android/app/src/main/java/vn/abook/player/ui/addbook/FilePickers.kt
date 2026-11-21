package vn.abook.player.ui.addbook

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.DocumentsContract
import androidx.activity.result.contract.ActivityResultContract
import vn.abook.player.AppLog

/**
 * Hộp chọn một file (ACTION_OPEN_DOCUMENT) mở ở chỗ của file cũ khi Android cho (EXTRA_INITIAL_URI, Android 8+): "Thử lại" của hàng đã mất
 * quyền đọc dùng nó để người dùng chọn lại đúng file ấy chỉ bằng một chạm.
 */
class ReopenDocument : ActivityResultContract<Uri?, Uri?>() {
    override fun createIntent(context: Context, input: Uri?): Intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        .addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
        .apply { if (input != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) putExtra(DocumentsContract.EXTRA_INITIAL_URI, input) }

    override fun parseResult(resultCode: Int, intent: Intent?): Uri? = intent?.takeIf { resultCode == Activity.RESULT_OK }?.data
}

/**
 * Giữ quyền đọc lâu dài cho file / thư mục vừa chọn, để hàng lỗi còn "Thử lại" được sau khi app khởi động lại. Nguồn không cho giữ quyền
 * (nhà cung cấp không đặt FLAG_GRANT_PERSISTABLE_URI_PERMISSION) thì chỉ ghi nhật ký: quyền tạm vẫn đủ cho lượt đọc này.
 */
fun keepReadAccess(context: Context, uri: Uri) {
    try {
        context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
    } catch (error: SecurityException) {
        AppLog.w("AddBook", "persistable read grant refused for ${uri.authority}: ${error.javaClass.simpleName}")
    }
}
