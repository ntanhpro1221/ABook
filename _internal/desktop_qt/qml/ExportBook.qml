import "UiStrings.js" as S
import QtQuick
import ABook
import "ExportLogic.js" as Logic
import "SizeFormat.js" as Size

// Hộp "Xuất “<tên sách>”" của Studio (ExportDialog của studio/ExportBook.tsx): nói trước bản xuất sẽ có gì (bao nhiêu chương, thiếu gì, còn sửa chưa áp),
// chọn kiểu (thư mục MP3 / file .abook / M4B / cả dự án), chọn nơi lưu bằng hộp chọn thư mục của hệ điều hành (Studio từ xa: file nằm ở máy tính), rồi xuất NỀN:
// tiến độ hiện ngay trong hộp, đóng hộp vẫn chạy và báo khi xong, mở lại hộp thì thấy lại tiến độ. Bốn kiểu cùng đi qua MỘT ExportJob.
// Khác bản web: MP3 / M4B cũng báo tiến độ + Huỷ trong hộp (web đặt ở thông báo nổi), nên thông báo xong khi hộp đã đóng không có nút "Mở thư mục".
StudioConfirm {
    id: root
    objectName: "exportBook"
    property var store: null
    property var snapshot: ({})
    property var live: null
    readonly property var book: live && live.id === snapshot.id ? live : snapshot
    property string kind: "mp3"
    property string scope: "part"
    property string layout: "single"
    property bool changedOnly: false
    property bool partial: false
    property var parts: []
    property var history: []
    property var estimate: null
    property var musicState: null
    property var chosenMusic: null
    property var ffmpeg: null
    property var finished: null
    property string askedSize: ""
    property string askedMusic: ""
    signal applyFirst()

    readonly property bool remote: store ? store.remote : false
    readonly property string computer: store ? store.computerName : S.s_may_tinh_8eafc226
    readonly property bool dialogs: !remote                 // Studio từ xa không có hộp chọn thư mục của máy này: file nằm ở máy tính
    readonly property var stale: Logic.staleOf(history)
    readonly property var changedIds: Logic.changedChapters(stale)
    readonly property var plan: Logic.plan(book, {kind: kind, scope: scope, layout: layout, parts: parts.length, changedOnly: changedOnly, changed: changedIds,
                                                 bytes: estimate ? estimate.bytes || 0 : 0})
    readonly property bool audioKind: kind === "mp3" || kind === "m4b"
    readonly property bool withMusic: Logic.musicChecked(musicState, chosenMusic, book.id)
    readonly property bool mixes: audioKind && withMusic
    readonly property bool wantsFfmpeg: open && !job.running && (kind === "m4b" || mixes)
    readonly property bool needsFfmpeg: (kind === "m4b" || mixes) && ffmpeg !== null && !ffmpeg.ready
    readonly property string phase: job.running ? "busy" : finished ? "finished" : "form"
    readonly property alias exportJob: job
    readonly property var kinds: Logic.kindsFor(remote)
    readonly property string savePlace: Logic.savePlace({dialogs: dialogs, remote: remote, computer: computer, libraryRoot: store && store.info ? store.info.libraryRoot : ""})

    title: S.s_xuat_e491a6dc + (book.title || "") + "”"
    description: plan.description
    panelWidth: 512
    actions: phase === "busy"
        ? [{key: "cancel", text: S.s_huy_xuat_ca425e96, kind: "ghost", enabled: !job.cancelling}, {key: "later", text: S.s_dong_cu_de_chay_9a342df0, kind: "ghost"}]
        : phase === "finished"
          ? (remote ? [] : [{key: "reveal", text: S.s_mo_thu_muc_4bf5b127, icon: "folder-open", kind: "ghost"}]).concat([{key: "done", text: S.s_xong_a6f4543a, kind: "primary"}])
          : [{key: "later", text: S.s_thoi_e68f9e88, kind: "ghost"},
             {key: "go", text: dialogs ? S.s_luu_va_xuat_e274cff0 : S.s_xuat_b2ebc56b, icon: Logic.kindInfo(kind).icon, kind: "primary", enabled: !(plan.blocked || needsFfmpeg)}]
    onChosen: key => {
        if (key === "cancel") job.cancel()
        else if (key === "reveal") { if (finished && finished.folder) store.quiet("POST", "/api/reveal-export", {folder: finished.folder}) }
        else if (key === "go") run()
        else close()
    }
    onClosed: finished = null
    onKindChanged: refetch()
    onScopeChanged: refetch()
    onMixesChanged: refetch()
    onPartsChanged: refetch()
    onWantsFfmpegChanged: if (wantsFfmpeg) loadFfmpeg()

    // ---- mở hộp ----
    function begin(data) {
        if (job.bookId !== data.id) { job.reset(); finished = null }
        snapshot = data
        job.bookId = data.id
        scope = "part"; layout = "single"; changedOnly = false; partial = false; chosenMusic = null
        parts = []; history = []; estimate = null; musicState = null; ffmpeg = null; askedSize = ""; askedMusic = ""
        kind = job.running ? job.kind : "mp3"
        show()
        const id = data.id
        get("/api/books/" + id + "/parts", function(result) { root.parts = result.parts || [] })
        loadHistory()
        // Máy chủ đang xuất cuốn này (hộp bị đóng giữa chừng, hay app mở lại): theo tiếp, không cho bấm xuất lần nữa. Studio từ xa cũng hỏi được.
        if (!job.running) job.attachRunning(function(attached) { root.kind = attached })
        refetch()
    }
    function get(path, apply) {
        if (!store) return
        const id = book.id
        store.quiet("GET", path, null, function(data, error) { if (!error && id === root.book.id) apply(data) })
    }
    function loadHistory() { get("/api/books/" + book.id + "/export-history", function(result) { root.history = result || [] }) }
    function loadFfmpeg() { get("/api/ffmpeg", function(result) { root.ffmpeg = result }) }
    // Cỡ file .abook và ô "Kèm nhạc nền" chỉ hỏi khi kiểu đang chọn cần đến
    function refetch() {
        if (!open || !book.id) return
        if (kind === "abook") {
            const key = book.id + ":" + plan.wholeSeries
            if (askedSize !== key) {
                askedSize = key
                get("/api/books/" + book.id + "/export-size" + (plan.wholeSeries ? "?series=1" : ""), function(result) { root.estimate = result })
            }
        }
        if (audioKind && askedMusic !== book.id) {
            askedMusic = book.id
            get("/api/books/" + book.id + "/export-music", function(result) { root.musicState = result })
        }
        if (wantsFfmpeg && ffmpeg === null) loadFfmpeg()
    }

    // ---- chọn nơi lưu rồi xuất ----
    function run() {
        if (plan.blocked || needsFfmpeg || job.running) return
        if (dialogs) folders.choose(Logic.SAVING[kind][0], "")
        else go("")
    }
    function go(target) {
        job.chapters = plan.wholeSeries ? 0 : plan.selectedCount
        job.countText = plan.countText
        finished = null
        job.start(kind, Logic.startBody(kind, {target: target, mixes: mixes, wholeSeries: plan.wholeSeries, changedOnly: changedOnly, changedIds: changedIds, layout: layout, partial: partial}), false)
    }
    function jobEnded(error, result) {
        const made = job.kind
        if (error === Logic.CANCELLED) { store.say(S.s_da_dung_xuat_ab8ac9d1); return }
        if (error) {
            const failure = Logic.failureOf(made, error)
            store.say(failure.title, failure.description)
            return
        }
        const done = Logic.finishedFor(made, result, {remote: remote, computer: computer, chapters: job.chapters})
        // Hộp còn mở: báo ngay trong hộp. Đã đóng: một thông báo; thiếu gì (phần bỏ qua, nguồn chương) thì kèm đúng phần thiếu.
        if (open) finished = done
        else store.say(done.title, done.note)
        store.refresh(book.id)
    }

    NativeFolders { id: folders; onPicked: path => root.go(path) }
    ExportJob { id: job; store: root.store; onEnded: (error, result) => root.jobEnded(error, result) }
    Timer { interval: 5000; repeat: true; running: root.open && root.phase === "form" && root.store !== null && root.store.active; onTriggered: root.loadHistory() }
    Timer { interval: 800; repeat: true; running: root.wantsFfmpeg && root.ffmpeg !== null && root.ffmpeg.downloading && root.store !== null && root.store.active; onTriggered: root.loadFfmpeg() }

    // ---- đang xuất ----
    Collapse {
        objectName: "exportBusyRegion"
        width: parent.width
        open: root.phase === "busy"
        ExportBusy { width: parent.width; fraction: job.view.fraction; title: job.view.title; note: job.view.note }
    }
    // ---- xong ----
    Collapse {
        objectName: "exportDoneRegion"
        width: parent.width
        open: root.phase === "finished"
        ExportDone {
            width: parent.width
            title: root.finished ? root.finished.title : ""
            detail: root.finished ? root.finished.detail : ""
            note: root.finished ? root.finished.note : ""
        }
    }
    // ---- chọn kiểu và lời cảnh báo ----
    Collapse {
        objectName: "exportFormRegion"
        width: parent.width
        open: root.phase === "form"
        spacing: 12
        Collapse {
            width: parent.width
            open: root.parts.length > 1 && !root.plan.whole && root.kind !== "m4b"
            ChoiceRow {
                objectName: "exportScope"
                width: parent.width
                label: S.s_pham_vi_ban_xuat_bcfd596b
                options: Logic.scopeOptions(root.parts.length)
                value: root.scope
                onPicked: value => root.scope = value
            }
        }
        ExportKinds { objectName: "exportKinds"; width: parent.width; kinds: root.kinds; value: root.kind; onPicked: value => root.kind = value }
        Collapse {
            width: parent.width
            open: root.plan.wholeSeries && root.kind === "abook"
            spacing: 8
            ChoiceRow {
                objectName: "exportLayout"
                width: parent.width
                label: S.s_cach_chia_file_14e62e54
                options: Logic.LAYOUTS
                value: root.layout
                onPicked: value => root.layout = value
            }
            Text {
                width: parent.width
                text: root.layout === "single" ? S.s_ca_bo_trong_mot_file_abook_nghe_noi_tiep_c_a02fc82b : S.s_moi_phan_mot_file_cung_thu_muc_cua_bo_4e8f08b0
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        Collapse {
            width: parent.width
            open: root.audioKind && root.musicState !== null && Boolean(root.musicState.available)
            ImportCheck {
                objectName: "exportMusic"
                width: parent.width
                label: S.s_kem_nhac_nen_c616e8d2
                help: Logic.MUSIC_MIX_HINT
                checked: root.withMusic
                onToggled: value => root.chosenMusic = {bookId: root.book.id, on: value}
            }
        }
        Text { objectName: "exportSavePlace"; width: parent.width; text: root.savePlace; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        Collapse {
            width: parent.width
            open: root.kind === "abook" && root.estimate !== null && (root.estimate.bytes || 0) > 0
            Text {
                objectName: "exportEstimate"
                width: parent.width
                text: S.s_co_uoc_tinh_khoang_a6ece2b0 + Size.formatSize(root.estimate ? root.estimate.bytes || 0 : 0)
                      + (root.estimate && root.estimate.musicPending > 0 ? S.s_cong_them_c1382cfe + root.estimate.musicPending + S.s_bai_nhac_khi_xuat_ea744e20 : "")
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        Collapse {
            width: parent.width
            open: root.needsFfmpeg
            FfmpegNeeded {
                width: parent.width
                status: root.ffmpeg
                remote: root.remote
                computer: root.computer
                onDownload: root.store.quiet("POST", "/api/ffmpeg", {}, function(result, error) {
                    if (error) root.store.say(S.s_chua_tai_duoc_cong_cu_cfe422f9, error)
                    else root.ffmpeg = result
                })
                onStop: root.store.quiet("POST", "/api/ffmpeg/cancel", {}, function(result, error) { if (!error) root.ffmpeg = result })
            }
        }
        Collapse {
            id: timingsRegion
            width: parent.width
            open: root.kind === "abook"
            OnComputerPill { Reveal { shown: root.remote } verb: S.s_chu_sang_theo_giong_57fb4327; computer: root.computer; maxWidth: parent.width }
            Loader {
                width: parent.width
                active: timingsRegion.reveal > 0 && !root.remote
                sourceComponent: Component { WordTimings { store: root.store; bookId: root.book.id; bookRunning: Boolean(root.book.running) } }
            }
        }
        Collapse {
            width: parent.width
            open: root.plan.wholeSeries && root.kind === "mp3"
            Text { width: parent.width; text: S.s_moi_phan_mot_thu_muc_con_trong_thu_muc_cua_7e868eba; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        }
        // Hỏi lại mỗi 5 giây: xuất lại xong thì hàng khép tại chỗ, hết hàng thì cả khung khép
        Collapse {
            width: parent.width
            open: root.stale.length > 0
            spacing: 8
            Text { objectName: "exportStaleTitle"; width: parent.width; text: S.s_ban_xuat_da_cu_7e726524; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightBold }
            Repeater {
                model: root.stale
                delegate: Column {
                    required property var modelData
                    objectName: "exportStale"
                    width: parent.width
                    spacing: 8
                    Text {
                        width: parent.width
                        text: modelData.target + "\u00a0·\u00a0" + modelData.changed.length + S.s_chuong_da_doi_a6114cc0
                        color: Theme.text
                        wrapMode: Text.WrapAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Button {
                        objectName: "exportStaleRedo"
                        size: "sm"
                        kind: "ghost"
                        text: Logic.staleAction(modelData)
                        onActivated: { root.kind = modelData.kind; root.scope = "part"; root.changedOnly = modelData.kind === "mp3" }
                    }
                    Text {
                        Reveal { shown: modelData.kind === "m4b" }
                        width: parent.width
                        text: S.s_m4b_gop_ca_cuon_ban_can_dung_lai_ca_file_v_6adad4ec
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
            }
        }
        Collapse {
            width: parent.width
            open: root.kind === "mp3" && !root.plan.wholeSeries && root.changedIds.length > 0
            ImportCheck {
                objectName: "exportChangedOnly"
                width: parent.width
                label: S.s_xuat_00fa2c47 + root.changedIds.length + S.s_chuong_doi_e42b9885
                checked: root.changedOnly
                onToggled: value => root.changedOnly = value
            }
        }
        Collapse {
            width: parent.width
            open: root.kind === "abook"
            ImportCheck {
                width: parent.width
                label: S.s_xuat_mot_phan_fc85b7e5
                checked: root.partial
                onToggled: value => root.partial = value
            }
        }
        Collapse {
            width: parent.width
            open: root.plan.warnings.length > 0 || (!root.plan.whole && Boolean(root.book.pendingChanges))
            spacing: 8
            Repeater {
                model: root.plan.warnings
                delegate: Item {
                    required property string modelData
                    objectName: "exportWarning"
                    width: parent.width
                    height: line.height
                    Icon { x: 0; y: 2; name: "triangle-alert"; size: 16; color: Theme.warning }
                    Text { id: line; x: 24; width: parent.width - 24; text: modelData; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                }
            }
            Flow {
                objectName: "exportPending"
                Reveal { shown: !root.plan.whole && Boolean(root.book.pendingChanges) }
                width: parent.width
                spacing: 8
                Item {
                    width: Math.min(parent.width, Math.max(220, parent.width - again.implicitWidth - 8))
                    height: pendingLine.height
                    Icon { x: 0; y: 2; name: "triangle-alert"; size: 16; color: Theme.warning }
                    Text {
                        id: pendingLine
                        x: 24
                        width: parent.width - 24
                        text: S.s_con_71d0e2b2 + root.book.pendingChanges + S.s_thay_doi_chua_ap_ban_xuat_doc_nhu_truoc_kh_3a7b1e79
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
                Button { id: again; objectName: "exportApplyFirst"; size: "sm"; kind: "ghost"; icon: "refresh-cw"; text: S.s_ap_dung_truoc_fec0937b; onActivated: { root.dismiss(); root.applyFirst() } }
            }
        }
    }
}
