import "UiStrings.js" as S
import QtQuick
import ABook
import "DevicesLogic.js" as Logic
import "TextWrap.js" as TextWrap

// Khung "Ghép thiết bị" của Cài đặt › Thiết bị (PairingPanel của desktop/PhoneSync.tsx): ba pha dùng chung một chỗ - mã 6 số đang hiện
// (kèm hướng dẫn, đồng hồ đếm ngược, vân tay, "Huỷ mã"), "Mã bị khoá" sau 5 lần sai (+ "Tạo mã mới"), và nút "Ghép thiết bị mới".
// Mỗi pha là một Collapse: pha cũ khép lại trong lúc pha mới mở ra, không bật tắt cứng. Mã dùng một lần, sống 5 phút (máy chủ tính).
Column {
    id: root
    property var sync: ({})
    property bool busy: false
    property real now: Date.now() / 1000
    readonly property real expiresAt: sync.pairing ? sync.pairing.expiresAt : 0
    readonly property int secondsLeft: expiresAt ? Math.max(0, Math.ceil(expiresAt - now)) : 0
    readonly property bool showCode: Boolean(sync.pairing) && secondsLeft > 0
    readonly property bool showBlocked: !showCode && Boolean(sync.pairingBlocked)
    readonly property bool showIdle: !showCode && !showBlocked
    readonly property string ink: String(Theme.text)
    signal pair()
    signal cancel()

    // ---- Mã đang hiện ----
    Collapse {
        id: codePhase
        width: parent.width
        open: root.showCode
        Column {
            id: codeBox
            width: parent.width
            topPadding: 20
            bottomPadding: 20
            readonly property real rightWidth: codeRow.width + 4.76
            readonly property bool sideBySide: width - rightWidth - 24 >= probe.implicitWidth
            Text { id: probe; visible: false; text: instruction.text; font.pixelSize: 13 }
            Item {
                width: parent.width
                height: codeBox.sideBySide ? Math.max(left.height, right.height) : left.height + 24 + right.height
                Column {
                    id: left
                    width: codeBox.sideBySide ? probe.implicitWidth : parent.width
                    anchors.verticalCenter: codeBox.sideBySide ? parent.verticalCenter : undefined
                    Text { width: parent.width; text: S.s_ma_ghep_thiet_bi_02370316; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: 600 }
                    Item { width: 1; height: 8 }
                    Text {
                        id: instruction
                        width: parent.width
                        text: TextWrap.keepDots(S.s_tren_may_kia_cai_dat_thiet_bi_chon_3c0003fa + (root.sync.name || "") + S.s_nhap_ma_84cf2ece)
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 13
                    }
                    Item { width: 1; height: 8 }
                    MoreInfo {
                        width: parent.width
                        label: S.s_cach_dung_ma_ae1cba85
                        HintText { width: parent.width; text: S.s_ma_dung_mot_lan_de_may_kia_nghe_thu_vien_n_a41fb816 }
                        HintText { width: parent.width; visible: (root.sync.addresses || []).length > 0; textFormat: Text.RichText; text: S.s_dia_chi_9945f0f4 + Logic.whereHtml(root.sync, false, root.ink) }
                    }
                }
                Column {
                    id: right
                    x: codeBox.sideBySide ? parent.width - width : (parent.width - width) / 2
                    y: codeBox.sideBySide ? (parent.height - height) / 2 : left.height + 24
                    width: codeBox.rightWidth
                    spacing: 8
                    Row {
                        id: codeRow
                        x: 4.76
                        objectName: "pairingCode"
                        Accessible.name: S.s_ma_ghep_noi_c00b217d + (root.sync.pairing ? root.sync.pairing.code.split("").join(" ") : "")
                        Text { text: root.sync.pairing ? root.sync.pairing.code.slice(0, 3) : ""; color: Theme.accentText; font.pixelSize: 34; font.weight: 600; font.letterSpacing: 4.76 }
                        Item { width: 12; height: 1 }
                        Text { text: root.sync.pairing ? root.sync.pairing.code.slice(3) : ""; color: Theme.accentText; font.pixelSize: 34; font.weight: 600; font.letterSpacing: 4.76 }
                    }
                    ClockLabel {
                        objectName: "pairingExpiry"
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: S.s_het_han_sau_34497ee1 + Math.floor(root.secondsLeft / 60) + ":" + String(root.secondsLeft % 60).padStart(2, "0")
                        color: Theme.text2
                        font.pixelSize: Theme.sizeCaption
                    }
                }
            }
            Item {
                width: parent.width
                height: fingerprint.visible ? fingerprint.height + 12 : 0
                Text {
                    id: fingerprint
                    y: 12
                    width: parent.width
                    visible: Boolean(root.sync.fingerprintShort)
                    text: S.s_pair_fingerprint_label + (root.sync.fingerprintShort || "") + "\n" + S.s_pair_fingerprint_help + "\n" + S.s_pair_string + (root.sync.pairing ? root.sync.pairing.pairString || "" : "")
                    color: Theme.text3
                    wrapMode: Text.WrapAnywhere
                    font.pixelSize: Theme.sizeCaption
                }
            }
            Item {
                width: parent.width
                height: cancelButton.height
                // Chỉ huỷ mã đang hiện, không gỡ thiết bị nào - "Huỷ ghép" dễ hiểu thành gỡ thiết bị (soát UX 29-09).
                Button { id: cancelButton; anchors.right: parent.right; size: "sm"; kind: "ghost"; text: S.s_huy_ma_1b0a6559; onClicked: root.cancel() }
            }
        }
    }

    // ---- Mã bị khoá ----
    Collapse {
        width: parent.width
        open: root.showBlocked
        Item {
            width: parent.width
            implicitHeight: blockedWords.height + 32
            height: implicitHeight
            Icon { x: 0; y: 16 + 2; name: "shield-alert"; size: 20; color: Theme.warning }
            Column {
                id: blockedWords
                x: 32
                y: 16
                width: parent.width - 32 - 12 - again.width
                Text { width: parent.width; text: S.s_ma_bi_khoa_48579bd8; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: 600 }
                Item { width: 1; height: 2 }
                Text { width: parent.width; text: S.s_sai_5_lan_chi_tao_ma_moi_khi_ban_dang_ghep_6f3c0e90; color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: 13 }
            }
            Button {
                id: again
                x: parent.width - width
                y: 16
                size: "sm"
                text: S.s_tao_ma_moi_0b393b03
                busy: root.busy
                onActivated: root.pair()
            }
        }
    }

    // ---- Chưa có mã ----
    Collapse {
        width: parent.width
        open: root.showIdle
        Item {
            width: parent.width
            implicitHeight: start.height
            height: implicitHeight
            Button { id: start; icon: "smartphone"; text: S.s_ghep_thiet_bi_moi_e22fb590; busy: root.busy; onActivated: root.pair() }
        }
    }
}
