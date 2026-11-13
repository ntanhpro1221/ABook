import "UiStrings.js" as S
import QtQuick
import ABook
import "NameLogic.js" as N
import "StudioLogic.js" as Studio
import "WorkLogic.js" as W
import "TextWrap.js" as TextWrap

// Hộp thư thay đổi từ điện thoại (PhoneEdits.tsx, docs/EDITING.md; webui/edits_inbox.py): điện thoại đã ghép gửi phần sửa của cuốn về máy tính. Tên sách, bìa, tên nhân vật, tên chương
// và nhạc áp NGAY (không qua đây); còn những việc cần Studio - đổi giọng, cách đọc, người nói, thu lại - nằm đây chờ chủ máy "Áp dụng" hay "Bỏ qua" từng việc, từng thiết bị.
// KHÔNG BAO GIỜ tự áp. "Áp dụng" chỉ biến việc thành yêu cầu trong "Áp dụng N thay đổi" - chưa thu lại gì. Việc bỏ qua nằm lại khay "Đã bỏ qua" để khôi phục.
Item {
    id: root
    objectName: "phoneEdits"
    property var work: null
    property string busy: ""
    property var skipping: null
    readonly property var view: work && work.inbox.data ? work.inbox.data : null
    function filled(v) { return v !== null && ((v.devices || []).length > 0 || (v.recent || []).length > 0 || (v.skipped || []).length > 0) }
    readonly property bool shown: filled(view)
    property var held: ({devices: [], recent: [], skipped: [], waiting: 0})
    onViewChanged: if (filled(view)) held = view
    width: parent ? parent.width : 600
    height: outer.height
    visible: outer.height > 0

    function decide(verb, device, item) {
        if (busy !== "") return
        busy = device.id + ":" + (item ? item.id : "all")
        work.decide(verb, device, item, function() { root.busy = "" })
    }

    Collapse {
        id: outer
        objectName: "phoneEditsOuter"
        width: root.width
        open: root.shown
        Column {
            width: parent.width
            Item { width: 1; height: 16 }
            // Tiêu đề mục: cao 56, biểu tượng điện thoại
            Row {
                width: parent.width
                height: Math.max(56, headingText.height)
                spacing: 8
                Icon { anchors.verticalCenter: parent.verticalCenter; name: "smartphone"; size: 16; color: Theme.text3 }
                Text {
                    id: headingText
                    objectName: "inboxHeading"
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 24
                    text: N.inboxHeading(root.held.waiting)
                    color: Theme.text
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeSection
                    font.weight: Theme.weightMedium
                }
            }
            Collapse {
                width: parent.width
                open: (root.held.devices || []).length > 0
                Column {
                    width: parent.width
                    Text { width: Math.min(parent.width, 768); topPadding: 4; text: S.s_ap_dung_de_dua_vao_hang_cho_bo_qua_van_kho_b65a72a7; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                    MoreInfo {
                        width: parent.width
                        label: S.s_da_ap_dung_0e69eb72
                        Text { width: parent.width; text: S.s_ten_sach_bia_ten_nhan_vat_ten_chuong_va_nh_da8df954; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                    }
                }
            }
            // Áp dụng / Bỏ qua / Khôi phục: hàng (và cả máy khi hết việc) khép / mở tại chỗ
            StudioRows {
                objectName: "inboxDevices"
                width: parent.width
                items: root.held.devices || []
                keyField: "id"
                delegate: deviceDelegate
            }
            WorkSection {
                objectName: "inboxSkipped"
                present: root.skippedCount > 0
                gap: 12
                title: S.s_da_bo_qua_7f216d1a + root.skippedCount + ")"
                StudioRows { width: parent.width; items: root.held.skipped || []; keyField: "id"; delegate: skippedDelegate }
            }
            WorkSection {
                objectName: "inboxRecent"
                present: (root.held.recent || []).length > 0
                gap: 12
                title: S.s_gui_gan_day_954ffe00 + (root.held.recent || []).length + ")"
                Column {
                    width: parent.width
                    spacing: 8
                    topPadding: 8
                    Repeater {
                        model: root.held.recent || []
                        delegate: Column {
                            required property var modelData
                            width: parent ? parent.width : 400
                            Text { width: parent.width; text: N.describePush(modelData); color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                            Repeater {
                                model: modelData.conflicts || []
                                delegate: Text { required property var modelData; width: parent.width; topPadding: 4; text: modelData; color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                            }
                        }
                    }
                }
            }
            Item { width: 1; height: 16 }
        }
    }
    readonly property int skippedCount: N.skippedCount(held.skipped)

    // Một máy: tên + "gửi …" + hai nút cho cả máy, rồi từng việc
    Component {
        id: deviceDelegate
        Column {
            id: block
            property var modelData: ({id: "", name: "", at: 0, items: []})
            width: parent ? parent.width : 400
            Item { width: 1; height: 12 }
            Flow {
                width: parent.width
                spacing: 8
                Text {
                    width: Math.max(160, parent.width - allApply.width - allSkip.width - 16)
                    height: allApply.height
                    verticalAlignment: Text.AlignVCenter
                    textFormat: Text.RichText
                    text: "<span style=\"font-weight:500\">" + W.esc(TextWrap.keepDots(block.modelData.name)) + "</span><span style=\"color:" + W.cssColor(Theme.text3) + S.s_nbsp_nbsp_gui_862864dc + W.esc(Studio.formatWhen(block.modelData.at)) + "</span>"
                    color: Theme.text
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Button {
                    id: allApply
                    objectName: "inboxApplyAll"
                    size: "sm"
                    icon: "check"
                    text: S.s_ap_dung_tat_ca_068378e0
                    busy: root.busy === block.modelData.id + ":all"
                    enabled: root.busy === ""
                    onActivated: root.decide("apply", block.modelData, null)
                }
                Button {
                    id: allSkip
                    objectName: "inboxSkipAll"
                    size: "sm"
                    kind: "ghost"
                    icon: "x"
                    text: S.s_bo_qua_tat_ca_e736ef1f
                    enabled: root.busy === ""
                    onClicked: { root.skipping = block.modelData; confirm.title = S.s_bo_qua_moi_viec_tu_863669f5 + (block.modelData.name || S.s_may_nay_e53e5d40) + "?"; confirm.description = S.s_bo_8d4fc41c + block.modelData.items.length + S.s_viec_khoi_hang_cho_khoi_phuc_duoc_o_da_bo_2e106212; confirm.show() }
                }
            }
            Item { width: 1; height: 8 }
            StudioRows {
                width: parent.width
                items: block.modelData.items || []
                keyField: "id"
                delegate: Component {
                    Item {
                        id: row
                        property var modelData: ({id: "", kind: "", label: "", chapter: "", conflict: ""})
                        width: parent ? parent.width : 400
                        height: Math.max(text.height, 32) + 16
                        Icon { x: 0; y: 11; name: N.kindIcon(row.modelData.kind); size: 16; color: Theme.text3 }
                        Text {
                            id: text
                            x: 28
                            y: 8
                            width: parent.width - 28 - 72
                            textFormat: Text.RichText
                            text: W.esc(row.modelData.label || "") + (row.modelData.chapter ? "<span style=\"color:" + W.cssColor(Theme.text3) + "\">&nbsp;·&nbsp;" + W.esc(row.modelData.chapter) + "</span>" : "")
                                + (row.modelData.conflict ? "<br><span style=\"color:" + W.cssColor(Theme.warning) + "; font-size:12px\">" + W.esc(row.modelData.conflict) + "</span>" : "")
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        IconButton {
                            objectName: "inboxApplyOne"
                            x: parent.width - 72
                            y: 4
                            implicitWidth: 32
                            implicitHeight: 32
                            icon: "check"
                            iconSize: 16
                            tip: S.s_ap_dung_viec_nay_76d8752a
                            Accessible.name: S.s_ap_dung_viec_nay_76d8752a
                            enabled: root.busy === ""
                            onClicked: root.decide("apply", block.modelData, row.modelData)
                        }
                        IconButton {
                            objectName: "inboxSkipOne"
                            x: parent.width - 36
                            y: 4
                            implicitWidth: 32
                            implicitHeight: 32
                            icon: "x"
                            iconSize: 16
                            tip: S.s_bo_qua_viec_nay_e6b2362b
                            Accessible.name: S.s_bo_qua_viec_nay_e6b2362b
                            enabled: root.busy === ""
                            onClicked: root.decide("skip", block.modelData, row.modelData)
                        }
                    }
                }
            }
        }
    }

    // Khay "Đã bỏ qua": khôi phục cả máy hay từng việc
    Component {
        id: skippedDelegate
        Column {
            id: block
            property var modelData: ({id: "", name: "", items: []})
            width: parent ? parent.width : 400
            Item { width: 1; height: 8 }
            Flow {
                width: parent.width
                spacing: 8
                Text {
                    width: Math.max(160, parent.width - restoreAll.width - 8)
                    height: restoreAll.height
                    verticalAlignment: Text.AlignVCenter
                    text: TextWrap.keepDots(block.modelData.name)
                    color: Theme.text
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                }
                Button {
                    id: restoreAll
                    objectName: "inboxRestoreAll"
                    size: "sm"
                    kind: "ghost"
                    icon: "rotate-ccw"
                    text: S.s_khoi_phuc_tat_ca_cc961492
                    enabled: root.busy === ""
                    onClicked: root.decide("restore", block.modelData, null)
                }
            }
            StudioRows {
                width: parent.width
                items: block.modelData.items || []
                keyField: "id"
                delegate: Component {
                    Item {
                        id: row
                        property var modelData: ({id: "", label: "", chapter: ""})
                        width: parent ? parent.width : 400
                        height: Math.max(text.height, 32) + 16
                        Text {
                            id: text
                            x: 0
                            y: 8
                            width: parent.width - 40
                            textFormat: Text.RichText
                            text: W.esc(row.modelData.label || "") + (row.modelData.chapter ? "<span style=\"color:" + W.cssColor(Theme.text3) + "\">&nbsp;·&nbsp;" + W.esc(row.modelData.chapter) + "</span>" : "")
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        IconButton {
                            objectName: "inboxRestoreOne"
                            x: parent.width - 36
                            y: 4
                            implicitWidth: 32
                            implicitHeight: 32
                            icon: "rotate-ccw"
                            iconSize: 16
                            tip: S.s_khoi_phuc_viec_nay_8da3e2a8
                            Accessible.name: S.s_khoi_phuc_viec_nay_8da3e2a8
                            enabled: root.busy === ""
                            onClicked: root.decide("restore", block.modelData, row.modelData)
                        }
                    }
                }
            }
        }
    }

    StudioConfirm {
        id: confirm
        objectName: "skipConfirm"
        panelWidth: 448
        actions: [{key: "later", text: S.s_thoi_e68f9e88}, {key: "go", text: S.s_bo_qua_tat_ca_e736ef1f, kind: "primary"}]
        onChosen: key => {
            const device = root.skipping
            confirm.dismiss()
            if (key === "go" && device) root.decide("skip", device, null)
        }
    }
}
