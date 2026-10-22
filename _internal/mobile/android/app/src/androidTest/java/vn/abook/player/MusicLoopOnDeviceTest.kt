package vn.abook.player

import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Bộ đo vào bản lặp của nhạc nền trên máy THẬT (PLAN_loop §36; Corpus/research/music/loopreal/loopphone.py gọi): một cuốn giả có MỘT mốc phủ cả bài với điểm
 * vòng cho trước, đồng hồ giọng giả đồng bộ [MusicBed.sync] mỗi 500 ms như Playback (pha nhịp tự do, không canh theo hạn); [MusicBed.debugLoopProbe] ghi mọi sự kiện
 * và vị trí hai bản (cũ / mới) mỗi 20 ms vào `getExternalFilesDir(null)/loopprobe/<id>.txt`. Chạy tới 4,5 giây sau khi bản lặp có tiếng rồi dừng nhạc (bản cũ không bị dừng sớm hơn: test chỉ gọi stop() ở cuối).
 *
 * Tham số (`am instrument -e ...`): `id`, `file` (mặc định `.../loopprobe/track.mp3`), `seconds` (độ dài bài), `audibleStart`, `audibleEnd`, `loopStart`, `loopEnd`,
 * `inject` (giây, mặc định 0: cố ý đẩy bản mới lệch pha để kiểm bước 3),
 * `settle` (mặc định true; false: bỏ bước 3 sửa pha - [MusicBed.debugLoopSettle]). Luồng nhạc của máy đang bằng 0 thì chạy im: test không đổi âm lượng hay cài đặt nào.
 */
@RunWith(AndroidJUnit4::class)
class MusicLoopOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val args = InstrumentationRegistry.getArguments()

    private fun number(name: String): Double? = args.getString(name)?.toDoubleOrNull()?.takeIf { it.isFinite() }

    @Test
    fun loopHandoffOnTheRealPlayer() {
        val dir = File(context.getExternalFilesDir(null), "loopprobe").apply { mkdirs() }
        val id = args.getString("id") ?: "manual"
        val file = args.getString("file")?.let(::File) ?: File(dir, "track.mp3")
        assertTrue("không có file nhạc ${file.path}", file.isFile)
        val seconds = number("seconds")
        val audibleStart = number("audibleStart") ?: 0.0
        val audibleEnd = number("audibleEnd") ?: seconds ?: error("thiếu audibleEnd hoặc seconds")
        val loopStart = number("loopStart")
        val loopEnd = number("loopEnd")
        val inject = number("inject") ?: 0.0
        val settle = args.getString("settle")?.lowercase()?.let { it != "false" && it != "0" } ?: true
        instrumentation.runOnMainSync { MusicBed.init(context) } // nạp hằng số trộn (MusicCues.mix)
        val fade = MusicCues.mix.loopCrossfadeSeconds
        // Bài vào ở loopEnd - X - 6: bản tạo sẵn (3 giây trước hạn) và hạn vào bản lặp đều rơi vào đoạn chạy, còn dư thời gian cho tải bài.
        val start = ((loopEnd ?: audibleEnd) - fade - 6 - audibleStart).coerceAtLeast(0.0)

        val track = "music/" + "0".repeat(40) + ".mp3"
        val cue = JSONObject().put("start", 0.0).put("end", start + 100_000.0).put("track", track).put("gainDb", -20.0)
            .put("audibleStart", audibleStart).put("audibleEnd", audibleEnd)
        if (loopStart != null) cue.put("loopStart", loopStart)
        if (loopEnd != null) cue.put("loopEnd", loopEnd)
        val music = JSONObject().put("levelDb", -20.0).put("tracks", JSONObject().put(track, JSONObject()))
            .put("chapters", JSONObject().put("1", JSONArray().put(cue)))

        val lines = mutableListOf("JOB $id " + args.keySet().filter { it != "id" && it != "class" && it != "file" }.sorted().joinToString(" ") { "$it=${args.getString(it)}" })
        val main = Handler(Looper.getMainLooper())
        val finished = CountDownLatch(1)
        var done = false
        val began = SystemClock.elapsedRealtimeNanos()
        val clock = object : Runnable {
            override fun run() {
                if (done) return
                MusicBed.sync(MusicBed.DEBUG_BOOK, 1, start + (SystemClock.elapsedRealtimeNanos() - began) / 1e9, true)
                main.postDelayed(this, 500)
            }
        }
        try {
            instrumentation.runOnMainSync {
                MusicBed.debugMusic = music
                MusicBed.debugTrack = Uri.fromFile(file)
                MusicBed.debugLoopInject = inject
                MusicBed.debugLoopSettle = settle
                MusicBed.debugLoopProbe = { line ->
                    lines += line
                    if (line.split(' ').getOrNull(2) == "playing") main.postDelayed({
                        done = true
                        MusicBed.stop()
                        finished.countDown()
                    }, 4500)
                }
                main.post(clock)
            }
            assertTrue("bản lặp không có tiếng trong 90 giây (bài thiếu vòng lặp mờ chéo?)", finished.await(90, TimeUnit.SECONDS))
        } finally {
            instrumentation.runOnMainSync {
                done = true
                MusicBed.debugLoopProbe = null
                MusicBed.debugLoopInject = 0.0
                MusicBed.debugLoopSettle = true
                MusicBed.debugMusic = null
                MusicBed.debugTrack = null
                MusicBed.stop()
            }
            File(dir, "$id.txt").writeBytes((lines.joinToString("\n") + "\n").toByteArray(Charsets.UTF_8))
        }
    }
}
