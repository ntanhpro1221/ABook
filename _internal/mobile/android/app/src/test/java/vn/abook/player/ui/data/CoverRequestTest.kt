package vn.abook.player.ui.data

import android.graphics.Bitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class CoverRequestTest {
    @Test
    fun squarePrefetchCannotUndersizeATallerSlotWithTheSameWidth() = runBlocking {
        val file = File.createTempFile("cover-request", ".jpg")
        try {
            val source = Bitmap.createBitmap(1200, 800, Bitmap.Config.RGB_565)
            file.outputStream().use { source.compress(Bitmap.CompressFormat.JPEG, 90, it) }
            source.recycle()
            val loader = CoverLoader(4 shl 20)
            val square = loader.key(file.path, 1, 300, 300)
            val tall = loader.key(file.path, 1, 300, 450)
            assertNotEquals(square, tall)
            val preview = loader.load(square, file.path, 300, 300)!!.asAndroidBitmap()
            val cover = loader.load(tall, file.path, 300, 450)!!.asAndroidBitmap()
            assertEquals(300, preview.height)
            assertEquals(450, cover.height)
            assertTrue(cover.width >= 300)
            loader.trim()
        } finally {
            file.delete()
        }
    }
}
