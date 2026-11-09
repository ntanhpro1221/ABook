import "UiStrings.js" as S
import QtQuick
import ABook
import "StudioMusicLogic.js" as Logic

// "Nhạc theo ngữ cảnh" (MoodsPanel của MusicTab.tsx): model nhỏ (tuỳ chọn, tải khi bấm) đọc nguyên đoạn để chọn nhạc sát không khí hơn. Chưa tải:
// "Tải thêm"; đang tải: tiến độ (hỏi lại mỗi 2 giây, chỉ khi cửa sổ đang thấy); đã tải: "Đọc lại ngữ cảnh" cho cuốn này.
Column {
    id: root
    objectName: "studioMusicMoods"
    property var store: null
    property string bookId: ""
    property var moods: null                // {running, error} của GET /music
    signal computed(var view)
    property var model: null
    property bool downloading: false        // đang gửi lệnh tải
    property bool computing: false          // đang gửi lệnh đọc lại
    readonly property bool running: Boolean(moods && moods.running) || computing
    readonly property string phase: Logic.moodsState(model, !!store && (store.remote || !!store.peer))
    readonly property var percent: Logic.moodsPercent(model)
    spacing: 8

    function load() {
        store.request("GET", "/api/music/moods-model", null, function(status, data) {
            if (root.store.ok(status) && data) root.model = data
        })
    }
    function download() {
        downloading = true
        store.request("POST", "/api/music/moods-model", null, function(status, data) {
            root.downloading = false
            if (root.store.ok(status) && data) root.model = data
            else Api.notice = S.s_chua_tai_duoc_phan_doc_khong_khi_95a9edf6 + root.store.errorText(status, data)
        })
    }
    function compute() {
        computing = true
        store.request("POST", "/api/books/" + bookId + "/music/moods", null, function(status, data) {
            root.computing = false
            if (root.store.ok(status) && data) root.computed(data)
            else Api.notice = S.s_chua_doc_lai_duoc_khong_khi_cac_doan_66dab5e3 + root.store.errorText(status, data)
        })
    }
    Component.onCompleted: load()
    Timer {
        objectName: "moodsModelPoll"
        interval: 2000
        repeat: true
        running: !!root.store && root.store.active && !!root.model && Boolean(root.model.downloading)
        onTriggered: root.load()
    }

    Collapse {
        width: parent.width
        open: root.phase !== "none"
        spacing: 8
        Text { width: parent.width; text: S.s_hieu_ngu_canh_de_chon_nhac_1_phut_moi_gio_1ed08581; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        Flow {
            width: parent.width
            visible: root.phase === "installed"
            spacing: 12
            Button {
                objectName: "moodsCompute"
                text: root.running ? S.s_dang_doc_khong_khi_0640731b : S.s_doc_lai_ngu_canh_edb18d3a
                icon: "refresh-cw"; kind: "ghost"; size: "sm"
                busy: root.running
                onActivated: root.compute()
            }
            Text {
                visible: !!root.moods && !!root.moods.error
                width: Math.min(implicitWidth, parent.width)
                height: 32; verticalAlignment: Text.AlignVCenter
                text: root.moods ? root.moods.error || "" : ""
                color: Theme.warning
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        ClockLabel {
            width: parent.width
            visible: root.phase === "downloading"
            text: S.s_dang_tai_phan_doc_khong_khi_a6481b11 + (root.percent !== null ? " - " + root.percent + "%" : "")
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Flow {
            width: parent.width
            visible: root.phase === "offer"
            spacing: 12
            Button {
                objectName: "moodsDownload"
                text: S.s_tai_them_3_2_gb_338f648d
                icon: "download"; kind: "ghost"; size: "sm"
                busy: root.downloading
                onActivated: root.download()
            }
            Text {
                visible: !!root.model && !!root.model.error
                width: Math.min(implicitWidth, parent.width)
                height: 32; verticalAlignment: Text.AlignVCenter
                text: root.model ? root.model.error || "" : ""
                color: Theme.warning
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        Text {
            width: parent.width
            visible: root.phase === "elsewhere"
            text: root.model && root.model.downloadable ? S.s_tai_phan_doc_khong_khi_tren_may_tinh_chu_s_f52208a6 : S.s_may_nay_chua_co_phan_doc_khong_khi_cai_qua_5174e4ee
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
}
