import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// Nhạc nền của cuốn nhập từ file (MusicSection của listen/EditBook.tsx): người làm sách đã gắn sẵn - người nghe bật / tắt, chỉnh mức, cho im lặng
// từng đoạn, và đổi một đoạn sang bài trong "Nhạc của tôi" (bài ấy đi cùng file sách khi lưu). Một lệnh `PUT /api/books/<mã>/music` cho mọi thay
// đổi; lời đáp là hình mới của nhạc. "Đổi bài" mở tại chỗ dưới đoạn nhạc và có lớp Back riêng (Back đóng nó trước hộp).
Column {
    id: root
    property string bookId: ""
    property var view: null               // hình đã chuẩn hoá (Logic.musicEditView)
    property bool loading: true
    property bool failed: false
    property bool changing: false
    property string choosingLink: ""
    property string swapping: ""          // khoá đoạn nhạc đang mở "Đổi bài"
    property int generation: 0
    signal changed()
    spacing: 12

    function load() {
        const mine = ++generation
        loading = view === null; failed = false
        Api.call("GET", "/api/books/" + bookId + "/music", null, function(data, error) {
            if (mine !== root.generation) return
            root.loading = false
            if (error) { Api.notice = ""; root.failed = root.view === null; return }
            root.view = Logic.musicEditView(data)
        })
    }
    // body: {enabled?, levelDb?, silence?: {khoá: bool}, pins?: {khoá: liên kết | null}}
    function change(body) {
        if (changing) return
        changing = true
        choosingLink = ""
        for (const key in (body.pins || {})) if (body.pins[key]) choosingLink = body.pins[key]
        Api.call("PUT", "/api/books/" + bookId + "/music", body, function(data, error) {
            root.changing = false; root.choosingLink = ""
            if (error) { Api.notice = Logic.toastText("Chưa chỉnh được nhạc nền", error); return }
            root.view = Logic.musicEditView(data)
            root.closeSwap()
            Api.editedBook(root.bookId)
            root.changed()
        })
    }
    QtObject {
        id: swapLayer
        property bool on: false
        function close() { root.closeSwap() }
    }
    function openSwap(key) {
        swapping = key
        if (!swapLayer.on) { swapLayer.on = true; Nav.openLayer(swapLayer) }
    }
    function closeSwap() { swapping = ""; if (swapLayer.on) { swapLayer.on = false; Nav.closedLayer(swapLayer) } }
    Component.onCompleted: load()
    Component.onDestruction: closeSwap()

    Collapse {
        width: parent.width
        open: root.loading
        EditBookSkeleton { width: parent.width; label: "Đang tải nhạc nền" }
    }
    EditBookError {
        width: parent.width
        open: root.failed && !root.loading
        message: "Bạn hãy thử tải lại nhạc nền của cuốn này."
        onRetry: root.load()
    }
    Collapse {
        width: parent.width
        open: !!root.view && !root.view.hasMusic
        Text {
            width: parent.width
            text: "Người làm sách không gắn nhạc nền cho cuốn này."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
    Collapse {
        id: full
        width: parent.width
        open: !!root.view && root.view.hasMusic
        spacing: 12
        Flow {
            width: parent.width
            spacing: 12
            // Công tắc có nhãn hành động rõ ("Nhạc nền: Bật")
            Row {
                height: 36
                spacing: 10
                Switch {
                    objectName: "musicSwitch"
                    anchors.verticalCenter: parent.verticalCenter
                    label: "Nhạc nền"
                    checked: root.view ? root.view.enabled : false
                    enabled: !root.changing
                    onToggled: value => root.change({enabled: value})
                }
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { text: "Nhạc nền: "; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
                    Text { text: root.view && root.view.enabled ? "Bật" : "Tắt"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: 600 }
                }
            }
            Column {
                width: Math.min(260, parent.width)
                spacing: 4
                Text { width: parent.width; text: "Mức nhạc dưới giọng đọc"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                Select {
                    objectName: "musicLevel"
                    width: parent.width
                    label: "Mức nhạc dưới giọng đọc"
                    options: root.view ? Logic.levelOptions(root.view.levelDb) : []
                    value: root.view ? root.view.levelDb : -20
                    onPicked: value => root.change({levelDb: Number(value)})
                }
            }
        }
        // Các đoạn nhạc: cao tối đa 288, cuộn trong khung; tắt nhạc thì mờ đi
        Item {
            width: parent.width
            height: Math.min(cues.contentHeight, 288)
            opacity: root.view && root.view.enabled ? 1 : 0.5
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Flickable {
                id: cues
                anchors.fill: parent
                contentWidth: width
                contentHeight: cueList.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: cueList
                    width: cues.width
                    Repeater {
                        model: root.view ? root.view.cues : []
                        Column {
                            id: cue
                            required property var modelData
                            required property int index
                            width: cueList.width
                            Rectangle { visible: cue.index > 0; width: parent.width; height: 1; color: Theme.line }
                            Flow {
                                width: parent.width
                                topPadding: 8
                                bottomPadding: 8
                                spacing: 4
                                Column {
                                    id: cueWords
                                    width: Math.max(144, cue.width - cueButtons.width - 12)
                                    Text {
                                        width: parent.width
                                        text: cue.modelData.title || "Nhạc nền"
                                        color: cue.modelData.silenced ? Theme.text3 : Theme.text
                                        font.strikeout: cue.modelData.silenced
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeBodySmall
                                    }
                                    Text {
                                        width: parent.width
                                        color: Theme.text2
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeCaption
                                        font.features: {"tnum": 1}
                                        text: cue.modelData.chapter + " · " + Logic.formatClock(cue.modelData.start) + " – " + Logic.formatClock(cue.modelData.end)
                                              + (cue.modelData.creator ? " · " + cue.modelData.creator : "") + (cue.modelData.pinned ? " · bài của bạn" : "")
                                    }
                                }
                                Row {
                                    id: cueButtons
                                    spacing: 4
                                    Button {
                                        visible: !!cue.modelData.pinned
                                        text: "Về bài gốc"; kind: "ghost"; size: "sm"
                                        enabled: !root.changing
                                        onClicked: { const pins = {}; pins[cue.modelData.key] = null; root.change({pins: pins}) }
                                    }
                                    Button {
                                        text: "Đổi bài"; icon: "shuffle"; kind: "ghost"; size: "sm"
                                        enabled: !root.changing
                                        onClicked: root.swapping === cue.modelData.key ? root.closeSwap() : root.openSwap(cue.modelData.key)
                                    }
                                    Button {
                                        text: cue.modelData.silenced ? "Có nhạc" : "Im lặng"; kind: "ghost"; size: "sm"
                                        enabled: !root.changing
                                        onClicked: { const silence = {}; silence[cue.modelData.key] = !cue.modelData.silenced; root.change({silence: silence}) }
                                    }
                                }
                            }
                            Collapse {
                                width: parent.width
                                open: root.swapping === cue.modelData.key
                                EditBookSwap {
                                    width: parent.width
                                    bookId: root.bookId
                                    cueKey: cue.modelData.key
                                    active: root.swapping === cue.modelData.key
                                    busy: root.changing
                                    choosing: root.choosingLink
                                    onChoose: link => {
                                        const pins = {}; pins[cue.modelData.key] = link
                                        const body = {pins: pins}
                                        if (cue.modelData.silenced) { const silence = {}; silence[cue.modelData.key] = false; body.silence = silence }
                                        root.change(body)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            ScrollEdges { target: cues; color: Theme.panel; x: cues.x; y: cues.y; width: cues.width; height: cues.height }
            Scrollbar { target: cues }
        }
        EditBookMyMusic { width: parent.width; onChanged: if (root.swapping !== "") root.load() }
    }
}
