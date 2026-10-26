import QtQuick
import ABook

// Cài đặt (D0: hai nhóm đủ để thử). Máy tính: danh sách nhóm phẳng, hai cột (DESIGN.md mục 7) - làm đủ ở D2.
Item {
    id: root

    readonly property var modes: [
        { key: "auto", label: "Tự động" },
        { key: "light", label: "Sáng" },
        { key: "dark", label: "Tối" }
    ]

    ScreenHeader {
        id: header
        x: Theme.margin
        width: parent.width - 2 * Theme.margin
        title: "Cài đặt"
    }

    Column {
        x: Theme.margin
        y: header.height + Theme.s16
        width: Math.min(parent.width - 2 * Theme.margin, 640)
        spacing: Theme.s32

        Column {
            width: parent.width
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
                height: 56
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Màu nền"
                    color: Theme.text
                    font.pixelSize: Theme.sizeBody
                }
                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
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
            width: parent.width
            Text {
                text: "NÂNG CAO"
                color: Theme.text3
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
                font.letterSpacing: 0.72
                bottomPadding: Theme.s8
            }
            Item {
                width: parent.width
                height: 64
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Text {
                        text: "Nhật ký"
                        color: Theme.text
                        font.pixelSize: Theme.sizeBody
                    }
                    Text {
                        text: "Ghi lại những gì ABook gặp khi chạy, để gửi khi cần."
                        color: Theme.text3
                        font.pixelSize: Theme.sizeCaption
                    }
                }
                Button {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    kind: "text"
                    text: "Mở thư mục"
                    onClicked: Platform.revealFile(Backend.logPath)
                }
            }
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            Item {
                width: parent.width
                height: 56
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Phiên bản"
                    color: Theme.text
                    font.pixelSize: Theme.sizeBody
                }
                Text {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: Backend.version
                    color: Theme.text2
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
        }
    }
}
