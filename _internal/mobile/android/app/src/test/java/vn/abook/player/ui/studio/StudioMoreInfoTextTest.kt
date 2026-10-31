package vn.abook.player.ui.studio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Chữ của các lời gập "?" (MoreInfo) của Studio: cùng từng chữ với web (`tests/test_moreinfo_parity.py` giữ nhãn và chữ giữa ba nền). */
class StudioMoreInfoTextTest {
    @Test fun theBatteryPauseSaysOneSentenceAndFoldsTheWhy() {
        val paused = studioBook(running = true, canPause = true, paused = StudioPause.Battery)
        assertTrue(StudioText.onBattery(paused))
        assertEquals("Studio tạm dừng; cắm sạc để tiếp tục.", StudioText.actionNote(paused, null))
        assertFalse(StudioText.onBattery(studioBook(running = true, canPause = true, paused = StudioPause.Listener)))
        assertFalse(StudioText.onBattery(studioBook(running = false, paused = StudioPause.Battery)))
    }

    @Test fun theFirstPersonGuessFollowsTheHint() {
        assertEquals(
            "3/5 chương đầu có lời kể xưng “tôi”. Bạn có thể sửa gợi ý này.",
            StudioNewText.firstPersonGuess(FirstPersonView(true, 0.8, emptyList(), chaptersSampled = 5, chaptersWithI = 3)),
        )
        assertEquals("80% đoạn lời kể có “tôi”. Bạn có thể sửa gợi ý này.", StudioNewText.firstPersonGuess(FirstPersonView(true, 0.8, emptyList())))
        assertEquals("Chọn nhân vật xưng “tôi” trong lời kể. Bạn có thể sửa gợi ý này.", StudioNewText.firstPersonGuess(FirstPersonView(false, 0.0, emptyList())))
    }

    @Test fun theFirstPersonHintCarriesTheChapterCounts() {
        val view = StudioNewJson.firstPerson(org.json.JSONObject("""{"firstPerson":true,"rate":0.5,"chaptersSampled":4,"chaptersWithI":2,"suggestions":["Kati"]}"""))
        assertEquals(4, view.chaptersSampled)
        assertEquals(2, view.chaptersWithI)
    }
}
