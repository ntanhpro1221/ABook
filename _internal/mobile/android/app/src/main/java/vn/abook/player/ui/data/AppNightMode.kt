package vn.abook.player.ui.data

import android.app.UiModeManager
import android.content.Context
import android.os.Build

/**
 * Màn chờ lúc mở app (Android 12+) vẽ trước mọi dòng mã của app, từ tài nguyên theo chế độ đêm: `drawable-night/splash_icon` và
 * `values-night` app_bg. Nếu chỉ máy quyết sáng / tối thì máy để Tối mà trong app chọn Sáng sẽ hiện màn chờ tối (hình kem) rồi bật
 * sang app sáng. Android 12+ nhớ một chế độ đêm RIÊNG của app (`UiModeManager.setApplicationNightMode`), áp cả cho màn chờ lần mở
 * sau - nên mỗi khi giao diện trong app đổi (và lúc mở app) ghi lựa chọn ấy xuống. Tự động = theo máy. Soát tapthru5 S4 (18-11).
 * Dưới Android 12 không có cách nào: màn chờ theo máy.
 */
object AppNightMode {
    fun of(theme: ThemeMode): Int = when (theme) {
        ThemeMode.Light -> UiModeManager.MODE_NIGHT_NO
        ThemeMode.Dark -> UiModeManager.MODE_NIGHT_YES
        ThemeMode.System -> UiModeManager.MODE_NIGHT_AUTO
    }

    fun apply(context: Context, theme: ThemeMode, loaded: Boolean, demo: Boolean = false) {
        // SettingsRepo starts at System while its stored choice is still loading. Do not clear the remembered splash override then.
        if (!loaded || demo || Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return
        context.getSystemService(UiModeManager::class.java)?.setApplicationNightMode(of(theme))
    }
}
