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

    /** audibleStart' = khung 10, loopStart' = khung 100, loopEnd' = khung 1000, X' = 83 khung (1,992 s, X = 2 s làm tròn về khung như LoopSeam.plan), 48 kHz (mọi khung là 24 ms). */
    private fun seam(cached: Boolean = false) = LoopSeam.Seam(File("a.mp3"), File("a.wav"), 10 * spf, 100 * spf, 1000 * spf, (83 * spf).toInt(), 48000, 2, spf.toInt(), 0, 3, cached)

    /** Giây trong bài của đích tua (như thước §43 (f): plan + kind + expSample; Nối tính trên trục bài cũ loopEnd' - X'). */
    private fun trackOf(s: LoopSeam.Seam, t: SeamClock.Target): Double = when {
        t.index == 0 -> (s.audibleStartSamples + t.sample).toDouble() / s.sampleRate
        t.index % 2 == 1 -> (s.loopEndSamples - s.xFrames + t.sample).toDouble() / s.sampleRate
        else -> (s.loopStartSamples + s.xFrames + t.sample).toDouble() / s.sampleRate
    }

    private fun fold(x: Double, period: Double) = x - Math.round(x / period) * period

    private fun periodOf(s: LoopSeam.Seam) = (s.loopEndSamples - s.loopStartSamples - s.xFrames).toDouble() / s.sampleRate

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
        assertEquals(2.4 + 1.992, SeamClock.trackSeconds(s, 1, 5000), 1e-9) // kẹp ở cuối Nối (X' = 1,992 s)
        // Clip lặp: mẫu danh nghĩa đầu là loopStart' + X' = 183 khung = 4,392 s, mở sớm 3 khung = 72 ms
        assertEquals(4.392, SeamClock.trackSeconds(s, 2, s.loopClipLeadMs.toLong()), 1e-3)
        assertEquals(4.392 + 1.0, SeamClock.trackSeconds(s, 2, s.loopClipLeadMs.toLong() + 1000), 1e-3)
        assertEquals(4.392, SeamClock.trackSeconds(s, 4, 0), 1e-9) // chưa tới chỗ cắt preroll: không lùi trước đầu Clip
    }

    /** Nối mà biên khung trùng biên khai báo: 46080 Hz (chỉ để thử) làm X = 2 s đúng 80 khung (25 ms một khung); A = 10, loopStart = 100, loopEnd = 1000 khung. */
    private fun exactSeam(): Pair<LoopSeam.Seam, MusicCues.Loop> {
        val rate = 46080
        val x = Math.round(MusicCues.mix.loopCrossfadeSeconds * rate)
        val s = LoopSeam.Seam(File("a.mp3"), File("a.wav"), 10 * spf, 100 * spf, 1000 * spf, x.toInt(), rate, 2, spf.toInt(), 0, 3)
        assertEquals(0L, x % spf)
        return s to MusicCues.Loop(s.audibleStart, 1e9, s.loopEnd - s.loopStart - MusicCues.mix.loopCrossfadeSeconds, true, s.loopStart, s.loopEnd)
    }

    @Test fun seekTargetSplitsFirstPassSeamAndLoopClip() {
        val (s, b) = exactSeam()
        val sr = s.sampleRate.toDouble()
        val x = s.xFrames.toLong()
        val clip0 = 1000 * spf - x - 10 * spf
        assertEquals(0, SeamClock.target(s, b, 0.0).index)
        assertEquals(0L, SeamClock.target(s, b, 0.0).sample)
        val inClip0 = SeamClock.target(s, b, 5.0)
        assertEquals(0, inClip0.index)
        assertEquals(5L * s.sampleRate, inClip0.sample)
        // ngay sau Clip đầu: Nối (mục 1)
        val atSeam = SeamClock.target(s, b, (clip0 + 1000) / sr)
        assertEquals(1, atSeam.index)
        assertEquals(1000L, atSeam.sample)
        // hết Nối: Clip lặp (mục 2), mẫu tính từ loopStart' + X'
        val atClip = SeamClock.target(s, b, (clip0 + x + 5000) / sr)
        assertEquals(2, atClip.index)
        assertEquals(5000L, atClip.sample)
        // vòng kế: chu kỳ P' = loopEnd' - loopStart' - X'
        val period = 1000 * spf - 100 * spf - x
        val again = SeamClock.target(s, b, (clip0 + period + x + 5000) / sr)
        assertEquals(2, again.index)
        assertEquals(5000L, again.sample)
        val againSeam = SeamClock.target(s, b, (clip0 + 3 * period + 7) / sr)
        assertEquals(1, againSeam.index)
        assertEquals(7L, againSeam.sample)
    }

    @Test fun seekTargetAgreesWithTheLegacyLoopPositionWithinAFrame() {
        // Cùng một giây của mốc: đích P3 (mục, mẫu) -> giây trong bài phải trùng MusicCues.loopPosition (đường a87).
        val (s, b) = exactSeam()
        val rate = s.sampleRate
        for (t in listOf(0.0, 3.0, 20.0, 22.7, 22.8, 23.0, 24.9, 25.0, 45.0, 45.6, 46.0, 60.0, 100.0)) {
            val target = SeamClock.target(s, b, t)
            val pos = target.sample * 1000 / rate + if (target.index == 2) s.loopClipLeadMs.toLong() else 0L
            assertEquals("t=$t index=${target.index}", MusicCues.loopPosition(b, t), SeamClock.trackSeconds(s, target.index, pos), 0.01)
        }
    }

    /** Nối dựng như LoopSeam.plan từ mốc khai báo không nằm trên ranh khung (44,1 kHz): A, loopStart, loopEnd làm tròn về khung, X' = X làm tròn về bội khung. */
    private fun offGridSeam(): Pair<LoopSeam.Seam, MusicCues.Loop> {
        val rate = 44100
        val cue = MusicCues.Cue(0.0, 900.0, "music/${"b".repeat(40)}.mp3", -20.0, audibleStart = 0.25, audibleEnd = 24.5, loopStart = 2.40, loopEnd = 23.99)
        val b = MusicCues.loopBounds(cue, 30.0)
        fun frames(sec: Double) = Math.round(ExactSeekMp3Extractor.frameBoundarySeconds(sec, rate) * rate / spf)
        val kx = Math.round(MusicCues.mix.loopCrossfadeSeconds * rate / spf)
        val s = LoopSeam.Seam(File("b.mp3"), File("b.wav"), maxOf(1L, frames(b.start)) * spf, frames(b.loopStart) * spf, frames(b.loopEnd) * spf, (kx * spf).toInt(), rate, 2, spf.toInt(), 0, 3)
        return s to b
    }

    @Test fun seekTargetFollowsTheDeclaredLoopNotTheFrameGridOverManyLoops() {
        // PLAN §43.2 (f): biên căn khung làm P' lệch P (ở đây 24 ms mỗi vòng); đếm vòng theo P' từ đầu mốc thì vài vòng đã lệch quá 1 khung. Đích phải trùng bản đồ khai báo (alignedA87) ở MỌI vòng.
        val (s, b) = offGridSeam()
        val sr = s.sampleRate.toDouble()
        val p = periodOf(s)
        assertTrue("P' khác P thật", Math.abs(p - b.period) > 0.010)
        val clip0 = (s.loopEndSamples - s.xFrames - s.audibleStartSamples) / sr
        var worstOwnGrid = 0.0
        var t = 0.0
        while (t < 400.0) {
            val target = SeamClock.target(s, b, t)
            val declared = MusicCues.loopPosition(b, t)
            val err = Math.abs(fold(trackOf(s, target) - declared, p))
            // trước audibleStart' (A' làm tròn lên) thì kẹp ở đầu Clip đầu: < 1 khung; còn lại đúng tới 1 mẫu
            val tol = if (target.index == 0 && target.sample == 0L) spf / sr else 1.0 / sr + 1e-9
            assertTrue("t=$t index=${target.index} lệch ${err * 1000} ms", err <= tol)
            // cách cũ (đếm chu kỳ P' từ A'): để thấy phép thử này bắt được lỗi
            val own = if (t < clip0) s.audibleStart + t else s.loopStart + (t - clip0) % p
            worstOwnGrid = maxOf(worstOwnGrid, Math.abs(fold(own - declared, p)))
            t += 0.37
        }
        assertTrue("cách cũ phải lệch quá 1 khung + 1 ms ($worstOwnGrid s)", worstOwnGrid > spf / sr + 0.001)
    }

    @Test fun declaredPositionJustBeforeTheFrameAlignedLoopStartLandsAtTheEndOfTheLoopClip() {
        // loopStart khai báo sớm hơn loopStart' (làm tròn lên): chỗ ấy trên Nối là cuối Clip lặp của chu kỳ trước (cùng nội dung), không phải mẫu âm.
        val (s, b) = offGridSeam()
        assertTrue(s.loopStart > b.loopStart)
        val t = b.loopEnd - MusicCues.mix.loopCrossfadeSeconds - b.start + 0.001 // vừa qua loopEnd - X khai báo: bài ở loopStart + 1 ms
        val target = SeamClock.target(s, b, t)
        assertEquals(2, target.index)
        assertTrue(target.sample > 0)
        assertEquals(0.0, fold(trackOf(s, target) - MusicCues.loopPosition(b, t), periodOf(s)), 1.0 / s.sampleRate + 1e-9)
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
        val t = SeamClock.target(built.seam, built.bounds, midLoopClip())
        assertEquals(2, t.index)
        val s = built.seam
        assertEquals(0.0, fold(trackOf(s, t) - MusicCues.alignedPosition(cue, midLoopClip(), built.bounds), periodOf(s)), 1.0 / s.sampleRate + 1e-9)
        assertEquals(1, SeamClock.target(built.seam, built.bounds, midSeam()).index)
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
        assertNull(SeamHandover.target(s, legacyAt(s, 1000.0), 900)) // trễ khởi động đẩy chỗ ra ngoài Nối
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
        fun decide(readings: List<Double>) = SeamHandover.decide(100, 800.0, 0, readings)
        // P3 chưa ra loa / chưa phát đủ SETTLE_MS (chưa có lần đọc tin được): a87 vẫn kêu
        assertEquals(SeamHandover.Act.WAIT, decide(emptyList()))
        // pha khớp nhưng mới thấy 1-2 lần: chờ đủ số lần đọc liền
        assertEquals(SeamHandover.Act.WAIT, decide(listOf(4.0, 3.0)))
        assertEquals(SeamHandover.Act.SWITCH, decide(listOf(4.0, 3.0, 5.0)))
        assertEquals(SeamHandover.Act.SWITCH, decide(listOf(80.0, 4.0, -SeamHandover.TOLERANCE_MS, 2.0))) // chỉ xét STEADY_READINGS lần cuối
    }

    @Test fun aSingleOutOfPhaseReadingNeverRetunes() {
        // PLAN §43.2 g6: tua lại 11-13 ms sau lần tua trước, theo một lần đọc lẻ. Nay cần STEADY_READINGS lần đọc ổn định (chênh <= STABLE_MS) mới tua lại.
        fun decide(readings: List<Double>, retunes: Int = 0) = SeamHandover.decide(600, 800.0, retunes, readings)
        assertEquals(SeamHandover.Act.WAIT, decide(listOf(82.6)))
        assertEquals(SeamHandover.Act.WAIT, decide(listOf(82.6, 40.0)))
        assertEquals(SeamHandover.Act.WAIT, decide(listOf(300.0, 82.6, 40.0, 20.0))) // còn trôi: chưa ổn định
        assertEquals(SeamHandover.Act.RETUNE, decide(listOf(82.6, 81.0, 83.5))) // ca đo được trên máy ảo: P3 muộn 82,6 ms, ổn định
        assertEquals(82.367, SeamHandover.settled(listOf(300.0, 82.6, 81.0, 83.5))!!, 0.001) // tua theo trung bình các lần ổn định
        assertNull(SeamHandover.settled(listOf(82.6, 81.0, 88.0)))
        assertEquals(SeamHandover.Act.RETUNE, decide(listOf(-11.0, -12.0, -11.5), retunes = SeamHandover.MAX_RETUNES - 1))
        assertEquals(SeamHandover.Act.FALLBACK, decide(listOf(40.0, 41.0, 40.5), retunes = SeamHandover.MAX_RETUNES))
        assertEquals(SeamHandover.Act.WAIT, decide(listOf(40.0, 60.0, 50.0), retunes = SeamHandover.MAX_RETUNES)) // chưa ổn định: không đốt lần tua, không bỏ sớm
    }

    @Test fun aColdHandoverNineMsOffRetunesOnceMoreThenSwitches() {
        // PLAN_loop §44.3, bed44s6thu1 #1: hread 160,8 x3 -> RETUNE -> -8,96 / -8,98 / -8,84 -> SWITCH với ±10 ms. Dung sai nay ±5: tua lại thêm một lần.
        val after = listOf(-8.96, -8.98, -8.84)
        assertTrue("với ±10 cũ thì đã đổi tiếng", after.all { Math.abs(it) <= 10.0 })
        assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(600, 800.0, 0, listOf(160.8, 160.8, 160.8)))
        assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(900, 700.0, 1, after))
        // tua lại theo pha trung bình như luật cũ: P3 muộn 8,93 ms -> trễ mới = trễ cũ + 9
        val settled = SeamHandover.settled(after)!!
        assertEquals(-8.927, settled, 0.001)
        assertEquals(259L, SeamHandover.nextLag(250, settled))
        // lần đọc sau lần tua ấy (danh sách đọc bắt đầu lại) trong ±5: đổi tiếng
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(1100, 600.0, 2, listOf(0.4, -0.7)))
        assertEquals(SeamHandover.Act.SWITCH, SeamHandover.decide(1150, 550.0, 2, listOf(0.4, -0.7, 0.2)))
    }

    @Test fun handoverToleranceIsFiveMsInclusive() {
        assertEquals(5.0, SeamHandover.TOLERANCE_MS, 0.0)
        fun decide(readings: List<Double>) = SeamHandover.decide(600, 800.0, 1, readings)
        assertEquals(SeamHandover.Act.SWITCH, decide(listOf(5.0, 5.0, 5.0)))
        assertEquals(SeamHandover.Act.SWITCH, decide(listOf(-5.0, 4.9, -5.0)))
        assertEquals(SeamHandover.Act.RETUNE, decide(listOf(5.1, 5.1, 5.1)))
        assertEquals(SeamHandover.Act.RETUNE, decide(listOf(-5.1, -5.1, -5.1)))
        assertEquals(SeamHandover.Act.RETUNE, decide(listOf(5.0, 5.1, 5.0))) // một lần ngoài dung sai mà ba lần ổn định: tua lại
        assertEquals(SeamHandover.Act.WAIT, decide(listOf(-5.1, 5.1, 0.0))) // ngoài dung sai mà chưa ổn định (chênh > STABLE_MS): chờ
    }

    @Test fun handoverOutOfFiveMsWithNoRetunesLeftFallsBack() {
        val after = listOf(-8.96, -8.98, -8.84)
        assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(900, 700.0, SeamHandover.MAX_RETUNES - 1, after))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(900, 700.0, SeamHandover.MAX_RETUNES, after))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 700.0, 1, after)) // hết hạn cũng thế
        assertEquals(3, SeamHandover.MAX_RETUNES)
        assertEquals(1500L, SeamHandover.DEADLINE_MS)
    }

    @Test fun onlyTimestampsOfTheAudioTrackBornAfterTheLastSeekCount() {
        val issued = 1_000_000_000L
        // lần tua chưa tới luồng phát (chưa xả sau mốc): AudioTrack cũ vẫn chạy, timestamp mới nhưng nói về tiếng cũ
        assertFalse(SeamHandover.fresh(issued, issued - 5_000_000, issued + 10_000_000, 900_000))
        // đã xả sau lần tua, nhưng timestamp chụp trước lần xả
        assertFalse(SeamHandover.fresh(issued, issued + 3_000_000, issued + 2_000_000, 900))
        // AudioTrack mới chưa chạy
        assertFalse(SeamHandover.fresh(issued, issued + 3_000_000, issued + 90_000_000, 0))
        assertTrue(SeamHandover.fresh(issued, issued + 3_000_000, issued + 90_000_000, 2_400))
    }

    @Test fun staleTimestampTwelveMsAfterASeekNeverRetunes() {
        // Chuỗi đo được (PLAN §43.2 g6, Music S6x3 ls_00 #3): tua -> 12 ms sau đọc được timestamp của AudioTrack CŨ (còn chạy, framePosition lớn) -> trước đây RETUNE ngay.
        val s = seam()
        val ms = 1_000_000L
        val sr = s.sampleRate
        val issued = 10_000 * ms // lần tua (mẫu đích 4800 = 100 ms vào Nối)
        val target = 4800L
        val readings = ArrayList<Double>() // MusicBed xoá ở mỗi lần tua
        fun tick(stamp: SeamHandover.Stamp, now: Long, a87: Double): SeamHandover.Act {
            val delta = SeamHandover.reading(s, target, issued, stamp, now, a87)
            if (delta != null) readings += delta
            return SeamHandover.decide(400, 800.0, 0, if (delta != null) readings else emptyList())
        }
        val a87At = { now: Long -> legacyAt(s, 100.0 + 40.0 + (now - issued) / 1e6) } // a87 đi trước đích 40 ms: cần tua lại
        // +12 ms: lần tua chưa xả (AudioTrack cũ, xả lần cuối từ lâu), timestamp mới chụp, đã phát 0,6 s
        val old = SeamHandover.Stamp(28_800, issued + 11 * ms, sr, issued - 900 * ms)
        assertNull(SeamHandover.reading(s, target, issued, old, issued + 12 * ms, a87At(issued + 12 * ms)))
        assertEquals(SeamHandover.Act.WAIT, tick(old, issued + 12 * ms, a87At(issued + 12 * ms)))
        // trước đây: nanoTime sau lần tua + framePosition > 0 là tin -> pha rác, |δ| > 10 ms -> RETUNE ở chính nhịp này
        assertTrue(Math.abs((SeamHandover.p3Seconds(s, target, old.framesAt(issued + 12 * ms)) - a87At(issued + 12 * ms)) * 1000) > SeamHandover.TOLERANCE_MS)
        // +4 ms đã xả, AudioTrack mới chưa chạy / mới phát 30 ms: chưa tính
        val flushed = issued + 4 * ms
        assertEquals(SeamHandover.Act.WAIT, tick(SeamHandover.Stamp(0, issued + 20 * ms, sr, flushed), issued + 22 * ms, a87At(issued + 22 * ms)))
        val startAt = issued + 80 * ms // AudioTrack mới ra loa
        fun running(now: Long) = SeamHandover.Stamp((now - 2 * ms - startAt) * sr / 1_000_000_000L, now - 2 * ms, sr, flushed)
        assertEquals(SeamHandover.Act.WAIT, tick(running(startAt + 30 * ms), startAt + 30 * ms, a87At(startAt + 30 * ms)))
        assertTrue(readings.isEmpty())
        // đã phát >= SETTLE_MS: cần STEADY_READINGS lần đọc ổn định rồi mới tua lại, theo pha trung bình
        var act = SeamHandover.Act.WAIT
        var now = startAt + 60 * ms
        var ticks = 0
        while (act == SeamHandover.Act.WAIT && ticks < 10) {
            act = tick(running(now), now, a87At(now - startAt + issued)) // a87 cùng dòng thời gian, P3 vào sau startAt
            now += SeamHandover.POLL_MS * ms
            ticks++
        }
        assertEquals(SeamHandover.Act.RETUNE, act)
        assertEquals(SeamHandover.STEADY_READINGS, ticks)
        assertTrue(Math.abs(SeamHandover.settled(readings)!!) > SeamHandover.TOLERANCE_MS)
    }

    @Test fun legacyTimestampIsUsedOnlyWhenTheAudioTrackRuns() {
        val stamp = SeamHandover.Stamp(44_100, 5_000_000_000L, 44100, 1_000_000_000L)
        assertEquals(21.0 + 1.0 + 0.01, SeamHandover.legacySeconds(21_000_000L, stamp, 5_010_000_000L)!!, 1e-6) // ngoại suy 10 ms
        assertNull(SeamHandover.legacySeconds(21_000_000L, SeamHandover.Stamp(0, 5_000_000_000L, 44100, 1_000_000_000L), 5_010_000_000L))
        assertNull(SeamHandover.legacySeconds(21_000_000L, SeamHandover.Stamp(44_100, 900_000_000L, 44100, 1_000_000_000L), 5_010_000_000L)) // timestamp trước lần xả
    }

    @Test fun handoverPhaseFromTheLoggedTimestampsMatchesTheContent() {
        // bed44thu ls_30 S6 (APK43e): Nối 44,1 kHz loopEnd' = 6455808, X' = 88704; lần tua cuối của P3 tới mẫu 21777 (EV 19800468238029, xả 19800470893529).
        // a87: khung đầu của AudioTrack ở mẫu 3184 x 1152 (thước Music, NCC 1,0 với bản giải mã liền) = startUs của app.
        val s = LoopSeam.Seam(File("ls_30.mp3"), File("ls_30.wav"), 1152, 794_880, 6_455_808, 88_704, 44100, 2, 1152, 0, 3)
        val now = 19_800_652_865_629L // P3 lên âm lượng (t_on của thước)
        val startUs = Math.round(3184 * 1152 * 1e6 / 44100)
        val a87 = SeamHandover.legacySeconds(startUs, SeamHandover.Stamp(2_724_015, 19_800_632_289_729L, 44100, 19_738_716_916_129L), now)!!
        val p3 = SeamHandover.Stamp(3103, 19_800_632_289_729L, 44100, 19_800_470_893_529L)
        val delta = SeamHandover.reading(s, 21_777, 19_800_468_238_029L, p3, now, a87)!!
        assertEquals(0.0, delta, 0.1) // app: -0,05 ms; thước lấy cả timestamp của AudioTrack P3 CŨ sau lần tua (4083 khung lúc 19800473182329) nên ra -10,5 ms
        assertEquals(4010, SeamHandover.played(s, p3, now))
        assertEquals("hread 1 0.022 90.930", SeamEvents.handoverReading(1, delta, SeamHandover.played(s, p3, now) * 1000.0 / s.sampleRate))
    }

    @Test fun legacyPositionIsMeasuredLikeP3() {
        // a87 tua tới khung bắt đầu ở 21,000 s (giây bài của khung đầu AudioTrack), đã phát 2205 khung ở 44,1 kHz: 21,050 s - cùng cách P3 = đích + framePosition / sr
        assertEquals(21.05, SeamHandover.legacySeconds(21_000_000L, 2205, 44100), 1e-9)
        val s = seam()
        val a87 = SeamHandover.legacySeconds(Math.round(legacyAt(s, 100.0) * 1_000_000), 4800, 48000) // a87 ở 200 ms vào Nối
        assertEquals(0.0, (SeamHandover.p3Seconds(s, 7200, 2400) - a87) * 1000.0, 0.01) // P3 tua tới 150 ms + phát 50 ms: cùng chỗ
    }

    /** Nối như MusicBed.planSeam dựng (bounds = loopBounds(cue, độ dài), 44,1 kHz, mốc khai báo lệch ranh khung), mốc bắt đầu ở giây 12 của chương; `file` quyết định có phải mp3. */
    private fun demoteRig(file: String = "b.mp3"): Triple<SeamPicker.Built, MusicCues.Cue, Int> {
        val rate = 44100
        val cue = MusicCues.Cue(12.0, 900.0, "music/${"b".repeat(40)}.mp3", -20.0, audibleStart = 0.25, audibleEnd = 24.5, loopStart = 2.40, loopEnd = 23.99)
        val duration = 30.0
        val b = MusicCues.loopBounds(cue, duration)
        fun frames(sec: Double) = Math.round(ExactSeekMp3Extractor.frameBoundarySeconds(sec, rate) * rate / spf)
        val kx = Math.round(MusicCues.mix.loopCrossfadeSeconds * rate / spf)
        val s = LoopSeam.Seam(File(file), File("b.wav"), maxOf(1L, frames(b.start)) * spf, frames(b.loopStart) * spf, frames(b.loopEnd) * spf, (kx * spf).toInt(), rate, 2, spf.toInt(), 0, 3)
        return Triple(SeamPicker.Built(s, b, duration, "k"), cue, rate)
    }

    @Test fun demotedLegacyPlayerStartsAtTheDeclaredMapOnAFrameBoundary() {
        val (built, cue, rate) = demoteRig()
        // Bản đồ READY cũ của a87 (MusicCues.offsetMs) dùng loopBounds(cue, độ dài); Built mang đúng vòng ấy (planSeam, SeamPicker.compatible).
        assertEquals(MusicCues.loopBounds(cue, built.durationSeconds), built.bounds)
        assertTrue(SeamPicker.compatible(built, cue))
        val frame = spf.toDouble() / rate
        for (since in listOf(5.123, 60.7, 141.37)) { // vòng đầu (A + t) và các vòng sau loopStart (có X)
            val seconds = cue.start + since
            val aligned = MusicCues.alignedPosition(cue, seconds, built.bounds)
            val start = SeamClock.legacyStart(built, cue, seconds)
            assertEquals("since=$since", ExactSeekMp3Extractor.frameBoundarySeconds(aligned, rate), start, 1e-12)
            val k = start * rate / spf
            assertEquals("since=$since ở ranh khung", Math.round(k).toDouble(), k, 1e-6)
            // Cùng chỗ đường READY cũ tua tới (ms, cắt phần lẻ), lệch dưới 1 khung.
            val ready = MusicCues.offsetMs(cue, seconds, Math.round(built.durationSeconds * 1000))!!
            assertTrue("since=$since lệch ${start * 1000 - ready} ms", Math.abs(start * 1000 - ready) < frame * 1000)
        }
        assertTrue(MusicCues.firstPass(built.bounds, 5.123))
        assertFalse(MusicCues.firstPass(built.bounds, 60.7))
        assertTrue("vòng sau bắt đầu từ loopStart", SeamClock.legacyStart(built, cue, cue.start + 60.7) >= built.bounds.loopStart - frame)
    }

    @Test fun demotedLegacyPlayerOfANonMp3TrackIsNotFrameAligned() {
        val (built, cue, rate) = demoteRig("b.m4a")
        val seconds = cue.start + 5.123
        val aligned = MusicCues.alignedPosition(cue, seconds, built.bounds)
        assertEquals(aligned, SeamClock.legacyStart(built, cue, seconds), 0.0)
        assertTrue("phép thử có lực: chỗ này không nằm trên ranh khung", Math.abs(ExactSeekMp3Extractor.frameBoundarySeconds(aligned, rate) - aligned) > 1e-4)
        assertEquals(aligned, MusicCues.frameAligned(aligned, null), 0.0)
    }

    @Test fun aLegacyPlayerOpenedWithStartAtIsNotSeekedAgainWhenReady() {
        // demote mở a87 với startAt: lúc READY không tua (lần tua ấy tạo AudioTrack thứ hai).
        assertNull(MusicCues.readySeekMs(21.3, 200_000, 21_300, 0))
        assertNull(MusicCues.readySeekMs(0.0, 200_000, null, 5_000))
        // Đối chứng: không có startAt thì tua như cũ - theo giây mới nhất của chương, không thì chỗ vào gấp theo độ dài; chưa biết độ dài thì không tua.
        assertEquals(21_300L, MusicCues.readySeekMs(null, 200_000, 21_300, 0))
        assertEquals(5_000L, MusicCues.readySeekMs(null, 200_000, null, 205_000))
        assertNull(MusicCues.readySeekMs(null, 0, null, 5_000))
    }

    @Test fun handoverFallsBackAtTheDeadlineOrWhenTheSeamIsAlmostOver() {
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 800.0, 0, emptyList())) // P3 không chạy được
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(300, SeamHandover.GUARD_MS.toDouble(), 0, listOf(0.0, 0.0, 0.0))) // a87 tới cuối vòng trước khi P3 sẵn sàng
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(SeamHandover.DEADLINE_MS - 1, SeamHandover.GUARD_MS + 1.0, 0, emptyList()))
    }

    // ---- lưới an toàn: pha theo MẪU ĐÁP thật (PLAN_loop §44.7, ls_06 lần 3 đáp +4365 khung) ----

    /** Nối 44,1 kHz như ls_06 (X' = 77 khung ~ 2,01 s); đích 21703 (lần 3 của ls_06). */
    private val ls06 = LoopSeam.Seam(File("ls_06.mp3"), File("ls_06.wav"), 1152, 100 * 1152L, 1000 * 1152L, 77 * 1152, 44100, 2, 1152, 0, 3)
    private val lsTarget = 21703L

    /**
     * Chuỗi nhịp của MusicBed.stepHandover sau một lần tua tới [lsTarget] với trễ ước lượng ĐÚNG (lúc P3 ra loa a87 ở đúng đích): AudioTrack mới chạy từ +80 ms, đọc mỗi POLL_MS
     * từ SETTLE_MS. `landing` = kết quả lưới an toàn. Trả việc đầu tiên khác WAIT (hay WAIT sau 10 nhịp) và các lần đọc đã tính.
     */
    private fun ticks(landing: SeamHandover.Landing, retunes: Int = 0): Pair<SeamHandover.Act, List<Double>> {
        val s = ls06
        val sr = s.sampleRate
        val ms = 1_000_000L
        val issued = 10_000 * ms
        val flushed = issued + 4 * ms
        val startAt = issued + 80 * ms
        val readings = ArrayList<Double>()
        var now = startAt + 60 * ms
        repeat(10) {
            val stamp = SeamHandover.Stamp((now - 2 * ms - startAt) * sr / 1_000_000_000L, now - 2 * ms, sr, flushed)
            val a87 = (s.loopEndSamples - s.xFrames + lsTarget).toDouble() / sr + (now - startAt) / 1e9
            val delta = SeamHandover.landedReading(s, landing, issued, stamp, now, a87)
            if (delta != null) readings += delta
            val act = SeamHandover.decide(400, 800.0, retunes, if (delta != null) readings else emptyList(), landing)
            if (act != SeamHandover.Act.WAIT) return act to readings
            now += SeamHandover.POLL_MS * ms
        }
        return SeamHandover.Act.WAIT to readings
    }

    @Test fun aSeekThatLandsAChunkLateShowsAsPhaseAndRetunes() {
        val (act, readings) = ticks(SeamHandover.Landing.At(lsTarget + 4365))
        assertEquals(SeamHandover.Act.RETUNE, act)
        assertEquals(SeamHandover.STEADY_READINGS, readings.size)
        for (r in readings) assertEquals(98.98, r, 0.1) // hread thấy P3 trước a87 ~99 ms
        // trễ ước lượng vẫn đúng: lần tua lại học trễ từ pha TRỪ chỗ đáp lệch, không dời trễ 99 ms
        val settled = SeamHandover.settled(readings)!!
        assertEquals(0.0, SeamHandover.lagPhase(ls06, lsTarget, SeamHandover.Landing.At(lsTarget + 4365), settled), 0.1)
        assertEquals(250L, SeamHandover.nextLag(250, SeamHandover.lagPhase(ls06, lsTarget, SeamHandover.Landing.At(lsTarget + 4365), settled)))
        // đối chứng: theo mẫu ĐÍCH (cách cũ) pha ~0 -> đã đổi tiếng với nhạc lệch 99 ms
        val (old, _) = ticks(SeamHandover.Landing.At(lsTarget))
        assertEquals(SeamHandover.Act.SWITCH, old)
    }

    @Test fun aSeekThatLandsOnTheTargetSwitchesAsBefore() {
        val (act, readings) = ticks(SeamHandover.Landing.At(lsTarget))
        assertEquals(SeamHandover.Act.SWITCH, act)
        assertEquals(SeamHandover.STEADY_READINGS, readings.size)
        for (r in readings) assertEquals(0.0, r, 0.1)
        assertEquals(12.5, SeamHandover.lagPhase(ls06, lsTarget, SeamHandover.Landing.At(lsTarget), 12.5), 0.0) // đáp đúng: pha là trễ
    }

    @Test fun withoutALandingNoReadingCounts() {
        val (act, readings) = ticks(SeamHandover.Landing.Pending)
        assertEquals(SeamHandover.Act.WAIT, act)
        assertTrue(readings.isEmpty())
        // vẫn có hạn chót
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 800.0, 0, listOf(0.0, 0.0, 0.0), SeamHandover.Landing.Pending))
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(400, 800.0, 0, listOf(0.0, 0.0, 0.0), SeamHandover.Landing.Pending))
        assertEquals(3.0, SeamHandover.lagPhase(ls06, lsTarget, SeamHandover.Landing.Pending, 3.0), 0.0)
    }

    @Test fun aSeekWhoseContentIsNotFoundRetunesAtOnceThenFallsBack() {
        val none = SeamHandover.Landing.None
        assertNull(SeamHandover.landedReading(ls06, none, 0, SeamHandover.Stamp(44_100, 2_000_000_000L, 44100, 1_000_000_000L), 2_000_000_000L, 1.0))
        val (act, readings) = ticks(none)
        assertEquals(SeamHandover.Act.RETUNE, act) // ngay nhịp đầu, không chờ lần đọc
        assertTrue(readings.isEmpty())
        for (r in 0 until SeamHandover.MAX_RETUNES) assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(400, 800.0, r, emptyList(), none))
        assertEquals(SeamHandover.Act.FALLBACK, ticks(none, retunes = SeamHandover.MAX_RETUNES).first) // hết lượt: a87 lặp mờ chéo như cũ
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 800.0, 0, emptyList(), none))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(400, SeamHandover.GUARD_MS.toDouble(), 0, emptyList(), none))
        assertEquals(0.0, SeamHandover.lagPhase(ls06, lsTarget, none, 0.0), 0.0) // tua lại không đổi trễ
        assertSame(none, SeamHandover.Landing.of(null))
        assertEquals(26068L, (SeamHandover.Landing.of(26068) as SeamHandover.Landing.At).sample)
    }

    @Test fun landLineNamesTheTargetAndTheLandedSample() {
        assertEquals("land 2 21703 26068", SeamEvents.land(2, 21703, 26068))
        assertEquals("land 2 21703 none", SeamEvents.land(2, 21703, null))
    }

    // ---- dịch pha trong dòng (PLAN_loop §44.9): P3 câm, đáp đúng, lệch ổn định <= MAX_SHIFT_MS -> SHIFT thay cho RETUNE (không AudioTrack mới) ----

    /** Kết quả [shiftRun]: các việc khác WAIT theo thứ tự, K của lần dịch (0 = không dịch), các lần đọc sau khi ra lệnh dịch (null = không tính), các dịch đã áp. */
    private class ShiftRun(val acts: List<SeamHandover.Act>, val frames: Long, val afterShift: List<Double?>, val shifts: List<LoopSeam.Shift>)

    /**
     * Chuỗi nhịp của MusicBed.stepHandover sau một lần tua tới [lsTarget] (đáp đúng) mà lúc P3 ra loa nó lệch a87 `phaseMs` (> 0 = P3 đi trước): AudioTrack chạy từ +80 ms, đọc mỗi
     * POLL_MS. Tới SHIFT thì giả lập LoopSink: dịch áp ở chỗ đã GHI = chỗ đang phát + `bufferedMs` (bộ đệm AudioTrack), sink báo về sau `reportMs`; AudioTrack chạy liền (khung lặng
     * cũng tính vào framePosition, giả lập framePosition qua writtenAt).
     */
    private fun shiftRun(phaseMs: Double, muted: Boolean = true, bufferedMs: Long = 300, reportMs: Long = 5): ShiftRun {
        val s = ls06
        val sr = s.sampleRate
        val ms = 1_000_000L
        val issued = 10_000 * ms
        val flushed = issued + 4 * ms
        val startAt = issued + 80 * ms
        val landing = SeamHandover.Landing.At(lsTarget)
        val readings = ArrayList<Double>()
        val shifts = ArrayList<LoopSeam.Shift>()
        var reportAt = 0L
        var pending: LoopSeam.Shift? = null
        var frames = 0L
        val acts = ArrayList<SeamHandover.Act>()
        val after = ArrayList<Double?>()
        var now = startAt + 60 * ms
        repeat(100) {
            if (pending != null && now >= reportAt) {
                shifts += pending!!
                pending = null
            }
            val stamp = SeamHandover.Stamp((now - 2 * ms - startAt) * sr / 1_000_000_000L, now - 2 * ms, sr, flushed)
            val a87 = (s.loopEndSamples - s.xFrames + lsTarget).toDouble() / sr + (now - startAt) / 1e9 - phaseMs / 1000.0
            val delta = if (pending != null) null else SeamHandover.landedReading(s, landing, issued, stamp, now, a87, shifts) // chờ sink báo đã áp: không đọc
            if (frames != 0L) after += delta
            if (delta != null) readings += delta
            val settled = SeamHandover.settled(readings)
            val shiftsSoFar = acts.count { it == SeamHandover.Act.SHIFT }
            when (val act = SeamHandover.decide(400, 800.0, 0, if (delta != null) readings else emptyList(), landing, muted, shiftsSoFar)) {
                SeamHandover.Act.WAIT -> {}
                SeamHandover.Act.SHIFT -> {
                    acts += act
                    frames = SeamHandover.shiftFrames(s, settled!!)
                    readings.clear()
                    reportAt = now + reportMs * ms
                    pending = LoopSeam.Shift(stamp.framesAt(now) + bufferedMs * sr / 1000, frames)
                }
                else -> {
                    acts += act
                    return ShiftRun(acts, frames, after, shifts)
                }
            }
            now += SeamHandover.POLL_MS * ms
        }
        return ShiftRun(acts, frames, after, shifts)
    }

    @Test fun p3AheadWhileMutedIsShiftedInStreamBySilenceThenSwitches() {
        // ls_00 trên máy ảo: hread 146 rồi mỗi lần tua lại một trễ mới (13, -23, +21...). Nay: chèn 146 ms lặng vào chính AudioTrack đang chạy.
        val run = shiftRun(146.0)
        assertEquals(listOf(SeamHandover.Act.SHIFT, SeamHandover.Act.SWITCH), run.acts)
        assertEquals(6439.0, run.frames.toDouble(), 1.0) // ~round(146 x 44,1) > 0 = chèn (pha đo ra 145,98: khung đã phát ngoại suy làm tròn xuống)
        assertEquals(run.frames, run.shifts.single().frames)
        val counted = run.afterShift.filterNotNull()
        assertEquals(SeamHandover.STEADY_READINGS, counted.size)
        for (r in counted) assertEquals(0.0, r, 0.05) // pha sau dịch ~0
        assertNull(run.afterShift.first()) // chưa ra loa thì không tính
    }

    @Test fun p3BehindWhileMutedDropsFramesThenSwitches() {
        val run = shiftRun(-23.0)
        assertEquals(listOf(SeamHandover.Act.SHIFT, SeamHandover.Act.SWITCH), run.acts)
        assertEquals(-1014.0, run.frames.toDouble(), 1.0) // ~round(-23 x 44,1) < 0 = bỏ
        for (r in run.afterShift.filterNotNull()) assertEquals(0.0, r, 0.05)
    }

    @Test fun tooFarOrAudibleOrUnlandedIsNotShifted() {
        assertEquals(listOf(SeamHandover.Act.RETUNE), shiftRun(300.0).acts) // |δ| > MAX_SHIFT_MS: tua lại như cũ
        assertEquals(SeamHandover.Act.SHIFT, shiftRun(SeamHandover.MAX_SHIFT_MS - 1).acts.first())
        assertEquals(listOf(SeamHandover.Act.RETUNE), shiftRun(146.0, muted = false).acts) // không câm: không dịch
        val steady = listOf(146.0, 146.0, 146.0)
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(400, 800.0, 0, steady, SeamHandover.Landing.Pending, muted = true)) // chưa biết chỗ đáp: chờ
        assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(400, 800.0, 0, emptyList(), SeamHandover.Landing.None, muted = true)) // không thấy: tua lại
        assertEquals(SeamHandover.Act.SWITCH, SeamHandover.decide(400, 800.0, 0, listOf(1.0, 2.0, 3.0), SeamHandover.Landing.At(lsTarget), muted = true))
    }

    @Test fun shiftsHaveTheirOwnBudgetAndShareTheDeadline() {
        val at = SeamHandover.Landing.At(lsTarget)
        val steady = listOf(146.0, 146.0, 146.0)
        assertEquals(SeamHandover.Act.SHIFT, SeamHandover.decide(400, 800.0, 0, steady, at, muted = true, shifts = SeamHandover.MAX_SHIFTS - 1))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(400, 800.0, 0, steady, at, muted = true, shifts = SeamHandover.MAX_SHIFTS)) // hết lượt dịch
        assertEquals(SeamHandover.Act.SHIFT, SeamHandover.decide(400, 800.0, SeamHandover.MAX_RETUNES, steady, at, muted = true)) // hết lượt TUA vẫn dịch được
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 800.0, 0, steady, at, muted = true)) // hạn chót chung
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(400, SeamHandover.GUARD_MS.toDouble(), 0, steady, at, muted = true))
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(400, 800.0, 0, listOf(146.0, 120.0, 146.0), at, muted = true)) // chưa ổn định
    }

    @Test fun aLongerHandoverDeadlineOnlyMovesTheDeadline() {
        val steady = listOf(146.0, 146.0, 146.0)
        val at = SeamHandover.Landing.At(lsTarget)
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(2000, 5000.0, 0, emptyList())) // hạn mặc định 1500
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(2000, 5000.0, 0, emptyList(), deadlineMs = 6000L)) // hạn 6000: chưa tới hạn
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(6000, 5000.0, 0, emptyList(), deadlineMs = 6000L))
        assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(2000, 5000.0, 0, listOf(-8.96, -8.98, -8.84), deadlineMs = 6000L))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(2000, 5000.0, 0, emptyList(), SeamHandover.Landing.None)) // không tìm thấy mẫu đáp, quá hạn mặc định
        assertEquals(SeamHandover.Act.RETUNE, SeamHandover.decide(2000, 5000.0, 0, emptyList(), SeamHandover.Landing.None, deadlineMs = 6000L))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(2000, 5000.0, 0, steady, at, muted = true))
        assertEquals(SeamHandover.Act.SHIFT, SeamHandover.decide(2000, 5000.0, 0, steady, at, muted = true, deadlineMs = 6000L))
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(2000, SeamHandover.GUARD_MS.toDouble(), 0, steady, at, muted = true, deadlineMs = 6000L)) // sát hết Nối vẫn bỏ
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(6000, 5000.0, 0, steady, at, muted = true, deadlineMs = 6000L))
        assertEquals(1500L, SeamHandover.DEADLINE_MS)
        assertEquals(2500L, SeamClock.DEADLINE_MS) // cổng gắn Nối không đổi
    }

    @Test fun aReadingBeforeTheShiftIsOutDoesNotCount() {
        val s = ls06
        val sr = s.sampleRate
        val issued = 1_000_000_000L
        val flushed = issued + 4_000_000L
        val now = issued + 2_000_000_000L
        val settle = (SeamHandover.SETTLE_MS * sr / 1000).toLong() // 2646 khung
        val landed = SeamHandover.Landing.At(lsTarget)
        fun read(played: Long, shifts: List<LoopSeam.Shift>, a87: Double) =
            SeamHandover.landedReading(s, landed, issued, SeamHandover.Stamp(played, now, sr, flushed), now, a87, shifts)
        fun a87(content: Long) = (s.loopEndSamples - s.xFrames + lsTarget + content).toDouble() / sr // a87 ở đúng nội dung P3
        val insert = listOf(LoopSeam.Shift(20_000, 6439))
        assertNull(read(15_000, insert, a87(15_000))) // chưa tới chỗ dịch
        assertNull(read(20_000 + 3000, insert, a87(20_000))) // đang phát lặng
        assertNull(read(20_000 + 6439 + settle - 1, insert, a87(20_000 + settle - 1))) // qua lặng chưa đủ SETTLE_MS
        assertEquals(0.0, read(20_000 + 6439 + settle, insert, a87(20_000 + settle))!!, 1e-6) // vị trí = mẫu đáp + framePosition - khung chèn
        val drop = listOf(LoopSeam.Shift(20_000, -1014))
        assertNull(read(20_000 + settle - 1, drop, a87(20_000 + 1014 + settle - 1)))
        assertEquals(0.0, read(20_000 + settle, drop, a87(20_000 + 1014 + settle))!!, 1e-6) // + khung bỏ
        // không có dịch: như trước (đã phát >= SETTLE_MS kể từ lần xả)
        assertEquals(0.0, read(settle, emptyList(), a87(settle))!!, 1e-6)
    }

    @Test fun leadIsHowFarTheStampClockRunsAheadAndNeverNegative() {
        val sr = 44100
        val now = 5_000_000_000L
        val flushed = 1_000_000_000L
        assertEquals(1_400_000_000L, SeamHandover.leadNs(SeamHandover.Stamp(40_000, now + 1_400_000_000L, sr, flushed), now)) // OPPO: giờ tương lai 1,4 s
        assertEquals(0L, SeamHandover.leadNs(SeamHandover.Stamp(40_000, now - 13_000_000L, sr, flushed), now)) // máy ảo: -13..0 ms
        assertEquals(0L, SeamHandover.leadNs(SeamHandover.Stamp(40_000, now, sr, flushed), now))
        assertEquals(0L, SeamHandover.leadNs(null, now)) // a87 không có timestamp
        assertEquals(0L, SeamHandover.leadNs(SeamHandover.Stamp(0, now + 1_400_000_000L, sr, flushed), now)) // chưa chạy (framePosition 0): không tin
        assertEquals(0L, SeamHandover.leadNs(SeamHandover.Stamp(40_000, now + 1_400_000_000L, sr, now + 2_000_000_000L), now)) // timestamp trước lần xả: không tin
    }

    @Test fun phaseOfTwoTracksOnAClockRunningAheadIsReadAtNowPlusLead() {
        val s = ls06
        val sr = s.sampleRate
        val issued = 1_000_000_000L
        val flushed = issued + 4_000_000L
        val now = issued + 2_000_000_000L
        val stampNano = now + 1_400_000_000L // cả dòng ra ghi giờ tương lai 1,4 s (a87 và P3 như nhau)
        val settle = (SeamHandover.SETTLE_MS * sr / 1000).toLong()
        val fp = settle + 5000 // khung P3 đã phát ở stamp
        val p3Seconds = SeamHandover.p3Seconds(s, lsTarget, fp)
        val fa = Math.round((p3Seconds - 0.003) * sr) // a87 đi sau P3 đúng 3 ms (startUs = 0)
        val p3Stamp = SeamHandover.Stamp(fp, stampNano, sr, flushed)
        val a87Stamp = SeamHandover.Stamp(fa, stampNano, sr, issued - 900_000_000L)
        val lead = SeamHandover.leadNs(a87Stamp, now)
        assertEquals(1_400_000_000L, lead)
        val eval = now + lead
        val a87 = SeamHandover.legacySeconds(0L, a87Stamp, eval)!!
        assertEquals(3.0, SeamHandover.landedReading(s, SeamHandover.Landing.At(lsTarget), issued, p3Stamp, eval, a87)!!, 0.05) // ở now + lead: pha thật
        // ở `now` trơn (lỗi cũ): P3 "đã phát" âm tới khi now vượt stamp.nanoTime -> không lần đọc nào
        val a87Plain = SeamHandover.legacySeconds(0L, a87Stamp, now)!!
        assertNull(SeamHandover.landedReading(s, SeamHandover.Landing.At(lsTarget), issued, p3Stamp, now, a87Plain))
        // lead = 0 (máy ảo: stamp ở quá khứ): mốc là chính now, như trước
        val pastP3 = SeamHandover.Stamp(fp, now - 2_000_000L, sr, flushed)
        val pastA87 = SeamHandover.Stamp(fa, now - 2_000_000L, sr, issued - 900_000_000L)
        assertEquals(0L, SeamHandover.leadNs(pastA87, now))
        assertEquals(3.0, SeamHandover.landedReading(s, SeamHandover.Landing.At(lsTarget), issued, pastP3, now, SeamHandover.legacySeconds(0L, pastA87, now)!!)!!, 0.2)
    }

    @Test fun hreadLineEndsWithTheLead() {
        assertEquals("hread 2 3.000 120.500 1400.0", SeamEvents.handoverReading(2, 3.0, 120.5, 1400.04))
        assertEquals("hread 2 3.000 120.500 0.0", SeamEvents.handoverReading(2, 3.0, 120.5, 0.0))
    }

    @Test fun shiftLineNamesTheFramesAndThePhaseBefore() {
        assertEquals("shift 2 6439 146.000", SeamEvents.shift(2, 6439, 146.0))
        assertEquals("shift 2 -1014 -23.000", SeamEvents.shift(2, -1014, -23.0))
        assertEquals(6439L, SeamHandover.shiftFrames(ls06, 146.0))
        assertEquals(-1014L, SeamHandover.shiftFrames(ls06, -23.0))
    }
}
