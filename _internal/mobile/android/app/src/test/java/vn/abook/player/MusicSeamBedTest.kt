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

    @Test fun legacyPositionIsMeasuredLikeP3() {
        // a87 tua tới khung bắt đầu ở 21,000 s (giây bài của khung đầu AudioTrack), đã phát 2205 khung ở 44,1 kHz: 21,050 s - cùng cách P3 = đích + framePosition / sr
        assertEquals(21.05, SeamHandover.legacySeconds(21_000_000L, 2205, 44100), 1e-9)
        val s = seam()
        val a87 = SeamHandover.legacySeconds(Math.round(legacyAt(s, 100.0) * 1_000_000), 4800, 48000) // a87 ở 200 ms vào Nối
        assertEquals(0.0, (SeamHandover.p3Seconds(s, 7200, 2400) - a87) * 1000.0, 0.01) // P3 tua tới 150 ms + phát 50 ms: cùng chỗ
    }

    @Test fun handoverFallsBackAtTheDeadlineOrWhenTheSeamIsAlmostOver() {
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(SeamHandover.DEADLINE_MS, 800.0, 0, emptyList())) // P3 không chạy được
        assertEquals(SeamHandover.Act.FALLBACK, SeamHandover.decide(300, SeamHandover.GUARD_MS.toDouble(), 0, listOf(0.0, 0.0, 0.0))) // a87 tới cuối vòng trước khi P3 sẵn sàng
        assertEquals(SeamHandover.Act.WAIT, SeamHandover.decide(SeamHandover.DEADLINE_MS - 1, SeamHandover.GUARD_MS + 1.0, 0, emptyList()))
    }
}
