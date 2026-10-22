package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/** Đường P3 của nhạc nền (MusicSeamBed.kt): chọn đường (bật / tắt, rơi về khi dựng lỗi / trễ) và đồng hồ nhạc theo (mục, vị trí). Phần ExoPlayer do MusicLoopSeamTest kiểm trên máy. */
class MusicSeamBedTest {
    @get:Rule val folder = TemporaryFolder()

    private val spf = 1152L

    @Before fun mix() {
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
    }

    /** audibleStart' = khung 10, loopStart' = khung 100, loopEnd' = khung 1000, X' = 40 khung, 48 kHz (mọi khung là 24 ms). */
    private fun seam(cached: Boolean = false) = LoopSeam.Seam(File("a.mp3"), File("a.wav"), 10 * spf, 100 * spf, 1000 * spf, (40 * spf).toInt(), 48000, 2, spf.toInt(), 0, 3, cached)

    private val cue = MusicCues.Cue(0.0, 600.0, "music/${"a".repeat(40)}.mp3", -20.0, audibleStart = 0.24, audibleEnd = 24.0, loopStart = 2.4, loopEnd = 24.0)

    private fun bounds() = MusicCues.loopBounds(cue, 25.0)

    private inner class Rig(var enabled: Boolean = true, val cached: Boolean = false, val planFails: Boolean = false, val planNull: Boolean = false, val renderFails: Boolean = false) {
        val jobs = mutableListOf<Runnable>()
        val notes = mutableListOf<String>()
        var plans = 0
        var renders = 0
        val picker = SeamPicker(
            enabled = { enabled },
            async = { jobs += it },
            plan = { file, c ->
                plans++
                if (planFails) error("hỏng")
                if (planNull) null else SeamPicker.Built(seam(cached), bounds(), 25.0, SeamPicker.keyOf(file, c))
            },
            render = { renders++; if (renderFails) error("giải mã hỏng") },
            note = { notes += it },
        )
        fun runJobs() { val now = jobs.toList(); jobs.clear(); now.forEach { it.run() } }
    }

    private fun mp3(name: String = "a.mp3") = folder.newFile(name)

    // ---- chọn đường ----

    @Test fun disabledFlagIsAlwaysLegacyAndTouchesNothing() {
        val rig = Rig(enabled = false)
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(mp3(), cue))
        assertEquals(0, rig.plans)
        assertTrue(rig.jobs.isEmpty())
        assertTrue(rig.notes.isEmpty())
    }

    @Test fun tailCuesAndNonMp3StayOnTheLegacyPath() {
        val rig = Rig()
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(mp3(), cue.copy(tail = true)))
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(mp3("a.m4a"), cue))
        assertEquals(0, rig.plans)
    }

    @Test fun firstChoiceUsesSeamImmediatelyAndNeverWaitsForTheBuild() {
        val rig = Rig()
        val file = mp3()
        val choice = rig.picker.choose(file, cue)
        assertTrue(choice is SeamPicker.Choice.Use)
        val built = (choice as SeamPicker.Choice.Use).built
        assertEquals(SeamPicker.State.BUILDING, built.state) // Clip đầu phát ngay, Nối còn đang dựng
        assertEquals(1, rig.jobs.size)
        assertEquals(0, rig.renders)
        rig.runJobs()
        assertEquals(SeamPicker.State.READY, built.state)
        assertEquals(1, rig.renders)
        // bài thứ hai của cùng mốc dùng lại Nối đã có, không dựng lại
        assertSame(built, (rig.picker.choose(file, cue) as SeamPicker.Choice.Use).built)
        assertEquals(1, rig.plans)
        assertTrue(rig.jobs.isEmpty())
    }

    @Test fun cachedSeamIsReadyWithoutAnyBackgroundWork() {
        val rig = Rig(cached = true)
        val built = (rig.picker.choose(mp3(), cue) as SeamPicker.Choice.Use).built
        assertEquals(SeamPicker.State.READY, built.state)
        assertTrue(rig.jobs.isEmpty())
    }

    @Test fun planFailureFallsBackToLegacyOnceAndSaysSo() {
        val rig = Rig(planFails = true)
        val file = mp3()
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(file, cue))
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(file, cue))
        assertEquals(1, rig.plans) // không thử lại mỗi nhịp
        assertEquals(1, rig.notes.size)
        assertTrue(rig.notes[0].contains("đường cũ"))
    }

    @Test fun nonCrossfadeTrackIsLegacy() {
        val rig = Rig(planNull = true)
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(mp3(), cue))
        assertEquals(1, rig.notes.size)
    }

    @Test fun renderFailureMarksTheSeamDeadAndLaterChoicesAreLegacy() {
        val rig = Rig(renderFails = true)
        val file = mp3()
        val built = (rig.picker.choose(file, cue) as SeamPicker.Choice.Use).built
        rig.runJobs()
        assertEquals(SeamPicker.State.DEAD, built.state)
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(file, cue))
        assertTrue(rig.notes.single().contains("giải mã hỏng"))
    }

    @Test fun lateBuildNeverRevivesARejectedSeam() {
        val rig = Rig()
        val file = mp3()
        val built = (rig.picker.choose(file, cue) as SeamPicker.Choice.Use).built
        rig.picker.reject(built, "lỗi phát")
        rig.runJobs() // dựng xong muộn sau khi đã bỏ
        assertEquals(SeamPicker.State.DEAD, built.state)
        assertSame(SeamPicker.Choice.Legacy, rig.picker.choose(file, cue))
    }

    @Test fun sameLoopSharesTheSeamButAnotherLoopOrTailDoesNot() {
        val built = SeamPicker.Built(seam(), bounds(), 25.0, "k")
        assertTrue(SeamPicker.compatible(built, cue.copy(start = 30.0, end = 90.0)))
        assertFalse(SeamPicker.compatible(built, cue.copy(loopStart = 3.0)))
        assertFalse(SeamPicker.compatible(built, cue.copy(tail = true)))
    }

    // ---- hạn chót: dựng xong trước loopEnd / dựng trễ ----

    @Test fun builtBeforeLoopEndIsAttachedAtOnceHoweverFarTheLoopIs() {
        val clip0Ms = seam().clip0Ms
        assertEquals(SeamClock.Gate.ATTACH, SeamClock.gate(SeamPicker.State.READY, false, clip0Ms))
        assertEquals(SeamClock.Gate.ATTACH, SeamClock.gate(SeamPicker.State.READY, false, SeamClock.DEADLINE_MS + 1))
        assertEquals(SeamClock.Gate.ATTACH, SeamClock.gate(SeamPicker.State.READY, false, 100)) // kịp sát hạn: vẫn nối
        assertEquals(SeamClock.Gate.DONE, SeamClock.gate(SeamPicker.State.READY, true, 100))
    }

    @Test fun stillBuildingWaitsUntilTheDeadlineThenFallsBack() {
        assertEquals(SeamClock.Gate.WAIT, SeamClock.gate(SeamPicker.State.BUILDING, false, 60_000))
        assertEquals(SeamClock.Gate.WAIT, SeamClock.gate(SeamPicker.State.BUILDING, false, SeamClock.DEADLINE_MS + 1))
        assertEquals(SeamClock.Gate.DEMOTE, SeamClock.gate(SeamPicker.State.BUILDING, false, SeamClock.DEADLINE_MS))
        assertEquals(SeamClock.Gate.DEMOTE, SeamClock.gate(SeamPicker.State.BUILDING, false, 0))
    }

    @Test fun failedBuildFallsBackAtOnce() {
        assertEquals(SeamClock.Gate.DEMOTE, SeamClock.gate(SeamPicker.State.DEAD, false, 60_000))
    }

    @Test fun lateBuildEndToEndOnTheClip0Timeline() {
        val s = seam()
        val rig = Rig()
        val built = (rig.picker.choose(mp3(), cue) as SeamPicker.Choice.Use).built
        // dựng chưa xong: đi hết nhịp đồng bộ 0,5 s trên Clip đầu, tới hạn chót thì rơi về
        var pos = 0L
        var gate = SeamClock.Gate.WAIT
        while (gate == SeamClock.Gate.WAIT) {
            gate = SeamClock.gate(built.state, false, SeamClock.clip0RemainingMs(s, 0, pos))
            if (gate == SeamClock.Gate.WAIT) pos += 500
        }
        assertEquals(SeamClock.Gate.DEMOTE, gate)
        assertTrue("rơi về trước khi Clip đầu hết", pos < s.clip0Ms)
        assertTrue("không rơi về sớm hơn hạn chót", s.clip0Ms - pos > SeamClock.DEADLINE_MS - 500)
        // còn dựng xong trước hạn chót: nối vào
        rig.runJobs()
        assertEquals(SeamClock.Gate.ATTACH, SeamClock.gate(built.state, false, SeamClock.clip0RemainingMs(s, 0, 5000)))
    }

    // ---- đồng hồ nhạc (mục, vị trí) ----

    @Test fun clockFollowsTheTrackPositionInEveryItemKind() {
        val s = seam()
        // Clip đầu: bắt đầu ở audibleStart' = 10 khung = 0,24 s
        assertEquals(0.24, SeamClock.trackSeconds(s, 0, 0), 1e-9)
        assertEquals(1.24, SeamClock.trackSeconds(s, 0, 1000), 1e-9)
        // Nối: bản lặp mới vừa vào, loopStart' = 100 khung = 2,4 s
        assertEquals(2.4, SeamClock.trackSeconds(s, 1, 0), 1e-9)
        assertEquals(2.4 + 0.5, SeamClock.trackSeconds(s, 1, 500), 1e-9)
        assertEquals(2.4 + 0.96, SeamClock.trackSeconds(s, 1, 5000), 1e-9) // kẹp ở cuối Nối (X' = 0,96 s)
        // Clip lặp: mẫu danh nghĩa đầu là loopStart' + X' = 140 khung = 3,36 s, mở sớm 3 khung = 72 ms
        assertEquals(3.36, SeamClock.trackSeconds(s, 2, s.loopClipLeadMs.toLong()), 1e-3)
        assertEquals(3.36 + 1.0, SeamClock.trackSeconds(s, 2, s.loopClipLeadMs.toLong() + 1000), 1e-3)
        assertEquals(3.36, SeamClock.trackSeconds(s, 4, 0), 1e-9) // chưa tới chỗ cắt preroll: không lùi trước đầu Clip
    }

    @Test fun seekTargetSplitsFirstPassSeamAndLoopClip() {
        val s = seam()
        val sr = 48000.0
        // Clip đầu dài (1000 - 40 - 10) khung
        val clip0 = (1000 - 40 - 10) * spf
        assertEquals(0, SeamClock.target(s, 0.0).index)
        assertEquals(0L, SeamClock.target(s, 0.0).sample)
        val inClip0 = SeamClock.target(s, 5.0)
        assertEquals(0, inClip0.index)
        assertEquals(240000L, inClip0.sample)
        // ngay sau Clip đầu: Nối (mục 1)
        val atSeam = SeamClock.target(s, (clip0 + 1000) / sr)
        assertEquals(1, atSeam.index)
        assertEquals(1000L, atSeam.sample)
        // hết Nối (X' = 40 khung): Clip lặp (mục 2), mẫu tính từ loopStart' + X'
        val atClip = SeamClock.target(s, (clip0 + 40 * spf + 5000) / sr)
        assertEquals(2, atClip.index)
        assertEquals(5000L, atClip.sample)
        // vòng kế: chu kỳ P' = loopEnd' - loopStart' - X' = 860 khung
        val period = (1000 - 100 - 40) * spf
        val again = SeamClock.target(s, (clip0 + period + 40 * spf + 5000) / sr)
        assertEquals(2, again.index)
        assertEquals(5000L, again.sample)
        val againSeam = SeamClock.target(s, (clip0 + 3 * period + 7) / sr)
        assertEquals(1, againSeam.index)
        assertEquals(7L, againSeam.sample)
    }

    @Test fun seekTargetAgreesWithTheLegacyLoopPositionWithinAFrame() {
        // Cùng một giây của mốc: đích P3 (mục, mẫu) -> giây trong bài phải trùng MusicCues.loopPosition (đường a87). Tần số 46080 Hz (chỉ để thử) làm X = 2 s đúng 80 khung.
        val rate = 46080
        val x = (MusicCues.mix.loopCrossfadeSeconds * rate / spf).toInt() * spf
        val s = LoopSeam.Seam(File("a.mp3"), File("a.wav"), 10 * spf, 100 * spf, 1000 * spf, x.toInt(), rate, 2, spf.toInt(), 0, 3)
        assertEquals(MusicCues.mix.loopCrossfadeSeconds * rate, x.toDouble(), 0.0)
        val b = MusicCues.Loop(s.audibleStart, 1e9, s.loopEnd - s.loopStart - MusicCues.mix.loopCrossfadeSeconds, true, s.loopStart, s.loopEnd)
        for (t in listOf(0.0, 3.0, 20.0, 22.7, 22.8, 23.0, 24.9, 25.0, 45.0, 45.6, 46.0, 60.0, 100.0)) {
            val target = SeamClock.target(s, t)
            val pos = target.sample * 1000 / rate + if (target.index == 2) s.loopClipLeadMs.toLong() else 0L
            assertEquals("t=$t index=${target.index}", MusicCues.loopPosition(b, t), SeamClock.trackSeconds(s, target.index, pos), 0.01)
        }
    }

    @Test fun clip0RemainingIsNullOncePastTheFirstClip() {
        val s = seam()
        assertEquals(s.clip0Ms, SeamClock.clip0RemainingMs(s, 0, 0))
        assertEquals(s.clip0Ms - 1000, SeamClock.clip0RemainingMs(s, 0, 1000))
        assertNull(SeamClock.clip0RemainingMs(s, 1, 10))
        assertNull(SeamClock.clip0RemainingMs(s, 2, 10))
    }

    @Test fun playedItemsAreDroppedInPairsKeepingParity() {
        assertNull(SeamClock.stale(0))
        assertNull(SeamClock.stale(3))
        assertNotNull(SeamClock.stale(4))
        assertEquals(2, SeamClock.stale(4)!!.first)
        assertEquals(4, SeamClock.stale(4)!!.last + 1) // removeMediaItems(2, 4): chẵn lẻ của mục không đổi
        assertEquals(2, SeamClock.stale(9)!!.first)
    }

    // ---- vào giữa vòng (Task 3): a) Nối có sẵn trên đĩa -> P3 ngay; b) chưa có -> a87 phục vụ, xong thì P3 nhận ở ranh lặp ----

    /** Giây kể từ đầu mốc rơi vào giữa Clip lặp thứ nhất (mục 2) / giữa Nối đầu (mục 1) của [seam]. */
    private fun midLoopClip(s: LoopSeam.Seam = seam()): Double {
        val clip0 = s.loopEndSamples - s.xFrames - s.audibleStartSamples
        val period = s.loopEndSamples - s.loopStartSamples - s.xFrames
        return (clip0 + s.xFrames + period / 2).toDouble() / s.sampleRate
    }

    private fun midSeam(s: LoopSeam.Seam = seam()): Double {
        val clip0 = s.loopEndSamples - s.xFrames - s.audibleStartSamples
        return (clip0 + s.xFrames / 2).toDouble() / s.sampleRate
    }

    @Test fun entryInsideTheFirstClipNeedsNoSeam() {
        val built = (Rig().picker.choose(mp3(), cue) as SeamPicker.Choice.Use).built
        assertEquals(SeamPicker.State.BUILDING, built.state)
        assertTrue(SeamClock.servesEntry(built, 0.0))
        assertTrue(SeamClock.servesEntry(built, 3.0))
    }

    @Test fun cachedSeamServesAMidLoopEntryAtOnceAndSeeksToTheExactItem() {
        val rig = Rig(cached = true)
        val built = (rig.picker.choose(mp3(), cue) as SeamPicker.Choice.Use).built
        // a) WAV có sẵn: READY ngay trong choose, không việc nền, và mọi chỗ vào (giữa Nối, giữa Clip lặp) đều phục vụ được
        assertEquals(SeamPicker.State.READY, built.state)
        assertTrue(rig.jobs.isEmpty())
        assertTrue(SeamClock.servesEntry(built, midSeam()))
        assertTrue(SeamClock.servesEntry(built, midLoopClip()))
        val t = SeamClock.target(built.seam, midLoopClip())
        assertEquals(2, t.index)
        val s = built.seam
        val period = s.loopEndSamples - s.loopStartSamples - s.xFrames
        assertTrue(Math.abs(period / 2 - t.sample) <= 1L)
        assertEquals(1, SeamClock.target(built.seam, midSeam()).index)
    }

    @Test fun noCacheMidLoopEntryIsServedByTheLegacyPathWhileTheSeamBuilds() {
        val rig = Rig()
        val built = (rig.picker.choose(mp3(), cue) as SeamPicker.Choice.Use).built
        assertEquals(SeamPicker.State.BUILDING, built.state)
        assertFalse(SeamClock.servesEntry(built, midSeam()))
        assertFalse(SeamClock.servesEntry(built, midLoopClip()))
        assertEquals(1, rig.jobs.size) // Nối vẫn dựng nền cho lần nhận sau
        // b) a87 phục vụ; ranh lặp mà Nối chưa xong thì đợi ranh sau; xong thì nhận; hỏng thì ở lại a87
        assertEquals(SeamClock.Promote.WAIT, SeamClock.promote(built.state))
        rig.runJobs()
        assertEquals(SeamClock.Promote.NOW, SeamClock.promote(built.state))
        assertTrue(SeamClock.servesEntry(built, midLoopClip())) // và lần vào kế (cùng Nối) đi P3 luôn
    }

    @Test fun brokenSeamNeverPromotes() {
        val rig = Rig(renderFails = true)
        val built = (rig.picker.choose(mp3(), cue) as SeamPicker.Choice.Use).built
        rig.runJobs()
        assertEquals(SeamClock.Promote.NEVER, SeamClock.promote(built.state))
        // bản P3 tạo sẵn lỗi phát -> MusicBed gọi reject: cũng không nhận nữa
        val rig2 = Rig()
        val other = (rig2.picker.choose(mp3("b.mp3"), cue) as SeamPicker.Choice.Use).built
        rig2.picker.reject(other, "lỗi phát")
        assertEquals(SeamClock.Promote.NEVER, SeamClock.promote(other.state))
    }

    @Test fun legacySampleMapsTheOldBedPositionOntoTheSeam() {
        val s = seam()
        val start = s.loopEndSamples - s.xFrames // a87 bắt đầu mờ chéo ở loopEnd' - X'
        fun at(offsetFrames: Long) = SeamClock.legacySample(s, (start + offsetFrames).toDouble() / s.sampleRate)
        assertEquals(0L, at(0))
        assertEquals(480L, at(480)) // trễ 10 ms so với hạn: Nối ở đúng chỗ ấy, nội dung trùng bài cũ
        assertEquals(-5000L, at(-5000)) // sớm hơn hạn / muộn quá Nối: không kẹp, người gọi quyết
        assertEquals(s.xFrames + 99999L, at(s.xFrames + 99999L))
    }

    @Test fun legacySampleMatchesTheLoopPositionOfTheSeamItem() {
        // Nối ở mẫu u ứng với vị trí bài loopStart' + u/sr (SeamClock.trackSeconds): bài cũ ở loopEnd' - X' + u/sr cùng nhịp mờ chéo
        val s = seam()
        val u = 12345L
        val oldPos = (s.loopEndSamples - s.xFrames + u).toDouble() / s.sampleRate
        assertEquals(u, SeamClock.legacySample(s, oldPos))
        val seamItemMs = u * 1000 / s.sampleRate
        assertEquals(s.loopStart + seamItemMs / 1000.0, SeamClock.trackSeconds(s, 1, seamItemMs), 0.002)
    }

    // ---- a87 -> P3 không để quãng im (SeamHandover) ----

    private fun legacyAt(s: LoopSeam.Seam, offsetMs: Double) = (s.loopEndSamples - s.xFrames).toDouble() / s.sampleRate + offsetMs / 1000.0

    @Test fun handoverTargetIsWhereTheOldBedWillBeWhenP3IsAudible() {
        val s = seam()
        val t = SeamHandover.target(s, legacyAt(s, 100.0), 250)!!
        assertEquals(1, t.index)
        assertEquals(Math.round(0.350 * s.sampleRate), t.sample) // 100 ms vào Nối + 250 ms trễ khởi động
        assertEquals(0L, SeamHandover.target(s, legacyAt(s, -20.0), 0)!!.sample) // hẹn sớm hơn hạn một chút: kẹp ở đầu Nối
    }

    @Test fun handoverTargetGivesUpWhenTheSeamIsAboutToEnd() {
        val s = seam()
        val seamMs = s.xFrames * 1000.0 / s.sampleRate // 960 ms
        assertNotNull(SeamHandover.target(s, legacyAt(s, seamMs - SeamHandover.GUARD_MS - 5.0), 0))
        assertNull(SeamHandover.target(s, legacyAt(s, seamMs - SeamHandover.GUARD_MS + 5.0), 0))
        assertNull(SeamHandover.target(s, legacyAt(s, 100.0), 900)) // trễ khởi động đẩy chỗ ra ngoài Nối
        assertEquals(seamMs - 100.0, SeamHandover.remainingMs(s, legacyAt(s, 100.0)), 0.01)
    }

    @Test fun p3PositionIsTheSeekTargetPlusTheFramesTheAudioTrackPlayed() {
        val s = seam()
        // đã tua tới mẫu 4800 của Nối (100 ms), AudioTrack đã phát 2400 khung (50 ms): P3 ở 150 ms vào Nối, trên trục a87
        assertEquals(legacyAt(s, 150.0), SeamHandover.p3Seconds(s, 4800, 2400), 1e-9)
    }

    @Test fun startupLagLearnsFromTheMeasuredPhase() {
        assertEquals(170L, SeamHandover.nextLag(250, 80.0)) // P3 ra loa sớm hơn dự tính 80 ms (lệch dương = P3 ở trước a87)
        assertEquals(330L, SeamHandover.nextLag(250, -80.0))
        assertEquals(20L, SeamHandover.nextLag(100, 500.0)) // kẹp
        assertEquals(900L, SeamHandover.nextLag(800, -500.0))
    }

    @Test fun handoverWaitsInSilenceUntilP3IsAudibleAndInPhase() {
        fun decide(elapsed: Long = 100, remaining: Double = 800.0, retunes: Int = 0, played: Double? = null, delta: Double? = null, steady: Int = 0) =
            SeamHandover.decide(elapsed, remaining, retunes, played, delta, steady)
        // P3 chưa ra loa (không có số đo AudioTrack) hay mới phát chưa đủ: a87 vẫn kêu, chưa đổi tiếng dù pha tình cờ khớp
        assertEquals(SeamHandover.Act.WAIT, decide(played = null, delta = null))
        assertEquals(SeamHandover.Act.WAIT, decide(played = 20.0, delta = 0.0, steady = 5))
        // đã ra loa, pha khớp nhưng mới thấy 1-2 lần: chờ đủ số lần đọc liền
        assertEquals(SeamHandover.Act.WAIT, decide(played = 80.0, delta = 4.0, steady = 2))
        assertEquals(SeamHandover.Act.SWITCH, decide(played = 80.0, delta = 4.0, steady = SeamHandover.STEADY_READINGS))
        assertEquals(SeamHandover.Act.SWITCH, decide(played = 80.0, delta = -SeamHandover.TOLERANCE_MS, steady = SeamHandover.STEADY_READINGS))
    }

    @Test fun handoverRetunesWhenOutOfPhaseThenGivesUp() {
        fun decide(delta: Double, retunes: Int, elapsed: Long = 600) = SeamHandover.decide(elapsed, 800.0, retunes, 90.0, delta, SeamHandover.steady(3, delta))
        assertEquals(SeamHandover.Act.RETUNE, decide(delta = 82.6, retunes = 0)) // ca đo được trên máy ảo: P3 muộn 82,6 ms
        assertEquals(SeamHandover.Act.RETUNE, decide(delta = -11.0, retunes = SeamHandover.MAX_RETUNES - 1))
        assertEquals(SeamHandover.Act.FALLBACK, decide(delta = 40.0, retunes = SeamHandover.MAX_RETUNES))
    }

    @Test fun handoverFallsBackAtTheDeadlineOrWhenTheSeamIsAlmostOver() {
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 800.0, 0, null, null, 0)) // P3 không chạy được
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(300, SeamHandover.GUARD_MS.toDouble(), 0, 90.0, 0.0, 9)) // a87 tới cuối vòng trước khi P3 sẵn sàng
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(SeamHandover.DEADLINE_MS - 1, SeamHandover.GUARD_MS + 1.0, 0, null, null, 0))
    }

    @Test fun steadyCountResetsWhenThePhaseDrifts() {
        assertEquals(1, SeamHandover.steady(0, 3.0))
        assertEquals(3, SeamHandover.steady(2, -9.9))
        assertEquals(0, SeamHandover.steady(2, 10.1))
    }
}
