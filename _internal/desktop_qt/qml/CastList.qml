import QtQuick
import ABook
import "CastLogic.js" as Logic

// Tab "Nhân vật" của trang sách (CastList của listen/BookScreen.tsx): người kể chuyện, rồi "Vai chính", "Vai phụ" và (cuốn có xưởng) "Từ phần trước" -
// mỗi nhóm một khối gập. Dàn nhân vật hỏi máy chủ khi tab được mở lần đầu (`active`) và hỏi lại mỗi khi sách được sửa (Api.edited). Chưa phân vai:
// "Chưa có dàn nhân vật". Ba trạng thái (đang tải / trống / có người) mờ qua tại chỗ như MotionRegion của web, không đổi cứng.
// Việc của từng người (đổi giọng, gộp, đổi tên, đổi giới tính) do trang sách mở hộp: CastList chỉ phát `request(loại, người)` / `menuRequested`.
// `caps`: rename / merge / gender / voice / unmerge / waiting (xem CastPerson). `reached`: {tên chương: true} tới chỗ đang nghe, null = hiện hết.
Item {
    id: root
    objectName: "castList"
    property string bookId: ""
    property bool active: false
    property var caps: ({})
    property var reached: null
    property var cast: null
    property string status: "idle"          // idle | loading | ready | failed
    property bool later: false              // "Hiện chương sau"
    readonly property var characters: cast && cast.characters ? cast.characters : []
    readonly property var extras: cast && cast.extras ? cast.extras : []
    readonly property var carried: caps.voice && cast && cast.carried ? cast.carried : []
    readonly property bool hasPeople: characters.length > 0 || extras.length > 0 || carried.length > 0
    readonly property bool isEmpty: status === "failed" || (status === "ready" && !hasPeople)
    readonly property var narrator: cast && cast.narrator ? cast.narrator : ({})
    property int generation: 0
    signal request(string kind, var person)
    signal menuRequested(Item anchor, var person)

    function load() {
        if (!bookId) return
        const mine = ++generation
        if (!cast) status = "loading"
        Api.quiet("GET", "/api/books/" + bookId + "/cast", null, function(data, error) {
            if (mine !== root.generation) return
            if (error || !data) { if (!root.cast) root.status = "failed"; return }
            root.cast = data
            root.status = "ready"
        })
    }
    onActiveChanged: if (active && status === "idle") load()
    onBookIdChanged: { generation++; cast = null; status = "idle"; later = false; if (active) load() }
    Connections {
        target: Api
        function onEdited(id) { if (id === root.bookId && root.status !== "idle") root.load() }
    }
    function shown(person) { return root.later || !Logic.hidden(person, root.reached) }
    function fold(key) { return "book." + root.bookId + "." + key }

    Flickable {
        id: flick
        objectName: "castFlick"
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.height + Theme.s16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: column
            width: flick.width
            // Đang tải: khung chờ đúng hình danh sách, nhịp mờ 0,6 <-> 1
            Collapse {
                width: parent.width
                open: root.status === "loading"
                Column {
                    id: skeleton
                    objectName: "castSkeleton"
                    width: parent.width
                    topPadding: Theme.s16
                    spacing: Theme.s16
                    Accessible.role: Accessible.Indicator
                    Accessible.name: "Đang tải nhân vật"
                    SequentialAnimation {
                        running: skeleton.visible && Nav.uiVisible && !Theme.reduceMotion
                        loops: Animation.Infinite
                        OpacityAnimator { target: skeleton; from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
                        OpacityAnimator { target: skeleton; from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
                    }
                    Repeater {
                        model: 3
                        Item {
                            width: skeleton.width
                            height: 40
                            Rectangle { width: 40; height: 40; radius: width / 2; color: Theme.line }
                            Rectangle { x: 52; y: 6; width: (parent.width - 52) * 0.6; height: 12; radius: Theme.radiusControl; color: Theme.line }
                            Rectangle { x: 52; y: 26; width: (parent.width - 52) * 0.4; height: 12; radius: Theme.radiusControl; color: Theme.line }
                        }
                    }
                }
            }
            // Chưa phân vai (hay không hỏi được): cùng một câu như web
            Collapse {
                width: parent.width
                open: root.isEmpty
                EmptyState {
                    objectName: "castEmpty"
                    width: parent.width
                    icon: "audio-lines"
                    title: "Chưa có dàn nhân vật"
                    text: "Dàn nhân vật hiện ra khi truyện đã được phân vai."
                }
            }
            Collapse {
                width: parent.width
                open: root.status === "ready" && root.hasPeople
                Column {
                    id: content
                    objectName: "castContent"
                    width: parent.width
                    topPadding: Theme.s16
                    spacing: Theme.s16
                    // Người kể chuyện
                    Item {
                        id: narratorRow
                        objectName: "castNarrator"
                        width: parent.width
                        height: Math.max(40, narratorTexts.height) + 16
                        readonly property string voice: root.narrator.voice || ""
                        readonly property real buttonsWidth: narratorButtons.width
                        Rectangle {
                            x: 0; y: 8; width: 40; height: 40; radius: width / 2
                            color: Theme.accentSoft
                            Icon { anchors.centerIn: parent; name: "book-open-text"; size: 20; color: Theme.accentText }
                        }
                        Column {
                            id: narratorTexts
                            x: 52
                            y: 8
                            width: Math.max(0, narratorRow.width - x - 12 - narratorRow.buttonsWidth)
                            spacing: 2
                            Text {
                                width: parent.width
                                text: "Người kể chuyện"
                                color: Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                                font.weight: 600
                                font.capitalization: Font.AllUppercase
                                font.letterSpacing: 0.72
                            }
                            Text {
                                objectName: "castNarratorVoice"
                                width: parent.width
                                text: narratorRow.voice || "Mặc định"
                                color: Theme.text
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBody
                                font.weight: 600
                            }
                            Text {
                                objectName: "castNarratorPending"
                                visible: Boolean(root.caps.voice) && text !== ""
                                width: parent.width
                                text: Logic.narratorPending(root.narrator)
                                color: Theme.accentText
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                                font.weight: Theme.weightMedium
                            }
                            Text {
                                width: parent.width
                                text: Logic.narratorLine(root.narrator)
                                color: Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                                font.features: { "tnum": 1 }
                            }
                        }
                        Row {
                            id: narratorButtons
                            x: narratorRow.width - width
                            y: 8 + (40 - 36) / 2
                            spacing: 4
                            CastSample {
                                objectName: "castNarratorSample"
                                visible: narratorRow.voice !== ""
                                clipId: Logic.voiceId(narratorRow.voice)
                                url: Logic.voiceUrl(narratorRow.voice)
                                label: "Nghe giọng " + narratorRow.voice
                            }
                            IconButton {
                                objectName: "castNarratorVoiceButton"
                                visible: Boolean(root.caps.voice) && Boolean(root.caps.narrator)
                                implicitWidth: 36
                                implicitHeight: 36
                                icon: "sliders-horizontal"
                                iconSize: 16
                                ink: Theme.text2
                                hoverInk: Theme.text
                                tip: "Đổi giọng người kể"
                                Accessible.name: "Đổi giọng người kể"
                                onClicked: root.request("narrator", ({name: "NARRATOR", displayName: "người kể"}))
                            }
                        }
                    }
                    DevicesFold {
                        width: parent.width
                        storageKey: root.fold("cast")
                        title: "Vai chính"
                        summary: root.characters.length + " người có lời thoại"
                        defaultOpen: root.characters.length <= 4
                        Column {
                            width: parent.width
                            spacing: 0
                            CastPeople {
                                width: parent.width
                                bookId: root.bookId
                                people: root.characters
                                caps: root.caps
                                shown: person => root.shown(person)
                                onRequest: (kind, person) => root.request(kind, person)
                                onMenuRequested: (anchor, person) => root.menuRequested(anchor, person)
                            }
                            // "Hiện / Ẩn chương sau": người chỉ xuất hiện sau chỗ đang nghe (không lộ nội dung chưa nghe tới)
                            Collapse {
                                width: parent.width
                                open: Boolean(root.reached) && Logic.ahead(root.characters, root.reached) > 0
                                Interactive {
                                    objectName: "castLater"
                                    width: parent.width
                                    implicitHeight: Math.max(Theme.buttonHeight, laterText.height + 8)
                                    height: implicitHeight
                                    Accessible.role: Accessible.Button
                                    Accessible.name: laterText.text
                                    onClicked: root.later = !root.later
                                    Text {
                                        id: laterText
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width
                                        text: (root.later ? "Ẩn chương sau" : "Hiện chương sau") + " · " + Logic.ahead(root.characters, root.reached) + " người"
                                        color: Theme.text2
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeBodySmall
                                        font.weight: Theme.weightMedium
                                    }
                                }
                            }
                        }
                    }
                    Collapse {
                        width: parent.width
                        open: root.extras.length > 0
                        DevicesFold {
                            width: parent.width
                            storageKey: root.fold("extras")
                            title: "Vai phụ"
                            summary: root.extras.length + " người trong một cảnh"
                            CastPeople {
                                width: parent.width
                                bookId: root.bookId
                                people: root.extras
                                caps: root.caps
                                onRequest: (kind, person) => root.request(kind, person)
                                onMenuRequested: (anchor, person) => root.menuRequested(anchor, person)
                            }
                        }
                    }
                    // Phần nối tiếp: dàn mang sang chưa nói ở phần này. Mở sẵn khi chưa ai nói câu nào - lúc ấy đây là cả dàn.
                    Collapse {
                        width: parent.width
                        open: root.carried.length > 0
                        DevicesFold {
                            width: parent.width
                            storageKey: root.fold("carried")
                            title: "Từ phần trước"
                            summary: root.carried.length + " người chưa xuất hiện"
                            defaultOpen: root.characters.length === 0 && root.carried.length <= 4
                            CastPeople {
                                width: parent.width
                                bookId: root.bookId
                                people: root.carried
                                caps: ({rename: root.caps.rename, gender: root.caps.gender, voice: root.caps.voice})
                                onRequest: (kind, person) => root.request(kind, person)
                                onMenuRequested: (anchor, person) => root.menuRequested(anchor, person)
                            }
                        }
                    }
                }
            }
        }
        SmoothWheel { flick: flick }
    }
    Scrollbar { target: flick }
    ScrollEdges {
        x: flick.x; y: flick.y; width: flick.width; height: flick.height
        target: flick
    }
}
