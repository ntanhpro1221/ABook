package vn.abook.player.ui.data

import android.graphics.Bitmap
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
class CoverCacheTest {
    @get:Rule val temp = TemporaryFolder()

    @Test fun headerUsesTheDecodedCellUntilItsLargerImageArrives() = runBlocking {
        val file = temp.newFile("cover.png")
        val bitmap = Bitmap.createBitmap(400, 600, Bitmap.Config.ARGB_8888)
        bitmap.eraseColor(0xffb24932.toInt())
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        val loader = CoverLoader(4 shl 20)
        val cell = loader.load(loader.key(file.path, 1, 100, 150), file.path, 100, 150)
        assertNotNull(cell)
        assertSame(cell, loader.peek(file.path, 1))
        assertNull(loader.peek(file.path, 2))
        val header = loader.load(loader.key(file.path, 1, 200, 300), file.path, 200, 300)
        assertNotNull(header)
        assertTrue(header!!.width >= cell!!.width)
        assertSame(header, loader.peek(file.path, 1))
        assertSame(cell, loader.peek(loader.key(file.path, 1, 100, 150)))
        assertSame(header, loader.load(loader.key(file.path, 1, 150, 225), file.path, 150, 225))
    }
}
