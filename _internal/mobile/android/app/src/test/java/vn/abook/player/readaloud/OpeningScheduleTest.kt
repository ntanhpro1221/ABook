package vn.abook.player.readaloud

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class OpeningScheduleTest {
    @get:Rule val temp = TemporaryFolder()

    // Dựng lại dev/gap [21]: 6 khúc (tiêu đề + 4 đoạn) / 238 ký tự làm 16,1 s; khúc đầu 115 ký tự của đoạn 5 làm 5,4 s.
    // Hai phép đo cho a = 1,252876 s/khúc, b = 0,0360619 s/ký tự. Đây là số dựng lịch JVM, không phải đo lại điện thoại.
    private val b = (6 * 5.4 - 16.1) / (6 * 115 - 238)
    private val a = 5.4 - 115 * b
    private val work = VoiceWork(a, b)
    private val audio = (13.2 - 2.19) / 202
    private val opening = listOf(
        OpeningParagraph(listOf(58, 66), 125),
        OpeningParagraph(listOf(5)),
        OpeningParagraph(listOf(64)),
        OpeningParagraph(listOf(8)),
        OpeningParagraph(listOf(115, 171), 287),
    )
    private val body = List(12) { OpeningParagraph(listOf(115, 171), 287) }

    /** Đồng hồ độc lập: không cho phép im rồi dùng cái im ấy làm đà cho đoạn sau; mỗi đoạn phải có khúc đầu trước đúng hạn H + tiếng trước nó. */
    private fun assertStartsOnTime(hold: Long, paragraphs: List<OpeningParagraph>, model: VoiceWork, perChar: Double, firstMs: Long = 2_190L, speed: Double = 1.0) {
        var machine = 0.0
        var listener = firstMs / 1000.0 / speed
        for ((index, paragraph) in paragraphs.withIndex()) {
            if (listener >= 60) break
            val units = paragraph.units.map { model.perUnit + model.perChar * it }
            if (!paragraph.cached && units.isNotEmpty()) {
                assertTrue("đoạn $index: xong=${machine + units.first()}, tới=${hold / 1000.0 + listener}", machine + units.first() <= hold / 1000.0 + listener)
                machine += units.sum()
            }
            listener += (paragraph.chars * perChar + paragraph.silenceMs / 1000.0) / speed
        }
    }

    @Test fun oppoBookAWaitsForTheShortParagraphsAndTheFifthParagraph() {
        assertEquals(16.1, work.seconds(238, 6), 1e-9)
        assertEquals(5.4, work.seconds(115), 1e-9)
        assertTrue(work.seconds(5) in 1.2..1.6)
        assertTrue(work.seconds(8) in 1.2..1.6)
        val paragraphs = opening + body
        val hold = OpeningSchedule.holdMs(2_190, paragraphs, work, audio, firstUnits = listOf(37))
        assertEquals(5_913L, hold)
        assertStartsOnTime(hold, paragraphs, work, audio)
        assertThrows(AssertionError::class.java) { assertStartsOnTime(1_500, paragraphs, work, audio) }
        // Kiểm cả ranh khúc đoạn 5 bằng giây tiếng đã ghi: khúc đầu 7,53 s đủ chờ khúc sau (7,42 s theo mô hình).
        assertTrue(work.seconds(171) < 7.53)
        println("a OPPO A holdMs=$hold; first 60 s: no late paragraph start")
    }

    @Test fun bookBWithALongParagraphAfterTheHeadingAddsOnlyTheSmallMargin() {
        // Đoạn dài ngay sau tiêu đề: không có chuỗi chi phí cố định của sách A. Máy đã đo nhanh hơn OPPO nóng ở c2_stB.
        val model = VoiceWork(0.25, 0.026)
        val paragraphs = listOf(OpeningParagraph(listOf(115, 171), 287)) + body
        val previous = ReadAheadPolicy.openingHoldMs(2_230, LocalLive.charsBeforeStart(listOf(115, 171), 0.029), 0.029)
        val hold = OpeningSchedule.holdMs(2_230, paragraphs, model, 0.06, firstUnits = listOf(38))
        assertEquals(1_210L, hold)
        assertTrue("cũ $previous ms, mới $hold ms", hold <= previous + 500)
        assertStartsOnTime(hold, paragraphs, model, 0.06, 2_230)
        println("b long-paragraph B holdMs=$hold; legacyMs=$previous")
    }

    @Test fun theRecordedHotOppoBookBCannotFitTheOldCapPlusHalfASecond() {
        // gap [22], c2_stB: tiêu đề 2,230 s; hai khúc 109/171 ký tự làm 5,367/7,910 s, tiếng cả đoạn 18,600 s.
        // Riêng hạn khúc đầu đã cần 3,137 s chưa cộng biên. Ca này ghi rõ mâu thuẫn với trần B <= 2 s, không dùng một máy nhanh giả làm OPPO.
        val perChar = (7.910 - 5.367) / (171 - 109)
        val measured = VoiceWork(5.367 - 109 * perChar, perChar)
        val paragraph = OpeningParagraph(listOf(109, 171), 238)
        val hold = OpeningSchedule.holdMs(2_230, List(12) { paragraph }, measured, 18.6 / 238, firstUnits = listOf(38))
        assertEquals(3_337L, hold)
        assertTrue(hold > 1_500 + 500)
        assertStartsOnTime(hold, List(12) { paragraph }, measured, 18.6 / 238, 2_230)
        println("b recorded hot OPPO B holdMs=$hold; exceeds legacy+500ms (incompatible constraints)")
    }

    @Test fun anUnmeasuredOrLegacyVoiceKeepsTheExactOldOpeningRule() {
        val file = temp.newFile()
        file.writeText("""{"supertonic:F1":{"chars":1000,"seconds":40,"audioChars":1000,"audio":60}}""")
        val speeds = VoiceSpeeds(file)
        assertNull(speeds.work("supertonic:F1"))
        assertNull(speeds.work("unmeasured"))
        assertEquals(1_500L, ReadAheadPolicy.openingHoldMs(2_190, 125, null))
        assertEquals(1_500L, ReadAheadPolicy.openingHoldMs(2_190, 125, speeds.secondsPerChar("supertonic:F1")))
        assertEquals(1_500L, ReadAheadPolicy.openingHoldMs(20_000, 125, null))
        assertEquals(0L, ReadAheadPolicy.openingHoldMs(2_190, null, null))
        println("c unmeasured holdMs=1500; legacy JSON holdMs=1500")
    }

    @Test fun sustainedChapterRtfOfOneOrMoreNeverHolds() {
        val paragraphs = List(12) { OpeningParagraph(listOf(100)) }
        assertEquals(0L, OpeningSchedule.holdMs(6_000, paragraphs, VoiceWork(1.0, 0.05), 0.06, firstUnits = listOf(100)))
        assertEquals(0L, OpeningSchedule.holdMs(6_000, paragraphs, VoiceWork(1.2, 0.05), 0.06, firstUnits = listOf(100)))
        assertEquals(0L, OpeningSchedule.holdMs(2_190, opening + body, work, audio, 2.0, listOf(37)))
        println("d chapter RTF=1 / >1 / speed 2x: holdMs=0")
    }

    @Test fun theFitMeasuresBothCoefficientsAndPersistsItsWeightedWindow() {
        val file = temp.newFile()
        val speeds = VoiceSpeeds(file)
        val shapes = listOf(5 to 1, 8 to 1, 125 to 2, 287 to 2)
        for ((chars, units) in shapes.take(3)) speeds.record("v", chars, work.seconds(chars, units), chars * audio, units)
        assertNull("ba mẫu chưa đủ", speeds.work("v"))
        speeds.record("v", 287, work.seconds(287, 2), 287 * audio, 2)
        assertEquals(a, VoiceSpeeds(file).work("v")!!.perUnit, 1e-9)
        assertEquals(b, VoiceSpeeds(file).work("v")!!.perChar, 1e-9)
        assertEquals(audio, VoiceSpeeds(file).audioPerChar("v")!!, 1e-9)
        repeat(1000) { i ->
            val (chars, units) = shapes[i % shapes.size]
            speeds.record("v", chars, 2.0 * units + 0.05 * chars, units = units)
        }
        assertEquals(2.0, speeds.work("v")!!.perUnit, 0.001)
        assertEquals(0.05, speeds.work("v")!!.perChar, 0.0001)
        assertNull(speeds.work("other"))
    }

    @Test fun equalLengthUnitsCannotMeasureTheFixedCostSeparately() {
        val speeds = VoiceSpeeds(temp.newFile())
        repeat(10) { speeds.record("v", 200, 8.0, units = 2) }
        assertNull(speeds.work("v"))
    }

    @Test fun recordingAndPlanningUseTheSameRealSupertonicCuts() {
        val text = "Hồ Quang trở lại thăm cây đa đầu làng vào một sớm đầu thu. Lý Nam chậm rãi bước qua cánh đồng lúa chín vào lúc sương còn dày."
        val speeds = VoiceSpeeds(temp.newFile())
        for (paragraph in listOf("Hả?", "Ai đó?", text, "$text $text")) {
            val (tokens, units) = LocalLive.unitsOf("supertonic:F1", paragraph, null, null)!!
            val lengths = units.map { it.text(tokens).length }
            speeds.recordRead("supertonic:F1", paragraph, null, null, work.seconds(lengths.sum(), lengths.size), paragraph.length * audio)
        }
        assertEquals(a, speeds.work("supertonic:F1")!!.perUnit, 1e-9)
        assertEquals(b, speeds.work("supertonic:F1")!!.perChar, 1e-9)
    }

    @Test fun theChapterScheduleUsesTheVoiceCutsSceneGapsAndCacheOfEveryParagraph() {
        // Lịch cả chương (ReadAloud tính ở luồng nền): cùng khúc thật, quãng lặng và đoạn có sẵn như dựng tay rồi gọi holdMs.
        val text = "Hồ Quang trở lại thăm cây đa đầu làng vào một sớm đầu thu. Lý Nam chậm rãi bước qua cánh đồng lúa chín vào lúc sương còn dày."
        val chapter = listOf("Chương 1: Sớm thu", "Hả?", "Ai đó?", "***", text, "$text $text", "Ừ.") + List(12) { "$text $text $text" }
        val gaps = IntArray(chapter.size).also { it[3] = 1_200 }
        for (voice in listOf("supertonic:F1", "vieneu:nano/Đức Trí")) {
            val shapes = chapter.mapIndexed { index, paragraph ->
                if (index == 3) OpeningParagraph(emptyList(), silenceMs = 1_200) else {
                    val (tokens, units) = LocalLive.unitsOf(voice, paragraph, null, null)!!
                    OpeningParagraph(units.map { it.text(tokens).length }, paragraph.length, paragraph == "Ai đó?")
                }
            }
            assertTrue(shapes[5].units.size > 1)
            val expected = OpeningSchedule.holdMs(2_190, shapes.drop(1), work, audio, 1.0, shapes[0].units)
            val hold = OpeningSchedule.forChapter(voice, chapter, { it == 3 }, gaps, 0, 2_190, work, audio, 1.0, null, null) { it == "Ai đó?" }
            assertEquals(expected, hold)
            assertTrue(hold > 0)
            assertEquals(OpeningSchedule.holdMs(2_190, shapes.drop(2), work, audio, 1.0, shapes[1].units),
                OpeningSchedule.forChapter(voice, chapter, { it == 3 }, gaps, 1, 2_190, work, audio, 1.0, null, null) { it == "Ai đó?" })
        }
        assertThrows(IllegalStateException::class.java) {
            OpeningSchedule.forChapter("edge:vi-VN-HoaiMyNeural", chapter, { false }, gaps, 0, 2_190, work, audio, 1.0, null, null) { false }
        }
    }

    @Test fun aStreamThatBreaksWhileHeldLeavesTheQueueSoOnlyItsReplacementIsReleased() {
        // Codex P1: mục phát luồng đã vào hàng giữ rồi lượt đọc hỏng trước hạn - trước đây tới hạn nhả cả mục hỏng lẫn clip thay nối sau nó.
        val queue = OpeningQueue("heading", scheduled = true)
        queue.items += "short paragraph"
        queue.items += "live:7"
        assertTrue(queue.withdraw { it == "live:7" })
        assertFalse("đã bỏ rồi", queue.withdraw { it == "live:7" })
        queue.items += "clip:7"
        assertFalse(queue.releases(ready = true))
        assertTrue(queue.releases(ready = false))
        assertEquals(listOf("heading", "short paragraph", "clip:7"), queue.items)
        assertFalse("clip đang giữ không bao giờ bị bỏ", OpeningQueue("live:7", scheduled = true).withdraw { it == "live:7" })
    }

    @Test fun changingTheVoiceWhileNothingPlaysYetRestartsTheWaitingPlace() {
        // Codex P2: đang giữ clip đầu (ExoPlayer rỗng) mà đổi giọng - trước đây không làm gì, đoạn đã giữ và lượt đang chạy vẫn giọng cũ.
        assertEquals(ReadAloud.VoiceSwitch.RESTART, ReadAloud.VoiceSwitch.of(null, waitingText = true, failed = false))
        assertEquals(ReadAloud.VoiceSwitch.REQUEUE, ReadAloud.VoiceSwitch.of(3, waitingText = false, failed = false))
        assertEquals(ReadAloud.VoiceSwitch.REQUEUE, ReadAloud.VoiceSwitch.of(0, waitingText = true, failed = false))
        assertEquals("chương audio", ReadAloud.VoiceSwitch.NONE, ReadAloud.VoiceSwitch.of(-1, waitingText = false, failed = false))
        assertEquals("đang dừng vì lỗi: bấm phát mới đọc lại", ReadAloud.VoiceSwitch.NONE, ReadAloud.VoiceSwitch.of(null, waitingText = true, failed = true))
        assertEquals("chờ chương audio / không chờ gì", ReadAloud.VoiceSwitch.NONE, ReadAloud.VoiceSwitch.of(null, waitingText = false, failed = false))
    }

    @Test fun aScheduledOpeningQueuesBothFinishedAndStreamingClipsUntilTheDeadline() {
        val queue = OpeningQueue("heading", scheduled = true)
        queue.items += "short paragraph"
        assertFalse(queue.releases(ready = true))
        queue.items += "streaming paragraph"
        assertFalse(queue.releases(ready = true))
        assertTrue(queue.releases(ready = false)) // hết hạn hay hỏng: phần đã có được phát theo đúng thứ tự
        assertEquals(listOf("heading", "short paragraph", "streaming paragraph"), queue.items)
        assertTrue(OpeningQueue("heading", scheduled = false).releases(ready = true))
    }

    @Test fun cachedParagraphsScenePausesAndTheHorizonDoNotCreateExtraWork() {
        val paragraphs = opening.map { it.copy(cached = true) } + OpeningParagraph(emptyList(), silenceMs = 60_000) + body
        assertEquals(0L, OpeningSchedule.holdMs(2_190, paragraphs, work, audio))
        assertEquals(0L, OpeningSchedule.holdMs(60_000, opening + body, work, audio))
        val cramped = List(20) { OpeningParagraph(listOf(5)) } + List(100) { OpeningParagraph(listOf(200)) }
        assertEquals(6_000L, OpeningSchedule.holdMs(2_190, cramped, work, audio))
    }

    @Test fun theMarginAlsoCoversAParagraphThatIsOnlyJustInTime() {
        // Khúc đầu xong ở 4 s, tiêu đề hết ở 4,1 s: thêm đúng 0,1 s để có biên 0,2 s, không tự ép lên một mức giữ tối thiểu.
        assertEquals(100L, OpeningSchedule.holdMs(4_100, List(10) { OpeningParagraph(listOf(100)) }, VoiceWork(0.0, 0.04), 0.06))
    }
}
