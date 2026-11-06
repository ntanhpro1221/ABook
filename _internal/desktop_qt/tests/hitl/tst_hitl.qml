import QtQuick
import QtTest
import ABook
import "../../qml/WorkLogic.js" as W
import "../../qml/PrecastLogic.js" as P

Item {
    width: 900
    height: 700
    Component { id: factory; WorkSpeaker { width: 850; voicePick: true } }
    Component {
        id: cardFactory
        Rectangle {
            property alias item: card.item
            property alias work: card.work
            width: 850
            height: card.height + 32
            color: Theme.bg
            WorkCard { id: card; x: 16; y: 16; width: parent.width - 32; voicePick: true }
        }
    }
    QtObject {
        id: fake
        property var saved: null
        property var savedLines: null
        property string pendingNote: "chờ áp dụng"
        function saveSpeaker(item, lines, scope, request, done) { saved = request; savedLines = lines; done() }
    }
    TestCase {
        name: "HitlRolesAndCallers"
        when: windowShown
        function test_kind_and_review_scope() {
            compare(W.kindLabel("caller"), "Người gọi / ngoài khung")
            verify(W.BULK_KINDS.indexOf("caller") >= 0)
            verify(P.LINE_KINDS.indexOf("caller") >= 0)
            verify(!W.chipMarked({kind: "caller", suggested: false}, {}, 0))
        }
        function test_role_keeps_all_chapter_lines_and_opens_voice_picker() {
            fake.saved = null
            const item = {kind: "unnamed", currentValue: "NPC_LOCAL::c1::người gác", current: "người gác",
                suggestedName: "Người gác chương 1", pickVoice: {name: "NPC", displayName: "người gác"},
                lines: [{stableId: "a", textSha256: "sha-a"}, {stableId: "b", textSha256: "sha-b"}], choices: []}
            const view = createTemporaryObject(factory, parent, {item: item, work: fake})
            verify(view)
            compare(findChild(view, "speakerName").text, "Người gác chương 1")
            compare(findChild(view, "speakerOther").text, "Đặt tên")
            compare(findChild(view, "speakerVoice").text, "Giới / giọng")
            compare(fake.saved, null)
            mouseClick(findChild(view, "speakerKeep"))
            compare(fake.saved.speaker, item.currentValue)
            compare(fake.savedLines.length, 2)
            const spy = Qt.createQmlObject('import QtTest; SignalSpy {}', view)
            spy.target = view
            spy.signalName = "pickVoice"
            mouseClick(findChild(view, "speakerVoice"))
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0].name, "NPC")
        }
        function test_caller_uses_existing_speaker_request() {
            const item = {kind: "caller", current: "Mai", currentValue: "MAI", suggested: false,
                keepLabel: "Giữ Mai (máy đề xuất)", lines: [{stableId: "a", textSha256: "sha-a"}], choices: []}
            const view = createTemporaryObject(factory, parent, {item: item, work: fake})
            verify(view)
            compare(findChild(view, "speakerKeep").text, item.keepLabel)
            mouseClick(findChild(view, "speakerKeep"))
            compare(fake.saved.speaker, "MAI")
            compare(fake.savedLines[0].textSha256, "sha-a")
        }
        function test_gallery_cards() {
            const cards = [
                {kind: "unnamed", key: "role", title: "“người gác” trong chương này", problem: "Vai phụ nói 2 câu trong chương này. Đặt tên hoặc chọn người đã có; giới / giọng áp cho cả vai.", affected: 2,
                    current: "người gác", currentValue: "NPC", suggestedName: "Người gác chương 1", suggested: false, pickVoice: {name: "NPC", displayName: "người gác"},
                    lines: [{stableId: "a", textSha256: "sha-a"}, {stableId: "b", textSha256: "sha-b"}],
                    choices: [{label: "Mai", value: "MAI"}], examples: [{segmentId: 1, chapterId: 1, chapterTitle: "Chương 1", seq: 1, speaker: "người gác", text: "“Ai đang ở ngoài đó?”", hasAudio: false}], keepLabel: "Giữ người gác (máy đề xuất)"},
                {kind: "caller", key: "caller", title: "Ai nói từ xa?", problem: "Lời kể gợi giọng qua điện thoại: “Đầu dây bên kia có tiếng đáp.” — bạn kiểm tra người nói.", affected: 1,
                    current: "Mai", currentValue: "MAI", suggested: false, lines: [{stableId: "c", textSha256: "sha-c"}], choices: [{label: "Lan", value: "LAN"}],
                    examples: [{segmentId: 3, chapterId: 1, chapterTitle: "Chương 1", seq: 4, speaker: "Mai", text: "“Tôi đang nghe đây.”", before: "Đầu dây bên kia có tiếng đáp.", hasAudio: false}], keepLabel: "Giữ Mai (máy đề xuất)"}
            ]
            for (const theme of ["light", "dark"]) {
              Theme.mode = theme
              for (let i = 0; i < cards.length; ++i) {
                const view = createTemporaryObject(cardFactory, parent, {item: cards[i], work: fake})
                verify(view)
                waitForRendering(view)
                let captured = false
                verify(view.grabToImage(function(result) {
                    captured = result.url.toString().length > 0
                }))
                tryVerify(function() { return captured })
                view.destroy()
              }
            }
            Theme.mode = "auto"
        }
    }
}
