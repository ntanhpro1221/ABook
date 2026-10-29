import QtQuick
import ABook
import "StudioMusicLogic.js" as Logic

// Tab "Nhạc nền" của trang dự án (MusicTab.tsx; docs/MUSIC_SELECTION_MODEL.md mục 4 - ba tầng chỉnh): cả cuốn (bật/tắt, thể loại của truyện, mức
// nhạc), từng đoạn (đổi bài, im lặng, bỏ ghim), từng bài (không dùng bài này nữa). Máy tự làm hết; mọi chỉnh ở đây là tuỳ chọn và được giữ khi máy
// chọn lại. Sửa nhạc không bao giờ phải đọc lại giọng. Mọi lời gọi đi qua `store` (máy này hay Studio của máy đã ghép); hỏi lại khi đang đọc không
// khí / đang tải sẵn nhạc, nhưng CHỈ khi cửa sổ đang thấy (`store.active`). "Nghe thử": MỘT clip một lúc (Clip), ~20 giây, rời tab thì dừng.
Column {
    id: root
    objectName: "studioMusic"
    property var store: null
    property string bookId: ""
    property var chapters: []
    property Item overlay: null             // nơi đặt bảng "…" của một đoạn (cả màn dự án)
    property var view: null                 // MusicView của lần trả lời gần nhất
    property bool failed: false
    property int generation: 0
    property var pending: null              // thân lệnh PUT đang gửi
    property bool rebuilding: false
    property bool cancelling: false
    property string swapping: ""            // khoá đoạn đang mở "Đổi bài"
    property var menuScene: ({})
    property int libraryVersion: 0          // "Nhạc của tôi" vừa đổi: "Đổi bài" đang mở hỏi lại
    readonly property bool changing: pending !== null
    readonly property var plan: view ? view.plan : null
    readonly property var overrides: view ? view.overrides : ({enabled: true, levelDb: -20, genre: null, pins: {}, silenced: [], banned: []})
    readonly property var taxonomy: view ? view.taxonomy || ({}) : ({})
    readonly property var scenes: plan ? plan.scenes || [] : []
    readonly property var groups: Logic.chapterGroups(scenes)
    readonly property var credits: Logic.credits(plan)
    readonly property bool remote: !!store && (store.remote || !!store.peer)
    readonly property string choosing: {
        const pins = pending ? pending.pins || {} : {}
        for (const key in pins) if (pins[key]) return pins[key]
        return ""
    }
    readonly property string previewing: Clip.current.indexOf("music:") === 0 ? Clip.current.slice(6) : ""
    spacing: 24
    topPadding: 24

    // ---- dữ liệu ----
    function load() {
        if (!store || !bookId) return
        const ask = ++generation
        store.request("GET", "/api/books/" + bookId + "/music", null, function(status, data) {
            if (ask !== root.generation) return
            if (root.store.ok(status) && data) { root.failed = false; root.accept(data) }
            else if (root.view === null) root.failed = true
        })
    }
    // Lời đáp mới; báo những lần chuyển: đọc không khí vừa xong, lượt tải sẵn vừa dừng vì lỗi
    function accept(next) {
        const wasMoods = Boolean(view && view.moods && view.moods.running)
        const wasDownload = Boolean(view && view.download && view.download.active)
        view = next
        const moods = Boolean(next.moods && next.moods.running)
        if (wasMoods && !moods) {
            Api.editedBook(bookId)
            Api.notice = next.moods && next.moods.error ? "Không đọc xong không khí các đoạn\n" + next.moods.error : "Đã đọc xong không khí các đoạn - nhạc đã chọn lại"
        }
        if (wasDownload && !(next.download && next.download.active) && next.error) Api.notice = "Chưa tải được nhạc\n" + next.error
    }
    function refreshSoon() { soon.restart() }
    Timer { id: soon; interval: 600; onTriggered: root.load() }
    readonly property bool polling: !!store && store.active && !!view
                                    && (Boolean(view.moods && view.moods.running) || Boolean(view.download && view.download.active))
    Timer {
        interval: root.view && root.view.moods && root.view.moods.running ? 3000 : 2000
        repeat: true
        running: root.polling
        onTriggered: root.load()
    }
    // Cửa sổ hiện lại (hay đổi máy): hỏi ngay một lần
    Connections {
        target: root.store
        function onActiveChanged() { if (root.store.active) root.load() }
    }
    Component.onCompleted: if (generation === 0) load()     // onBookIdChanged có thể đã hỏi
    onBookIdChanged: { view = null; failed = false; closeSwap(); load() }

    // body: {enabled?, genre?, levelDb?, silence?: {khoá: bool}, pins?: {khoá: liên kết | null}, ban?: [..], unban?: [..]}
    function change(body, done) {
        if (changing) return
        pending = body
        store.request("PUT", "/api/books/" + bookId + "/music", body, function(status, data) {
            root.pending = null
            if (!root.store.ok(status) || !data) { Api.notice = "Không đổi được nhạc nền\n" + root.store.errorText(status, data); return }
            root.view = data
            root.closeSwap()
            Api.editedBook(root.bookId)
            root.refreshSoon()
            if (data.error) Api.notice = "Đã lưu lựa chọn\n" + data.error
            if (done) done()
        })
    }
    function rebuild() {
        if (rebuilding) return
        rebuilding = true
        store.request("POST", "/api/books/" + bookId + "/music/rebuild", null, function(status, data) {
            root.rebuilding = false
            if (!root.store.ok(status) || !data) { Api.notice = "Không chọn lại được nhạc\n" + root.store.errorText(status, data); return }
            root.view = data
            root.closeSwap()
            Api.editedBook(root.bookId)
            root.refreshSoon()
        })
    }
    function cancelDownload() {
        cancelling = true
        store.request("POST", "/api/books/" + bookId + "/music/download/cancel", null, function(status, data) {
            root.cancelling = false
            if (!root.store.ok(status) || !data) { Api.notice = "Không dừng được việc tải nhạc\n" + root.store.errorText(status, data); return }
            // Máy chủ dừng ở khúc kế (một phần giây): ẩn dòng tiến độ ngay thay vì đợi lần hỏi sau
            const next = Object.assign({}, data); delete next.download
            root.view = next
            Api.notice = "Đã dừng tải nhạc nền"
        })
    }
    // Bỏ một bài cho cả cuốn: báo (kèm số đoạn đang dùng bài ấy, đếm trước khi đổi) và cho "Hoàn tác"
    function ban(link, label) {
        const used = Logic.usedBy(plan, link)
        change({ban: [link]}, function() {
            Api.toast("Đã bỏ “" + label + "” cho cả cuốn (đang dùng ở " + used + " đoạn)", {action: {label: "Hoàn tác", run: function() { root.change({unban: [link]}) }}})
        })
    }

    // ---- "Đổi bài": một đoạn mở một lúc, là một lớp của ngăn xếp Back ----
    QtObject {
        id: swapLayer
        property bool on: false
        function close() { root.closeSwap() }
    }
    function toggleSwap(key) {
        if (swapping === key) { closeSwap(); return }
        swapping = key
        if (!swapLayer.on) { swapLayer.on = true; Nav.openLayer(swapLayer) }
    }
    function closeSwap() { swapping = ""; if (swapLayer.on) { swapLayer.on = false; Nav.closedLayer(swapLayer) } }

    // ---- nghe thử ----
    function togglePreview(link) { Clip.toggle("music:" + link, store.path(Logic.previewPath(link))) }
    function stopPreview() { if (previewing !== "") Clip.stop() }
    property int previewMs: Logic.PREVIEW_SECONDS * 1000
    Timer { id: previewCap; interval: root.previewMs; onTriggered: root.stopPreview() }
    Connections {
        target: Clip
        function onStarted() { if (root.previewing !== "") previewCap.restart() }
        function onCurrentChanged() { if (root.previewing === "") previewCap.stop() }
    }
    Component.onDestruction: { closeSwap(); stopPreview() }

    // ---- đang tải / lỗi ----
    Collapse {
        width: parent.width
        open: root.view === null && !root.failed
        EditBookSkeleton { width: parent.width; shape: "cards"; label: "Đang tải nhạc nền" }
    }
    EditBookError {
        width: parent.width
        open: root.failed && root.view === null
        message: "Bạn hãy kiểm tra kết nối rồi tải lại nhạc nền."
        onRetry: { root.failed = false; root.load() }
    }

    Collapse {
        id: ready
        width: parent.width
        open: root.view !== null
        spacing: 24

        // ---- cài đặt nhạc của cuốn: một hàng một việc, công tắc / ô chọn bên phải như trang Cài đặt ----
        Column {
            width: parent.width
            SettingRow {
                width: parent.width
                label: "Nhạc nền"
                hint: root.overrides.enabled ? "Đang bật cho cuốn này." : "Đang tắt: các đoạn dưới đây sẽ không phát."
                Switch {
                    objectName: "musicEnabled"
                    label: "Nhạc nền"
                    checked: root.overrides.enabled
                    enabled: !root.changing
                    onToggled: value => root.change({enabled: value})
                }
            }
            SettingRow {
                width: parent.width
                label: "Thể loại truyện"
                // Màn hẹp: ô chọn không đủ rộng cho tên thể loại dài nên ghi đủ tên bên dưới
                readonly property string named: Logic.genreName(root.taxonomy, root.overrides.genre)
                hint: "Chưa chọn thì nhạc lấy từ mọi thể loại" + (root.width < 640 && named.length > 28 ? "\n" + named : "")
                Select {
                    objectName: "musicGenre"
                    implicitWidth: 256
                    width: 256
                    label: "Thể loại truyện"
                    options: Logic.genreOptions(root.taxonomy)
                    value: root.overrides.genre || ""
                    enabled: !root.changing && !root.rebuilding
                    onPicked: value => root.change({genre: value || null})
                }
            }
            SettingRow {
                width: parent.width
                label: "Mức nhạc dưới giọng đọc"
                hint: "Nhỏ hơn giọng đọc bấy nhiêu; máy tự bù bài to hay nhỏ"
                Select {
                    objectName: "musicLevel"
                    implicitWidth: 200
                    width: 200
                    label: "Mức nhạc dưới giọng đọc"
                    options: Logic.levelOptions()
                    value: root.overrides.levelDb
                    enabled: !root.changing && !root.rebuilding
                    onPicked: value => root.change({levelDb: Number(value)})
                }
            }
            SettingRow {
                width: parent.width
                label: "Bài cho từng đoạn"
                hint: "Máy chọn lại theo thể loại và mức nhạc ở trên."
                Button {
                    objectName: "musicRebuild"
                    text: root.rebuilding ? "Đang chọn lại" : "Chọn lại nhạc"
                    icon: "refresh-cw"; kind: "ghost"
                    busy: root.rebuilding
                    onActivated: root.rebuild()
                }
            }
            Collapse {
                width: parent.width
                open: root.changing || root.rebuilding
                Text {
                    objectName: "musicBusy"
                    width: parent.width
                    topPadding: 8
                    text: root.rebuilding || (root.pending && root.pending.genre !== undefined) ? Logic.REBUILDING : Logic.SAVING
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                    Accessible.role: Accessible.StaticText
                }
            }
            // Đang tải sẵn các bài của rãnh nhạc: MB đổi mỗi 2 giây, trình đọc màn hình chỉ đọc mốc 25 %
            Collapse {
                id: downloadBox
                width: parent.width
                open: Boolean(root.view && root.view.download && root.view.download.active)
                readonly property var download: root.view && root.view.download ? root.view.download : null
                spacing: 4
                Flow {
                    width: parent.width
                    topPadding: 8
                    spacing: 12
                    Text {
                        objectName: "musicDownload"
                        width: Math.min(implicitWidth, parent.width)
                        height: Math.max(32, implicitHeight)
                        verticalAlignment: Text.AlignVCenter
                        text: downloadBox.download ? Logic.downloadText(downloadBox.download) : ""
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                        Accessible.role: Accessible.StaticText
                        Accessible.name: downloadBox.download ? Logic.spokenProgress("Đang tải sẵn nhạc nền", Logic.downloadShare(downloadBox.download)) : ""
                    }
                    Button {
                        objectName: "musicCancelDownload"
                        text: "Huỷ tải"; icon: "square"; kind: "ghost"; size: "sm"
                        busy: root.cancelling
                        onActivated: root.cancelDownload()
                    }
                }
                MyMusicBar {
                    width: parent.width
                    value: downloadBox.download ? Logic.downloadShare(downloadBox.download) : 0
                    label: "Tải sẵn nhạc nền"
                }
            }
            // "Dùng lại": dòng khép tại chỗ; bỏ hết thì cả mục khép lại
            Collapse {
                width: parent.width
                open: root.overrides.banned.length > 0
                StudioMusicDetails {
                    objectName: "musicBanned"
                    width: parent.width
                    topPadding: 8
                    summary: "Bài đã bỏ (" + root.overrides.banned.length + ")"
                    Repeater {
                        model: root.overrides.banned
                        Item {
                            required property string modelData
                            width: parent.width
                            height: Math.max(bannedName.height, again.height) + 4
                            Text {
                                id: bannedName
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - again.width - 12
                                text: Logic.trackLabel(modelData, (root.view.bannedTracks || {})[modelData] || (root.plan ? (root.plan.tracks || {})[modelData] : undefined))
                                color: Theme.text
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBodySmall
                            }
                            Button {
                                id: again
                                objectName: "musicUnban"
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Dùng lại"; kind: "ghost"; size: "sm"
                                enabled: !root.changing
                                onActivated: root.change({unban: [modelData]})
                            }
                        }
                    }
                }
            }
        }

        VoiceFold {
            objectName: "musicMoodsFold"
            width: parent.width
            storageKey: "studio.music.moods"
            title: "Nhạc theo ngữ cảnh"
            StudioMusicMoods {
                width: parent.width
                store: root.store
                bookId: root.bookId
                moods: root.view ? root.view.moods || null : null
                onComputed: next => root.accept(next)
            }
        }
        VoiceFold {
            objectName: "musicLocalFold"
            width: parent.width
            storageKey: "studio.music.local"
            title: "Nhạc của tôi"
            StudioMyMusic {
                width: parent.width
                store: root.store
                previewing: root.previewing
                onPreview: link => root.togglePreview(link)
                onLibraryChanged: root.libraryVersion++
            }
        }

        Text {
            width: parent.width
            visible: !!root.view && !!root.view.error
            text: root.view ? root.view.error || "" : ""
            color: Theme.warning
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Text {
            objectName: "musicOffNote"
            width: parent.width
            visible: !root.overrides.enabled && root.scenes.length > 0
            text: "Nhạc nền đang tắt - các đoạn dưới đây sẽ không phát."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Text {
            objectName: "musicNoScenes"
            width: parent.width
            visible: root.scenes.length === 0
            text: "Chưa có đoạn nào - nhạc nền dựng sau khi sách đã phân tích."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        // ---- các đoạn, theo chương: mỗi chương một khối gập có nhớ; tắt nhạc thì mờ đi ----
        Repeater {
            model: root.groups
            VoiceFold {
                id: fold
                required property var modelData
                objectName: "musicChapter"
                width: ready.width
                storageKey: "studio.music." + root.bookId + "." + modelData.chapterId
                title: Logic.chapterTitle(root.chapters, modelData.chapterId)
                summary: String(modelData.scenes.length)
                opacity: root.overrides.enabled ? 1 : 0.5
                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                // Thân chỉ dựng khi mở lần đầu: sách dài có hàng trăm đoạn
                property bool made: expanded
                onExpandedChanged: if (expanded) made = true
                Loader {
                    width: fold.width
                    active: fold.made
                    sourceComponent: Column {
                        Repeater {
                            model: fold.modelData.scenes
                            StudioMusicScene {
                                required property var modelData
                                required property int index
                                objectName: "musicScene"
                                width: fold.width
                                scene: modelData
                                scenes: fold.modelData.scenes
                                position: index
                                plan: root.plan
                                taxonomy: root.taxonomy
                                open: root.swapping === modelData.key
                                busy: root.changing
                                choosing: root.choosing
                                previewing: root.previewing
                                store: root.store
                                bookId: root.bookId
                                canPreviewMine: !root.remote
                                remote: root.remote
                                libraryVersion: root.libraryVersion
                                onSwapRequested: root.toggleSwap(modelData.key)
                                onMenuRequested: anchor => {
                                    root.menuScene = modelData
                                    sceneMenu.items = Logic.sceneMenu(modelData)
                                    sceneMenu.anchorItem = anchor
                                    sceneMenu.show()
                                }
                                onPreview: link => root.togglePreview(link)
                                onStopPreview: root.stopPreview()
                                // Đoạn đang im lặng (bạn chọn) mà chọn bài thì có nhạc lại
                                onChoose: link => {
                                    const pins = {}; pins[modelData.key] = link
                                    const body = {pins: pins}
                                    if (modelData.silenced) { const silence = {}; silence[modelData.key] = false; body.silence = silence }
                                    root.change(body)
                                }
                            }
                        }
                    }
                }
            }
        }

        Collapse {
            width: parent.width
            open: root.credits.lines.length > 0
            StudioMusicDetails {
                objectName: "musicCredits"
                width: parent.width
                fontSize: Theme.sizeCaption
                summary: "Ghi công (" + root.credits.lines.length + ")"
                Column {
                    width: parent.width
                    topPadding: 8
                    spacing: 4
                    Repeater {
                        model: root.credits.lines
                        HintText { required property string modelData; width: parent.width; text: modelData }
                    }
                    HintText { width: parent.width; visible: root.credits.modified; topPadding: 4; text: Logic.MODIFIED_NOTE }
                }
            }
        }
    }

    ProjectMenu {
        id: sceneMenu
        objectName: "sceneMenu"
        parent: root.overlay || root
        onPicked: key => {
            const scene = root.menuScene
            if (key === "silence") { const silence = {}; silence[scene.key] = !scene.silenced; root.change({silence: silence}) }
            else if (key === "unpin") { const pins = {}; pins[scene.key] = null; root.change({pins: pins}) }
            else if (key === "ban" && scene.link) {
                const track = root.plan ? (root.plan.tracks || {})[scene.link] : undefined
                root.ban(scene.link, Logic.trackLabel(scene.link, track))
            }
        }
    }
}
