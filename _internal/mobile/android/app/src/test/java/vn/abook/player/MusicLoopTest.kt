package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import kotlin.math.abs
import org.junit.After
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import java.io.File

/**
 * Điểm vòng của bài có đoạn kết (Corpus/research/music/PLAN_loop.md §10) trên điện thoại: [MusicCues.loopBounds], [MusicCues.loopPosition],
 * [MusicCues.loopSchedule] ra cùng số với Python (`music_mix`, nguồn sự thật) và máy tính (musicBed.test.ts) trên đúng các fixture
 * `tests/fixtures/music_loop` (scripts/music_loop_fixtures.py), lệch <= 1 ms. Bài không có điểm vòng (hay không hợp lệ): trùng từng số với 0.4.89.
 */
class MusicLoopTest {
    private val mixFile = File("../../../abook/webui/assets/music_mix.json")
    private val fixtures = File("../../../tests/fixtures/music_loop")
    private val ms = 1e-3

    @Before
    fun loadMix() {
        MusicCues.mix = MusicMix.parse(mixFile.readText())
    }

    private fun number(json: JSONObject, key: String): Double? = if (json.has(key) && !json.isNull(key)) json.getDouble(key) else null

    private fun doubles(array: JSONArray): List<Double> = List(array.length()) { array.getDouble(it) }

    private fun cue(track: JSONObject): MusicCues.Cue = MusicCues.Cue(
        0.0, 0.0, "", null, audibleStart = number(track, "audibleStart"), audibleEnd = number(track, "audibleEnd"),
        loopStart = number(track, "loopStart"), loopEnd = number(track, "loopEnd"),
    )

    private fun near(label: String, want: List<Double>, got: List<Double>) {
        assertEquals("$label: số phần tử", want.size, got.size)
        want.indices.forEach { assertEquals("$label #$it", want[it], got[it], ms) }
    }

    @Test
    fun every_loop_fixture_matches_the_python_reference() {
        val names = fixtures.listFiles { file -> file.extension == "json" }!!.map { it.nameWithoutExtension }.sorted()
        assertEquals(listOf("invalid_points", "with_points", "without_points"), names)
        for (name in names) {
            val case = JSONObject(File(fixtures, "$name.json").readText())
            val track = case.getJSONObject("track")
            val bounds = MusicCues.loopBounds(cue(track), track.getDouble("seconds"))
            val want = case.getJSONObject("bounds")
            assertEquals(name, MusicCues.Loop(want.getDouble("start"), want.getDouble("end"), want.getDouble("period"), want.getBoolean("crossfade"),
                want.getDouble("loopStart"), want.getDouble("loopEnd")), bounds)
            case.optJSONArray("invalidVariants")?.let { variants ->
                val plain = MusicCues.loopBounds(cue(track).copy(loopStart = null, loopEnd = null), track.getDouble("seconds"))
                for (index in 0 until variants.length()) {
                    val variant = variants.getJSONObject(index)
                    val odd = cue(track).copy(loopStart = number(variant, "loopStart"), loopEnd = number(variant, "loopEnd"))
                    assertEquals("$name: $variant như không có điểm vòng", plain, MusicCues.loopBounds(odd, track.getDouble("seconds")))
                }
            }
            val ts = doubles(case.getJSONArray("ts"))
            val positions = ts.map { MusicCues.loopPosition(bounds, it) }
            near("$name: vị trí", doubles(case.getJSONArray("positions")), positions)
            val cues = case.getJSONArray("cues")
            for (index in 0 until cues.length()) {
                val item = cues.getJSONObject(index)
                val length = item.getDouble("seconds")
                near("$name $length: mở phần tử", doubles(item.getJSONArray("opens")), MusicCues.loopSchedule(bounds, length).opens)
                val tail = MusicCues.loopSchedule(bounds, length, tail = true)
                near("$name $length tail: mở phần tử", doubles(item.getJSONObject("tail").getJSONArray("opens")), tail.opens)
                assertEquals("$name $length: hết vòng cuối", item.getJSONObject("tail").getDouble("seconds"), tail.end, ms)
            }
            case.optJSONObject("legacy")?.let { legacy ->
                assertEquals("$name: vị trí trùng từng số với 0.4.89", doubles(legacy.getJSONArray("positions")), positions)
                val old = legacy.getJSONArray("cues")
                for (index in 0 until old.length()) {
                    val item = old.getJSONObject(index)
                    val length = item.getDouble("seconds")
                    near("$name $length: như 0.4.89", doubles(item.getJSONArray("opens")), MusicCues.loopSchedule(bounds, length).opens)
                    val tail = MusicCues.loopSchedule(bounds, length, tail = true)
                    near("$name $length tail: như 0.4.89", doubles(item.getJSONObject("tail").getJSONArray("opens")), tail.opens)
                    assertEquals(item.getJSONObject("tail").getDouble("seconds"), tail.end, ms)
                }
            }
        }
    }

    @Test
    fun the_loop_element_opens_at_loop_end_less_x_from_loop_start() {
        val track = JSONObject(File(fixtures, "with_points.json").readText()).getJSONObject("track")
        val cue = cue(track).copy(start = 100.0, end = 700.0)
        val bounds = MusicCues.loopBounds(cue, track.getDouble("seconds"))
        val x = MusicCues.mix.loopCrossfadeSeconds
        assertTrue("tới loopEnd - X thì mở", MusicCues.loopDue(bounds, bounds.loopEnd - x))
        assertTrue("chưa tới thì chưa", !MusicCues.loopDue(bounds, bounds.loopEnd - x - 0.05))
        assertEquals("tua vòng đầu: A + t", 1.5 + 100.0, MusicCues.alignedPosition(cue, 200.0, bounds), 1e-9)
        assertEquals("tua vòng sau", 12.5 + (200.0 - 11.0) % 146.25, MusicCues.alignedPosition(cue, 300.0, bounds), 1e-9)
        assertEquals((12.5 * 1000).toLong(), MusicCues.offsetMs(cue, 100.0 + 157.25, 200_000))
    }

    @Test
    fun the_loop_points_come_from_the_book_package_and_the_catalog() {
        val name = "music/" + "a".repeat(40) + ".mp3"
        val music = JSONObject("""{"tracks": {"$name": {"file": "$name"}}, "chapters": {"1": [
            {"start": 0, "end": 300, "track": "$name", "gainDb": -9, "audibleStart": 1.5, "audibleEnd": 190.25, "loopStart": 12.5, "loopEnd": 160.75},
            {"start": 300, "end": 400, "track": "$name", "gainDb": -9}]}}""")
        val (fresh, old) = MusicCues.of(music, 1)
        assertEquals(12.5, fresh.loopStart!!, 0.0)
        assertEquals(160.75, fresh.loopEnd!!, 0.0)
        assertEquals(null, old.loopStart)
        val track = SceneTrack.of(JSONObject("""{"link": "https://x/a.mp3", "valence": 0.1, "arousal": 0.2, "loopStart": 12.5, "loopEnd": 160.75}"""))!!
        assertEquals(12.5 to 160.75, track.loopStart to track.loopEnd)
    }

    // ---- bù trễ khi vào bản lặp (PLAN_loop §29-32): cùng ca số với musicBed.test.ts ---------------------------------------------------------

    private val handoffBounds: MusicCues.Loop get() = MusicCues.loopBounds(
        MusicCues.Cue(0.0, 600.0, "", null, audibleStart = 2.0, audibleEnd = 110.0, loopStart = 12.0, loopEnd = 100.0), 120.0,
    )

    @Test
    fun handoff_hand_computed_cases() {
        val b = handoffBounds
        assertEquals(12.0, b.loopStart, 0.0)
        assertEquals(100.0, b.loopEnd, 0.0)
        assertEquals(2.0, MusicCues.mix.loopCrossfadeSeconds, 0.0)
        assertEquals(12.0, MusicCues.loopStartAt(b, 98.0), 1e-9)
        assertEquals(12.25, MusicCues.loopStartAt(b, 98.25), 1e-9)
        assertEquals(12.5, MusicCues.loopStartAt(b, 98.5), 1e-9)
        assertEquals("chưa tới hạn: không lùi dưới loopStart", 12.0, MusicCues.loopStartAt(b, 97.9), 1e-9)
        assertEquals(0.2, MusicCues.loopHandoffDelay(b, 97.8, 0.25)!!, 1e-9)
        assertNull(MusicCues.loopHandoffDelay(b, 97.0, 0.25))
        assertEquals(0.0, MusicCues.loopHandoffDelay(b, 98.1, 0.25)!!, 0.0)
        assertEquals("đúng hạn", 0.0, MusicCues.loopHandoffDelay(b, 98.0, 0.25)!!, 0.0)
        assertNull("nhịp 0,5: hẹn từ 0,75 s trước hạn", MusicCues.loopHandoffDelay(b, 97.0, 0.5))
        assertEquals(0.6, MusicCues.loopHandoffDelay(b, 97.4, 0.5)!!, 1e-9)
        assertEquals(0.15, MusicCues.loopDrift(b, 98.6, 12.45), 1e-9)
        assertEquals("bản mới đi trước: âm", -0.2, MusicCues.loopDrift(b, 98.1, 12.3), 1e-9)
        val short = MusicCues.loopBounds(MusicCues.Cue(0.0, 600.0, "", null, audibleStart = 0.2, audibleEnd = 4.9), 5.0)
        assertNull("bài quá ngắn để mờ chéo không bao giờ hẹn", MusicCues.loopHandoffDelay(short, 4.0, 0.25))
    }

    @Test
    fun settle_moves_a_nearly_silent_new_element_only_once_it_matters() {
        val b = handoffBounds
        assertEquals(12.12, MusicCues.loopSettle(b, 98.12, 12.0, 0f, 0.1f, true)!!, 1e-9)
        assertNull("lệch dưới 0,02 s thì để yên", MusicCues.loopSettle(b, 98.01, 12.0, 0f, 0.1f, true))
        assertNull("bản mới đã to: cú dời nghe thấy", MusicCues.loopSettle(b, 98.12, 12.0, 0.05f, 0.1f, true))
        assertNull("bài cũ đã dừng hay không còn mờ", MusicCues.loopSettle(b, 98.12, 12.0, 0f, 0.1f, false))
    }

    /** Đồng hồ ảo của Handler giả (SystemClock.elapsedRealtime): một "trình phát" chạy 1x từ `since` (ms), đứng yên trước đó. */
    private class Voice(var anchor: Double, var since: Long) {
        fun position(): Double = anchor + maxOf(0L, SystemClock.elapsedRealtime() - since) / 1000.0
        fun seekTo(seconds: Double) { anchor = seconds; since = SystemClock.elapsedRealtime() }
    }

    private class Rig(val b: MusicCues.Loop, latencyMs: Long) {
        val main = Handler(Looper.getMainLooper())
        val old = Voice(0.0, 0)
        var sounding = old // bài đang kêu (MusicBed.current): vào bản lặp thì là bản mới
        val opened = mutableListOf<Pair<Long, Voice>>()
        var created = 0 // trình phát giả đã tạo (tạo sẵn + mở mới)
        val discarded = mutableListOf<Voice>() // bản tạo sẵn đã nhả
        private fun make(at: Double): Voice = Voice(at, Long.MAX_VALUE / 2).also { created++ } // chưa phát: đứng yên
        val handoff = LoopHandoff<Voice>(
            main,
            { LoopHandoff.Snapshot(sounding, b, sounding.position(), true) },
            { make(b.loopStart) },
            { discarded += it },
        ) { snap, ready ->
            val voice = ready ?: make(0.0)
            val target = MusicCues.loopStartAt(b, snap.position)
            if (ready == null || kotlin.math.abs(ready.anchor - target) > 0.0005) voice.anchor = target
            voice.since = SystemClock.elapsedRealtime() + latencyMs // play(): có tiếng sau độ trễ mở trình phát
            opened += SystemClock.elapsedRealtime() to voice
            sounding = voice
            // sự kiện "đang phát" tới sau độ trễ mở trình phát; bản mới còn câm (âm lượng 0)
            main.postDelayed({
                MusicCues.loopSettle(b, old.position(), voice.position(), 0f, 0.1f, true)?.let(voice::seekTo)
            }, latencyMs)
        }
        fun everySync(phaseMs: Long, tickMs: Long) {
            val sync = object : Runnable {
                override fun run() {
                    handoff.check()
                    main.postDelayed(this, tickMs)
                }
            }
            main.postDelayed(sync, phaseMs)
        }
    }

    @After
    fun resetClock() = Handler.reset()

    @Test
    fun handoff_opens_at_the_deadline_and_lines_up_the_phase_for_every_sync_phase_and_player_latency() {
        for (latency in listOf(0L, 120L)) {
            for (phase in listOf(0L, 100L, 250L, 400L, 499L)) {
                Handler.reset()
                        val rig = Rig(handoffBounds, latency)
                val lead = 1600L // còn 1,6 s tới hạn loopEnd - X = 98
                rig.old.anchor = 98.0 - lead / 1000.0
                rig.old.since = 0
                rig.everySync((lead + phase) % 500, 500)
                Handler.advance(lead + 40)
                val label = "trễ ${latency} ms, pha ${phase} ms"
                assertEquals("$label: chỉ tạo một trình phát (tạo sẵn, tới hạn dùng lại)", 1, rig.created)
                assertEquals("$label: mở một bản mới", 1, rig.opened.size)
                val (at, voice) = rig.opened.single()
                assertTrue("$label: mở lúc đồng hồ = hạn (mở ở $at ms)", at in lead..lead + 1)
                Handler.advance(latency + 100)
                val drift = (rig.old.position() - 98.0) - (voice.position() - 12.0)
                assertTrue("$label: lệch pha còn $drift s", abs(drift) <= 0.02)
                Handler.advance(5000)
                assertEquals("$label: vòng này chỉ mở một lần", 1, rig.opened.size)
            }
        }
    }

    @Test
    fun a_sync_that_arrives_late_opens_at_loop_start_plus_the_lateness() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 98.3
        rig.handoff.check()
        assertEquals(1, rig.opened.size)
        assertEquals(12.3, rig.opened.single().second.anchor, 1e-9)
    }

    @Test
    fun one_sync_just_before_the_deadline_is_enough_the_ticket_does_the_rest() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 97.8
        rig.handoff.check()
        assertTrue(rig.opened.isEmpty())
        Handler.advance(199)
        assertTrue(rig.opened.isEmpty())
        Handler.advance(2)
        assertEquals(1, rig.opened.size)
        assertEquals(200L, rig.opened.single().first)
    }

    @Test
    fun the_standby_is_made_once_when_less_than_3_s_remain_and_used_at_the_deadline() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 94.9 // còn 3,1 s
        rig.handoff.check()
        assertEquals("còn >= 3 s: chưa tạo", 0, rig.created)
        rig.old.anchor = 96.0 - SystemClock.elapsedRealtime() / 1000.0 // còn 2 s
        repeat(5) { rig.handoff.check(); Handler.advance(100) }
        assertEquals("một lần mỗi vòng", 1, rig.created)
        val standby = rig.handoff.prepared()!!
        assertEquals("đứng ở loopStart, chưa phát", 12.0, standby.position(), 0.0)
        rig.everySync(0, 500)
        Handler.advance(3000)
        assertEquals("tới hạn dùng đúng bản đã sẵn, không tạo mới", 1, rig.created)
        assertTrue(rig.opened.single().second === standby)
        assertNull("dùng xong thì không còn giữ", rig.handoff.prepared())
    }

    @Test
    fun a_late_entry_moves_the_standby_to_loop_start_plus_the_lateness() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 95.5
        rig.handoff.check()
        assertEquals(1, rig.created)
        rig.old.anchor = 98.3 // đồng bộ đến muộn
        rig.handoff.check()
        assertEquals(1, rig.created)
        assertEquals(12.3, rig.opened.single().second.anchor, 1e-9)
    }

    @Test
    fun reset_releases_the_standby_and_nothing_opens_afterwards() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 97.8 // còn 0,2 s: đã tạo sẵn và đã hẹn
        rig.handoff.check()
        assertEquals(1, rig.created)
        assertNotNull(rig.handoff.prepared())
        rig.handoff.reset() // tua / đổi bài / dừng / chương mới
        assertEquals("nhả đúng một lần", 1, rig.discarded.size)
        assertNull(rig.handoff.prepared())
        Handler.advance(2000)
        assertTrue("vé không nổ", rig.opened.isEmpty())
        assertEquals("không tạo thêm", 1, rig.created)
        rig.handoff.reset()
        assertEquals("nhả lần hai không có gì để nhả", 1, rig.discarded.size)
    }

    @Test
    fun a_standby_that_failed_is_dropped_quietly_and_the_deadline_makes_a_fresh_one() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 96.0
        rig.handoff.check()
        rig.handoff.discardReady() // lỗi mạng của bản tạo sẵn (MusicBed.onPlayerError)
        assertEquals(1, rig.discarded.size)
        rig.old.anchor = 98.1
        rig.handoff.check()
        assertEquals(2, rig.created)
        assertEquals(12.1, rig.opened.single().second.anchor, 1e-9)
    }

    @Test
    fun a_ticket_cancelled_by_a_seek_never_fires() {
        Handler.reset()
        val rig = Rig(handoffBounds, 0)
        rig.old.anchor = 97.8 // còn 0,2 s: đã hẹn
        rig.handoff.check()
        assertTrue(rig.opened.isEmpty())
        rig.handoff.reset() // MusicBed huỷ vé khi tua / đổi bài / dừng
        Handler.advance(2000)
        assertTrue("vé cũ không nổ", rig.opened.isEmpty())
    }
}
