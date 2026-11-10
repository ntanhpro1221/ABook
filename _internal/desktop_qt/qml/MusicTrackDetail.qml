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
        Row {
            visible: !!root.detail && !root.playing
            width: parent.width
            spacing: Theme.s8
            Button {
                width: (parent.width - parent.spacing) / 2
                objectName: "musicDetailPreview"
                text: root.previewing ? S.s_dung_nghe_f20939be : S.s_nghe_thu_fa024065
                icon: root.previewing ? "square" : "play"
                enabled: root.online || root.load.kind === "done"
                onActivated: root.preview()
            }
            Button {
                width: (parent.width - parent.spacing) / 2
                objectName: "musicDetailDownload"
                kind: "outline"
                text: root.load.kind === "loading" ? S.s_huy_tai_1a9ff73d + (root.load.percent !== null && root.load.percent !== undefined ? "\u00a0·\u00a0" + root.load.percent + " %" : "")
                    : root.load.kind === "done" ? S.s_xoa_ban_tai_4b461f4a : root.load.kind === "failed" ? S.s_tai_tiep_1efbd854 : S.s_tai_ve_9b5bdb44
                icon: root.load.kind === "loading" ? "x" : root.load.kind === "done" ? "trash" : "download"
                enabled: root.online || root.load.kind === "done" || root.load.kind === "loading"
                Accessible.name: root.load.kind === "done" ? S.s_xoa_ban_tai_4b461f4a : text
                onActivated: root.load.kind === "loading" ? root.cancelDownload() : root.load.kind === "done" ? root.unsave() : root.save()
            }
        }
        Flow {
            visible: !!root.detail && (root.picking || root.playing)
            width: parent.width
            spacing: Theme.s8
            Button { visible: root.picking; objectName: "musicDetailUse"; text: S.s_dung_7927ca4e; kind: "ghost"; onActivated: root.use() }
            Button {
                visible: root.playing
                objectName: "musicDetailSave"
                text: root.detail && root.detail.saved ? S.s_bo_luu_2fd51455 : S.s_luu_e91f26c0
                kind: root.detail && root.detail.saved ? "ghost" : "primary"
                onActivated: root.detail && root.detail.saved ? root.unsave() : root.save()
            }
            Button { visible: root.playing; text: S.s_xem_trong_kho_2a139d05; kind: "ghost"; onActivated: root.openLibrary(root.detail ? root.detail.title || "" : "") }
            Button { visible: root.playing && !!root.context; text: S.s_doi_bai_7b81488f; kind: "ghost"; onActivated: root.swap() }
            Button { visible: root.picking; text: S.s_khong_tu_chon_bai_nay_ab3af35f; kind: "ghost"; onActivated: root.ban() }
        }
        // Vì sao bài này
        Column {
            visible: !!(root.detail && root.detail.why && root.detail.why.matches.length)
            width: parent.width
            spacing: Theme.s8
            Text { text: S.s_vi_sao_bai_nay_f681e004; color: Theme.text; font.pixelSize: Theme.sizeBody; font.weight: Font.DemiBold }
            Text {
                width: parent.width; wrapMode: Text.Wrap
                text: root.detail && root.detail.why && root.detail.why.matches.length ? S.s_doan_va_bai_cung_0_music(Logic.labelOf(root.meta ? root.meta.emotions : [], root.detail.why.matches[0].id)) : ""
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
            Row {
                spacing: Theme.s16
                Row {
                    spacing: Theme.s4
                    Rectangle { width: 16; height: 4; anchors.verticalCenter: parent.verticalCenter; color: Theme.text3 }
                    Text { text: S.s_doan_nay_82d01522; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                }
                Row {
                    spacing: Theme.s4
                    Rectangle { width: 16; height: 4; anchors.verticalCenter: parent.verticalCenter; color: Theme.accent }
                    Text { text: S.s_bai_nay_d9683a01; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                }
            }
            Repeater {
                model: root.detail && root.detail.why ? root.detail.why.matches : []
                delegate: Item {
                    required property var modelData
                    width: parent ? parent.width : 0
                    height: Math.max(28, whyLabel.implicitHeight)
                    Text { id: whyLabel; width: 120; anchors.verticalCenter: parent.verticalCenter; text: Logic.labelOf(root.meta ? root.meta.emotions : [], modelData.id); color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
                    Column {
                        x: 128; width: parent.width - x; spacing: 4; anchors.verticalCenter: parent.verticalCenter
                        LevelBar { width: parent.width; height: 4; score: modelData.scene; ink: Theme.text3; label: whyLabel.text + ": " + S.s_doan_nay_82d01522 }
                        LevelBar { width: parent.width; height: 4; score: modelData.track; label: whyLabel.text + ": " + S.s_bai_nay_d9683a01 }
                    }
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
            Text { text: S.s_thong_tin_4aa16c92; color: Theme.text; font.pixelSize: Theme.sizeBody; font.weight: Font.DemiBold; bottomPadding: Theme.s8 }
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
                    if (d.license) rows.push([S.s_giay_phep_b609ade1, Logic.licenseLabel(d.license, d.licenseUrl)])
                    if (d.playlists && d.playlists.length) rows.push([S.s_co_trong_1312af9f, d.playlists.map(item => item.name).join(", ")])
                    if (d.attribution) rows.push([S.s_ghi_cong_9c291f64, d.attribution])
                    if (String(d.landing || "").indexOf("https://") === 0) rows.push([S.s_nguon_c76d57b3, S.s_mo_trang_nguon_af980960, d.landing])
                    return rows
                }
                delegate: Item {
                    required property var modelData
                    width: parent ? parent.width : 0
                    height: Math.max(name.height, modelData[2] ? source.height : value.height) + Theme.s8
                    Text { id: name; width: 140; text: modelData[0]; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
                    Text { id: value; x: 140; width: parent.width - 140; visible: modelData[1] !== null && !modelData[2]; text: modelData[1] || ""; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
                    Icon { x: 140; visible: modelData[1] === null; name: "check"; size: 16; color: Theme.success }
                    TextLink { id: source; x: 140; width: parent.width - 140; visible: !!modelData[2]; text: modelData[1] || ""; accent: true; onClicked: Qt.openUrlExternally(modelData[2]) }
                }
            }
        }
    }

    component Bar: Item {
        property string label: ""
        property real score: 0
        width: parent ? parent.width : 0
        height: 24
        Text { width: 120; anchors.verticalCenter: parent.verticalCenter; text: parent.label; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; elide: Text.ElideNone; wrapMode: Text.Wrap }
        LevelBar {
            x: 128; width: parent.width - 128 - 52; height: 6
            anchors.verticalCenter: parent.verticalCenter
            score: parent.score; label: parent.label
        }
        Text {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: Logic.percent(parent.score) + " %"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; font.features: {"tnum": 1}
        }
    }
}
