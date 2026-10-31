import QtQuick
import QtQuick.Dialogs
import ABook
import "MyMusicText.js" as Music

// "Nhạc của tôi" trong tab Nhạc nền của Studio (MyMusic của studio/MusicTab.tsx): nhạc bạn tự có làm nền ngoài danh mục. Nhập, xem, xoá, nghe thử ở
// đây; ghim cho từng đoạn ở "Đổi bài". Nhập / xoá chỉ trên máy tính chủ sách (Studio của máy đã ghép thì một câu thay cho nút). Nhập từng file một
// để thấy tiến độ; xoá hai bước (Back về bước trước). GET /api/music/local, POST .../import, DELETE .../<mã>, POST .../<mã>/auto.
Column {
    id: root
    objectName: "studioMyMusic"
    property var store: null
    property string previewing: ""
    signal preview(string link)
    signal libraryChanged()                 // danh sách đổi: "Đổi bài" đang mở hỏi lại
    readonly property bool canImport: !!store && !store.peer
    property var view: null
    property bool loadFailed: false
    property var progress: null
    property string removing: ""
    property bool removingNow: false
    property string picking: ""
    property var results: []
    property var chosen: []
    property bool firstBatch: true
    readonly property var tracks: view ? (view.tracks || []) : []
    readonly property string phase: !canImport ? "ready" : view === null ? (loadFailed ? "error" : "loading") : (!tracks.length ? "empty" : "ready")
    spacing: 12

    function load() {
        if (!canImport) return
        store.request("GET", "/api/music/local", null, function(status, data) {
            if (!root.store.ok(status) || !data) { if (!root.view) root.loadFailed = true; return }
            root.loadFailed = false
            root.refresh(data, false)
        })
    }
    function refresh(next, changed) {
        view = next
        syncRows()
        if (changed !== false) libraryChanged()
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
    function say(title, status, data) { Api.notice = Music.toast(title, store.errorText(status, data)) }

    // ---- nhập ----
    function importFiles(paths) {
        if (!paths.length || progress) return
        chosen = paths
        results = []
        progress = {done: 0, total: paths.length}
        importNext(0)
    }
    function importNext(at) {
        store.request("POST", "/api/music/local/import", {paths: [chosen[at]]}, function(status, data) {
            if (!root.store.ok(status) || !data) { root.finishImport(root.store.errorText(status, data)); return }
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
        store.request("DELETE", "/api/music/local/" + link.slice(Music.LOCAL_PREFIX.length), null, function(status, data) {
            root.removingNow = false
            if (!root.store.ok(status) || !data) { root.say("Chưa xoá được bài này", status, data); return }
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
        store.request("POST", "/api/music/local/" + digest + "/auto", {auto: next}, function(status, data) {
            root.picking = ""
            if (!root.store.ok(status) || !data) { root.say("Chưa đổi được", status, data); return }
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

    Text { width: parent.width; text: Music.MY_MUSIC_INTRO; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
    MoreInfo { width: parent.width; label: "Nhạc riêng"; HintText { width: parent.width; text: Music.MY_MUSIC_HELP } }
    Text {
        width: parent.width
        visible: !root.canImport
        text: "Nhập/xoá trên máy chủ; ở đây dùng “Đổi bài” để ghim nhạc."
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
    }
    Collapse {
        width: parent.width
        open: root.canImport && root.tracks.length > 0
        spacing: 12
        Flow {
            width: parent.width
            Button {
                objectName: "musicImport"
                text: root.progress ? "Đang thêm " + root.progress.done + "/" + root.progress.total : "Thêm nhạc của bạn"
                icon: "upload"; kind: "ghost"; size: "sm"; wrap: true
                width: Math.min(implicitWidth, parent.width)
                busy: Boolean(root.progress)
                onActivated: files.open()
            }
        }
        MyMusicModule { width: parent.width; view: root.view; onUpdated: next => root.refresh(next) }
    }
    MyMusicState {
        width: parent.width
        visible: root.canImport
        state: root.phase
        adding: Boolean(root.progress)
        emptyTitle: "Thêm nhạc của bạn"
        addText: "Nhập nhạc"
        addKind: "primary"
        onRetry: { root.loadFailed = false; root.load() }
        onAdd: files.open()
    }
    Column {
        id: list
        objectName: "studioTrackList"
        width: Math.min(parent.width, Theme.listMeasure)
        Repeater {
            model: rows
            MyMusicTrack {
                objectName: "track:" + model.key
                width: list.width
                track: JSON.parse(model.json)
                first: model.index === 0
                leaving: model.leaving
                canImport: root.canImport
                canPreview: true
                previewing: root.previewing === model.key
                confirming: root.removing === model.key
                removing: root.removingNow && root.removing === model.key
                picking: root.picking === model.key
                entered: model.instant
                onPreview: root.preview(model.key)
                onAskRemove: root.removing = model.key
                onKeep: root.removing = ""
                onRemove: root.removeTrack(model.key)
                onPick: next => root.pickAuto(track, next)
            }
        }
    }
}
