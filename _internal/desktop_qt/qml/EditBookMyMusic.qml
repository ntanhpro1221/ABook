import QtQuick
import QtQuick.Dialogs
import ABook
import "EditBookLogic.js" as Logic

// "Nhạc của tôi" trong hộp "Sửa sách" (MyMusicSection của listen/MyMusic.tsx): nhạc bạn tự có làm nhạc nền - nhập, xem, xoá ở đây; "Đổi bài" ở
// từng đoạn nhạc của sách. Khối gập có nhớ (khoá "my-music.library"), tên + một dòng tóm tắt. Xoá hai bước ("Xoá bài" / "Giữ lại"), Back lùi
// bước xoá trước. Bài đi / đến bằng Collapse (chiều cao chạy), không bật tắt cứng.
Column {
    id: root
    property var view: ({tracks: []})
    property bool loading: true
    property bool failed: false
    property int done: 0
    property int total: 0
    property bool importing: false
    property string removing: ""          // liên kết bài đang hỏi lại "Xoá bài / Giữ lại"
    property bool removeBusy: false
    property bool starting: false         // đang gửi lệnh của thẻ Phân tích nhạc
    property bool expanded: Platform.setting("fold.my-music.library", "0") === "1"
    readonly property var tracks: view.tracks || []
    readonly property var module: view.module || null
    signal changed()

    function load() {
        Api.call("GET", "/api/music/local", null, function(data, error) {
            root.loading = false
            if (error) { Api.notice = ""; root.failed = !root.view.tracks.length; return }
            root.failed = false
            root.apply(data)
        })
    }
    function apply(next) {
        view = next
        // Danh sách hàng: bài mới thêm cuối, bài mất đi khép dần rồi mới gỡ
        const links = (next.tracks || []).map(t => t.link)
        for (let i = 0; i < rowsModel.count; ++i) {
            const at = links.indexOf(rowsModel.get(i).link)
            if (at < 0) rowsModel.setProperty(i, "gone", true)
            else { rowsModel.setProperty(i, "gone", false); rowsModel.setProperty(i, "json", JSON.stringify(next.tracks[at])) }
        }
        for (const track of next.tracks || []) {
            let found = false
            for (let i = 0; i < rowsModel.count; ++i) if (rowsModel.get(i).link === track.link) found = true
            if (!found) rowsModel.append({link: track.link, json: JSON.stringify(track), gone: false})
        }
        purge.restart()
    }
    Component.onCompleted: load()

    // ---- nhập nhạc: từng file một, thấy tiến độ, một file hỏng không làm mất những file đã vào ----
    property var added: []
    property var existing: []
    property var lost: []
    function importNext(paths, at) {
        if (at >= paths.length) { finishImport(null); return }
        done = at; total = paths.length
        Api.call("POST", "/api/music/local/import", {paths: [DesktopApi.localPath(paths[at])]}, function(data, error) {
            if (error) { finishImport(error); return }
            root.added = root.added.concat(data.added || []); root.existing = root.existing.concat(data.existing || []); root.lost = root.lost.concat(data.failed || [])
            root.apply(data); root.done = at + 1
            root.importNext(paths, at + 1)
        })
    }
    function finishImport(error) {
        importing = false
        if (error) Api.notice = Logic.toastText("Đang thêm nhạc thì dừng", error)
        else {
            const summary = Logic.importSummary({added: added, existing: existing, failed: lost})
            Api.notice = Logic.toastText(summary.title, summary.description)
        }
        changed()
    }
    function startImport(paths) {
        importing = true; done = 0; total = paths.length; added = []; existing = []; lost = []
        importNext(paths, 0)
    }
    function removeTrack(link) {
        removeBusy = true
        Api.call("DELETE", "/api/music/local/" + link.slice(6), null, function(data, error) {
            root.removeBusy = false
            if (error) { Api.notice = Logic.toastText("Không xoá được bài này", error); return }
            root.apply(data); root.dropRemoving(); Api.notice = "Đã xoá khỏi Nhạc của tôi"; root.changed()
        })
    }
    function post(path, body) {
        starting = true
        Api.call("POST", path, body || {}, function(data, error) { root.starting = false; if (!error) root.apply(data) })
    }
    // Lớp Back của bước "Xoá bài / Giữ lại"
    QtObject {
        id: removeLayer
        property bool on: false
        function close() { root.dropRemoving() }
    }
    function askRemove(link) { removing = link; if (!removeLayer.on) { removeLayer.on = true; Nav.openLayer(removeLayer) } }
    function dropRemoving() { removing = ""; if (removeLayer.on) { removeLayer.on = false; Nav.closedLayer(removeLayer) } }
    Component.onDestruction: dropRemoving()

    ListModel { id: rowsModel }
    Timer { id: purge; interval: 400; onTriggered: { for (let i = rowsModel.count - 1; i >= 0; --i) if (rowsModel.get(i).gone) rowsModel.remove(i) } }
    // Phân tích nhạc đang chạy: hỏi lại mỗi giây để thấy tiến độ
    Timer {
        interval: 1000
        repeat: true
        running: root.module !== null && (root.module.state === "downloading" || !!root.module.analysing)
        onTriggered: root.load()
    }
    FileDialog {
        id: files
        title: "Chọn nhạc của bạn"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Nhạc (*.mp3 *.m4a *.ogg *.opus *.flac *.wav)"]
        onAccepted: root.startImport(selectedFiles)
    }

    DisclosureRow {
        width: parent.width
        section: true
        title: "Nhạc của tôi"
        summary: root.tracks.length ? root.tracks.length + " bài" : "Chưa có bài nào"
        expanded: root.expanded
        onClicked: { root.expanded = !root.expanded; Platform.setSetting("fold.my-music.library", root.expanded ? "1" : "0") }
    }
    Collapse {
        width: parent.width
        open: root.expanded
        spacing: 8
        Button {
            text: root.importing ? "Đang thêm " + root.done + "/" + root.total : "Thêm nhạc của bạn"
            icon: "upload"
            kind: "ghost"
            size: "sm"
            wrap: true
            busy: root.importing
            onActivated: files.open()
        }
        // Thẻ Phân tích nhạc: chỉ khi đã có bài
        Collapse {
            width: parent.width
            readonly property bool calm: !root.module || (root.module.state === "ready" && !root.module.analysing && !root.module.restart && (root.module.stale || 0) === 0)
            open: root.tracks.length > 0 && !calm
            spacing: 6
            HintText { width: parent.width; text: root.module ? Logic.moduleLabel(root.module) : ""; color: root.module && root.module.state === "error" ? Theme.danger : Theme.text2; visible: text !== "" }
            MoreInfo {
                width: parent.width
                label: "Phân tích nhạc"
                visible: !!root.module && root.module.state === "missing"
                HintText { width: parent.width; text: "Tải một lần, phân tích trên máy rồi dùng không cần mạng. Chưa tải vẫn nhập, nghe và ghim nhạc bằng tay." }
            }
            Item {
                width: parent.width
                height: root.module && root.module.state === "downloading" ? 40 : 0
                visible: height > 0
                Rectangle {
                    y: 17; width: parent.width - cancel.width - 12; height: 6; radius: height / 2; color: Theme.sunken
                    Rectangle { width: parent.width * (root.module ? Logic.modulePercent(root.module) / 100 : 0); height: parent.height; radius: height / 2; color: Theme.accent }
                }
                Button {
                    id: cancel
                    x: parent.width - width
                    visible: !!root.module && !!root.module.cancellable
                    text: "Huỷ"; kind: "ghost"; size: "sm"; busy: root.starting
                    onActivated: root.post("/api/music/local/module/cancel")
                }
            }
            Button {
                readonly property string action: !root.module || root.module.state === "downloading" || root.module.analysing || root.module.state === "unsupported" || root.module.restart ? "" : ((root.module.stale || 0) > 0 && root.module.state === "ready" ? "reanalyse" : "install")
                visible: action !== ""
                size: "sm"; kind: "ghost"; wrap: true; busy: root.starting
                text: !root.module ? "" : action === "reanalyse" ? "Phân tích " + root.module.stale + " bài"
                      : root.module.state === "error" ? "Thử lại"
                      : root.module.stopped ? "Tải lại (" + Logic.formatSize(root.module.outdatedBytes || root.module.total) + ")"
                      : root.module.state === "outdated" ? "Cập nhật (" + Logic.formatSize(root.module.outdatedBytes || root.module.total) + ")"
                      : "Tải (" + Logic.formatSize(root.module.total) + ")"
                onActivated: root.post(action === "reanalyse" ? "/api/music/local/reanalyse" : "/api/music/local/module")
            }
            HintText { width: parent.width; color: Theme.warning; text: "Bạn đang dùng dữ liệu di động - nên đợi khi có Wi-Fi."; visible: !!root.module && !!root.module.metered && root.module.state !== "ready" && root.module.state !== "error" }
        }
        HintText { width: parent.width; text: Logic.MY_MUSIC_INTRO }
        MoreInfo {
            width: parent.width
            label: "Nhạc riêng"
            HintText { width: parent.width; text: Logic.MY_MUSIC_HELP }
        }
        Collapse {
            width: parent.width
            open: root.loading
            EditBookSkeleton { width: parent.width; count: 2; label: "Đang tải nhạc riêng" }
        }
        EditBookError {
            width: parent.width
            open: root.failed && !root.loading
            message: "Bạn hãy thử tải lại nhạc của bạn."
            onRetry: { root.loading = true; root.load() }
        }
        Collapse {
            width: parent.width
            open: !root.loading && !root.failed && root.tracks.length === 0
            Column {
                width: parent.width
                topPadding: 24
                bottomPadding: 24
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 56; height: 56; radius: Theme.radiusCover; color: Theme.accentSoft
                    Icon { anchors.centerIn: parent; name: "eighth-note"; size: 28; color: Theme.accentText }
                }
                Item { width: 1; height: 16 }
                Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "Chưa có bài nào"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBody; font.weight: 600 }
                Item { width: 1; height: 20 }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.importing ? "Đang thêm " + root.done + "/" + root.total : "Thêm nhạc của bạn"
                    icon: "upload"
                    kind: "ghost"
                    busy: root.importing
                    onActivated: files.open()
                }
            }
        }
        Column {
            width: parent.width
            Repeater {
                model: rowsModel
                Collapse {
                    id: item
                    required property int index
                    required property string link
                    required property string json
                    required property bool gone
                    readonly property var track: JSON.parse(json)
                    width: parent.width
                    open: !gone
                    Rectangle { visible: item.index > 0; width: parent.width; height: 1; color: Theme.line }
                    Item {
                        width: parent.width
                        height: Math.max(words.height, ask.height) + 16
                        Column {
                            id: words
                            y: 8
                            width: parent.width - ask.width - 12
                            Text {
                                width: parent.width
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                color: Theme.text
                                font.pixelSize: Theme.sizeBodySmall
                                lineHeight: 1.25
                                textFormat: Text.StyledText
                                // Nốt nhạc nhấn màu đứng đầu tên bài; tên + nghệ sĩ + thời lượng (số đều) như bản web
                                text: "<font color='" + Theme.accentText + "'>♪</font> " + escapeHtml(item.track.title)
                                      + (item.track.creator ? "<font color='" + Theme.text2 + "'> · " + escapeHtml(item.track.creator) + "</font>" : "")
                                      + (item.track.duration ? "<font color='" + Theme.text2 + "'> · " + Logic.formatClock(item.track.duration) + "</font>" : "")
                                function escapeHtml(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
                            }
                            Flow {
                                width: parent.width
                                spacing: 8
                                topPadding: 2
                                readonly property string label: Logic.autoLabel(item.track) || Logic.analysisLabel(item.track)
                                HintText { id: note; width: Math.min(implicitWidth, parent.width); text: parent.label; anchors.verticalCenter: undefined }
                                Button {
                                    readonly property var swap: Logic.autoSwitch(item.track)
                                    text: swap.text
                                    kind: "ghost"
                                    size: "sm"
                                    height: 24
                                    Accessible.name: swap.text + ": " + item.track.title
                                    onClicked: root.post("/api/music/local/" + Logic.localDigest(item.track.link) + "/auto", {auto: swap.next})
                                }
                            }
                        }
                        // Xoá hai bước: hàng nút đổi bề ngang (trượt) chứ không bật tắt
                        Item {
                            id: ask
                            readonly property bool asking: root.removing === item.link
                            x: parent.width - width
                            width: asking ? confirm.natural : single.implicitWidth
                            height: 40
                            clip: true
                            Behavior on width {
                                enabled: !Theme.reduceMotion
                                NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
                            }
                            Button {
                                id: single
                                x: parent.width - width
                                opacity: ask.asking ? 0 : 1
                                enabled: !ask.asking
                                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                                text: "Xoá"; icon: "trash-2"; kind: "ghost"; size: "sm"
                                Accessible.name: "Xoá: " + item.track.title
                                onClicked: root.askRemove(item.link)
                            }
                            Row {
                                id: confirm
                                readonly property real natural: keep.implicitWidth + 4 + drop.implicitWidth
                                x: parent.width - width
                                spacing: 4
                                opacity: ask.asking ? 1 : 0
                                enabled: ask.asking
                                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                                Button {
                                    id: drop
                                    text: "Xoá bài"; icon: "trash-2"; kind: "ghost"; size: "sm"
                                    busy: root.removeBusy
                                    Accessible.name: "Xoá bài: " + item.track.title
                                    onActivated: root.removeTrack(item.link)
                                }
                                Button {
                                    id: keep
                                    text: "Giữ lại"; kind: "ghost"; size: "sm"
                                    enabled: !root.removeBusy
                                    Accessible.name: "Giữ lại: " + item.track.title
                                    onClicked: root.dropRemoving()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
