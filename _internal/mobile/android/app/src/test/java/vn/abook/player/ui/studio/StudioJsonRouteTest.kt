package vn.abook.player.ui.studio

import android.content.Intent
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Đọc lời đáp của máy tính, và đường mở Studio (đường `/#/studio/...` của web chỉ được đọc, không dựng lại). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StudioJsonRouteTest {
    @Test fun aFullBookSummaryIsRead() {
        val json = JSONObject(
            """{"id":"b1","title":"Tắt đèn","phase":"synthesis","statusLabel":"Đang thu âm","running":true,"canPause":true,"paused":"battery",
            "queuePosition":null,"queueWaitsOn":{"title":"Kia","paused":"listener"},"precast":{"held":true},"pendingChanges":2,
            "chapters":{"total":10,"completed":4,"redo":1},"segments":{"total":100,"analyzed":60,"pending":40},
            "progress":{"overall":0.45,"analysis":1,"synthesis":0.3},"eta":{"phase":"synthesis","seconds":300},
            "speakerPass":{"done":3,"total":9,"active":true},"lastError":null}""",
        )
        val book = StudioJson.book(json)
        assertEquals("b1", book.id)
        assertEquals(StudioPause.Battery, book.paused)
        assertNull(book.queuePosition)
        assertEquals(StudioQueueWait("Kia", StudioPause.Listener), book.queueWaitsOn)
        assertTrue(book.precastHeld)
        assertEquals(10, book.chaptersTotal)
        assertEquals(40, book.segmentsPending)
        assertEquals(0.45f, book.overall, 0.0001f)
        assertEquals(StudioEta("synthesis", 300.0), book.eta)
        assertEquals(StudioSpeakerPass(3, 9, true), book.speaker)
        // JSON null không thành chữ "null".
        assertEquals("", book.lastError)
    }

    @Test fun anOlderMachineWithFewerFieldsStillReads() {
        val book = StudioJson.book(JSONObject("""{"id":"x"}"""))
        assertEquals("x", book.id)
        assertFalse(book.running)
        assertNull(book.paused)
        assertNull(book.eta)
        assertEquals(0f, book.overall, 0f)
    }

    @Test fun aBookWithoutAnIdIsABrokenReply() {
        try {
            StudioJson.book(JSONObject("""{"title":"x"}"""))
            fail("phải ném")
        } catch (expected: org.json.JSONException) {
        }
    }

    @Test fun libraryAndPageParse() {
        val library = StudioJson.library(JSONObject("""{"root":"x","books":[{"id":"a"},{"id":"b"}]}"""))
        assertEquals(listOf("a", "b"), library.map { it.id })
        assertTrue(StudioJson.library(JSONObject("{}")).isEmpty())
        val page = StudioJson.page(JSONObject("""{"book":{"id":"a"},"chapters":[{"id":1,"index":1,"title":"C1","displayTitle":"Chương một","status":"completed","seconds":90.5,"playable":true}]}"""))
        assertEquals("a", page.book.id)
        assertEquals("Chương một", page.chapters.single().title)
        assertEquals(90.5, page.chapters.single().seconds, 0.0)
        assertTrue(page.chapters.single().playable)
    }

    @Test fun webPathsAreReadInto() {
        assertEquals(StudioRoute(), StudioRoute.parse(null))
        assertEquals(StudioRoute(), StudioRoute.parse("/#/studio"))
        assertEquals(StudioRoute("b1", StudioTab.Chapters), StudioRoute.parse("/#/studio/b1"))
        assertEquals(StudioRoute("b1", StudioTab.Work), StudioRoute.parse("/#/studio/b1?tab=work"))
        assertEquals(StudioRoute("b1", StudioTab.Cast), StudioRoute.parse("/#/studio/b1?x=1&tab=cast"))
        // Màn con của web mở thẳng màn con; tab chưa có ở điện thoại, hay mã lạ: về chỗ gần nhất.
        assertEquals(StudioRoute("b1", StudioTab.Chapters, StudioSubKind.Precast), StudioRoute.parse("/#/studio/b1?tab=precast"))
        assertEquals(StudioRoute("b1", StudioTab.Chapters, StudioSubKind.Script), StudioRoute.parse("/#/studio/b1?tab=script"))
        assertEquals(StudioRoute("b1", StudioTab.Chapters), StudioRoute.parse("/#/studio/b1?tab=activity"))
        assertEquals(StudioRoute(), StudioRoute.parse("/#/studio/../etc"))
        assertEquals(StudioRoute(), StudioRoute.parse("/#/library"))
    }

    @Test fun anIntentCarriesComputerBookAndTab() {
        val intent = StudioRoute.put(Intent(), "pc1", StudioRoute("b2", StudioTab.Review))
        assertEquals(StudioRequest("pc1", StudioRoute("b2", StudioTab.Review)), StudioRoute.request(intent))
        assertEquals(StudioRequest("", StudioRoute()), StudioRoute.request(StudioRoute.put(Intent(), "", StudioRoute())))
        val precast = StudioRoute("b2", sub = StudioSubKind.Precast)
        assertEquals(StudioRequest("pc1", precast), StudioRoute.request(StudioRoute.put(Intent(), "pc1", precast)))
        assertNull(StudioRoute.request(Intent()))
        assertNull(StudioRoute.request(null))
        // Mã sách hỏng trong Intent không mở được gì, nhưng vẫn mở Studio của máy.
        assertEquals(StudioRequest("pc1", StudioRoute()), StudioRoute.request(Intent().putExtra(StudioRoute.EXTRA_COMPUTER, "pc1").putExtra(StudioRoute.EXTRA_BOOK, "../x")))
    }
}
