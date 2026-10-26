package vn.abook.player.ui.export

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import vn.abook.player.ui.data.CoverArt
import java.io.ByteArrayOutputStream

/**
 * Bìa tự vẽ cho file xuất của sách không có ảnh bìa thật: cùng cặp màu với ô bìa trong Thư viện ([CoverArt.style], cùng tên - cùng bìa), tên sách xuống dòng ở giữa
 * (chữ nhỏ dần cho vừa, không bao giờ cắt). PNG vuông, nhúng vào file MP3 / M4B như bìa thật.
 */
object DrawnCover {
    fun png(title: String, size: Int = 600): ByteArray {
        val style = CoverArt.style(title)
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val ground = Paint(Paint.ANTI_ALIAS_FLAG).apply { shader = LinearGradient(0f, 0f, size.toFloat(), size.toFloat(), style.from, style.to, Shader.TileMode.CLAMP) }
        canvas.drawRect(0f, 0f, size.toFloat(), size.toFloat(), ground)
        val (main, sub) = CoverArt.splitTitle(title)
        val text = (main + if (sub.isNotEmpty()) "\n$sub" else "").ifEmpty { title }
        val ink = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = style.ink; typeface = Typeface.DEFAULT_BOLD }
        val width = (size * 0.78f).toInt()
        var layout: StaticLayout
        var scale = 0.10f
        while (true) {
            ink.textSize = size * scale
            layout = StaticLayout.Builder.obtain(text, 0, text.length, ink, width).setAlignment(Layout.Alignment.ALIGN_CENTER).build()
            if (layout.height <= size * 0.7f || scale <= 0.03f) break
            scale -= 0.005f
        }
        canvas.save()
        canvas.translate((size - width) / 2f, (size - layout.height) / 2f)
        layout.draw(canvas)
        canvas.restore()
        return ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray().also { bitmap.recycle() }
    }
}
