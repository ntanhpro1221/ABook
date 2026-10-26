package vn.abook.player.ui.editbook

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.ui.addbook.BookAction
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.addbook.BookProblem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import java.io.ByteArrayOutputStream

object CoverCrop {
    /** Bounds first, sampled to the phone's display width; no full-resolution photo on the UI thread. */
    suspend fun load(context: Context, uri: Uri, displayPixels: Int): Bitmap = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        require(bounds.outWidth > 0 && bounds.outHeight > 0) { "Không đọc được ảnh. Bạn hãy chọn JPEG, PNG hoặc WebP." }
        var sample = 1
        val side = displayPixels.coerceIn(360, 1600)
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > side * 2) sample *= 2
        val bitmap = resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample }) }
            ?: error("Bạn hãy chọn lại ảnh bìa.")
        val orientation = runCatching { resolver.openInputStream(uri)?.use { ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, 1) } }.getOrNull()
        val matrix = Matrix().apply {
            when (orientation) {
                2 -> setScale(-1f, 1f)
                3 -> setRotate(180f)
                4 -> setScale(1f, -1f)
                5 -> { setRotate(90f); postScale(-1f, 1f) }
                6 -> setRotate(90f)
                7 -> { setRotate(270f); postScale(-1f, 1f) }
                8 -> setRotate(270f)
            }
        }
        val oriented = if (matrix.isIdentity) bitmap else Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        if (oriented !== bitmap) bitmap.recycle()
        val ratio = side.toFloat() / maxOf(oriented.width, oriented.height)
        if (ratio >= 1f) oriented else Bitmap.createScaledBitmap(oriented, (oriented.width * ratio).toInt().coerceAtLeast(1),
            (oriented.height * ratio).toInt().coerceAtLeast(1), true).also { if (it !== oriented) oriented.recycle() }
    }

    suspend fun jpeg(bitmap: Bitmap, choice: CropChoice): ByteArray = withContext(Dispatchers.Default) {
        val rect = CropLogic.rect(bitmap.width, bitmap.height, choice)
        val crop = Bitmap.createBitmap(bitmap, rect.left, rect.top, rect.width, rect.height)
        try { ByteArrayOutputStream().use { bytes -> crop.compress(Bitmap.CompressFormat.JPEG, 92, bytes); bytes.toByteArray() } }
        finally { if (crop !== bitmap) crop.recycle() }
    }
}

@Composable
fun CoverCropRoute(editor: BookEditor, uri: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val state by editor.state.collectAsState()
    var bitmap by remember(uri) { mutableStateOf<Bitmap?>(null) }
    var problem by remember(uri) { mutableStateOf("") }
    var attempt by remember { mutableIntStateOf(0) }
    var choice by remember(uri) { mutableStateOf(CropChoice()) }
    var committing by remember { mutableStateOf(false) }
    val width = with(LocalDensity.current) { context.resources.configuration.screenWidthDp.dp.toPx().toInt() }
    LaunchedEffect(uri, attempt) {
        problem = ""
        try { bitmap = CoverCrop.load(context, Uri.parse(uri), width) }
        catch (error: Exception) { problem = error.message ?: "Bạn hãy chọn lại ảnh." }
    }
    BookForm("Cắt ảnh bìa", onBack, "cover_crop_screen", footer = {
        BookProblem(problem.ifEmpty { state.problem })
        if (bitmap != null && !committing) PrimaryButton("Dùng ảnh", {
            committing = true
            scope.launch {
                try {
                    val bytes = CoverCrop.jpeg(requireNotNull(bitmap), choice)
                    editor.setCover(bytes) { onBack() }.join()
                } catch (error: Exception) { problem = error.message.orEmpty() }
                finally { committing = false }
            }
        }, Modifier.fillMaxWidth().testTag("use_cover"))
    }) {
        val image = bitmap?.asImageBitmap()
        if (image == null) {
            BasicText(if (problem.isEmpty()) "Đang đọc ảnh" else "Chưa đọc được ảnh", style = Abook.type.bodySmall)
            if (problem.isNotEmpty()) BookAction("Thử lại", { attempt++ })
        } else {
            BasicText("Bạn kéo và chụm để chọn khung bìa.", style = Abook.type.bodySmall)
            BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                val cropWidth = minOf(maxWidth, maxHeight * 2 / 3)
                Canvas(Modifier.align(Alignment.Center).width(cropWidth).aspectRatio(2f / 3f).testTag("cover_crop_canvas")
                    .pointerInput(image) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            choice = choice.copy(zoom = (choice.zoom * zoom).coerceIn(1f, 4f),
                                x = (choice.x - pan.x / size.width * 2f).coerceIn(-1f, 1f),
                                y = (choice.y - pan.y / size.height * 2f).coerceIn(-1f, 1f))
                        }
                    }) {
                    val rect = CropLogic.rect(image.width, image.height, choice)
                    drawImage(image, srcOffset = IntOffset(rect.left, rect.top), srcSize = IntSize(rect.width, rect.height),
                        dstSize = IntSize(size.width.toInt(), size.height.toInt()))
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(Dim.s24)) {
                BookAction("Thu nhỏ", { choice = choice.copy(zoom = (choice.zoom / 1.25f).coerceAtLeast(1f)) })
                BookAction("Phóng to", { choice = choice.copy(zoom = (choice.zoom * 1.25f).coerceAtMost(4f)) })
                BookAction("Đặt lại", { choice = CropChoice() })
            }
        }
    }
}
