import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic
import "TextWrap.js" as TextWrap
import "SizeFormat.js" as Size

// Màn "Nhạc" (ui/src/music/MusicScreen.tsx; DESIGN.md §7 "Nhạc"): "Đã lưu" (bài đã lưu + đã tải để nghe không mạng, rồi "Nhạc của tôi")
// và "Kho nhạc" (tìm bỏ dấu, lọc theo danh sách phát / phong cách / cảm xúc / nhịp / độ dài / đã tải, đếm số bài, danh sách cuộn ảo). Lọc chạy ở
// máy chủ (GET /api/music/library) như bản web. Bấm bài mở chi tiết. `pickBook` + `pickScene`: chế độ chọn bài cho một đoạn ("Đổi bài" ›
// "Xem cả kho"): mỗi bài có "Dùng", chọn xong lưu như gợi ý sẵn có (PUT /api/books/<id>/music {pins}) rồi quay lại. Rời màn thì dừng nghe thử.
FocusScope {
    id: root
    objectName: "musicScreen"
    property string pickBook: ""
    property string pickScene: ""
    property int part: picking ? 1 : 0                  // 0 Đã lưu, 1 Kho nhạc
    property var filters: Logic.noFilters()
    property string query: ""
    property var meta: null
    property var list: null
    property var savedList: null
    property var downloads: null
    property string error: ""
    property bool loading: false
    property bool online: true
    readonly property bool picking: pickBook !== "" && pickScene !== ""
    readonly property real contentW: Math.min(width - 2 * Theme.margin, 880)
    readonly property real contentX: (width - contentW) / 2
    readonly property var shown: part === 1 ? (list ? list.tracks : []) : (savedList ? savedList.tracks : [])
    readonly property bool busy: !!(downloads && downloads.active && Object.keys(downloads.active).length)
    readonly property string previewing: Clip.current.indexOf("library:") === 0 ? Clip.current.slice(8) : ""

    function refresh() {
        loading = true
        const forSaved = part === 0
        const effective = Object.assign({}, filters, {q: query})
        Api.quiet("GET", "/api/music/library" + Logic.libraryQuery(forSaved ? Logic.noFilters() : effective, forSaved), null, function(data, problem) {
            loading = false
            online = !problem
            if (problem) { error = problem; return }
            error = data.error || ""
            if (forSaved) savedList = data; else list = data
        })
    }
    function loadMeta() { Api.quiet("GET", "/api/music/library/meta", null, function(data, problem) { if (!problem) meta = data }) }
    function pollDownloads() { Api.quiet("GET", "/api/music/library/downloads", null, function(data, problem) { if (!problem) { const was = busy; downloads = data; if (was && !busy) refresh() } }) }
    function setFilter(key, value) { const next = Object.assign({}, filters); next[key] = value; filters = next; refresh() }
    function clearFilters() { filters = Logic.noFilters(); refresh() }
    function save(links) {
        Api.quiet("POST", "/api/music/library/save", {links: links}, function(data, problem) {
            if (problem) { Api.notice = problem; return }
            downloads = data; refresh(); detail.reload()
        })
    }
    function unsave(links) {
        Api.quiet("POST", "/api/music/library/unsave", {links: links}, function(data, problem) {
            if (problem) { Api.notice = problem; return }
            downloads = data; refresh(); detail.reload()
        })
    }
    function togglePreview(track) {
        if (!online && !track.downloaded) return
        const start = Number(track.audibleStart) || 0
        Clip.toggle("library:" + track.link, Logic.previewPath(track.link), start, start + Logic.PREVIEW_SECONDS)
    }
    function use(link) {
        Api.quiet("PUT", "/api/books/" + encodeURIComponent(pickBook) + "/music", {pins: (function() { const pins = {}; pins[pickScene] = link; return pins })()}, function(data, problem) {
            if (problem) { Api.notice = problem; return }
            detail.open = false
            Api.notice = S.s_da_chon_bai_cho_doan_nay_774deab2
            Nav.back()
        })
    }
    function ban(link) {
        Api.quiet("PUT", "/api/books/" + encodeURIComponent(pickBook) + "/music", {ban: [link]}, function(data, problem) {
            if (problem) { Api.notice = problem; return }
            detail.open = false
            Api.notice = S.s_khong_tu_chon_02ae1742
        })
    }
    function search(text) { part = 1; query = text; refresh() }

    onPartChanged: refresh()
    onQueryChanged: queryTimer.restart()
    Component.onCompleted: { loadMeta(); refresh(); pollDownloads() }
    Component.onDestruction: if (previewing !== "") Clip.stop()
    onVisibleChanged: if (!visible && previewing !== "") Clip.stop()
    Timer { id: queryTimer; interval: 120; onTriggered: root.refresh() }
    Timer { interval: 700; repeat: true; running: root.busy && root.visible; onTriggered: root.pollDownloads() }

    ScreenHeader {
        id: header
        x: root.contentX; width: root.contentW
        title: root.picking ? S.s_chon_bai_cho_doan_840afc40 : S.s_nhac_0e4413e9
        showBack: root.picking
        subtitle: root.part === 0 && root.savedList ? S.s_da_tai_0_bai_1_3cac202f(root.savedList.saved.count, Size.formatSize(root.savedList.saved.bytes)) : ""
    }
    Column {
        id: controls
        x: root.contentX; y: header.y + header.height + Theme.s16
        width: root.contentW
        spacing: Theme.s12
        PageSwitch {
            objectName: "musicParts"
            visible: !root.picking
            labels: [S.s_da_luu_6379aeba, S.s_kho_nhac_94affa81]
            index: root.part
            onPicked: index => root.part = index
        }
        FormField {
            objectName: "musicSearch"
            visible: root.part === 1
            width: parent.width
            label: S.s_tim_trong_kho_nhac_b9972ac9; placeholderText: S.s_tim_ten_bai_nguoi_sang_tac_fdee04f4
            text: root.query
            onTextChanged: root.query = text
        }
        Flow {
            objectName: "musicFilters"
            visible: root.part === 1
            width: parent.width
            spacing: Theme.s8
            Accessible.name: S.s_loc_kho_nhac_6c590fb5
            Repeater {
                model: [
                    {key: "playlist", label: S.s_danh_sach_phat_26862e10, options: root.meta ? root.meta.playlists.map(item => ({value: item.id, label: item.name})) : []},
                    {key: "style", label: S.s_phong_cach_d80ae8d9, options: root.meta ? root.meta.styles.map(item => ({value: item.id, label: item.label})) : []},
                    {key: "emotion", label: S.s_cam_xuc_05c1aee0, options: root.meta ? root.meta.emotions.map(item => ({value: item.id, label: item.label})) : []},
                    {key: "tempo", label: S.s_nhip_8a75919d, options: [{value: "slow", label: S.s_cham_6ddeaddc}, {value: "mid", label: S.s_vua_8af1c03b}, {value: "fast", label: S.s_nhanh_c2385879}]},
                    {key: "length", label: S.s_do_dai_5e055f59, options: [{value: "short", label: S.s_duoi_2_phut_c8f6f04e}, {value: "mid", label: S.s_2_5_phut_29244d26}, {value: "long", label: S.s_tren_5_phut_42aafebc}]},
                ]
                delegate: Select {
                    required property var modelData
                    objectName: "musicFilter_" + modelData.key
                    width: 180
                    label: modelData.label
                    placeholder: modelData.label
                    options: [{value: "", label: S.s_tat_ca_49c73a31}].concat(modelData.options)
                    value: root.filters[modelData.key] || ""
                    onPicked: value => root.setFilter(modelData.key, value)
                }
            }
            ChoiceChip {
                normalFill: Theme.hover
                objectName: "musicFilterDownloaded"
                text: S.s_da_tai_b7362bbf
                selected: root.filters.downloaded
                onClicked: root.setFilter("downloaded", !root.filters.downloaded)
            }
        }
        Item {
            visible: root.part === 1
            width: parent.width
            height: Math.max(count.height, clear.height)
            Text {
                id: count
                objectName: "musicCount"
                anchors.verticalCenter: parent.verticalCenter
                text: S.s_0_bai_1e392237(root.list ? root.list.count : 0)
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
            Row {
                anchors.right: parent.right
                spacing: Theme.s8
                TextLink { id: clear; visible: Logic.filtering(root.filters); text: S.s_bo_loc_74de0064; onClicked: root.clearFilters() }
                Button {
                    visible: root.filters.playlist !== "" && !!root.list && root.list.missingBytes > 0
                    objectName: "musicSavePlaylist"
                    text: S.s_tai_ca_danh_sach_0_63e52378(Size.formatSize(root.list ? root.list.missingBytes : 0))
                    kind: "ghost"; size: "sm"; icon: "download"
                    onActivated: root.save(root.list.tracks.filter(track => !track.downloaded).map(track => track.link))
                }
            }
        }
        Text {
            visible: !root.online || root.error !== ""
            width: parent.width; wrapMode: Text.Wrap
            text: root.error !== "" ? root.error : S.s_mat_mang_chi_nghe_thu_duoc_bai_da_tai_cab0d6f8
            color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
        }
    }
    ListView {
        id: rows
        objectName: "musicList"
        x: root.contentX; y: controls.y + controls.height + Theme.s8
        width: root.contentW
        height: root.height - y - (bar.visible ? bar.height + Theme.s16 : 0)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        model: root.shown
        cacheBuffer: 600
        delegate: MusicTrackRow {
            required property var modelData
            required property int index
            width: rows.width
            track: modelData
            first: index === 0
            downloads: root.downloads
            styles: root.meta ? root.meta.styles : []
            online: root.online
            previewing: root.previewing === modelData.link
            picking: root.picking
            onPreview: root.togglePreview(modelData)
            onUse: root.use(modelData.link)
            onSave: root.save([modelData.link])
            onCancelDownload: root.unsave([modelData.link])
            onClicked: detail.show(modelData.link, root.picking ? {book: root.pickBook, scene: root.pickScene} : null)
        }
        footer: Column {
            width: rows.width
            topPadding: Theme.s16
            spacing: Theme.s8
            Text {
                visible: !root.loading && root.shown.length === 0
                text: root.part === 0 ? S.s_chua_luu_bai_nao_6e7558df : S.s_khong_co_bai_nao_hop_5b5b11b5
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
            // "Nhạc của tôi" (nhạc tự nhập) là một phần của "Đã lưu" - một chỗ duy nhất, như MyMusicSection trong MusicScreen.tsx của web
            MyMusicSettings { visible: root.part === 0; width: parent.width }
        }
    }
    Scrollbar { target: rows }
    SmoothWheel { flick: rows }
    // "Đang nghe thử · tên · ■"
    Rectangle {
        id: bar
        objectName: "musicPreviewBar"
        visible: root.previewing !== ""
        x: root.contentX; width: root.contentW
        y: root.height - height - Theme.s8
        height: 48
        radius: Theme.radiusControl
        color: Theme.panel
        border.color: Theme.line
        readonly property var track: root.shown.find(item => item.link === root.previewing) || null
        Text {
            x: Theme.s16; width: parent.width - stop.width - 2 * Theme.s16
            anchors.verticalCenter: parent.verticalCenter
            text: TextWrap.keepDots(S.s_dang_nghe_thu_f1fb4cba + (bar.track ? "\u00a0·\u00a0" + bar.track.title : ""))
            color: Theme.text; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap
        }
        IconButton { id: stop; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; icon: "square"; tip: S.s_dung_nghe_f20939be; onClicked: Clip.stop() }
    }
    MusicTrackDetail {
        id: detail
        meta: root.meta
        downloads: root.downloads
        picking: root.picking
        online: root.online
        previewing: root.previewing !== "" && root.previewing === detail.link
        onPreview: if (detail.detail) root.togglePreview(detail.detail)
        onSave: root.save([detail.link])
        onUnsave: root.unsave([detail.link])
        onCancelDownload: Api.quiet("POST", "/api/music/library/unsave", {links: [detail.link]}, function(data, problem) { if (!problem) { root.downloads = data; detail.reload() } })
        onUse: root.use(detail.link)
        onBan: root.ban(detail.link)
    }
}
