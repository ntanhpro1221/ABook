package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.pow

/**
 * Mốc nhạc của sách trên điện thoại (MusicCues, phần dữ liệu của MusicBed) - cùng luật với ui/src/listen/musicBed.ts (musicBed.test.ts)
 * và music_plan.packaged_cues: bước âm lượng `steps` và mốc nối bài anh em `sibling` đi qua gói, âm lượng = gainDb + bước đang hiệu lực.
 */
class MusicCuesTest {
    private val calm = "music/" + "a".repeat(40) + ".mp3"
    private val sibling = "music/" + "b".repeat(40) + ".mp3"
    private val music = JSONObject(
        """{"levelDb": -20, "tracks": {"$calm": {"link": "x"}, "$sibling": {"link": "y"}}, "chapters": {"3": [
            {"start": 0, "end": 300, "track": "$calm", "gainDb": -8, "steps": [{"at": 240, "db": -1.5}, {"at": 180, "db": 2}, {"at": "x", "db": 1}]},
            {"start": 300, "end": 500, "track": "$sibling", "gainDb": -2, "sibling": true, "steps": [{"at": 300, "db": 3}]},
            {"start": 500, "end": 600, "track": "music/nope.mp3"}
        ]}}""",
    )

    @Test
    fun steps_and_the_sibling_flag_come_through_and_broken_steps_are_dropped() {
        val cues = MusicCues.of(music, 3)
        assertEquals(listOf(calm, sibling), cues.map { it.track })
        assertEquals(listOf(180.0, 240.0), cues[0].steps.map { it.at })
        assertFalse(cues[0].sibling)
        assertTrue(cues[1].sibling)
        assertTrue(MusicCues.of(music, 4).isEmpty())
    }

    @Test
    fun the_step_in_force_is_the_last_one_reached() {
        val cue = MusicCues.of(music, 3)[0]
        assertEquals(0.0, MusicCues.stepDbAt(cue, 100.0), 0.0)
        assertEquals(2.0, MusicCues.stepDbAt(cue, 180.0), 0.0)
        assertEquals(-1.5, MusicCues.stepDbAt(cue, 299.0), 0.0)
    }

    @Test
    fun the_target_is_gain_plus_step_and_never_above_zero_db() {
        val (calmCue, siblingCue) = MusicCues.of(music, 3)
        assertEquals(10.0.pow(-8.0 / 20).toFloat(), MusicCues.targetGain(calmCue, 10.0, 0.1f), 1e-6f)
        assertEquals(10.0.pow(-6.0 / 20).toFloat(), MusicCues.targetGain(calmCue, 200.0, 0.1f), 1e-6f)
        assertEquals(1f, MusicCues.targetGain(siblingCue, 310.0, 0.1f), 0f) // -2 + 3 > 0: kẹp ở 0 dB
        val old = MusicCues.Cue(0.0, 10.0, calm, null, listOf(MusicCues.Step(0.0, -6.0)))
        assertEquals(0.1f * 10.0.pow(-6.0 / 20).toFloat(), MusicCues.targetGain(old, 1.0, 0.1f), 1e-6f)
    }

    @Test
    fun a_ramp_moves_toward_its_goal_from_either_side_and_stops_there() {
        assertEquals(0.3f, MusicCues.toward(0.2f, 0.5f, 0.1f), 1e-6f)
        assertEquals(0.4f, MusicCues.toward(0.5f, 0.2f, 0.1f), 1e-6f)
        assertEquals(0.5f, MusicCues.toward(0.45f, 0.5f, 0.1f), 0f)
        // 4 s trượt ở nhịp 50 ms: 80 nhịp từ mức cũ tới mức mới
        var volume = 0.2f
        val perTick = (0.4f - 0.2f) * 50 / MusicCues.STEP_RAMP_MS
        repeat(79) { volume = MusicCues.toward(volume, 0.4f, perTick) }
        assertTrue(volume < 0.4f)
        volume = MusicCues.toward(volume, 0.4f, perTick)
        assertEquals(0.4f, volume, 1e-5f)
    }

    @Test
    fun the_place_in_the_track_follows_the_place_in_the_chapter_and_wraps_when_it_loops() {
        val cue = MusicCues.Cue(start = 100.0, end = 600.0, track = calm, gainDb = -8.0)
        assertEquals(95_000L, MusicCues.offsetMs(cue, 195.0, 200_000L))
        assertEquals(50_000L, MusicCues.offsetMs(cue, 350.0, 200_000L))
        assertEquals(0L, MusicCues.offsetMs(cue, 90.0, 200_000L))
        assertEquals(null, MusicCues.offsetMs(cue, 195.0, -1L))
    }
}
