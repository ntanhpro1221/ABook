package vn.abook.player

import android.os.Debug
import android.os.SystemClock
import android.util.Log
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Trình phát nhạc stream ([MusicBed] với bài http) trên thiết bị thật: đứng TẠM DỪNG ở chỗ vào (như lúc chờ cổng [StreamPace.playsThrough]) thì ExoPlayer có tải tiếp không,
 * tới đâu, và bộ nhớ của tiến trình (PSS) lúc đệm đầy. `<audio src>` của Chrome ngừng tải ở ~3,5 MB phía trước khi phần tử tạm dừng (đo 02-11); ExoPlayer mặc định
 * ngừng ở 50 s phía trước - [StreamPace.loadControl] nâng lên [StreamPace.BUFFER_MS].
 *
 * Tham số (`-e`): `url` (bài mp3 qua http, vd máy chủ bóp tốc độ trên máy tính qua 10.0.2.2), `buffer` = "stream" ([StreamPace.loadControl], mặc định) hay "default"
 * (DefaultLoadControl của media3), `seconds` (giây theo dõi, mặc định 120), `id` (tên bản ghi). Mỗi giây một dòng
 * `t=<s> buffered=<ms> duration=<ms> state=<n> loading=<0|1> pss=<KB>` ra logcat thẻ "StreamPaceE2E" và `getExternalFilesDir(null)/streampace/<id>.txt`.
 * Chạy bằng `am instrument -w -e class vn.abook.player.StreamPaceOnDeviceTest -e url ...`.
 */
@RunWith(AndroidJUnit4::class)
class StreamPaceOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val args = InstrumentationRegistry.getArguments()

    private fun <T> onMain(block: () -> T): T {
        var result: Result<T>? = null
        instrumentation.runOnMainSync { result = runCatching(block) }
        return result!!.getOrThrow()
    }

    @Test
    fun aPausedStreamKeepsLoading() {
        val url = requireNotNull(args.getString("url")) { "thiếu -e url" }
        val stream = args.getString("buffer", "stream") != "default"
        val seconds = args.getString("seconds")?.toIntOrNull() ?: 120
        val id = args.getString("id", "pace")
        val context = instrumentation.targetContext
        val lines = mutableListOf("url=$url buffer=${if (stream) "stream" else "default"}")
        Runtime.getRuntime().gc()
        lines += "before pss=${Debug.getPss()}"
        val player = onMain {
            ExoPlayer.Builder(context).setLoadControl(if (stream) StreamPace.loadControl() else DefaultLoadControl()).build().apply {
                volume = 0f
                playWhenReady = false
                setMediaItem(MediaItem.fromUri(url))
                prepare()
            }
        }
        val start = SystemClock.elapsedRealtime()
        try {
            for (second in 1..seconds) {
                SystemClock.sleep(start + second * 1000L - SystemClock.elapsedRealtime())
                val row = onMain { listOf(player.bufferedPosition, player.duration, player.playbackState.toLong(), if (player.isLoading) 1L else 0L) }
                val line = "t=$second buffered=${row[0]} duration=${row[1]} state=${row[2]} loading=${row[3]} pss=${Debug.getPss()}"
                Log.i("StreamPaceE2E", line)
                lines += line
            }
        } finally {
            onMain { player.release() }
            File(context.getExternalFilesDir(null), "streampace").apply { mkdirs() }.resolve("$id.txt").writeText(lines.joinToString("\n", postfix = "\n"))
        }
    }
}
