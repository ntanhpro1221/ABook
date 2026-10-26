package vn.abook.player

import android.content.Context
import android.os.Build
import android.provider.Settings

/**
 * Tên của điện thoại này ở máy khác (máy tính đã ghép, thư viện chia sẻ - LibraryServer): người dùng đặt được (Cài đặt › Thiết bị → "Tên điện thoại này");
 * chưa đặt thì một tên dễ đọc - tên máy người dùng đặt trong Cài đặt Android, không thì "Điện thoại <hãng> <đời>" (soát a68 lỗi 16: trước đây
 * là Build.MANUFACTURER + MODEL thô, "Google sdk_gphone64_x86_64"). Lưu ngoài SharedPreferences "sync": bỏ ghép máy tính chính xoá sạch nó.
 */
object DeviceName {
    private const val PREFS = "abook_self"
    private const val KEY = "name"
    const val MAX_LENGTH = 60

    /** Phần thuần (test được): tên mặc định từ tên máy người dùng đặt (`userSet`, Settings.Global DEVICE_NAME - nhiều máy để nguyên đời máy thô
     *  ở đó), hay hãng + đời máy. Máy ảo của Android Studio ("sdk_gphone64_x86_64") thành "(máy ảo)". */
    fun fallback(userSet: String?, manufacturer: String, model: String): String {
        val brand = manufacturer.trim().replaceFirstChar { it.uppercase() }
        val raw = model.trim()
        val chosen = userSet?.trim().orEmpty()
        if (chosen.isNotEmpty() && !chosen.equals(raw, ignoreCase = true) && !emulator(chosen)) return chosen.take(MAX_LENGTH)
        if (emulator(raw)) return listOf("Điện thoại", brand, "(máy ảo)").filter { it.isNotEmpty() }.joinToString(" ")
        // Đời máy hay lặp lại tên hãng ("samsung SM-A525F" thì không, "Xiaomi Xiaomi 13" thì có): bỏ phần lặp.
        val bare = (if (brand.isEmpty()) raw else raw.replace(Regex("^" + Regex.escape(brand) + """\s*""", RegexOption.IGNORE_CASE), "")).trim().replace('_', ' ')
        return listOf("Điện thoại", brand, bare).filter { it.isNotEmpty() }.joinToString(" ").take(MAX_LENGTH)
    }

    private fun emulator(name: String): Boolean = Regex("""(^|[_\s])(sdk|gphone|emulator)""", RegexOption.IGNORE_CASE).containsMatchIn(name)

    /** Tên đang dùng: người dùng đặt ở ABook, không thì [fallback]. */
    fun of(context: Context): String {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)?.trim()?.takeIf { it.isNotEmpty() }?.let { return it }
        val userSet = runCatching { Settings.Global.getString(context.contentResolver, Settings.Global.DEVICE_NAME) }.getOrNull()
        return fallback(userSet, Build.MANUFACTURER.orEmpty(), Build.MODEL.orEmpty())
    }

    /** Đặt tên (rỗng = về tên mặc định); trả tên đang dùng sau khi đặt. */
    fun set(context: Context, name: String): String {
        val clean = name.replace(Regex("""\s+"""), " ").trim().take(MAX_LENGTH)
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply { if (clean.isEmpty()) remove(KEY) else putString(KEY, clean) }.commit()
        return of(context)
    }
}
