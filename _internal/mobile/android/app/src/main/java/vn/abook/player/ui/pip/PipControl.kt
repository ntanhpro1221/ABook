package vn.abook.player.ui.pip

import android.app.AppOpsManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * Cầu giữa Activity (giữ chế độ PiP của hệ thống) và giao diện Compose: `available` = máy và app được phép vào PiP (nút "Cửa sổ mini" và công tắc ở Cài đặt chỉ hiện
 * khi true); `active` = đang ở trong cửa sổ nhỏ (khung vẽ chỉ còn [PipContent]); [enter] = vào PiP ngay (nút "Cửa sổ mini" của Đang nghe).
 */
@Stable
class PipControl(val available: Boolean, private val enterNow: () -> Unit = {}) {
    var active by mutableStateOf(false)

    fun enter() = enterNow()
}

object PipSupport {
    /** Hàm thuần của [available]: PiP có từ Android 8 (API 26), máy phải khai tính năng, và người dùng chưa tắt PiP cho app ở Cài đặt hệ thống. */
    fun allowed(sdk: Int, hasFeature: Boolean, appOpAllowed: Boolean): Boolean = sdk >= Build.VERSION_CODES.O && hasFeature && appOpAllowed

    fun available(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false
        val hasFeature = context.packageManager.hasSystemFeature(PackageManager.FEATURE_PICTURE_IN_PICTURE)
        val ops = context.getSystemService(AppOpsManager::class.java)
        val mode = if (ops == null) AppOpsManager.MODE_ALLOWED else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_PICTURE_IN_PICTURE, Process.myUid(), context.packageName)
        } else {
            @Suppress("DEPRECATION")
            ops.checkOpNoThrow(AppOpsManager.OPSTR_PICTURE_IN_PICTURE, Process.myUid(), context.packageName)
        }
        return allowed(Build.VERSION.SDK_INT, hasFeature, mode == AppOpsManager.MODE_ALLOWED)
    }
}
