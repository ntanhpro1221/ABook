import QtQuick
import ABook

// Danh sách phím tắt của máy tính trong Cài đặt › Giao diện › Phím tắt (ShortcutList `inSettings` của listen/Shortcuts.tsx). Phím một chữ cái tắt
// được: hậu tố "(đang tắt)", gạch ngang qua phím, và câu cuối mở ra tại chỗ (không trỏ về chính trang này).
Column {
    id: root
    property bool letters: true
    // phím theo thứ tự, việc, có là phím một chữ cái không; "+" là chữ nối giữa các phím
    readonly property var rows: [
        {keys: ["Ctrl", "+", "Shift", "+", "M"], label: "Cửa sổ mini", letter: false},
        {keys: ["Space"], label: "Phát / tạm dừng", letter: false},
        {keys: ["←", "→"], label: "Lùi / tới 15 giây", letter: false},
        {keys: ["Shift", "+", "←", "→"], label: "Chương trước / sau", letter: false},
        {keys: ["M"], label: "Tắt / bật tiếng", letter: true},
        {keys: ["[", "]"], label: "Giảm / tăng tốc độ đọc", letter: true},
        {keys: ["Esc"], label: "Thu nhỏ màn hình đang nghe", letter: false},
        {keys: ["?"], label: "Xem các phím tắt này", letter: true}
    ]
    Column {
        width: parent.width
        spacing: 10
        Repeater {
            model: root.rows
            Item {
                id: entry
                required property var modelData
                readonly property bool off: modelData.letter && !root.letters
                width: parent.width
                height: Math.max(label.implicitHeight, 20)
                Text {
                    id: label
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - keys.width - 16
                    text: entry.modelData.label + (entry.off ? " (đang tắt)" : "")
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Row {
                    id: keys
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4
                    Repeater {
                        model: entry.modelData.keys
                        Item {
                            id: key
                            required property string modelData
                            width: key.modelData === "+" ? plus.implicitWidth : cap.width
                            height: 20
                            Text {
                                id: plus
                                visible: key.modelData === "+"
                                anchors.verticalCenter: parent.verticalCenter
                                text: "+"
                                color: Theme.text2
                                font.pixelSize: Theme.sizeBodySmall
                            }
                            LookKbd { id: cap; visible: key.modelData !== "+"; struck: entry.off; text: key.modelData === "+" ? "" : key.modelData }
                        }
                    }
                }
            }
        }
    }
    Collapse {
        width: parent.width
        open: !root.letters
        Item {
            width: parent.width
            height: tail.implicitHeight + 12
            Text {
                id: tail
                y: 12
                width: Math.min(parent.width, 448)
                text: "Phím một chữ cái đang tắt. Space, mũi tên, Esc vẫn chạy."
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: 13
            }
        }
    }
}
