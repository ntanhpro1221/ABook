package vn.abook.player

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import java.io.ByteArrayOutputStream

/**
 * Bìa sách cho màn hình khoá và thông báo - cùng thuật toán với bìa trên giao diện (ui/src/shared/cover.ts):
 * cùng tên sách thì cùng cặp màu ở mọi nơi.
 */
object Artwork {
    private val palettes = listOf(
        Triple("#1f3b57", "#0f1f30", "#f2a93f"), Triple("#4a2345", "#241124", "#f7b9c4"),
        Triple("#1d4a43", "#0d2622", "#8fe0c6"), Triple("#50301c", "#28170c", "#f2c078"),
        Triple("#2d2f5c", "#15162e", "#b7b9ff"), Triple("#5a2626", "#2d1111", "#ffb199"),
        Triple("#1f4d2c", "#0e2615", "#b8e986"), Triple("#3d3d46", "#1b1b20", "#e8d5a3"),
        Triple("#123f5c", "#081f2e", "#7fd1ff"), Triple("#4b3a14", "#241b07", "#ffd76a"),
    )
    private val cache = mutableMapOf<String, ByteArray>()

    private fun hash(text: String): Long {
        var value = 2166136261L
        for (char in text.trim().lowercase()) {
            value = value xor char.code.toLong()
            value = (value * 16777619L) and 0xffffffffL
        }
        return value
    }

    /**
     * Bìa cho màn hình khoá, thông báo, widget: ảnh bìa thật nếu sách có (`cover.jpg` tải về cùng gói), không thì vẽ
     * từ tên như bản web. Ảnh dọc không bị cắt: đặt trọn ở giữa khung vuông, nền là chính ảnh ấy phóng to và nhoè.
     */
    fun cover(title: String, bookId: String?): ByteArray {
        val file = bookId?.let { Store.file(it, "cover.jpg") }
        if (file == null || !file.isFile) return cover(title)
        return cache.getOrPut("${file.path}:${file.lastModified()}") { photo(file) ?: cover(title) }
    }

    private fun photo(file: java.io.File): ByteArray? {
        val size = 512
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.path, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= size) sample *= 2
        val source = BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return null
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        // Nền: thu ảnh về 12 điểm rồi phóng lại - nhoè đủ để làm nền mà không cần RenderScript.
        val tiny = Bitmap.createScaledBitmap(source, 12, 12, true)
        canvas.drawBitmap(tiny, null, android.graphics.Rect(0, 0, size, size), paint)
        tiny.recycle()
        val scale = minOf(size.toFloat() / source.width, size.toFloat() / source.height)
        val width = source.width * scale
        val height = source.height * scale
        val left = (size - width) / 2f
        val top = (size - height) / 2f
        canvas.drawBitmap(source, null, android.graphics.RectF(left, top, left + width, top + height), paint)
        source.recycle()
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 90, stream)
        bitmap.recycle()
        return stream.toByteArray()
    }

    fun cover(title: String): ByteArray = cache.getOrPut(title) {
        val size = 512
        val seed = hash(title)
        val (from, to, ink) = palettes[(seed % palettes.size).toInt()]
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        paint.shader = LinearGradient(0f, 0f, size * 0.6f, size.toFloat(), Color.parseColor(from), Color.parseColor(to), Shader.TileMode.CLAMP)
        canvas.drawRect(0f, 0f, size.toFloat(), size.toFloat(), paint)
        paint.shader = null
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 3f
        paint.color = Color.parseColor(ink)
        val cx = if (seed % 2L == 1L) size.toFloat() else 0f
        listOf(0.28f, 0.46f, 0.64f, 0.82f, 1.0f).forEachIndexed { index, radius ->
            paint.alpha = (255 * (0.09f + index * 0.025f)).toInt()
            canvas.drawCircle(cx, size.toFloat(), radius * size, paint)
        }
        val main = title.split(Regex("\\s*[·|:—–-]\\s*(?=(Tập|Quyển|Phần|Vol|Book)\\b)", RegexOption.IGNORE_CASE)).first()
        val text = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 58f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        val layout = StaticLayout.Builder.obtain(main, 0, main.length, text, size - 72)
            .setAlignment(Layout.Alignment.ALIGN_NORMAL).setMaxLines(4).setEllipsize(android.text.TextUtils.TruncateAt.END)
            .setLineSpacing(0f, 1.08f).build()
        canvas.save()
        canvas.translate(36f, 40f)
        layout.draw(canvas)
        canvas.restore()
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
        bitmap.recycle()
        stream.toByteArray()
    }
}
