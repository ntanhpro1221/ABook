import QtQuick
import ABook

// Một nhóm thẻ việc (WorkCards của WorkInbox.tsx): đúng thẻ của hộp "Việc cần duyệt", sửa ngay trên thẻ. Hộp việc dùng cho cả bốn nhóm của nó, màn "Duyệt trước khi thu"
// dùng cho các bước duyệt. `activeKey`: thẻ đang chọn bằng phím J / K.
StudioRows {
    id: root
    objectName: "workCards"
    property var work: null
    property bool voicePick: false
    property string activeKey: ""
    signal openReview(string card)
    signal openScript(int chapterId, string stableId, bool pick, string card)
    signal openNames(string name, string card)
    signal pickVoice(var person)
    keyField: "key"
    delegate: WorkCard {
        property var modelData: ({})
        work: root.work
        item: modelData || ({})
        active: Boolean(modelData) && modelData.key === root.activeKey
        scriptLinks: Boolean(modelData) && !modelData.requested
        namesLink: true
        voicePick: root.voicePick
        onOpenReview: card => root.openReview(card)
        onOpenScript: (chapterId, stableId, pick, card) => root.openScript(chapterId, stableId, pick, card)
        onOpenNames: (name, card) => root.openNames(name, card)
        onPickVoice: person => root.pickVoice(person)
    }
}
