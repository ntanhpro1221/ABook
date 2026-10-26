import QtQuick
import ABook

// Settings groups change columns using content width; text always wraps.
Item {
    id: root

    readonly property var modes: [
        { key: "auto", label: "Tự động" },
        { key: "light", label: "Sáng" },
        { key: "dark", label: "Tối" }
    ]

    readonly property bool expanded: width >= Theme.widthExpanded
    property real split: expanded ? 1 : 0
    Behavior on split {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, 800 + 400 * split)
    readonly property real groupWidth: (bodyWidth - Theme.s32 * split) / (1 + split)

    ScreenHeader {
        id: header
        x: (parent.width - root.bodyWidth) / 2
        width: root.bodyWidth
        title: "Cài đặt"
    }
    Flickable {
        id: scroll
        x: header.x
        y: header.height + Theme.s16
        width: root.bodyWidth
        height: parent.height - y
        contentHeight: Math.max(appearance.height, advanced.y + advanced.height) + Theme.s32
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: appearance
            objectName: "settingsAppearance"
            width: root.groupWidth
            Text {
                text: "GIAO DIỆN"
                color: Theme.text3
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
                font.letterSpacing: 0.72
                bottomPadding: Theme.s8
            }
            Item {
                width: parent.width
                height: Theme.s24 + choices.height
                Text {
                    text: "Màu nền"
                    color: Theme.text
                    font.pixelSize: Theme.sizeBody
                }
                Flow {
                    id: choices
                    y: Theme.s24
                    width: parent.width
                    spacing: Theme.s24
                    Repeater {
                        model: root.modes
                        // Hàng chữ có gạch chân hổ phách, không hộp phân đoạn (DESIGN.md mục 6, "Bộ lọc")
                        Interactive {
                            required property var modelData
                            readonly property bool chosen: Theme.mode === modelData.key
                            width: label.implicitWidth
                            height: Theme.hit
                            ringRadius: 4
                            onClicked: {
                                Theme.mode = modelData.key
                                Platform.setSetting("themeMode", modelData.key)
                            }
                            Text {
                                id: label
                                anchors.verticalCenter: parent.verticalCenter
                                text: parent.modelData.label
                                color: parent.chosen ? Theme.text : Theme.text2
                                font.pixelSize: Theme.sizeBodySmall
                                font.weight: parent.chosen ? Theme.weightMedium : Theme.weightRegular
                            }
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.horizontalCenter: parent.horizontalCenter
                                height: 2
                                radius: 1
                                color: Theme.accent
                                width: parent.chosen ? parent.width : 0
                                Behavior on width {
                                    NumberAnimation {
                                        duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                                        easing.type: Easing.BezierSpline
                                        easing.bezierCurve: Theme.easeStandard
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Column {
            id: advanced
            objectName: "settingsAdvanced"
            width: root.groupWidth
            x: (root.groupWidth + Theme.s32) * root.split
            y: (appearance.height + Theme.s32) * (1 - root.split)
            Text {
                width: parent.width
                text: "NÂNG CAO"
                color: Theme.text3
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
                font.letterSpacing: 0.72
                bottomPadding: Theme.s8
            }
            Column {
                width: parent.width
                spacing: Theme.s8
                Text {
                    width: parent.width
                    text: "Nhật ký"
                    color: Theme.text
                    font.pixelSize: Theme.sizeBody
                    wrapMode: Text.Wrap
                }
                Text {
                    width: parent.width
                    text: "Ghi lại những gì ABook gặp khi chạy, để gửi khi cần."
                    color: Theme.text3
                    font.pixelSize: Theme.sizeCaption
                    wrapMode: Text.Wrap
                }
                Button {
                    kind: "text"
                    text: "Mở thư mục"
                    onClicked: Platform.revealFile(Backend.logPath)
                }
            }
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            Flow {
                width: parent.width
                spacing: Theme.s24
                topPadding: Theme.s16
                Text {
                    text: "Phiên bản"
                    color: Theme.text
                    font.pixelSize: Theme.sizeBody
                }
                Text {
                    text: Backend.version
                    color: Theme.text2
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
        }
        SmoothWheel { flick: scroll }
    }
    Scrollbar { target: scroll }
}
