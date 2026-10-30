package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextReplacement
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Ba tab nội dung trên JVM với nguồn giả: thẻ việc trả lời được và hoàn tác được, thẻ cách đọc kiểm trước khi giữ, danh sách nghe lại, dàn nhân vật và bảng giọng. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class StudioWorkScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val sheets = SheetHost()
    private val source = FakeStudioSource(listOf(studioBook(running = true)))
    private val hub = StudioHub(source, scope)
    private var listened = 0

    private fun project(tab: StudioTab): StudioProjectState = StudioProjectState(hub.session(""), "b1", tab, never).also { state ->
        rule.setContent {
            AbookTheme(false) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    StudioProjectScreen(state, sheets, {}, { listened++ }, true)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun tag(tag: String) = rule.onNodeWithTag(tag)
    private fun absent(tag: String) = assertEquals(0, rule.onAllNodesWithTag(tag).fetchSemanticsNodes().size)

    // ---- Việc cần duyệt ----

    @Test fun anAnsweredCardSlidesAwayAndOffersUndoWithoutSendingAnything() {
        source.workView = WorkView(listOf(speakerCard("a"), speakerCard("b").copy(title = "Câu thứ hai")), emptyMap())
        project(StudioTab.Work)
        tag("studio_work_count").assertTextEquals("Còn 2 việc")
        tag("studio_card_title").assertTextEquals("Ai nói câu này?")
        tag("studio_choice_1").performScrollTo().performClick()
        rule.waitForIdle()
        tag("studio_undo_text").assertTextEquals("Đã ghi: câu này của Noah")
        tag("studio_work_count").assertTextEquals("Còn 1 việc")
        assertTrue(source.writes.isEmpty())
        tag("studio_undo_undo").performClick()
        rule.waitForIdle()
        tag("studio_work_count").assertTextEquals("Còn 2 việc")
        absent("studio_undo")
        assertTrue(source.writes.isEmpty())
    }

    @Test fun skippingNeedsMoreThanOneCardAndMovesTheCardToTheBottomWithoutSending() {
        source.workView = WorkView(listOf(speakerCard("a").copy(title = "Thẻ một"), speakerCard("b").copy(title = "Thẻ hai")), emptyMap())
        project(StudioTab.Work)
        tag("studio_card_title").assertTextEquals("Thẻ một")
        tag("studio_card_skip").performScrollTo().performClick()
        rule.waitForIdle()
        tag("studio_card_title").assertTextEquals("Thẻ hai")
        tag("studio_work_count").assertTextEquals("Còn 2 việc")
        assertTrue(source.writes.isEmpty())
    }

    @Test fun aLoneCardHasNoSkip() {
        source.workView = WorkView(listOf(speakerCard("a")), emptyMap())
        project(StudioTab.Work)
        absent("studio_card_skip")
    }

    @Test fun anEmptyDeckSaysEverythingIsReviewed() {
        project(StudioTab.Work)
        tag("studio_work_empty").assertIsDisplayed()
        absent("studio_card_title")
    }

    @Test fun aReadingCardKeepsTheMachinesReadingOrChecksWhatYouTyped() {
        val reading = workItem(kind = WorkKind.Pronunciation, key = "p", title = "Đọc “Hên-kơ” thế nào?", surface = "Hên-kơ", current = "hen co")
        source.workView = WorkView(listOf(reading), emptyMap())
        project(StudioTab.Work)
        tag("studio_reading_keep").assertTextEquals("Đúng rồi, giữ “hen co”")
        tag("studio_reading_save").assertIsNotEnabled()
        tag("studio_reading_field").performScrollTo().performTextReplacement("hen co2")
        rule.waitForIdle()
        tag("studio_reading_save").performScrollTo().performClick()
        rule.waitForIdle()
        assertEquals(listOf("pronunciation/check"), source.writes.map { it.first })
        tag("studio_undo_text").assertTextEquals("Đã ghi: “Hên-kơ” đọc là “hen co2”")
    }

    @Test fun aRejectedReadingStaysUnderTheFieldAndIsNeverHeld() {
        val reading = workItem(kind = WorkKind.Pronunciation, key = "p", surface = "Hên-kơ", current = "hen co")
        source.workView = WorkView(listOf(reading), emptyMap())
        source.writeError = { vn.abook.player.StudioError.Server("Không đọc được chữ này", 400, """{"suggestion":"hen cơ"}""") }
        project(StudioTab.Work)
        tag("studio_reading_field").performScrollTo().performTextReplacement("hen!")
        rule.waitForIdle()
        tag("studio_reading_save").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Không đọc được chữ này").assertIsDisplayed()
        rule.onNodeWithText("Dùng “hen cơ”").assertIsDisplayed()
        absent("studio_undo")
    }

    @Test fun anAudioCardOpensTheReviewTab() {
        source.workView = WorkView(listOf(workItem(kind = WorkKind.Audio, key = "au", title = "Vài câu thu hỏng")), emptyMap())
        val state = project(StudioTab.Work)
        tag("studio_card_listen").performScrollTo().performClick()
        rule.waitForIdle()
        assertEquals(StudioTab.Review, state.tab)
    }

    @Test fun aRefusedRequestCanBeDroppedAtOnce() {
        source.workView = WorkView(listOf(workItem(kind = WorkKind.Refused, key = "r", refused = RefusedRef("voice", "kati", 3.0))), emptyMap())
        project(StudioTab.Work)
        tag("studio_card_drop").performScrollTo().performClick()
        rule.waitForIdle()
        assertEquals(listOf("pending-changes/withdraw"), source.writes.map { it.first })
    }

    // ---- Cần nghe lại ----

    @Test fun theReviewListShowsEachSentenceAndAVerdictIsSentAtOnce() {
        source.reviewPages[""] = emptyReview(listOf(reviewItem(1, text = "Câu đầu"), reviewItem(2, text = "Câu hai")))
        project(StudioTab.Review)
        tag("studio_review_1").assertIsDisplayed()
        tag("studio_review_play_all").assertTextEquals("Nghe liền 2 câu")
        rule.onAllNodesWithTag("studio_review_ok")[0].performClick()
        rule.waitForIdle()
        assertEquals(listOf("review"), source.writes.map { it.first })
        assertEquals("ok", source.writes[0].second.getString("verdict"))
    }

    @Test fun anEmptyReviewOfARecordedBookSaysNothingIsLeftAndAnUnrecordedOneSaysItIsTooEarly() {
        source.reviewPages[""] = emptyReview()
        project(StudioTab.Review)
        tag("studio_review_empty").assertIsDisplayed()
    }

    // ---- Nhân vật ----

    @Test fun theCastListsTheNarratorAndTheCharactersAndATapOpensTheirVoices() {
        source.cast = Cast(
            CastNarrator("Giọng A", 3, 10.0, VoiceProfile("k", "p", "Giọng A", ""), null, 0),
            listOf(castMember("kati", "Kati")), listOf(castMember("lính", "Lính gác")), emptyList(),
        )
        source.voiceChoicesFor["kati"] = voiceChoices("kati", "female", listOf(voiceEntry("v1", "Ngọc Huyền", gender = "female")))
        project(StudioTab.Cast)
        tag("studio_cast_narrator").assertIsDisplayed()
        tag("studio_cast_kati").assertIsDisplayed()
        tag("studio_cast_lính").assertIsDisplayed()
        tag("studio_cast_kati").performClick()
        rule.waitForIdle()
        tag("studio_voice_sheet").assertIsDisplayed()
        tag("studio_voice_v1").assertIsDisplayed()
        tag("studio_voice_choose_v1").performClick()
        rule.waitForIdle()
        tag("studio_undo_text").assertTextEquals("Đã ghi: Kati đọc bằng giọng Ngọc Huyền")
        assertTrue(source.writes.isEmpty())
    }

    @Test fun anEmptyCastSaysWhenCharactersAppear() {
        project(StudioTab.Cast)
        tag("studio_cast_empty").assertIsDisplayed()
    }

    @Test fun onlyTheMusicTabStillHasNoContent() {
        project(StudioTab.Music)
        tag("studio_frame_music").assertIsDisplayed()
    }
}
