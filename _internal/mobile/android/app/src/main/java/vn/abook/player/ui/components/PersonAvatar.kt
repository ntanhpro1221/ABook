package vn.abook.player.ui.components

import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.ui.data.AvatarArt
import vn.abook.player.ui.data.AvatarRef
import vn.abook.player.ui.theme.Abook

private object PortraitCache {
    val images = object : LruCache<String, ImageBitmap>(4 * 1024 * 1024) {
        override fun sizeOf(key: String, value: ImageBitmap): Int = value.width * value.height * 4
    }
}

/** Lazy composition plus background decoding; no image library or model is bundled. */
@Composable
fun PersonAvatar(name: String, avatar: AvatarRef? = null, size: Dp = 40.dp, voice: Boolean = false,
                 load: (suspend () -> ByteArray?)? = null) {
    val context = LocalContext.current
    val fallback = remember(name, avatar) { if (avatar?.kind == "pattern") avatar else AvatarArt.pattern(avatar?.key?.ifEmpty { name } ?: name) }
    val file = if (voice) AvatarArt.voiceFile(name) else avatar?.file.orEmpty()
    val key = if (voice) "voice:$file" else file
    var image by remember(key) { mutableStateOf(PortraitCache.images.get(key)) }
    LaunchedEffect(key) {
        if (key.isEmpty() || image != null) return@LaunchedEffect
        image = withContext(Dispatchers.IO) {
            runCatching {
                val bytes = if (voice && file.matches(Regex("voice-[0-9a-f]{8}\\.webp"))) context.assets.open("voice_avatars/$file").use { it.readBytes() }
                    else if (AvatarArt.imageFile(file)) load?.invoke() else null
                if (bytes == null || bytes.size > 4 * 1024 * 1024) null
                else BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()?.also { PortraitCache.images.put(key, it) }
            }.getOrNull()
        }
    }
    val color = remember(fallback.color) { runCatching { Color(android.graphics.Color.parseColor(fallback.color)) }.getOrDefault(Color(0xff805c38)) }
    Box(Modifier.size(size).clip(CircleShape).background(color), contentAlignment = Alignment.Center) {
        Canvas(Modifier.matchParentSize()) {
            for (y in 0..4) for (x in 0..4) if (AvatarArt.cell(fallback.bits, x, y)) {
                drawRect(Color.White.copy(alpha = 0.1f), Offset(x * this.size.width / 5, y * this.size.height / 5), Size(this.size.width / 5, this.size.height / 5))
            }
        }
        BasicText(fallback.initials, style = Abook.type.label.copy(color = Color.White, fontSize = (size.value * 0.30f).sp, fontWeight = FontWeight.Bold))
        image?.let { Image(it, contentDescription = null, modifier = Modifier.matchParentSize(), contentScale = ContentScale.Crop) }
    }
}
