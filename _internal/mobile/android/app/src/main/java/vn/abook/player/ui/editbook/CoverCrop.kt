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
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.ClipOp
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import kotlin.math.roundToInt
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
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.TextAction
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

/**
 * Cắt ảnh bìa: cả ảnh hiện trong màn, khung 2:3 sẽ thành bìa nằm trên ảnh, phần bị cắt đi được phủ tối. Kéo dời khung, chụm đổi cỡ khung - không có nút phóng / thu
 * (trợ năng có hai thao tác "Phóng to" / "Thu nhỏ" trên chính vùng ảnh). "Đặt lại" ở đầu màn, "Dùng ảnh" ghim ở đáy.
 */
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
    val image = bitmap?.asImageBitmap()
    BookForm("Cắt ảnh bìa", onBack, "cover_crop_screen", footer = {
        InlineProblem(problem.ifEmpty { state.problem }, if (bitmap == null) ({ attempt++ }) else null, "crop_problem")
        PrimaryButton(if (committing) "Đang lưu" else "Dùng ảnh", {
            val shown = bitmap ?: return@PrimaryButton
            committing = true
            scope.launch {
                try {
                    val bytes = CoverCrop.jpeg(shown, choice)
                    editor.setCover(bytes) { onBack() }.join()
                } catch (error: Exception) { problem = error.message.orEmpty() }
                finally { committing = false }
            }
        }, Modifier.fillMaxWidth().testTag("use_cover"), enabled = image != null && !committing)
    }, trailing = {
        if (image != null) TextAction("Đặt lại", { choice = CropChoice() }, "crop_reset")
    }) {
        if (image == null) {
            if (problem.isEmpty()) Caption("Đang đọc ảnh", Modifier.padding(top = Dim.s16))
        } else CropArea(image, choice) { choice = it }
    }
}

/** Vùng ảnh: ảnh vừa khung màn, khung cắt (viền hổ phách) trên ảnh, phần ngoài khung phủ tối. */
@Composable
private fun CropArea(image: ImageBitmap, choice: CropChoice, onChoice: (CropChoice) -> Unit) {
    val colors = Abook.colors
    val scrim = if (colors.dark) Color.Black.copy(alpha = 0.6f) else Color(0xFF1A1814).copy(alpha = 0.55f)
    val current by rememberUpdatedState(choice)
    BoxWithConstraints(Modifier.fillMaxSize().padding(vertical = Dim.s16)) {
        val scale = minOf(constraints.maxWidth.toFloat() / image.width, constraints.maxHeight.toFloat() / image.height)
        val shownWidth = with(LocalDensity.current) { (image.width * scale).toDp() }
        val shownHeight = with(LocalDensity.current) { (image.height * scale).toDp() }
        Canvas(
            Modifier.align(Alignment.Center).size(shownWidth, shownHeight).testTag("cover_crop_canvas")
                .pointerInput(image) {
                    detectTransformGestures { _, pan, zoom, _ ->
                        onChoice(CropLogic.transform(image.width, image.height, current, pan.x / scale, pan.y / scale, zoom))
                    }
                }
                .semantics {
                    customActions = listOf(
                        CustomAccessibilityAction("Phóng to") { onChoice(CropLogic.transform(image.width, image.height, current, 0f, 0f, ZoomStep)); true },
                        CustomAccessibilityAction("Thu nhỏ") { onChoice(CropLogic.transform(image.width, image.height, current, 0f, 0f, 1f / ZoomStep)); true },
                    )
                },
        ) {
            drawImage(image, dstSize = IntSize(size.width.roundToInt(), size.height.roundToInt()))
            val rect = CropLogic.rect(image.width, image.height, choice)
            val topLeft = Offset(rect.left * scale, rect.top * scale)
            val window = Size(rect.width * scale, rect.height * scale)
            clipPath(Path().apply { addRect(Rect(topLeft, window)) }, ClipOp.Difference) { drawRect(scrim) }
            drawRect(colors.accent, topLeft, window, style = Stroke(2.dp.toPx()))
        }
    }
}

/** Mỗi lần "Phóng to" / "Thu nhỏ" của trợ năng đổi cỡ khung chừng này. */
private const val ZoomStep = 1.25f
