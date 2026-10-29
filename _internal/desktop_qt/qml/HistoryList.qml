import QtQuick
import ABook
import "HistoryLogic.js" as Logic

// Tab "Lịch sử" của trang sách (HistoryTab của listen/BookScreen.tsx): mỗi lượt nghe một dòng, gom theo ngày, bấm để nghe tiếp từ CUỐI lượt ấy.
// Hỏi máy chủ khi tab được mở (GET /api/listen/books/<mã>/sessions), mở lại tab thì hỏi lại mà vẫn giữ danh sách đang hiện. Ba trạng thái (đang hỏi /
// chưa có / có lượt nghe) mờ qua tại chỗ như LoadingCrossfade + MotionRegion của web: đang hỏi là khung chờ, KHÔNG nháy "Chưa có lịch sử nghe" rồi
// mới thay bằng danh sách. `chapters`: chương của cuốn (tên chương trong dòng "… → …"; chương không còn là "chương đã gỡ").
Item {
    id: root
    objectName: "historyList"
    property string bookId: ""
    property bool active: false
    property var chapters: []
    property real now: 0                    // mili giây; 0 = giờ máy (để thử)
    property var sessions: null
    property string status: "idle"          // idle | loading | ready | failed
    property int generation: 0
    readonly property bool hasSessions: sessions !== null && sessions.length > 0
    readonly property bool isEmpty: status === "failed" || (status === "ready" && !hasSessions)
    readonly property var groups: Logic.groupByDay(sessions, now > 0 ? now : undefined)
    readonly property real week: Logic.weekListened(sessions, now > 0 ? now : undefined)
    signal play(int chapterId, real seconds)

    function load() {
        if (!bookId) return
        const mine = ++generation
        if (sessions === null) status = "loading"
        Api.quiet("GET", "/api/listen/books/" + bookId + "/sessions", null, function(data, error) {
            if (mine !== root.generation) return
            if (error || !Array.isArray(data)) { if (root.sessions === null) root.status = "failed"; return }
            root.sessions = data
            root.status = "ready"
        })
    }
    onActiveChanged: if (active) load()
    onBookIdChanged: { generation++; sessions = null; status = "idle"; if (active) load() }

    Flickable {
        id: flick
        objectName: "historyFlick"
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.height + Theme.s16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: column
            width: flick.width
            // Đang hỏi: khung chờ đúng hình danh sách (một dòng chữ + hai dòng), nhịp mờ 0,6 <-> 1
            Collapse {
                width: parent.width
                open: root.status === "loading"
                Column {
                    id: skeleton
                    objectName: "historySkeleton"
                    width: parent.width
                    topPadding: Theme.s12
                    spacing: Theme.s12
                    Accessible.role: Accessible.Indicator
                    Accessible.name: "Đang tải lịch sử"
                    SequentialAnimation {
                        running: skeleton.visible && Nav.uiVisible && !Theme.reduceMotion
                        loops: Animation.Infinite
                        OpacityAnimator { target: skeleton; from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
                        OpacityAnimator { target: skeleton; from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
                    }
                    Rectangle { width: Math.min(224, skeleton.width); height: 16; radius: Theme.radiusControl; color: Theme.line }
                    Rectangle { width: skeleton.width; height: 40; radius: Theme.radiusControl; color: Theme.line }
                    Rectangle { width: skeleton.width; height: 40; radius: Theme.radiusControl; color: Theme.line }
                }
            }
            Collapse {
                width: parent.width
                open: root.isEmpty
                EmptyState {
                    objectName: "historyEmpty"
                    width: parent.width
                    icon: "history"
                    title: "Chưa có lịch sử nghe"
                    text: "Mỗi lượt nghe lưu lại chỗ bạn dừng."
                }
            }
            Collapse {
                width: parent.width
                open: root.status === "ready" && root.hasSessions
                Column {
                    id: dayColumn
                    objectName: "historyContent"
                    width: parent.width
                    topPadding: Theme.s12
                    spacing: Theme.s4
                    Flow {
                        objectName: "historyWeek"
                        width: parent.width
                        spacing: 4
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "7 ngày qua: " + Logic.formatLength(root.week) + " nghe cuốn này."
                        Text { text: "7 ngày qua:"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                        Text { objectName: "historyWeekLength"; text: Logic.formatLength(root.week); color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: 600 }
                        Text { text: "nghe cuốn này."; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                    }
                    Repeater {
                        model: root.groups
                        DevicesFold {
                            id: dayFold
                            required property var modelData
                            objectName: "historyDay"
                            width: dayColumn.width
                            storageKey: "book." + root.bookId + ".history." + modelData.day
                            title: modelData.day
                            summary: Logic.groupSummary(modelData)
                            Column {
                                width: parent.width
                                Repeater {
                                    model: dayFold.modelData.items
                                    Item {
                                        id: session
                                        required property var modelData
                                        required property int index
                                        objectName: "historySession"
                                        width: parent.width
                                        height: Math.max(texts.height, resume.height) + 20
                                        Rectangle { visible: session.index > 0; width: parent.width; height: 1; color: Theme.line }
                                        Column {
                                            id: texts
                                            y: 10
                                            width: Math.max(0, session.width - resume.width - 12)
                                            spacing: 2
                                            Text {
                                                objectName: "historyHeadline"
                                                width: parent.width
                                                text: Logic.headline(session.modelData)
                                                color: Theme.text
                                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                                font.pixelSize: Theme.sizeBodySmall
                                                font.weight: Theme.weightMedium
                                                font.features: { "tnum": 1 }
                                            }
                                            Text {
                                                objectName: "historyWhere"
                                                width: parent.width
                                                text: Logic.where(session.modelData, root.chapters)
                                                color: Theme.text2
                                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                                font.pixelSize: Theme.sizeCaption
                                                font.features: { "tnum": 1 }
                                            }
                                        }
                                        Button {
                                            id: resume
                                            objectName: "historyResume"
                                            x: session.width - width
                                            y: 10
                                            width: Math.min(implicitWidth, Math.max(140, session.width * 0.4))
                                            size: "sm"
                                            kind: "ghost"
                                            icon: "play"
                                            wrap: true
                                            text: Logic.resumeLabel(session.modelData)
                                            onActivated: root.play(session.modelData.to.chapterId, session.modelData.to.seconds)
                                        }
                                    }
                                }
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
