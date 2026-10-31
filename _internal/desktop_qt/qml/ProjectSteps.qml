import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Khối sản xuất dưới đầu trang dự án khi sách chưa xong (ProductionPanel của studio/ProjectScreen.tsx): lời báo nhật ký không ghi được, rồi "Các bước"
// gập / mở (nhớ theo cuốn, Fold storageKey project.<id>.steps) với ba bước Phân tích truyện / Phân vai / Thu âm và kiểm tra - vòng số / dấu xong / biểu
// tượng, tiêu đề, một dòng nói bước làm gì và thanh tiến độ. Màn rộng ba bước đứng cạnh nhau, hẹp thì chồng xuống.
Column {
    id: root
    property var book: null
    readonly property var states: book ? Logic.stepStates(book) : ["pending", "pending", "pending"]
    readonly property var details: book ? Logic.stepDetails(book) : ["", "", ""]
    readonly property var progress: book && book.progress ? [book.progress.analysis, undefined, book.progress.synthesis] : [undefined, undefined, undefined]
    readonly property bool side: width >= 600
    spacing: Theme.s12

    Row {
        objectName: "projectLogLost"
        width: parent.width
        spacing: Theme.s8
        visible: lost.text !== ""
        Icon { name: "circle-alert"; size: 16; color: Theme.warning; y: 2 }
        Text {
            id: lost
            width: parent.width - 16 - Theme.s8
            text: root.book ? Logic.logLostLine(root.book) : ""
            color: Theme.warning
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
    ImportFold {
        objectName: "projectSteps"
        width: parent.width
        prefix: "fold.project."
        storageKey: (root.book ? root.book.id : "") + ".steps"
        title: "Các bước"
        summary: root.book ? Logic.stepSummary(root.book) : ""
        Grid {
            id: steps
            width: parent.width
            topPadding: Theme.s12
            columns: root.side ? 3 : 1
            columnSpacing: Theme.s32
            rowSpacing: Theme.s24
            readonly property real cell: root.side ? (width - 2 * columnSpacing) / 3 : width
            Repeater {
                model: 3
                delegate: Column {
                    id: step
                    required property int index
                    readonly property string look: root.states[index]
                    readonly property string title: Logic.STEP_TITLES[index]
                    readonly property var value: root.progress[index]
                    objectName: "projectStep_" + index
                    width: steps.cell
                    spacing: Theme.s8
                    Accessible.role: Accessible.Grouping
                    Accessible.name: title
                    Item {
                        width: parent.width
                        height: 28
                        Rectangle {
                            id: dot
                            width: 28; height: 28; radius: height / 2
                            color: step.look === "done" ? Theme.success : step.look === "active" ? Theme.accent : step.look === "paused" ? Theme.text3 : Theme.hover
                            Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium } }
                            Icon {
                                anchors.centerIn: parent
                                visible: step.look === "done" || step.look === "active"
                                name: step.look === "done" ? "check" : Logic.STEP_ICONS[step.index]
                                size: step.look === "done" ? 16 : 14
                                color: step.look === "done" ? Theme.successInk : Theme.accentInk
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: step.look === "paused" || step.look === "pending"
                                text: String(step.index + 1)
                                color: step.look === "paused" ? Theme.bg : Theme.text2
                                font.pixelSize: Theme.sizeCaption
                                font.weight: Theme.weightBold
                            }
                        }
                        Text {
                            x: 28 + 10
                            width: parent.width - x - 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: step.title
                            color: step.look === "pending" ? Theme.text3 : Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                            font.weight: Font.DemiBold
                        }
                        Icon {
                            objectName: "projectStepMark_" + step.index
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            visible: step.look === "active" || step.look === "paused"
                            name: step.look === "active" ? "audio-lines" : "pause"
                            size: 14
                            color: step.look === "active" ? Theme.accent : Theme.text3
                        }
                    }
                    Text {
                        width: parent.width
                        text: root.details[step.index]
                        color: step.look === "pending" ? Theme.text3 : Theme.text2
                        wrapMode: Text.Wrap
                        lineHeight: 1.4
                        font.pixelSize: Theme.sizeCaption
                    }
                    Row {
                        visible: step.value !== undefined && step.look !== "pending"
                        width: parent.width
                        topPadding: Theme.s4
                        spacing: Theme.s8
                        StudioBar {
                            width: parent.width - 36 - Theme.s8
                            anchors.verticalCenter: parent.verticalCenter
                            size: "sm"
                            value: step.value || 0
                            tone: step.look === "done" ? "success" : step.look === "paused" ? "muted" : "accent"
                            label: step.title
                        }
                        Text {
                            width: 36
                            horizontalAlignment: Text.AlignRight
                            text: Logic.formatPercent(step.value || 0)
                            color: Theme.text
                            font.pixelSize: Theme.sizeCaption
                            font.weight: Font.DemiBold
                            font.features: { "tnum": 1 }
                        }
                    }
                }
            }
        }
    }
}
