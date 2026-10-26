package vn.abook.player.ui.nowplaying

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PlayerState

class NowPlayingLogicTest {
    private val chapter = PlayerChapter(7, "Chương bảy", 65_000)
    private fun mapped(raw: String) =
        nowPlayingState(PlayerState.from(JSONObject(raw), CoverRef("/cover.jpg", 9), listOf(chapter), "voice:a"), emptyList(), false, 0)

    @Test fun metadataMapsNativePlaybackContract() {
        val state = mapped("""{"bookId":"b","bookTitle":"Sách","chapterId":7,"chapterTitle":"Chương bảy","playing":true,"duration":65.5,"rate":1.25,"sleep":{"mode":"minutes","remaining":891,"minutes":15,"counting":true}}""")
        assertEquals("b", state.bookId); assertEquals("Sách", state.bookTitle)
        assertEquals(7, state.chapterId); assertEquals(65_500L, state.durationMs)
        assertEquals(1.25, state.rate, 0.0); assertTrue(state.playing)
        assertEquals(listOf(chapter), state.chapters); assertEquals(CoverRef("/cover.jpg", 9), state.cover)
        assertTrue(state.readAlongAvailable); assertEquals("voice:a", state.voiceId)
        assertEquals(PlayerSleep(SleepKind.Minutes, 15, true), state.sleep)
    }
    @Test fun decimalRateSurvivesTheMappingSoTheSheetMarksTheChosenCell() {
        assertEquals(1.1, mapped("""{"bookId":"b","chapterId":7,"rate":1.1}""").rate, 0.0)
        assertTrue(PlayerLabels.rates.contains(mapped("""{"bookId":"b","chapterId":7,"rate":0.9}""").rate))
    }
    @Test fun absentChapterDoesNotOfferReadAlong() {
        val state = mapped("""{"chapterId":null}""")
        assertNull(state.chapterId); assertFalse(state.readAlongAvailable)
        assertEquals(1.0, state.rate, 0.0); assertEquals(SleepKind.Off, state.sleep.kind)
    }
    @Test fun clockIsExcludedFromMetadata() {
        val a = mapped("""{"bookId":"b","position":1}""")
        val b = mapped("""{"bookId":"b","position":90}""")
        assertEquals(a, b)
    }
    @Test fun playbackErrorPrecedesSaveError() {
        assertEquals("Mất mạng", mapped("""{"error":"Mất mạng","saveError":"Hết chỗ"}""").error)
        assertEquals("Hết chỗ", mapped("""{"saveError":"Hết chỗ"}""").error)
    }
    @Test fun returnChipFollowsTheRepoBookNotAStaleOne() {
        val player = PlayerState(bookId = "b", chapterId = 7)
        assertTrue(nowPlayingState(player, emptyList(), true, 3).returnAvailable)
        assertEquals(3, nowPlayingState(player, emptyList(), true, 3).returnSerial)
    }
    @Test fun vietnameseRatesMatchWebLabels() {
        assertEquals("1×", PlayerLabels.rate(1.0))
        assertEquals("1,25×", PlayerLabels.rate(1.25))
        assertEquals("0,75×", PlayerLabels.rate(0.75))
        assertEquals("1,1×", PlayerLabels.rate(1.1))
    }
    @Test fun timeClampsAndDoesNotWrapAtHour() {
        assertEquals("0:00", PlayerLabels.time(-1))
        assertEquals("1:05", PlayerLabels.time(65_999))
        assertEquals("61:01", PlayerLabels.time(3_661_000))
    }
    // Matching listen/sleep.test.ts button cases; the time left now comes straight from the one clock.
    @Test fun sleepButtonHasUnitsAndRoundsUp() {
        val sleep = PlayerSleep(SleepKind.Minutes, 15, true)
        assertEquals("15 phút", PlayerLabels.sleep(sleep, 891_000))
        assertEquals("15 phút", PlayerLabels.sleep(sleep, 851_000))
        assertEquals("13 phút", PlayerLabels.sleep(sleep, 771_000))
        assertEquals("41 giây", PlayerLabels.sleep(sleep, 41_000))
        assertEquals("0:41", PlayerLabels.sleep(sleep, 41_000, clock = true))
        assertEquals("Hết chương", PlayerLabels.sleep(PlayerSleep(SleepKind.Chapter), 0))
        assertEquals("Hẹn giờ", PlayerLabels.sleep(PlayerSleep(), 0))
    }
    @Test fun pausedSleepShowsWhatIsLeftAndNeverGoesNegative() {
        assertEquals("10:00", PlayerLabels.sleep(PlayerSleep(SleepKind.Minutes, 10, false), 600_000, true))
        assertEquals("0:00", PlayerLabels.sleep(PlayerSleep(SleepKind.Minutes, 10, true), -50, true))
    }
    @Test fun sleepSubsecondUsesCeiling() {
        assertEquals("0:01", PlayerLabels.sleep(PlayerSleep(SleepKind.Minutes), 1, true))
        assertEquals("1 giây", PlayerLabels.sleep(PlayerSleep(SleepKind.Minutes), 0))
    }

    private val sentenceText = "Trời vừa hửng sáng, sương mù."
    private val spans = "[[100,400],[400,600],[600,900],[900,1500],[1700,2000],[2000,2400]]"
    private val words get() = ReadAlongLookup.words(sentenceText, JSONArray(spans))
    @Test fun tokensUseUnicodeWhitespaceAndKeepOffsets() {
        val text = "  Một hai \n ba  "
        val tokens = ReadAlongLookup.words(text, JSONArray("[[0,1],[1,2],[2,3]]"))
        assertEquals(listOf("Một", "hai", "ba"), tokens.map { text.substring(it.from, it.until) })
        assertEquals(6, words.size)
    }
    @Test fun malformedWordTimingsAreDiscardedAsAWhole() {
        for (raw in listOf("[]", "[[100,400]]", "[[500,600],[100,200]]", "[[100,50],[200,300]]", "[[0,1,2],[2,3]]", "[[\"0\",1],[2,3]]"))
            assertTrue(raw, ReadAlongLookup.words("a b", JSONArray(raw)).isEmpty())
        assertTrue(ReadAlongLookup.words(sentenceText, null).isEmpty())
    }
    @Test fun wordLeadAndBreathGapsMatchWeb() {
        assertEquals(-1, ReadAlongLookup.word(words, 0))
        assertEquals(-1, ReadAlongLookup.word(words, 59))
        assertEquals(0, ReadAlongLookup.word(words, 60))
        assertEquals(0, ReadAlongLookup.word(words, 359))
        assertEquals(1, ReadAlongLookup.word(words, 360))
        assertEquals(2, ReadAlongLookup.word(words, 650))
        assertEquals(3, ReadAlongLookup.word(words, 1600))
        assertEquals(4, ReadAlongLookup.word(words, 1660))
    }
    @Test fun lastWordHoldsExactlyFourHundredMilliseconds() {
        assertEquals(5, ReadAlongLookup.word(words, 2800))
        assertEquals(-1, ReadAlongLookup.word(words, 2801))
        assertEquals(-1, ReadAlongLookup.word(emptyList(), 5000))
    }
    @Test fun tailClipNeverLightsAnEarlierWord() {
        val tail = ReadAlongLookup.words("a b c d", JSONArray("[[0,0],[0,0],[0,400],[500,900]]"))
        for (ms in 0L..600L step 10) assertTrue(ReadAlongLookup.word(tail, ms) >= 2)
    }
    @Test fun longSentenceAdvancesMonotonicallyAtSixtyHz() {
        val words = List(400) { WordTiming(it * 250L, (it + 1) * 250L, it, it + 1) }
        var previous = -1
        for (ms in 0L until 100_000L step 16) {
            val at = ReadAlongLookup.word(words, ms)
            assertTrue(at >= previous); assertTrue(at - previous <= 1)
            previous = at
        }
        assertEquals(399, previous)
    }
    @Test fun sentenceLookupUsesFiftyMillisecondLeadAndLastEqualStart() {
        val paragraphs = listOf(100L, 1000L, 1000L, 2000L).mapIndexed { i, start -> ReadParagraph(i, "câu $i", start, start + 1000, true) }
        assertEquals(-1, ReadAlongLookup.sentence(paragraphs, 49))
        assertEquals(0, ReadAlongLookup.sentence(paragraphs, 50))
        assertEquals(0, ReadAlongLookup.sentence(paragraphs, 949))
        assertEquals(2, ReadAlongLookup.sentence(paragraphs, 950))
        assertEquals(3, ReadAlongLookup.sentence(paragraphs, 9999))
        assertEquals(-1, ReadAlongLookup.sentence(emptyList(), 0))
    }
    @Test fun untimedParagraphDoesNotPretendToBeRead() {
        assertEquals(-1, ReadAlongLookup.sentence(listOf(ReadParagraph(0, "chưa đọc", 0, 1000, false)), 200))
    }
    @Test fun audioAndLiveTextUseTheSameParserWithExactLoadedText() {
        val audio = ReadAlongLookup.parse(JSONObject("""{"timed":true,"segments":[{"text":"Một hai","start":1.5,"end":2,"words":[[1500,1700],[1700,2000]]}]}"""))
        assertEquals("Một hai", audio.single().text); assertEquals(1500L, audio.single().startMs)
        assertEquals(2, audio.single().words.size); assertTrue(audio.single().timed)
        val live = ReadAlongLookup.parse(JSONObject("""{"paragraphs":["Bản đang nghe"],"segments":[{"text":"Bản đã sửa","start":0,"end":2,"timed":true}]}"""))
        assertEquals("Bản đang nghe", live.single().text)
    }
    @Test fun activeTimelineHighlightsAStreamingParagraphBeforeItsClipFinishes() {
        val live = ReadAlongLookup.parse(JSONObject("""{"active":true,"paragraphs":["Một hai"],"segments":[{"start":0,"end":1,"timed":false,"words":[[0,400],[400,1000]]}]}"""))
        assertEquals(0, ReadAlongLookup.sentence(live, 500))
        assertEquals(1, ReadAlongLookup.word(live.single().words, 500))
    }
}
