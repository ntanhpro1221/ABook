package vn.abook.player

import android.os.SystemClock
import androidx.media3.exoplayer.ExoPlayer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.Locale

/**
 * Nhạc nền nghe thẳng từ máy tính ĐẦU-CUỐI: sách giả có mốc nhạc mà bài không nằm trên máy, máy tính chính giả (`sync` prefs: địa chỉ, vân tay TLS, mã)
 * trỏ tới máy chủ bóp tốc độ trên máy tính chủ (10.0.2.2) - nên URI bài, ghim TLS, bộ đệm đĩa, ExoPlayer stream và cổng [StreamPace] đều là mã thật.
 * Giọng giả: [MusicBed.sync] mỗi 500 ms với giây trôi theo đồng hồ thật. Mỗi 100 ms đọc mọi trình phát nhạc (bài hiện tại + bài đang mờ) bằng phản chiếu
 * (chỉ đọc), nên cùng một APK test chạy được trên APK app của các bản cũ (so gốc / chờ-trọn / cổng mới).
 *
 * Tham số (`-e`): `id` (tên bản ghi, cũng là mã sách - phải khác nhau mỗi lượt để bộ đệm đĩa không giữ bài lượt trước), `host` (mặc định 10.0.2.2:8766),
 * `fingerprint` (SHA-256 hex của chứng chỉ máy chủ), `cues` (`đầu:cuối:sha1,...` - giây và tên bài trong pool của máy chủ), `seconds` (giây giọng, mặc định 250).
 * Ra `getExternalFilesDir(null)/musicstream/<id>.txt`: mỗi lần đọc một dòng `t=<giây> v=<giây giọng>` rồi mỗi trình phát
 * ` | <mã> <bài 6 ký tự> vol=<logic> state=<n> pwr=<0|1> play=<0|1> pos=<ms> buf=<ms> dur=<ms>`.
 */
@RunWith(AndroidJUnit4::class)
class MusicStreamOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val args = InstrumentationRegistry.getArguments()

    private fun <T> onMain(block: () -> T): T {
        var result: Result<T>? = null
        instrumentation.runOnMainSync { result = runCatching(block) }
        return result!!.getOrThrow()
    }

    private val bedClass = Class.forName("vn.abook.player.MusicBed\$Bed")
    private fun field(owner: Class<*>, name: String) = owner.getDeclaredField(name).apply { isAccessible = true }
    private val currentField = field(MusicBed::class.java, "current")
    private val fadingField = field(MusicBed::class.java, "fading")
    private val playerField = field(bedClass, "player")
    private val volumeField = field(bedClass, "volume")
    private val trackField = field(bedClass, "track")

    private fun beds(): List<Any> {
        val current = currentField.get(MusicBed)
        val fading = (fadingField.get(MusicBed) as List<*>).filterNotNull()
        return listOfNotNull(current) + fading
    }

    private fun describe(bed: Any): String {
        val player = playerField.get(bed) as ExoPlayer
        val track = (trackField.get(bed) as String).substringAfterLast('/').take(6)
        return String.format(
            Locale.ROOT, " | %08x %s vol=%.3f state=%d pwr=%d play=%d pos=%d buf=%d dur=%d", System.identityHashCode(bed), track, volumeField.getFloat(bed),
            player.playbackState, if (player.playWhenReady) 1 else 0, if (player.isPlaying) 1 else 0, player.currentPosition, player.bufferedPosition, player.duration,
        )
    }

    @Test
    fun musicStreamsFromTheComputer() {
        val id = requireNotNull(args.getString("id")) { "thiếu -e id" }
        val host = args.getString("host", "10.0.2.2:8766")
        val fingerprint = requireNotNull(args.getString("fingerprint")) { "thiếu -e fingerprint" }
        val cues = requireNotNull(args.getString("cues")) { "thiếu -e cues" }.split(',').map { it.split(':') }
        val seconds = args.getString("seconds")?.toDoubleOrNull() ?: 250.0
        val bookId = id
        val lines = mutableListOf("id=$id host=$host cues=$cues")
        val out = File(context.getExternalFilesDir(null), "musicstream").apply { mkdirs() }.resolve("$id.txt")
        try {
            onMain {
                Store.init(context)
                MusicBed.init(context)
            }
            val port = host.substringAfterLast(':').toInt()
            check(
                SyncLink.prefs(context).edit().clear()
                    .putString("host", host.substringBeforeLast(':')).putInt("port", port).putString("fingerprint", fingerprint).putString("token", "e2e")
                    .putString("addresses", JSONArray().put(JSONObject().put("address", host).put("lastSuccess", 0)).toString()).putString("name", "máy tính thử").commit(),
            )
            val tracks = JSONObject()
            val chapterCues = JSONArray()
            for (cue in cues) {
                val track = "music/${cue[2]}.mp3"
                tracks.put(track, JSONObject())
                chapterCues.put(JSONObject().put("start", cue[0].toDouble()).put("end", cue[1].toDouble()).put("track", track))
            }
            val music = JSONObject().put("levelDb", -6.0).put("tracks", tracks).put("chapters", JSONObject().put("0", chapterCues))
            val manifest = JSONObject().put("format", "abook").put("version", 1).put("title", "Music stream e2e")
                .put("chapters", JSONArray().put(JSONObject().put("id", 0).put("title", "c0").put("file", "c0.mp3"))).put("music", music)
            val bookDir = Store.bookDir(bookId).apply { mkdirs() }
            File(bookDir, "book.json").writeBytes(manifest.toString().toByteArray(Charsets.UTF_8))

            val start = SystemClock.elapsedRealtime()
            var nextSync = start
            var nextSample = start
            while (true) {
                val now = SystemClock.elapsedRealtime()
                val voice = (now - start) / 1000.0
                if (voice > seconds) break
                if (now >= nextSync) {
                    onMain { MusicBed.sync(bookId, 0, voice, true) }
                    nextSync += 500
                }
                if (now >= nextSample) {
                    val row = onMain { beds().joinToString("") { describe(it) } }
                    lines += String.format(Locale.ROOT, "t=%.2f v=%.2f", (SystemClock.elapsedRealtime() - start) / 1000.0, voice) + row
                    nextSample += 100
                }
                SystemClock.sleep(maxOf(1L, minOf(nextSync, nextSample) - SystemClock.elapsedRealtime()))
            }
        } finally {
            runCatching { onMain { MusicBed.release() } }
            out.writeText(lines.joinToString("\n", postfix = "\n"))
            runCatching { Store.deleteBook(bookId) }
        }
    }
}
