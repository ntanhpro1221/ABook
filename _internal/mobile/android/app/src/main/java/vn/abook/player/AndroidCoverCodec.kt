package vn.abook.player

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.media.ExifInterface
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

/**
 * [CoverCodec] thật trên điện thoại - `covers.render_cover` của máy tính bằng BitmapFactory: xoay theo EXIF, bỏ kênh trong
 * suốt (đặt lên nền trắng), cạnh dài tối đa 1400, JPEG chất lượng 88, cạnh ngắn dưới 64 điểm ảnh thì từ chối. Màu chủ đạo
 * xấp xỉ `covers.dominant_color` (8 màu thay vì lượng tử hoá của Pillow): cùng cách chấm - nhiều điểm ảnh, ưu tiên có sắc, tránh
 * tối/sáng quá - rồi đưa độ sáng về dải đọc được; hai bên không cần ra đúng từng chữ số, chỉ cần màu nhuộm nền hợp ảnh.
 */
object AndroidCoverCodec : CoverCodec {
    override fun normalize(raw: ByteArray): CoverCodec.Normalized {
        if (raw.size > Covers.MAX_UPLOAD_BYTES) throw Covers.tooLarge()
        val unreadable = CoverCodec.CoverError("Không đọc được ảnh này")
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(raw, 0, raw.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw unreadable
        if (minOf(bounds.outWidth, bounds.outHeight) < Covers.MIN_SIDE) {
            throw CoverCodec.CoverError("Ảnh quá nhỏ để làm bìa (cần ít nhất ${Covers.MIN_SIDE} điểm ảnh mỗi cạnh)")
        }
        // Ảnh chụp 12 MB không cần giải mã hết cỡ: bỏ bớt điểm ảnh sao cho cạnh dài còn >= MAX_SIDE rồi thu về đúng cỡ.
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= Covers.MAX_SIDE) sample *= 2
        val decoded = BitmapFactory.decodeByteArray(raw, 0, raw.size, BitmapFactory.Options().apply { inSampleSize = sample })
            ?: throw unreadable
        val upright = rotated(decoded, orientation(raw))
        val scale = minOf(1.0, Covers.MAX_SIDE.toDouble() / maxOf(upright.width, upright.height))
        val sized = if (scale < 1.0) {
            Bitmap.createScaledBitmap(upright, maxOf(1, Math.round(upright.width * scale).toInt()), maxOf(1, Math.round(upright.height * scale).toInt()), true)
        } else upright
        // JPEG không có kênh trong suốt: đặt lên nền trắng như bản máy tính.
        val flat = Bitmap.createBitmap(sized.width, sized.height, Bitmap.Config.ARGB_8888)
        Canvas(flat).apply {
            drawColor(Color.WHITE)
            drawBitmap(sized, 0f, 0f, null)
        }
        val out = ByteArrayOutputStream()
        flat.compress(Bitmap.CompressFormat.JPEG, 88, out)
        val result = CoverCodec.Normalized(out.toByteArray(), dominantColor(flat), flat.width, flat.height)
        for (bitmap in setOf(decoded, upright, sized, flat)) if (!bitmap.isRecycled) bitmap.recycle()
        return result
    }

    private fun orientation(raw: ByteArray): Int = runCatching {
        ExifInterface(ByteArrayInputStream(raw)).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
    }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)

    private fun rotated(bitmap: Bitmap, orientation: Int): Bitmap {
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matrix.postRotate(90f)
                matrix.postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matrix.postRotate(270f)
                matrix.postScale(-1f, 1f)
            }
            else -> return bitmap
        }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    /** Màu đại diện: 8 ô (mỗi kênh một bit) trên bản thu 64x64, chấm theo số điểm ảnh x (0,25 + độ bão hoà), rồi đưa độ sáng về 0,32..0,62. */
    private fun dominantColor(bitmap: Bitmap): String {
        val small = Bitmap.createScaledBitmap(bitmap, 64, 64, true)
        val pixels = IntArray(64 * 64)
        small.getPixels(pixels, 0, 64, 0, 0, 64, 64)
        if (small !== bitmap) small.recycle()
        val count = IntArray(8)
        val sums = Array(8) { LongArray(3) }
        for (pixel in pixels) {
            val r = Color.red(pixel)
            val g = Color.green(pixel)
            val b = Color.blue(pixel)
            val bin = (if (r >= 128) 4 else 0) or (if (g >= 128) 2 else 0) or (if (b >= 128) 1 else 0)
            count[bin]++
            sums[bin][0] += r.toLong()
            sums[bin][1] += g.toLong()
            sums[bin][2] += b.toLong()
        }
        var best = doubleArrayOf(120.0, 120.0, 120.0)
        var bestScore = -1.0
        for (bin in 0 until 8) {
            if (count[bin] == 0) continue
            val rgb = DoubleArray(3) { sums[bin][it].toDouble() / count[bin] }
            val (_, lightness, saturation) = hls(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
            val score = count[bin] * (0.25 + saturation) * (if (lightness > 0.12 && lightness < 0.88) 1.0 else 0.35)
            if (score > bestScore) {
                best = rgb
                bestScore = score
            }
        }
        val (hue, lightness, saturation) = hls(best[0] / 255, best[1] / 255, best[2] / 255)
        val (r, g, b) = rgb(hue, lightness.coerceIn(0.32, 0.62), minOf(saturation, 0.75))
        return "#%02x%02x%02x".format(Math.round(r * 255), Math.round(g * 255), Math.round(b * 255))
    }

    /** `colorsys.rgb_to_hls`. */
    private fun hls(r: Double, g: Double, b: Double): Triple<Double, Double, Double> {
        val high = maxOf(r, g, b)
        val low = minOf(r, g, b)
        val lightness = (low + high) / 2
        if (high == low) return Triple(0.0, lightness, 0.0)
        val span = high - low
        val saturation = if (lightness <= 0.5) span / (high + low) else span / (2 - high - low)
        val rc = (high - r) / span
        val gc = (high - g) / span
        val bc = (high - b) / span
        val hue = when (high) {
            r -> bc - gc
            g -> 2 + rc - bc
            else -> 4 + gc - rc
        }
        return Triple((hue / 6) - Math.floor(hue / 6), lightness, saturation)
    }

    /** `colorsys.hls_to_rgb`. */
    private fun rgb(hue: Double, lightness: Double, saturation: Double): Triple<Double, Double, Double> {
        if (saturation == 0.0) return Triple(lightness, lightness, lightness)
        val m2 = if (lightness <= 0.5) lightness * (1 + saturation) else lightness + saturation - lightness * saturation
        val m1 = 2 * lightness - m2
        fun channel(h: Double): Double {
            val x = h - Math.floor(h)
            return when {
                x < 1.0 / 6 -> m1 + (m2 - m1) * x * 6
                x < 0.5 -> m2
                x < 2.0 / 3 -> m1 + (m2 - m1) * (2.0 / 3 - x) * 6
                else -> m1
            }
        }
        return Triple(channel(hue + 1.0 / 3), channel(hue), channel(hue - 1.0 / 3))
    }
}
