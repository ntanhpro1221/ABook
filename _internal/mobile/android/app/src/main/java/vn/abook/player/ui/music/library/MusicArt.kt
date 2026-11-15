package vn.abook.player.ui.music.library
import vn.abook.player.ui.components.visualImage

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import vn.abook.player.MusicArtwork
import vn.abook.player.MusicLibrary
import vn.abook.player.DeviceMusic
import org.json.JSONObject
import vn.abook.player.ui.theme.Abook
import java.io.File
import java.net.HttpURLConnection
import java.net.URI
import java.security.MessageDigest

/** Only composed covers load. Decode and disk/network I/O stay off main. */
@Composable
fun MusicArt(track: MusicLibrary.Track, modifier: Modifier = Modifier) {
    val context = LocalContext.current.applicationContext
    val seed = remember(track.link, track.info) { MusicArtwork.seed(track.link, track.info) }
    val art = track.info.optJSONObject("art")
    val sha = art?.optString("sha1") ?: ""
    val key = "${track.link}|$seed|$sha"
    val image by produceState<Pair<String, Bitmap>?>(null, key) {
        value = key to withContext(Dispatchers.Default) { ArtImages.generated(seed) }
        val url = art?.optString("url") ?: ""
        if (url.isNotEmpty()) {
            val real = withContext(Dispatchers.IO) { runCatching { ArtImages.real(File(context.cacheDir, "music-art"), url, sha) }.getOrNull() }
            if (real != null) value = key to real
        }
    }
    Box(modifier.size(40.dp).clip(RoundedCornerShape(vn.abook.player.ui.theme.Dim.radiusCover)).background(Abook.colors.text3).testTag("music_art")) {
        image?.takeIf { it.first == key }?.second?.let { bitmap ->
            Image(bitmap.asImageBitmap(), contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.matchParentSize().visualImage().testTag("music_art_image"))
        }
    }
}

@Composable
fun PlayingMusicArt(link: String) {
    val app = LocalContext.current.applicationContext
    val info by produceState<JSONObject?>(null, link) {
        if (!link.startsWith("local:") && link.isNotEmpty()) {
            value = withContext(Dispatchers.IO) { runCatching { DeviceMusic.catalog(app).lookup(listOf(link))[link] }.getOrNull() }
        }
    }
    val track = remember(link, info) { MusicLibrary.Track(link, info ?: JSONObject()) }
    MusicArt(track, Modifier.size(32.dp))
}

internal object ArtImages {
    private val generated = LruCache<Int, Bitmap>(96)
    private val real = LruCache<String, Bitmap>(12)
    private val gate = Semaphore(3)
    fun ready(seed: Int, sha: String = ""): Boolean = if (sha.isEmpty()) generated.get(seed) != null else real.get(sha) != null
    fun generated(seed: Int): Bitmap = synchronized(generated) {
        generated.get(seed) ?: run {
            val rgb = MusicArtwork.rgb(seed)
            val colors = IntArray(96*96) { at ->
                (255 shl 24) or ((rgb[at*3].toInt() and 255) shl 16) or ((rgb[at*3+1].toInt() and 255) shl 8) or (rgb[at*3+2].toInt() and 255)
            }
            Bitmap.createBitmap(colors, 96, 96, Bitmap.Config.ARGB_8888).also { generated.put(seed, it) }
        }
    }
    suspend fun real(folder: File, url: String, sha: String): Bitmap? = gate.withPermit {
        if (!sha.matches(Regex("[0-9a-f]{40}")) || URI(url).scheme != "https") return@withPermit null
        real.get(sha)?.let { return@withPermit it }
        fun verified(raw: ByteArray): Boolean = raw.size <= 512*1024 && MessageDigest.getInstance("SHA-1").digest(raw).joinToString("") { "%02x".format(it) } == sha
        fun decode(raw: ByteArray): Bitmap? {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(raw, 0, raw.size, bounds)
            if (bounds.outWidth !in 1..512 || bounds.outHeight !in 1..512) return null
            return BitmapFactory.decodeByteArray(raw, 0, raw.size)
        }
        val file = File(folder, "$sha.jpg")
        val held = if (file.isFile && file.length() <= 512*1024) file.readBytes() else null
        if (held != null && verified(held)) decode(held)?.let { real.put(sha, it); return@withPermit it }
        val connection = URI(url).toURL().openConnection() as HttpURLConnection
        connection.connectTimeout = 6000; connection.readTimeout = 6000
        connection.instanceFollowRedirects = false
        val raw = try {
            if (connection.responseCode != 200) return@withPermit null
            connection.inputStream.use { input ->
                val bytes = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (bytes.size() <= 512*1024) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    bytes.write(buffer, 0, count)
                }
                bytes.toByteArray()
            }
        } finally { connection.disconnect() }
        if (!verified(raw)) return@withPermit null
        val bitmap = decode(raw) ?: return@withPermit null
        folder.mkdirs()
        val temporary = File.createTempFile("art-", ".part", folder)
        try {
            temporary.outputStream().use { it.write(raw); it.fd.sync() }
            temporary.renameTo(file)
        } finally { temporary.delete() }
        real.put(sha, bitmap)
        bitmap
    }
}
