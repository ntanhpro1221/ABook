import QtQuick
import QtQuick.Dialogs
import ABook
import "MyMusicText.js" as Music

// "Nhạc của tôi" trong Cài đặt › Nghe › Nhạc nền (MyMusicSection của listen/MyMusic.tsx, docs/MUSIC_IMPORT.md): nhạc bạn tự có làm nhạc nền. Khối gập
// (Fold "my-music.library", mặc định gập, nhớ lần sau): nút nhập, thẻ Phân tích nhạc, lời giới thiệu, "Nhạc riêng", rồi danh sách bài. Nhập từng file
// một để thấy tiến độ; xoá hai bước (Back về bước trước). Cùng JSON với máy tính / điện thoại: GET /api/music/local, POST .../import, DELETE .../<mã>.
Column {
    id: root
    objectName: "myMusic"
    property var view: null                 // LocalMusicView của lần trả lời gần nhất
    property bool loadFailed: false
    property var progress: null             // {done, total} khi đang nhập
    property string removing: ""            // link bài đang hỏi lại xoá
    property bool removingNow: false
    property string picking: ""             // link bài đang đổi công tắc tự chọn
    property bool canImport: true           // máy tính có hộp chọn file của hệ điều hành
    property bool open: Platform.setting("fold.my-music.library", "0") === "1"
    property var results: []
    property var chosen: []
    property bool firstBatch: true
    readonly property var tracks: view ? (view.tracks || []) : []
    readonly property string phase: view === null ? (loadFailed ? "error" : "loading") : (canImport && !tracks.length ? "empty" : "ready")

    function load() {
        Api.call("GET", "/api/music/local", null, function(data, error) {
            if (error) { if (!root.view) root.loadFailed = true; return }
            root.loadFailed = false
            root.refresh(data)
        })
    }
    // Lời đáp mới của máy chủ: danh sách bài và mô-đun đổi theo (refresh của bản web)
    function refresh(next) {
        view = next
        syncRows()
    }
    function syncRows() {
        const wanted = (view && view.tracks) || []
        const keep = {}
        for (const track of wanted) keep[track.link] = track
        for (let i = rows.count - 1; i >= 0; --i) {
            const link = rows.get(i).key
            if (keep[link]) { rows.setProperty(i, "json", JSON.stringify(keep[link])); rows.setProperty(i, "leaving", false); delete keep[link] }
            else rows.setProperty(i, "leaving", true)
        }
        for (const track of wanted) if (keep[track.link]) rows.append({key: track.link, json: JSON.stringify(track), leaving: false, instant: firstBatch})
        firstBatch = false
        if (rows.count && wanted.length < rows.count) purge.restart()
    }
    function toast(title, description) { Api.notice = Music.toast(title, description) }

    // ---- nhập ----
    function importFiles(paths) {
        if (!paths.length || progress) return
        chosen = paths
        results = []
        progress = {done: 0, total: paths.length}
        importNext(0)
    }
    function importNext(at) {
        Api.call("POST", "/api/music/local/import", {paths: [chosen[at]]}, function(data, error) {
            if (error) { root.finishImport(error); return }
            root.results = root.results.concat([data])
            root.refresh(data)
            root.progress = {done: at + 1, total: root.chosen.length}
            if (at + 1 < root.chosen.length) root.importNext(at + 1)
            else root.finishImport("")
        })
    }
    function finishImport(error) {
        progress = null
        const merged = results.length ? Music.mergeImports(results) : null
        let words = error ? Music.toast("Đang thêm nhạc thì dừng", error) : ""
        if (merged) {
            refresh(merged)
            const summary = Music.importSummary(merged)
            words += (words ? "\n\n" : "") + Music.toast(summary.title, summary.description)
        }
        if (words) Api.notice = words
    }

    // ---- xoá ----
    function removeTrack(link) {
        removingNow = true
        Api.call("DELETE", "/api/music/local/" + link.slice(Music.LOCAL_PREFIX.length), null, function(data, error) {
            root.removingNow = false
            if (error) { root.toast("Chưa xoá được bài này", error); return }
            root.refresh(data)
            root.removing = ""
            Api.notice = "Đã xoá khỏi Nhạc của tôi"
        })
    }
    // ---- công tắc tự chọn của một bài (AutoPickNote) ----
    function pickAuto(track, next) {
        const digest = Music.localDigest(track.link)
        if (!digest || picking) return
        picking = track.link
        Api.call("POST", "/api/music/local/" + digest + "/auto", {auto: next}, function(data, error) {
            root.picking = ""
            if (error) { root.toast("Chưa đổi được", error); return }
            root.refresh(data)
        })
    }

    // Back đóng bước hỏi lại xoá trước (useBackLayer của bản web)
    property QtObject backLayer: QtObject { function close() { root.removing = "" } }
    onRemovingChanged: {
        Nav.closedLayer(backLayer)
        if (removing !== "") Nav.openLayer(backLayer)
    }
    Component.onCompleted: load()
    Component.onDestruction: Nav.closedLayer(backLayer)

    ListModel { id: rows }
    Timer { id: purge; interval: 400; onTriggered: { for (let i = rows.count - 1; i >= 0; --i) if (rows.get(i).leaving) rows.remove(i) } }
    FileDialog {
        id: files
        title: "Chọn nhạc của bạn"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Nhạc (*.mp3 *.m4a *.ogg *.opus *.flac *.wav)"]
        onAccepted: root.importFiles(selectedFiles.map(url => DesktopApi.localPath(url)))
    }

    DisclosureRow {
        width: parent.width
        section: true
        title: "Nhạc của tôi"
        summary: root.tracks.length ? root.tracks.length + " bài" : "Chưa có bài nào"
        expanded: root.open
        onClicked: {
            root.open = !root.open
            Platform.setSetting("fold.my-music.library", root.open ? "1" : "0")
        }
    }
    Collapse {
        width: parent.width
        open: root.open
        spacing: 8
        Flow {
            width: parent.width
            visible: root.canImport
            Button {
                text: root.progress ? "Đang thêm " + root.progress.done + "/" + root.progress.total : "Thêm nhạc của bạn"
                icon: "upload"; kind: "ghost"; size: "sm"; wrap: true
                width: Math.min(implicitWidth, parent.width)
                busy: Boolean(root.progress)
                onActivated: files.open()
            }
        }
        Collapse {
            width: parent.width
            open: root.tracks.length > 0
            MyMusicModule { width: parent.width; view: root.view; onUpdated: next => root.refresh(next) }
        }
        HintText { width: parent.width; text: Music.MY_MUSIC_INTRO }
        MoreInfo { width: parent.width; label: "Nhạc riêng"; HintText { width: parent.width; text: Music.MY_MUSIC_HELP } }
        Collapse {
            width: parent.width
            open: !root.canImport
            HintText { width: parent.width; text: "Thêm và xoá nhạc làm trên máy tính chủ sách." }
        }
        MyMusicState {
            width: parent.width
            state: root.phase
            adding: Boolean(root.progress)
            onRetry: { root.loadFailed = false; root.load() }
            onAdd: files.open()
        }
        Column {
            id: list
            objectName: "musicTrackList"
            width: Math.min(parent.width, Theme.listMeasure)
            Repeater {
                model: rows
                MyMusicTrack {
                    id: entry
                    objectName: "track:" + model.key
                    width: list.width
                    track: JSON.parse(model.json)
                    first: model.index === 0
                    leaving: model.leaving
                    canImport: root.canImport
                    confirming: root.removing === model.key
                    removing: root.removingNow && root.removing === model.key
                    picking: root.picking === model.key
                    entered: model.instant
                    onAskRemove: root.removing = model.key
                    onKeep: root.removing = ""
                    onRemove: root.removeTrack(model.key)
                    onPick: next => root.pickAuto(track, next)
                }
            }
        }
        Item { width: 1; height: 0 }    // pb-2 của thân Fold: khoảng cách 8 còn lại sau danh sách
    }
}
