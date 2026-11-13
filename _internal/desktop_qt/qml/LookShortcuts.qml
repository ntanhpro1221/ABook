import "UiStrings.js" as S
import QtQuick
import ABook

// Danh sách phím tắt của máy tính (ShortcutList của listen/Shortcuts.tsx): trong Cài đặt › Giao diện › Phím tắt (`inSettings`) và trong hộp
// "Phím tắt" mở bằng phím "?". Phím một chữ cái tắt được: hậu tố "(đang tắt)", gạch ngang qua phím; câu cuối trong Cài đặt chỉ mở ra khi phím
// chữ đang tắt (không trỏ về chính trang này), trong hộp thì luôn có và nói bật / tắt ở đâu.
Column {
    id: root
    property bool letters: true
    property bool inSettings: true
    readonly property string tailText: letters ? S.s_tat_phim_mot_chu_cai_o_cai_dat_giao_dien_dea67281
        : S.s_phim_mot_chu_cai_dang_tat_e4f92ede + (inSettings ? "" : S.s_bat_o_cai_dat_giao_dien_e4e0ca4b) + S.s_space_mui_ten_esc_van_chay_94acd406
    // phím theo thứ tự, việc, có là phím một chữ cái không; "+" là chữ nối giữa các phím
    readonly property var rows: [
        {keys: ["Ctrl", "+", "Shift", "+", "M"], label: S.s_cua_so_mini_65edeb9b, letter: false},
        {keys: ["Space"], label: S.s_phat_tam_dung_563530d1, letter: false},
        {keys: ["←", "→"], label: S.s_lui_toi_15_giay_5f952fd6, letter: false},
        {keys: ["Shift", "+", "←", "→"], label: S.s_chuong_truoc_sau_1f7a3d2b, letter: false},
        {keys: ["M"], label: S.s_tat_bat_tieng_152563ae, letter: true},
        {keys: ["[", "]"], label: S.s_giam_tang_toc_do_doc_484ba2e5, letter: true},
        {keys: [S.s_esc_52f878ed], label: S.s_thu_nho_man_hinh_dang_nghe_ec2467a0, letter: false},
        {keys: ["?"], label: S.s_xem_cac_phim_tat_nay_bdc607f4, letter: true}
    ]
    Column {
        width: parent.width
        spacing: 12
        Repeater {
            model: root.rows
            Item {
                id: entry
                required property var modelData
                readonly property bool off: modelData.letter && !root.letters
                width: parent ? parent.width : 0
                height: Math.max(label.implicitHeight, 20)
                Text {
                    id: label
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - keys.width - 16
                    text: entry.modelData.label + (entry.off ? S.s_dang_tat_3aac6b7f : "")
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
                                Reveal { shown: key.modelData === "+" }
                                anchors.verticalCenter: parent.verticalCenter
                                text: "+"
                                color: Theme.text2
                                font.pixelSize: Theme.sizeBodySmall
                            }
                            LookKbd { id: cap; Reveal { shown: key.modelData !== "+" } struck: entry.off; text: key.modelData === "+" ? "" : key.modelData }
                        }
                    }
                }
            }
        }
    }
    Collapse {
        width: parent.width
        open: !(root.inSettings && root.letters)
        Item {
            width: parent.width
            height: tail.implicitHeight + 12
            Text {
                id: tail
                y: 12
                width: Math.min(parent.width, 448)
                objectName: "shortcutsTail"
                text: root.tailText
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: 14
            }
        }
    }
}
