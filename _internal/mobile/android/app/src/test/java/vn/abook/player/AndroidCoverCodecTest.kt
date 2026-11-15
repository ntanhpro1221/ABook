package vn.abook.player

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import java.io.ByteArrayOutputStream
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class AndroidCoverCodecTest {
    private fun image(width: Int, height: Int, format: Bitmap.CompressFormat): ByteArray {
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        bitmap.eraseColor(Color.rgb(47, 103, 181))
        val out = ByteArrayOutputStream()
        bitmap.compress(format, 93, out)
        bitmap.recycle()
        return out.toByteArray()
    }

    @Test fun a_compliant_jpeg_keeps_every_byte_on_each_save() {
        for ((width, height) in listOf(64 to 64, 600 to 900, 1400 to 1400)) {
            val raw = image(width, height, Bitmap.CompressFormat.JPEG)
            val first = AndroidCoverCodec.normalize(raw)
            assertArrayEquals(raw, first.jpeg)
            assertArrayEquals(raw, AndroidCoverCodec.normalize(first.jpeg).jpeg)
            assertEquals(width, first.width)
            assertEquals(height, first.height)
        }
    }

    @Test fun oversized_jpeg_and_other_formats_are_still_normalized() {
        for (raw in listOf(image(1800, 1600, Bitmap.CompressFormat.JPEG), image(600, 900, Bitmap.CompressFormat.PNG))) {
            val normalized = AndroidCoverCodec.normalize(raw)
            assertFalse(raw.contentEquals(normalized.jpeg))
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(normalized.jpeg, 0, normalized.jpeg.size, bounds)
            assertEquals("image/jpeg", bounds.outMimeType)
            assertTrue(maxOf(bounds.outWidth, bounds.outHeight) <= Covers.MAX_SIDE)
            assertEquals(bounds.outWidth, normalized.width)
            assertEquals(bounds.outHeight, normalized.height)
        }
    }
}
