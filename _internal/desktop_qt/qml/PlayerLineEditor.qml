import QtQuick
import ABook
import "UiStrings.js" as S
import "PlayerLineLogic.js" as L
import "ScriptLogic.js" as Script

// One frozen sentence, above the native player/reader. Studio owns request and undo semantics.
Modal {
    id: root
    objectName: "playerLineEditor"
    panelWidth: 512
    title: step === "speaker" ? (line && line.kind === "thought" ? S.s_ai_nghi_cau_nay_1d5dd20c : S.s_ai_noi_cau_nay_39d97e95) : step === "delivery" ? S.s_cach_doc_cau_nay_d8d0b9f1 : S.s_sua_cau_nay_a82aec43
    property string bookId: ""
    property int chapterId: 0
    property var sourceLine: ({})
    property bool timed: false
    property var line: null
    property var chapter: ({cast: [], others: [], lines: []})
    property string step: "menu"
    property string problem: ""
    property bool loading: false
    property int generation: 0
    property int writing: 0
    readonly property bool identified: L.identified(sourceLine)
    property var commands: null
    readonly property var scriptCommands: commands
    onStepChanged: if (open) stepMotion.restart()
    NumberAnimation { id: stepMotion; target: editorBody; property: "opacity"; from: 0; to: 1; duration: Theme.reduceMotion ? Theme.motionFast : Theme.motionMedium }
    keepOpen: function() { if (root.step !== "menu") { root.step = "menu"; return true }; return false }

    function begin(snapshot, audio) {
        if (writing || !snapshot || !snapshot.source) return
        if (commands) commands.retire()
        bookId = snapshot.bookId; chapterId = snapshot.chapterId; sourceLine = snapshot.source
        commands = commandFactory.createObject(root, {bookId: bookId, chapterId: chapterId})
        timed = !!audio; step = "menu"; line = null; problem = ""; loading = true
        show(); reload()
    }
    function reload() {
        const mine = ++generation
        const base = "/api/books/" + encodeURIComponent(bookId)
        Api.quiet("GET", "/api/listen/books/" + encodeURIComponent(bookId), null, function(meta, err) {
            if (mine !== root.generation) return
            if (err) { root.problem = err; root.loading = false; return }
            const book = meta.book || meta
            root.problem = L.blocked(book.capabilities, Api.info.listenOnly)
            if (root.problem) { root.loading = false; return }
            if (book.capabilities.workshop) {
                Api.quiet("GET", base + "/casting/" + root.chapterId, null, function(data, error) {
                    if (mine !== root.generation) return
                    root.loading = false
                    if (error) { root.problem = error; return }
                    // Both keys must match. Never select a nearby row or a row with the same audio position.
                    root.line = data.lines.find(l => l.stableId === root.sourceLine.stableId && l.textSha256 === root.sourceLine.textSha256) || null
                    root.chapter = data
                    commands.script.setData(data)
                    if (!root.line) root.problem = S.s_chua_sua_duoc_tung_cau_o_file_lam_bang_abo_82209a43
                })
            } else {
                Api.quiet("GET", base + "/cast", null, function(cast, error) {
                    if (mine !== root.generation) return
                    if (error) { root.problem = error; root.loading = false; return }
                    Api.quiet("GET", base + "/wishes", null, function(wishes, failure) {
                        if (mine !== root.generation) return
                        root.loading = false
                        if (failure) { root.problem = failure; return }
                        root.line = L.line(root.sourceLine, cast, wishes, root.timed)
                        root.chapter = {chapterId: root.chapterId, cast: L.people(cast, wishes), others: [], lines: [root.line]}
                        commands.script.setData(root.chapter)
                    })
                })
            }
        })
    }
    onClosed: { ++generation; Clip.stop() }

    Component {
        id: commandFactory
        ScriptStore {
            id: owner
            wanted: false
            // A previous toast keeps this immutable book/chapter owner through its Undo period.
            function retire() { retirement.start() }
            property Timer retirement: Timer { interval: 60000; onTriggered: owner.destroy() }
            store: StudioStore {
                active: false
                function loadBook() { if (root.open && root.commands === owner) root.reload(); Api.editedBook(owner.bookId) }
                function request(method, path, body, done) {
                    if (method !== "GET") root.writing++
                    return Api.transport.request(method, path, body, function(status, data) {
                        if (method !== "GET") root.writing--
                        done(status, data)
                        if (method !== "GET" && root.open && root.commands === owner) { root.step = "menu"; root.reload() }
                    })
                }
            }
            work: WorkStore { store: owner.store; bookId: owner.bookId; counting: false }
        }
    }

    Column {
        width: parent.width
        spacing: Theme.s12
        Text { width: parent.width; text: root.sourceLine.text || ""; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        Text { width: parent.width; text: S.s_player_line_waiting_audio; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
        Collapse {
            width: parent.width
            open: !root.identified
            Text { width: parent.width; text: S.s_file_sach_nay_lam_bang_abook_ban_cu_nen_ch_45df1722; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        }
        InlineError { width: parent.width; open: root.problem !== ""; message: root.problem; onRetry: root.reload() }
        Collapse {
            width: parent.width
            open: root.loading
            Text { width: parent.width; text: S.s_dang_tai_kich_ban_0eea9c53; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        }
        Loader {
            id: editorBody
            width: parent.width
            active: !!root.line && !root.loading && root.problem === ""
            sourceComponent: root.step === "speaker" ? people : root.step === "delivery" ? delivery : menu
            onLoaded: item.forceActiveFocus()
            opacity: status === Loader.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
            transform: Translate { x: Theme.reduceMotion ? 0 : 24 * (1 - editorBody.opacity) }
        }
    }
    Component {
        id: menu
        Column {
            width: parent.width
            enabled: root.identified && !root.writing
            MenuRow { objectName: "playerLineWho"; ringRadius: Theme.radiusCover; chevron: true; width: parent.width; icon: "user-round"; text: root.line.kind === "thought" ? S.s_ai_nghi_cau_nay_0656af4f : S.s_ai_noi_cau_nay_0e00a5c7; note: !Script.isSpeech(root.line) ? S.s_loi_ke_khong_co_nguoi_noi_muon_gan_nguoi_d_a62c8bf9 : root.line.wish ? S.s_dang_cho_may_lam_sach_0_712ab9de(root.line.wish.label) : S.s_hien_la_0_d6cdb2e8(root.line.label); enabled: Script.isSpeech(root.line); onClicked: root.step = "speaker" }
            MenuRow { objectName: "playerLineDelivery"; ringRadius: Theme.radiusCover; chevron: true; width: parent.width; icon: "message-square-quote"; text: S.s_cach_doc_cau_50f2072a; note: S.s_loai_cau_cam_xuc_chu_dem_doc_483deab7; onClicked: root.step = "delivery" }
            MenuRow { objectName: "playerLineSample"; ringRadius: Theme.radiusCover; chevron: true; solidIcon: false; width: parent.width; icon: "play"; text: S.s_nghe_thu_fa024065; enabled: root.timed && typeof root.sourceLine.start === "number" && root.sourceLine.end > root.sourceLine.start; onClicked: Clip.toggle("player-line-" + root.line.stableId, "/media/books/" + root.bookId + "/chapters/" + root.chapterId, root.sourceLine.start, root.sourceLine.end) }
            MenuRow { objectName: "playerLineRetake"; ringRadius: Theme.radiusCover; width: parent.width; icon: "rotate-ccw"; text: S.s_thu_lai_cau_nay_034c2834; note: !root.timed ? S.s_chuong_nay_chua_co_audio_chua_co_gi_de_thu_47e4d310 : root.line.retake === "pending" ? S.s_da_ghi_dang_cho_may_lam_sach_7335a8a2 : S.s_doc_lai_mot_lan_khac_giong_nhu_cu_a0908dad; enabled: root.timed && root.line.retake !== "pending"; onClicked: commands.retake([root.line]) }
        }
    }
    Component {
        id: people
        Column {
            width: parent.width
            ScriptSpeakerMenu { width: parent.width; line: root.line; script: root.chapter; enabled: !root.writing; onPicked: person => commands.assign([root.line], person) }
            Button { text: S.s_quay_lai_6d793582; kind: "ghost"; onActivated: root.step = "menu" }
        }
    }
    Component {
        id: delivery
        Column {
            width: parent.width
            ScriptDelivery { width: parent.width; line: root.line; script: root.chapter; enabled: !root.writing; onSave: change => commands.fixLine(root.line, change) }
            Button { text: S.s_quay_lai_6d793582; kind: "ghost"; onActivated: root.step = "menu" }
        }
    }
}
