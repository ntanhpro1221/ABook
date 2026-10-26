import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

// Mục "Bộ giọng" (LocalVoiceModules của listen/VieneuModuleCard.tsx): hai thẻ giọng trên máy (VieNeu, Supertonic) + một dòng khuyên tải bộ nào. Tóm tắt ở đầu
// mục nói bộ nào đang tải / đo. Tải / đo / gỡ xong ở thẻ nào thì thẻ kia hỏi lại (phần dùng chung tính lại cỡ) và `changed()` để danh sách giọng hỏi lại.
VoiceFold {
    id: root
    readonly property alias vieneu: vieneuCard
    readonly property alias supertonic: supertonicCard
    readonly property var advice: VoiceLogic.moduleAdvice(vieneuCard.status, supertonicCard.status)
    property string keptAdvice: ""
    signal changed()
    signal switched(string voice)
    storageKey: "voice.modules"
    title: "Bộ giọng"
    summary: VoiceLogic.moduleActivity(vieneuCard.status, supertonicCard.status)
    onAdviceChanged: if (advice.advice !== "") keptAdvice = advice.advice
    function refresh() { vieneuCard.refresh(); supertonicCard.refresh() }

    // Một dòng khuyên (max-w-xl), cách 20 với thẻ dưới
    VoiceBlock {
        width: parent.width
        gap: 0
        show: root.advice.advice !== ""
        Text {
            width: Math.min(parent.width, 576)
            bottomPadding: 20
            text: root.keptAdvice
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: 13
        }
    }
    VoiceModule {
        id: vieneuCard
        width: parent.width
        copy: VoiceLogic.VIENEU
        onChanged: { supertonicCard.refresh(); root.changed() }
        onSwitched: voice => root.switched(voice)
    }
    VoiceBlock {
        width: parent.width
        gap: 20
        show: supertonicCard.ready
        VoiceModule {
            id: supertonicCard
            width: parent.width
            copy: VoiceLogic.SUPERTONIC
            preselect: root.advice.preselectSupertonic
            onChanged: { vieneuCard.refresh(); root.changed() }
            onSwitched: voice => root.switched(voice)
        }
    }
}
