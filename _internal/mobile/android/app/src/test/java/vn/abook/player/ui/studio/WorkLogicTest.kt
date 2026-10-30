package vn.abook.player.ui.studio

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Logic thuần của ba tab nội dung: bộ bài, mẫu thẻ, thân yêu cầu (lines[{stableId,textSha256}], seen), phân tích JSON, chữ của bảng giọng. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class WorkLogicTest {
    // ---- bộ bài ----

    @Test fun theDeckKeepsOpenCardsInServerOrderAndPutsSkippedOnesLast() {
        val a = speakerCard("a")
        val b = speakerCard("b")
        val c = speakerCard("c")
        val decided = speakerCard("d").copy(requested = "Noah")
        val later = workItem(key = "e", redoOnly = true)
        assertEquals(listOf("a", "b", "c"), WorkLogic.deck(listOf(a, b, c, decided, later), emptySet(), emptyList()).map { it.key })
        assertEquals(listOf("b", "c", "a"), WorkLogic.deck(listOf(a, b, c), emptySet(), listOf("a")).map { it.key })
        assertEquals(listOf("c", "a", "b"), WorkLogic.deck(listOf(a, b, c), emptySet(), listOf("a", "b")).map { it.key })
        assertEquals(listOf("a", "c"), WorkLogic.deck(listOf(a, b, c), setOf("b"), emptyList()).map { it.key })
    }

    @Test fun eachKindPicksItsTemplateInTheWebOrder() {
        assertEquals(CardTemplate.Listen, WorkLogic.template(workItem(kind = WorkKind.Audio)))
        assertEquals(CardTemplate.Reading, WorkLogic.template(workItem(kind = WorkKind.Pronunciation, surface = "Hên-kơ")))
        assertEquals(CardTemplate.Plain, WorkLogic.template(workItem(kind = WorkKind.Pronunciation)))
        val section = NarratorSection(1, 0, 5, "Kati", "", emptyList(), null)
        assertEquals(CardTemplate.Choose, WorkLogic.template(workItem(kind = WorkKind.Narrator, narratorSection = section)))
        assertEquals(CardTemplate.Refused, WorkLogic.template(workItem(kind = WorkKind.Refused, refused = RefusedRef("voice", "k", 1.0))))
        assertEquals(CardTemplate.Voice, WorkLogic.template(workItem(kind = WorkKind.VoiceWish)))
        assertEquals(CardTemplate.Voice, WorkLogic.template(workItem(kind = WorkKind.Gender, voiceChoices = listOf(VoiceOption("Nữ", "kati", "female", null, null, null, null, true)))))
        assertEquals(CardTemplate.Choose, WorkLogic.template(speakerCard()))
        assertEquals(CardTemplate.Choose, WorkLogic.template(workItem(kind = WorkKind.Snap, lines = listOf(lineRef("s1")), choices = emptyList())))
        assertEquals(CardTemplate.Plain, WorkLogic.template(workItem(kind = WorkKind.Turn)))
    }

    @Test fun whatTheListenerWroteAlreadyTakesTheCardOutOfTheDeck() {
        assertTrue(WorkLogic.isOpen(speakerCard()))
        assertFalse(WorkLogic.isOpen(speakerCard().copy(requested = "Noah")))
        assertFalse(WorkLogic.isOpen(speakerCard().copy(redoOnly = true)))
    }

    @Test fun twoCardsDecidingTheSameLineAreOneWaitingChange() {
        val first = speakerCard("a").copy(requested = "Noah")
        val second = speakerCard("b").copy(requested = "Noah")
        val kept = speakerCard("c", "s9").copy(requested = "Kati")
        assertEquals(1, WorkLogic.waitingChanges(listOf(first, second)))
        assertEquals(1, WorkLogic.waitingChanges(listOf(first, second, kept)))
    }

    @Test fun applyWhenFollowsThePhaseAndThePromiseTextFollowsApplyWhen() {
        assertEquals(ApplyWhen.Start, WorkLogic.applyWhen(studioBook(phase = "idle")))
        assertEquals(ApplyWhen.Cast, WorkLogic.applyWhen(studioBook(phase = "analysis", running = true)))
        assertEquals(ApplyWhen.Running, WorkLogic.applyWhen(studioBook(running = true)))
        assertEquals(ApplyWhen.Done, WorkLogic.applyWhen(studioBook(phase = "done")))
        assertEquals("áp từ chương sau", WorkLogic.pendingNote(ApplyWhen.Running))
    }

    // ---- tô tên ----

    @Test fun markNamesHighlightsWholeNamesOnlyAndLongestFirst() {
        val parts = WorkLogic.markNames("Kati Noah nói với Katia", listOf("kati", "noah", "kati noah"))
        assertEquals(listOf(NamePart("Kati Noah", true), NamePart(" nói với Katia", false)), parts)
        assertEquals(listOf(NamePart("Không có tên", false)), WorkLogic.markNames("Không có tên", listOf("zed")))
        assertEquals(listOf(NamePart("x", false)), WorkLogic.markNames("x", emptyList()))
    }

    // ---- thân yêu cầu ----

    @Test fun aSpeakerChoiceSendsEveryLineWithItsHashAndTheSeenMap() {
        val card = speakerCard()
        val decision = WorkDecisions.speaker(card, "noah", WorkScope.Alternate, null)
        assertEquals("k1", decision.key)
        assertTrue(decision.hold)
        val body = decision.steps.single().body
        assertEquals("speaker", decision.steps.single().endpoint)
        assertEquals("noah", body.getString("speaker"))
        val line = body.getJSONArray("lines").getJSONObject(0)
        assertEquals("s1", line.getString("stableId"))
        assertEquals("h-s1", line.getString("textSha256"))
        assertEquals("kati", body.getJSONObject("seen").getString("s1"))
        assertEquals("Đã ghi: câu này của Noah", decision.summary)
    }

    @Test fun keepingThePersonAlreadyThereSaysSoInsteadOfWriting() {
        val decision = WorkDecisions.speaker(speakerCard(), "kati", WorkScope.Alternate, null)
        assertEquals("Giữ nguyên: câu này của Kati", decision.summary)
    }

    @Test fun theWholeChainScopeSendsEveryLineOfTheChain() {
        val card = speakerCard().copy(allLines = listOf(lineRef("s1"), lineRef("s2"), lineRef("s3")))
        val alternate = WorkDecisions.speaker(card, "noah", WorkScope.Alternate, null).steps.single().body
        val all = WorkDecisions.speaker(card, "noah", WorkScope.All, null).steps.single().body
        assertEquals(1, alternate.getJSONArray("lines").length())
        assertEquals(3, all.getJSONArray("lines").length())
        assertEquals("Đã ghi: 3 câu này của Noah", WorkDecisions.speaker(card, "noah", WorkScope.All, null).summary)
    }

    @Test fun aBracketCardAtBookScopeSetsTheBracketRuleAndAnAliasMergeNamesTheAlias() {
        val bracket = speakerCard().copy(kind = WorkKind.Bracket, allLines = listOf(lineRef("s1"), lineRef("s2")))
        assertTrue(WorkDecisions.speaker(bracket, "noah", WorkScope.All, null).steps.single().body.getBoolean("bracketRule"))
        assertFalse(WorkDecisions.speaker(bracket, "noah", WorkScope.Alternate, null).steps.single().body.has("bracketRule"))
        val alias = speakerCard().copy(kind = WorkKind.Alias)
        assertEquals("kati", WorkDecisions.speaker(alias, "noah", WorkScope.Alternate, null).steps.single().body.getString("alias"))
        assertFalse(WorkDecisions.speaker(alias, "kati", WorkScope.Alternate, null).steps.single().body.has("alias"))
    }

    @Test fun aNewPersonSendsTheirGender() {
        val body = WorkDecisions.speaker(speakerCard(), "Mira", WorkScope.Alternate, null, "female").steps.single().body
        assertEquals("female", body.getString("newGender"))
        assertEquals("", WorkDecisions.speaker(speakerCard(), "noah", WorkScope.Alternate, null).steps.single().body.getString("newGender"))
    }

    @Test fun aPickCardSendsOnlyTheLinesStillPicked() {
        val lines = listOf(lineRef("s1"), lineRef("s2"), lineRef("s3"))
        val card = speakerCard().copy(lines = lines, pick = true)
        var left = emptySet<String>()
        left = WorkLogic.toggleLine(left, "s2")
        val picked = WorkLogic.pickedLines(lines, left)
        assertEquals(listOf("s1", "s3"), picked.map { it.stableId })
        assertEquals(2, WorkDecisions.speaker(card, "noah", WorkScope.Alternate, picked).steps.single().body.getJSONArray("lines").length())
        assertEquals("Đang chọn 2/3 câu", WorkLogic.pickNote(2, 3))
        assertEquals("Đang chọn cả 3 câu", WorkLogic.pickNote(3, 3))
        assertEquals("Chưa chọn câu nào trong 3 câu", WorkLogic.pickNote(0, 3))
        assertEquals(setOf<String>(), WorkLogic.toggleLine(left, "s2"))
    }

    @Test fun keepAllWritesOneRequestPerRoleAndRefusesACardWithNothingToKeep() {
        val card = workItem(
            key = "g", keepLabel = "Giữ như cũ",
            keepGroups = listOf(SpeakerRequest(listOf(lineRef("s1")), "a"), SpeakerRequest(listOf(lineRef("s2")), "b")),
        )
        val decision = WorkDecisions.keepAll(card)!!
        assertEquals(listOf("a", "b"), decision.steps.map { it.body.getString("speaker") })
        assertEquals("Đã ghi: Giữ như cũ", decision.summary)
        assertNull(WorkDecisions.keepAll(workItem()))
    }

    @Test fun aReadingSendsTheSeenSpokenFormAndHasItsOwnCheckAndPreviewSteps() {
        val card = workItem(kind = WorkKind.Pronunciation, key = "p", surface = "Hên-kơ", current = "hen co", requested = null)
        val body = WorkDecisions.pronunciation(card, "hen cơ").steps.single().body
        assertEquals("Hên-kơ", body.getString("surface"))
        assertEquals("hen cơ", body.getString("spokenForm"))
        assertEquals("", body.getString("seen"))
        assertEquals("pronunciation/check", WorkDecisions.pronunciationCheck(card, "hen cơ").endpoint)
        assertEquals("pronunciation/preview", WorkDecisions.pronunciationPreview(card, "hen cơ").endpoint)
        assertEquals("Giữ cách đọc “hen co”", WorkDecisions.pronunciation(card, "hen co").summary)
    }

    @Test fun aNarratorSectionSendsItsWindowAndTheAction() {
        val section = NarratorSection(3, 10, 20, "Kati", "", emptyList(), NarratorHeading("l", "noah", "Noah"))
        val card = workItem(kind = WorkKind.Narrator, key = "n", current = "Kati", narratorSection = section)
        val body = WorkDecisions.narrator(card, "choose", "mira")!!.steps.single().body
        assertEquals(3, body.getInt("chapterIndex"))
        assertEquals(10, body.getInt("fromSeq"))
        assertEquals(20, body.getInt("toSeq"))
        assertEquals("choose", body.getString("action"))
        assertEquals("mira", body.getString("narrator"))
        assertEquals("Đã ghi: đoạn này do Noah kể", WorkDecisions.narrator(card, "accept")!!.summary)
        assertEquals("Giữ nguyên: đoạn này vẫn do Kati kể", WorkDecisions.narrator(card, "keep")!!.summary)
        assertNull(WorkDecisions.narrator(workItem(), "keep"))
    }

    @Test fun voiceBodiesCarryOnlyWhatTheButtonSets() {
        val choice = VoiceOption("Nữ", "kati", "female", null, null, "đổi giọng, thu lại 12 câu", "Kati là nữ", true)
        val voice = WorkDecisions.voice(workItem(kind = WorkKind.Gender), choice)
        assertEquals("Đã ghi: Kati là nữ", voice.summary)
        val body = voice.steps.single().body
        assertEquals("female", body.getString("gender"))
        assertFalse(body.has("preset"))
        val keep = WorkDecisions.voiceKeep(workItem(keepCharacters = listOf("a", "b")))!!
        assertEquals(2, keep.steps.size)
        assertFalse(keep.steps[0].body.has("gender"))
        val pick = WorkDecisions.voicePick("kati", "Kati", "Ngọc Huyền", "ngoc", "female", 7.0)
        assertEquals("voice:kati", pick.key)
        assertEquals("Đã ghi: Kati đọc bằng giọng Ngọc Huyền và là nữ", pick.summary)
        assertEquals(7.0, pick.steps.single().body.getDouble("seen"), 0.0)
        val withdraw = WorkDecisions.voiceWithdraw("kati", 7.0)
        assertFalse(withdraw.hold)
        assertTrue(withdraw.steps.single().body.getBoolean("withdraw"))
    }

    @Test fun aReviewVerdictBodyCarriesTheAudioHashAndTheSeenVerdictOrNull() {
        val body = WorkDecisions.review("r1", 4, "sha", "ok", "redo").body
        assertEquals("ok", body.getString("verdict"))
        assertEquals("redo", body.getJSONObject("seen").getString("r1"))
        assertEquals("sha", body.getString("audioSha256"))
        assertTrue(WorkDecisions.review("r1", 4, "sha", null, null).body.isNull("verdict"))
    }

    @Test fun theUndoHoldIsFifteenSeconds() {
        assertEquals(15_000L, WorkDecisions.UNDO_MS)
    }

    // ---- JSON ----

    @Test fun workJsonKeepsKnownKindsAndDropsUnknownOnes() {
        val json = JSONObject(
            """{"items":[
              {"kind":"speaker","key":"a","title":"Ai nói?","lines":[{"stableId":"s1","textSha256":"h"}],"choices":[{"label":"Kati","value":"kati"}],"seen":{"s1":"kati"},"currentValue":"kati","examples":[{"segmentId":3,"text":"Chào","names":["kati"],"hasAudio":true}]},
              {"kind":"from-the-future","key":"z"},
              {"kind":"refused","key":"r","refused":{"section":"voice","key":"kati","requestedAt":12.5}}
            ],"counts":{"speaker":1,"from-the-future":4}}""",
        )
        val view = StudioWorkJson.view(json)
        assertEquals(listOf("a", "r"), view.items.map { it.key })
        assertEquals(mapOf(WorkKind.Speaker to 1), view.counts)
        val item = view.items[0]
        assertEquals("h", item.lines!![0].textSha256)
        assertEquals(mapOf("s1" to "kati"), item.seen)
        assertTrue(item.examples[0].hasAudio)
        assertEquals(12.5, view.items[1].refused!!.requestedAt, 0.0)
        assertTrue(item.suggested)
    }

    @Test fun reviewJsonReadsTheClipWindowAndTheVerdict() {
        val page = StudioReviewJson.page(
            JSONObject(
                """{"counts":{"failed":2},"pending":2,"redoChapters":[1],"remaining":0,
                "items":[{"segmentId":9,"stableId":"r9","audioSha256":"a","chapterId":2,"text":"x","kind":"name-low","playable":false,"chapterClip":{"start":1.5,"end":3},"verdict":"ok"}]}""",
            ),
        )
        assertEquals(2, page.pending)
        assertEquals(listOf(1), page.redoChapters)
        val item = page.items.single()
        assertEquals(ReviewKind.NameLow, item.kind)
        assertEquals(ChapterWindow(1.5, 3.0), item.chapterClip)
        assertEquals("ok", item.verdict)
        assertNull(page.nextCursor)
    }

    @Test fun castAndVoicesJsonRead() {
        val cast = StudioCastJson.cast(
            JSONObject(
                """{"narrator":{"voice":"Giọng A","lines":3,"profile":{"key":"k","preset":"p","label":"Giọng A"}},
                "characters":[{"name":"kati","displayName":"Kati","lines":4,"sampleId":7,"voice":{"key":"k","preset":"p","label":"Giọng B"},"pendingVoice":{"preset":"q","label":"Giọng C","gender":"female"}}],
                "extras":[],"carried":[]}""",
            ),
        )
        assertEquals("Giọng A", cast.narrator.profile?.label)
        val kati = cast.characters.single()
        assertEquals(7, kati.sampleId)
        assertEquals("Giọng C", kati.pendingVoice?.label)
        val choices = StudioCastJson.voices(
            JSONObject(
                """{"character":{"value":"kati","label":"Kati","gender":"female","lines":4,"chapters":1},"current":"p",
                "pending":{"name":"Giọng C","requestedAt":5.5},"rerecord":{"lines":4,"seconds":30,"measured":false},
                "voices":[{"key":"a","name":"Ngọc","engine":"vieneu","engineLabel":"VieNeu","gender":"female","genderLabel":"Nữ","preview":true,"current":true}]}""",
            ),
        )
        assertEquals(5.5, choices.pending!!.requestedAt, 0.0)
        assertFalse(choices.rerecord!!.measured)
        assertTrue(choices.voices.single().current)
    }

    // ---- bảng giọng ----

    @Test fun voicesAreGroupedByEngineAndFilteredByGender() {
        val voices = listOf(voiceEntry("a", gender = "male"), voiceEntry("b", gender = "female"), voiceEntry("c", gender = "female", engine = "other"))
        assertEquals(listOf("a"), VoiceLogic.byGender(voices, GenderFilter.Male).map { it.key })
        assertEquals(3, VoiceLogic.byGender(voices, GenderFilter.All).size)
        val groups = VoiceLogic.groups(voices)
        assertEquals(listOf("vieneu", "other"), groups.map { it.engine })
        assertEquals(listOf("Giọng chính", "Giọng thêm"), VoiceLogic.groupLabels(groups))
    }

    @Test fun theGenderFilterOpensOnTheCurrentVoicesGenderThenTheCharacters() {
        val female = voiceChoices(gender = "male", voices = listOf(voiceEntry("a", gender = "female", current = true)))
        assertEquals(GenderFilter.Female, VoiceLogic.defaultFilter(female))
        assertEquals(GenderFilter.Female, VoiceLogic.defaultFilter(voiceChoices(gender = "female", voices = listOf(voiceEntry("a")))))
        assertEquals(GenderFilter.Male, VoiceLogic.defaultFilter(voiceChoices(gender = "", voices = emptyList())))
    }

    @Test fun theTryKeyAndRefusalTextMatchTheWeb() {
        assertEquals(VoiceLogic.tryKey("b", "kati", "p"), VoiceLogic.tryKey("b", "kati", "p"))
        assertFalse(VoiceLogic.tryKey("b", "kati", "p") == VoiceLogic.tryKey("b", "kati", "q"))
        assertEquals("Card đồ hoạ đang bận - thử lại sau ít phút", VoiceLogic.refusalText("gpu", "x", false))
        assertEquals("lời máy", VoiceLogic.refusalText("producing", "lời máy", true))
        assertEquals("Máy đang làm sách; thử lại khi xong.", VoiceLogic.refusalText("producing", "lời máy", false))
    }
}
