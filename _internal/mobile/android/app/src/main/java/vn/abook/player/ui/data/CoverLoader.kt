package vn.abook.player.ui.data

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.withContext

/** Cỡ lấy mẫu khi giải mã bìa (thuần số - thử trên JVM). */
object CoverSampling {
    /** `inSampleSize` lớn nhất (luỹ thừa 2) mà ảnh sau thu vẫn không nhỏ hơn ô cần vẽ ở cả hai chiều. */
    fun sampleSize(sourceWidth: Int, sourceHeight: Int, targetWidth: Int, targetHeight: Int): Int {
        if (sourceWidth <= 0 || sourceHeight <= 0 || targetWidth <= 0 || targetHeight <= 0) return 1
        var sample = 1
        while (sourceWidth / (sample * 2) >= targetWidth && sourceHeight / (sample * 2) >= targetHeight) sample *= 2
        return sample
    }

    /** Trần bộ nhớ đệm bìa: 1/16 heap (NATIVE_PHONE_UI.md §2). */
    fun cacheBytes(maxMemory: Long): Int = (maxMemory / 16).coerceIn(1L shl 20, Int.MAX_VALUE.toLong()).toInt()
}

/**
 * Bộ nạp bìa riêng, nhỏ (không thư viện ảnh): giải mã thu nhỏ đúng cỡ ô bằng `inSampleSize`, ngoài luồng chính, trên tối đa 3 luồng IO;
 * `LruCache` tính theo BYTE. RGB_565: bìa là ảnh chụp không trong suốt, nửa bộ nhớ so với ARGB_8888.
 */
class CoverLoader(maxBytes: Int = CoverSampling.cacheBytes(Runtime.getRuntime().maxMemory())) {
    private class Cached(val image: ImageBitmap, val bytes: Int)

    @OptIn(ExperimentalCoroutinesApi::class)
    private val decoders: CoroutineDispatcher = Dispatchers.IO.limitedParallelism(3)

    private val cache = object : LruCache<String, Cached>(maxBytes) {
        override fun sizeOf(key: String, value: Cached) = value.bytes
    }

    fun key(path: String, stamp: Long, width: Int) = "$path|$stamp|$width"

    /** Đã có trong bộ nhớ đệm thì lấy ngay (không chờ giải mã) - để ô cuộn vào không nháy khung trống. */
    fun peek(key: String): ImageBitmap? = cache.get(key)?.image

    /** Giải mã bìa ở `path` cho ô `width` x `height` px; null khi file hỏng / mất. */
    suspend fun load(key: String, path: String, width: Int, height: Int): ImageBitmap? {
        cache.get(key)?.let { return it.image }
        val decoded = withContext(decoders) { decode(path, width, height) } ?: return null
        val image = decoded.asImageBitmap()
        cache.put(key, Cached(image, decoded.allocationByteCount))
        return image
    }

    private fun decode(path: String, width: Int, height: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(path, bounds)
        val options = BitmapFactory.Options().apply {
            inSampleSize = CoverSampling.sampleSize(bounds.outWidth, bounds.outHeight, width, height)
            inPreferredConfig = Bitmap.Config.RGB_565
        }
        return BitmapFactory.decodeFile(path, options)
    }

    /** Hệ điều hành xin bớt bộ nhớ (UI ẩn / thiếu RAM): bỏ bìa đã nạp. */
    fun trim() = cache.evictAll()
}
