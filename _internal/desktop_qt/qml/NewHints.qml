import "UiStrings.js" as S
import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "StudioLogic.js" as Studio
import "TextWrap.js" as TextWrap

// Lời nhắn dưới ô Tên sách của trình tạo (SourceStep): đang sửa thiết lập cuốn nào; truyện này đã có dự án; gợi ý tách một file cả truyện thành các chương;
// trang phụ của file sách chưa tích. Máy chỉ ĐỀ XUẤT, không tự sửa nguồn (chủ sách 29-09). Mỗi khối mở / khép tại chỗ.
Column {
    id: root
    property var form: null
    signal projectRequested(string id)
    readonly property var draft: form ? form.draft : ({})
    readonly property var scan: form ? form.scan : null
    readonly property var replaces: draft.replaces
    readonly property var others: scan && scan.existing ? scan.existing.filter(project => !replaces || project.id !== replaces.id) : []
    readonly property var splits: scan ? scan.files.filter(file => file.split) : []
    readonly property var matter: form && form.rawScan ? Logic.matterFiles(form.rawScan.files) : []
    property string splitting: ""

    // Đang sửa thiết lập / làm lại
    Collapse {
        width: parent.width
        open: Boolean(root.replaces)
        NewNote {
            objectName: "newReplacesNote"
            width: parent.width
            icon: "info"
            Prose {
                textFormat: Text.StyledText
                tone: Theme.text
                text: root.replaces ? (root.replaces.restart ? S.s_dang_lam_lai_phan_tich_cua_a4a97a79 : S.s_dang_sua_thiet_lap_cua_e2a5f0e6) + "<b>“" + Logic.esc(root.replaces.title) + S.s_b_da_dien_thiet_lap_cu_tao_xong_se_dua_ban_c1eec016 : " "
            }
        }
    }
    // Truyện này đã có dự án
    Collapse {
        width: parent.width
        open: root.others.length > 0
        NewNote {
            objectName: "newExistingNote"
            width: parent.width
            icon: "info"
            Prose { strong: true; tone: Theme.text; text: S.s_truyen_nay_da_co_du_an_07223685 }
            Repeater {
                model: root.others
                delegate: Flow {
                    required property var modelData
                    width: parent.width
                    spacing: 8
                    Text {
                        width: Math.min(implicitWidth, parent.width)
                        text: TextWrap.keepDots("“" + modelData.title + "”\u00a0·\u00a0" + (modelData.shared === modelData.chapters ? S.s_ca_5887ed5b + modelData.chapters + S.s_chuong_9e6a01dc : S.s_trung_6eb22ee4 + modelData.shared + "/" + modelData.chapters + S.s_chuong_9e6a01dc) + "\u00a0·\u00a0" + modelData.statusLabel)
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    TextLink { objectName: "newExistingOpen"; text: S.s_mo_du_an_f990c9d8; accent: true; onClicked: root.projectRequested(modelData.id) }
                }
            }
            Prose { text: S.s_van_tao_duoc_du_an_moi_vi_du_de_thu_mot_gi_b8eda300 }
        }
    }
    // Gợi ý tách file cả truyện
    Collapse {
        width: parent.width
        open: root.splits.length > 0
        Column {
            width: parent.width
            Repeater {
                model: root.splits
                delegate: NewNote {
                    id: suggestion
                    required property var modelData
                    objectName: "newSplitNote"
                    width: parent.width
                    icon: "sparkles"
                    tone: Theme.accentText
                    readonly property var plan: modelData.split
                    readonly property var outcome: Logic.splitOutcome(plan, root.draft.title || "")
                    Prose {
                        strong: true
                        tone: Theme.text
                        text: S.s_goi_y_80f3b4ba + suggestion.modelData.name + S.s_co_ve_chua_ca_f34d3ea9 + Studio.formatNumber(suggestion.outcome.chapters) + S.s_chuong_9e6a01dc
                    }
                    Prose {
                        text: S.s_tach_theo_5f3e6530 + suggestion.plan.titles.map(title => "“" + title + "”").join(", ") + (suggestion.plan.chapters > suggestion.plan.titles.length ? "…" : "") + S.s_giu_file_goc_4cf6140f + (suggestion.plan.preamble ? S.s_va_chu_mo_dau_a047c58f : "") + "."
                    }
                    Item { width: 1; height: 6 }
                    Button {
                        objectName: "newSplitButton"
                        text: S.s_tach_thanh_a08e8a2c + Studio.formatNumber(suggestion.outcome.chapters) + S.s_chuong_9e6a01dc
                        icon: "scissors"
                        kind: "ghost"
                        size: "sm"
                        busy: root.splitting === suggestion.modelData.path
                        enabled: root.splitting === ""
                        onActivated: {
                            root.splitting = suggestion.modelData.path
                            root.form.splitSource(suggestion.modelData.path, function() { root.splitting = "" })
                        }
                    }
                }
            }
        }
    }
    // Trang phụ của file sách: có trong sách nhưng chưa tích
    Collapse {
        width: parent.width
        open: root.matter.length > 0
        Column {
            objectName: "newMatter"
            width: parent.width
            topPadding: 16
            Prose { strong: true; tone: Theme.text; topPadding: 16; text: Studio.formatNumber(root.matter.length) + S.s_trang_phu_chua_chon_fa525053 }
            Prose { topPadding: 4; text: S.s_bia_ban_quyen_muc_luc_hay_trang_ten_sach_n_49213805 }
            Item { width: 1; height: 8 }
            Repeater {
                model: root.matter
                delegate: ImportCheck {
                    required property var modelData
                    objectName: "newMatterRow"
                    width: parent.width
                    label: modelData.matter
                    help: modelData.firstLine || modelData.name
                    checked: (root.draft.keepMatter || []).indexOf(modelData.path) >= 0
                    onToggled: value => root.form.keepMatter(modelData.path, value)
                }
            }
            Item { width: 1; height: 16 }
        }
    }
}
