import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic

// Chi tiết một bài của Kho nhạc (TrackSheet.tsx của web): tên · người sáng tác; nút Dùng (chế độ chọn), Nghe thử, Tải về / Huỷ tải % / Xoá bản tải,
// Không tự chọn bài này (chế độ chọn: chặn bài ở cuốn ấy - overrides.banned như web); "Vì sao bài này" (cảm xúc đoạn cạnh cảm xúc bài, 3 cảm
// xúc khớp nhất - chỉ khi đoạn có cảm xúc); 13 cảm xúc thành thanh 0-100 % giảm dần, nhãn tiếng Việt của danh mục; năng lượng, nhịp, phong cách,
// độ dài, có lời, giấy phép, các danh sách phát; ghi công + "Mở trang nguồn". `playing`: hộp "Bài đang phát" (Lưu / Bỏ lưu, Xem trong kho, Đổi bài).
Modal {
    id: root
    objectName: "musicTrackDetail"
    property string link: ""
    property var context: null              // {book, scene}: "Vì sao bài này"
    property var meta: null                 // /api/music/library/meta (nhãn)
    property var downloads: null
    property bool picking: false
    property bool playing: false
    property bool previewing: false
    property bool online: true
    property var detail: null
    property bool loading: false
    signal preview()
    signal save()
    signal unsave()
    signal cancelDownload()
    signal use()
    signal ban()
    signal openLibrary(string title)
    signal swap()
    readonly property var load: detail ? Logic.loadOf(detail, downloads) : ({kind: "none"})
    title: playing ? S.s_bai_dang_phat_3c20c832 : (detail ? detail.title || "" : "")
    description: detail ? [playing ? detail.title || "" : "", detail.creator || ""].filter(part => part !== "").join("\u00a0·\u00a0") : ""
    panelWidth: 560

    function show(next, nextContext) {
        link = next || ""
        context = nextContext || null
        reload()
        open = true
    }
    function reload() {
        if (!link) return
        loading = true
        let path = "/api/music/library/track?link=" + encodeURIComponent(link)
        if (context && context.book && context.scene) path += "&book=" + encodeURIComponent(context.book) + "&scene=" + encodeURIComponent(context.scene)
        const asked = link
        Api.quiet("GET", path, null, function(data, error) {
            if (asked !== root.link) return
            loading = false
            detail = error ? null : data
        })
    }

    Column {
        width: root.bodyWidth
        spacing: Theme.s16
        Text {
            visible: !root.detail
            text: root.loading ? S.s_dang_tai_465b1987 : S.s_chua_tai_duoc_bai_nay_d66f95b6
            color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
        }
        Flow {
            visible: !!root.detail
            width: parent.width
            spacing: Theme.s8
            Button { visible: root.picking; objectName: "musicDetailUse"; text: S.s_dung_7927ca4e; onActivated: root.use() }
            Button {
                visible: root.playing
                objectName: "musicDetailSave"
                text: root.detail && root.detail.saved ? S.s_bo_luu_2fd51455 : S.s_luu_e91f26c0
                kind: root.detail && root.detail.saved ? "ghost" : "primary"
                onActivated: root.detail && root.detail.saved ? root.unsave() : root.save()
            }
            Button { visible: root.playing; text: S.s_xem_trong_kho_2a139d05; kind: "ghost"; onActivated: root.openLibrary(root.detail ? root.detail.title || "" : "") }
            Button { visible: root.playing && !!root.context; text: S.s_doi_bai_7b81488f; kind: "ghost"; onActivated: root.swap() }
            Button {
                visible: !root.playing && (root.online || root.load.kind === "done")
                objectName: "musicDetailPreview"
                text: root.previewing ? S.s_dung_nghe_thu_41a2925b : S.s_nghe_thu_fa024065
                icon: root.previewing ? "square" : "play"; kind: "ghost"
                onActivated: root.preview()
            }
            Button {
                visible: !root.playing && root.load.kind === "loading"
                text: S.s_huy_tai_1a9ff73d + (root.load.percent !== null && root.load.percent !== undefined ? "\u00a0·\u00a0" + root.load.percent + " %" : "")
                icon: "x"; kind: "ghost"; onActivated: root.cancelDownload()
            }
            Button {
                visible: !root.playing && root.load.kind === "done"
                text: S.s_xoa_ban_tai_4b461f4a; kind: "danger"; icon: "trash"
                onActivated: root.unsave()
            }
            Button {
                visible: !root.playing && (root.load.kind === "none" || root.load.kind === "failed")
                objectName: "musicDetailDownload"
                text: root.load.kind === "failed" ? S.s_tai_tiep_1efbd854 : S.s_tai_ve_9b5bdb44
                icon: "download"; kind: "ghost"
                onActivated: root.save()
            }
            Button { visible: root.picking; text: S.s_khong_tu_chon_bai_nay_ab3af35f; kind: "ghost"; onActivated: root.ban() }
        }
        // Vì sao bài này
        Column {
            visible: !!(root.detail && root.detail.why)
            width: parent.width
            spacing: Theme.s8
            Text { text: S.s_vi_sao_bai_nay_f681e004; color: Theme.text; font.pixelSize: Theme.sizeBody; font.weight: Font.DemiBold }
            ClockLabel {
                text: root.detail && root.detail.why ? S.s_khop_0_de400d49(Logic.percent(root.detail.why.fit)) : ""
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
            Repeater {
                model: root.detail && root.detail.why ? root.detail.why.matches : []
                delegate: Column {
                    required property var modelData
                    width: parent ? parent.width : 0
                    Text { text: Logic.labelOf(root.meta ? root.meta.emotions : [], modelData.id); color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
                    Bar { label: S.s_doan_nay_82d01522; score: modelData.scene }
                    Bar { label: S.s_bai_nay_d9683a01; score: modelData.track }
                }
            }
        }
        Column {
            visible: !!(root.detail && root.detail.emotions && root.detail.emotions.length)
            width: parent.width
            spacing: 2
            Text { text: S.s_cam_xuc_05c1aee0; color: Theme.text; font.pixelSize: Theme.sizeBody; font.weight: Font.DemiBold; bottomPadding: Theme.s4 }
            Repeater {
                model: root.detail ? root.detail.emotions || [] : []
                delegate: Bar {
                    required property var modelData
                    objectName: "musicEmotion"
                    label: Logic.labelOf(root.meta ? root.meta.emotions : [], modelData.id)
                    score: modelData.score
                }
            }
        }
        Column {
            visible: !!root.detail
            width: parent.width
            Repeater {
                model: {
                    const d = root.detail
                    if (!d) return []
                    const rows = []
                    const energy = Logic.energyPercent(d.arousal)
                    if (energy !== null) rows.push([S.s_nang_luong_1b9cc9af, energy + " %"])
                    if (d.bpm > 0) rows.push([S.s_nhip_8a75919d, S.s_0_nhip_phut_3c154e09(Math.round(d.bpm))])
                    if (d.style) rows.push([S.s_phong_cach_d80ae8d9, Logic.labelOf(root.meta ? root.meta.styles : [], d.style)])
                    if (d.duration) rows.push([S.s_do_dai_5e055f59, Logic.clock(d.duration)])
                    if (d.vocals >= 0.5) rows.push([S.s_co_loi_4b381f10, null])
                    if (d.license) rows.push([S.s_giay_phep_b609ade1, String(d.license).toUpperCase()])
                    if (d.playlists && d.playlists.length) rows.push([S.s_co_trong_1312af9f, d.playlists.map(item => item.name).join(", ")])
                    return rows
                }
                delegate: Item {
                    required property var modelData
                    width: parent ? parent.width : 0
                    height: Math.max(name.height, value.height) + Theme.s8
                    Text { id: name; width: 140; text: modelData[0]; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
                    Text { id: value; x: 140; width: parent.width - 140; visible: modelData[1] !== null; text: modelData[1] || ""; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
                    Icon { x: 140; visible: modelData[1] === null; name: "check"; size: 16; color: Theme.success }
                }
            }
        }
        Column {
            visible: !!(root.detail && (root.detail.attribution || root.detail.landing))
            width: parent.width
            spacing: Theme.s4
            Text { visible: !!(root.detail && root.detail.attribution); text: S.s_ghi_cong_9c291f64; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Font.DemiBold }
            Text {
                visible: !!(root.detail && root.detail.attribution)
                width: parent.width; text: root.detail ? root.detail.attribution || "" : ""
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
            TextLink {
                visible: !!(root.detail && String(root.detail.landing || "").indexOf("https://") === 0)
                text: S.s_mo_trang_nguon_af980960
                accent: true
                onClicked: Qt.openUrlExternally(root.detail.landing)
            }
        }
    }

    component Bar: Item {
        property string label: ""
        property real score: 0
        width: parent ? parent.width : 0
        height: 24
        Text { width: 120; anchors.verticalCenter: parent.verticalCenter; text: parent.label; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; elide: Text.ElideNone; wrapMode: Text.Wrap }
        Rectangle {
            x: 128; width: parent.width - 128 - 52; height: 8; radius: height / 2
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.sunken
            Rectangle { width: parent.width * Math.max(0, Math.min(1, parent.parent.score)); height: parent.height; radius: height / 2; color: Theme.accent }
        }
        Text {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: Logic.percent(parent.score) + " %"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; font.features: {"tnum": 1}
        }
    }
}
