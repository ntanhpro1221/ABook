import "UiStrings.js" as S
import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "UploadLogic.js" as Upload
import "TemplateLogic.js" as Templates
import "StudioSetupLogic.js" as Setup
import "StudioLogic.js" as Studio

// Dữ liệu và việc của trình tạo sách (data.ts + NewProjectScreen.tsx: nháp, quét nguồn, giọng, model, mẫu, gửi chương, tách file, tạo sách). Một bản sống
// cùng StudioScreen nên rời trang rồi quay lại không mất nháp (sessionStorage của web). Mọi lời gọi đi qua `store.request` (StudioStore): máy này hay máy tính
// đã ghép (`/api/peers/<mã>/studio/...`) đều cùng một đường. Studio của máy khác thì máy này không có đường dẫn nào của máy kia: file chọn ở đây được gửi lên
// (POST /api/sources/upload) rồi trình tạo đi tiếp bằng thư mục trên máy tính.
QtObject {
    id: root
    property var store: null
    property bool active: true
    signal created(string id)
    signal pickRequested()                    // "Dự án mới": mở hộp chọn file ngay (DESIGN.md §2 L10)
    signal leaveRequested(string id)          // sách đã bắt đầu chạy: về trang dự án

    readonly property var info: store ? store.info : Api.info
    readonly property bool remote: store ? store.remote : false
    // Máy tính Qt luôn có hộp chọn file của hệ điều hành (không hỏi `info.dialogs`); Studio của máy khác thì máy kia không có đường dẫn nào ở đây: gửi chương đi thay vì đưa đường dẫn
    readonly property bool dialogs: store ? store.peer === "" : true
    readonly property bool browser: !dialogs
    readonly property var studio: store ? store.studioState : Setup.studioMissing(null)
    readonly property bool noStudio: studio.missing
    readonly property bool setupNeeded: Boolean(info && info.studio && !info.studio.installed)

    property var draft: Logic.emptyDraft()
    property var scanned: null                // {key, result} gắn với đúng danh sách nguồn đã quét
    property bool scanning: false
    property var problem: null                // {text, subfolders}
    property string latest: ""
    property bool submitting: false
    property var voices: []
    property var prefs: null
    property var models: null
    property var hints: ({})                  // khoá nguồn -> gợi ý "Tôi là ai?"
    property var poked: ({})
    property bool profileApplied: false
    property bool prefsAsked: false           // đã có lời đáp (kể cả lỗi) cho tuỳ chọn: giọng mặc định mới chốt được
    property bool redoing: false              // đang đọc thiết lập của sách cần sửa
    property var uploading: null              // {files, totalFiles, bytes, totalBytes}
    property bool stopping: false

    property QtObject setupState: StudioSetupState {
        id: setup
        store: root.store
        wanted: root.active && root.setupNeeded
    }
    readonly property var fit: root.setupNeeded && setup.status && !setup.status.installed ? Setup.studioFit(setup.status.gpu) : null
    readonly property var unfit: root.noStudio && fit && fit.level === "no" ? fit : null
    readonly property var gpu: setup.gpu

    // ---- đọc dữ liệu ----
    function request(method, path, body, done) { return store ? store.request(method, path, body, done) : 0 }
    function fail(title, status, data) { Api.notice = title + "\n" + (store ? store.errorText(status, data) : S.s_chua_lam_duoc_luc_nay_2e7cacde) }
    function loadVoices() {
        const mine = store ? store.peer : ""
        request("GET", "/api/voices", null, function(status, data) {
            if (mine !== (root.store ? root.store.peer : "")) return
            if (status >= 200 && status < 300 && Array.isArray(data)) { root.voices = data; root.settle() }
        })
    }
    function loadPrefs() {
        const mine = store ? store.peer : ""
        request("GET", "/api/preferences", null, function(status, data) {
            if (mine !== (root.store ? root.store.peer : "")) return
            if (status >= 200 && status < 300 && data) root.prefs = data
            root.prefsAsked = true
            root.settle()
        })
    }
    function loadModels() {
        const mine = store ? store.peer : ""
        request("GET", "/api/analysis-models", null, function(status, data) {
            if (mine !== (root.store ? root.store.peer : "")) return
            if (status >= 200 && status < 300 && data) root.models = data
        })
    }
    // Mở trình tạo: hỏi lại giọng, tuỳ chọn (mẫu có thể vừa đổi ở Cài đặt) và model
    function open() { loadVoices(); loadPrefs(); loadModels(); if (setupNeeded) setup.load() }
    property QtObject peerWatch: Connections {
        target: root.store
        ignoreUnknownSignals: true
        function onPeerChanged() { root.reset(); root.voices = []; root.prefs = null; root.prefsAsked = false; root.models = null; root.hints = ({}); root.profileApplied = false; if (root.active) root.open() }
    }
    Component.onCompleted: open()

    readonly property string preferredNarrator: prefs && prefs.newBookNarrator ? prefs.newBookNarrator : ""
    readonly property var templates: Templates.templatesOf(prefs ? prefs.bookTemplates : null)
    readonly property var modelNames: Logic.availableModelNames(models)
    readonly property var voiceNames: voices.map(function(voice) { return voice.name })

    function update(changes) { draft = Object.assign({}, draft, changes) }
    // Chất lượng mặc định cho sách mới (Cài đặt > Studio) - chỉ khi trình tạo còn trống; giọng kể mặc định khi chưa có giọng.
    function settle() {
        if (!profileApplied && prefs) {
            profileApplied = true
            const wanted = prefs.newBookProfile
            if (!draft.paths.length && !draft.seed && wanted && Logic.PROFILE_VALUES.indexOf(wanted) >= 0 && wanted !== draft.profile) update({profile: wanted})
        }
        // Giọng mặc định chỉ chốt khi đã biết giọng nào là giọng bạn đặt (tuỳ chọn về sau danh sách giọng thì không được chốt nhầm giọng máy đề xuất)
        if (!draft.narrator && voices.length && prefsAsked) update({narrator: Logic.defaultNarrator(voices, preferredNarrator)})
    }
    onDraftChanged: if (!draft.narrator && voices.length && prefsAsked) Later.call(root, settle)

    function reset() {
        draft = Logic.emptyDraft()
        latest = ""
        scanned = null
        problem = null
        scanning = false
        uploading = null
        profileApplied = false
        settle()
    }

    // ---- "Sửa thiết lập" / "Làm tiếp": điền sẵn một lần ----
    function loadRedo(id) {
        redoing = true
        request("GET", "/api/books/" + id + "/redo", null, function(status, data) {
            root.redoing = false
            if (status < 200 || status >= 300 || !data) { root.fail(S.s_chua_doc_duoc_thiet_lap_cua_sach_d7efab34, status, data); root.leaveRequested(""); return }
            if (data.started) {
                Api.notice = S.s_sach_da_bat_dau_chay_khong_the_lam_lai_voi_cf900f37
                root.leaveRequested(id)
                return
            }
            root.draft = Logic.draftFromRedo(data, id)
            root.profileApplied = true
        })
    }
    function loadContinuation(id) {
        redoing = true
        request("GET", "/api/books/" + id + "/continuation", null, function(status, data) {
            root.redoing = false
            if (status < 200 || status >= 300 || !data) { root.fail(S.s_chua_mo_duoc_phan_truoc_52e838aa, status, data); root.leaveRequested(""); return }
            root.draft = Logic.draftFromContinuation(data, id)
            root.profileApplied = true
        })
    }
    function dropSeed() {
        const previous = draft.seed
        update({seed: undefined})
        Api.toast(S.s_da_bo_noi_tiep_sach_se_phan_vai_lai_tu_dau_fa1cf109, {duration: 10000, action: {label: S.s_hoan_tac_e72ff675, run: function() { root.update({seed: previous}) }}})
    }

    // ---- quét nguồn: chỉ khi danh sách nguồn đổi ----
    readonly property string pathsKey: Logic.sourcesKey(draft.paths)
    onPathsKeyChanged: Later.call(root, rescan)         // sau khi nháp đổi xong (lời đáp đồng bộ của máy thử không được ghi lại nháp giữa lúc đang đổi)
    function rescan() {
        if (!draft.paths.length) { latest = ""; scanned = null; problem = null; scanning = false; return }
        const key = pathsKey
        latest = key
        scanning = true
        request("POST", "/api/scan", draft.seed ? {paths: draft.paths, seedFrom: draft.seed.id} : {paths: draft.paths}, function(status, data) {
            // Lượt quét của danh sách nguồn đã bị thay thì bỏ, đừng để nó đè lên kết quả của danh sách hiện tại
            if (root.latest !== key) return
            root.scanning = false
            if (status < 200 || status >= 300 || !data) {
                root.scanned = {key: key, result: null}
                root.problem = {text: S.s_chua_doc_duoc_2213ed66 + (root.store ? root.store.errorText(status, data) : ""), subfolders: []}
                return
            }
            root.scanned = {key: key, result: data}
            if (!data.files.length) { root.problem = Logic.scanProblem(data); return }
            root.problem = null
            if (!root.draft.titleEdited && data.suggestedTitle) root.update({title: data.suggestedTitle})
        })
    }
    readonly property var rawScan: scanned ? scanned.result : null
    readonly property bool reading: !Logic.scanIsCurrent(scanned, draft.paths)
    readonly property bool splitting: draft.volumeStarts !== undefined && draft.volumeStarts !== null
    readonly property var excludedPaths: Logic.allExcluded(rawScan ? rawScan.files : [], draft.excluded, draft.keepMatter || [])
    readonly property var ordered: rawScan ? (splitting ? Logic.inOrder(rawScan.files, rawScan.volumes ? rawScan.volumes.order : null) : rawScan.files) : []
    readonly property var scan: Logic.viewOf(rawScan, ordered, excludedPaths, draft.limit || 0, splitting)
    readonly property var volumeStarts: splitting && scan ? Logic.startNumbers(ordered, draft.volumeStarts, excludedPaths) : [1]
    readonly property int totalFound: rawScan ? rawScan.files.length : 0
    readonly property int later: (rawScan ? rawScan.files.filter(function(file) { return excludedPaths.indexOf(file.path) < 0 }).length : 0) - (scan ? scan.files.length : 0)
    readonly property bool ready: Boolean(scan && scan.files.length)
    readonly property var credits: Logic.creditSummary(scan ? scan.files : [])

    // ---- "Tôi là ai?": đọc ~20 chương đầu của bộ file đang chọn, một lần cho mỗi bộ ----
    readonly property string hintKey: scan && scan.files.length ? scan.files.map(function(file) { return file.path }).join("\n") + "\u0001" + (draft.seed ? draft.seed.id : "") : ""
    readonly property var hint: hintKey !== "" ? hints[hintKey] : undefined
    readonly property bool hintLoading: hintKey !== "" && hints[hintKey] === undefined
    onHintKeyChanged: loadHint()
    function loadHint() {
        const key = hintKey
        if (key === "" || hints[key] !== undefined || poked[key]) return
        poked[key] = true
        const body = {paths: scan.files.map(function(file) { return file.path })}
        if (draft.seed) body.seedFrom = draft.seed.id
        request("POST", "/api/first-person", body, function(status, data) {
            if (status < 200 || status >= 300 || !data) { root.poked[key] = false; return }
            const next = Object.assign({}, root.hints)
            next[key] = data
            root.hints = next
        })
    }
    // "Sửa thiết lập": chương nào của gợi ý mà lúc tạo bạn không giữ thì tắt đi
    onHintChanged: {
        if (!draft.povKept || !hint) return
        update({povKept: undefined, povOff: Logic.povOffFrom(hint, draft.firstPerson, draft.povKept)})
    }
    readonly property var povChapters: Logic.chosenPovChapters(hint, draft.firstPerson, draft.povOff || [])
    readonly property bool autoNarrator: Logic.narratorIsAuto(draft, preferredNarrator, voices)
    readonly property var gate: Logic.createGate(draft.title, reading, Boolean(unfit))

    // ---- mẫu thiết lập ----
    function fallbackTemplate() {
        return {name: Logic.DEFAULT_LABEL, narrator: voices.length ? Logic.defaultNarrator(voices, preferredNarrator) : "", profile: Logic.profileFor(prefs ? prefs.newBookProfile : ""),
                analysisModel: "", startNow: true, precastWait: false}
    }
    function applyTo(current, template) {
        const fallback = fallbackTemplate()
        if (template) return Object.assign(Templates.applyTemplate(current, template, voiceNames, modelNames, fallback.narrator), {narratorPicked: Boolean(template.narrator)})
        return Object.assign(Templates.applyTemplate(current, fallback, undefined, undefined, undefined), {template: undefined, narratorPicked: false})
    }
    // Chọn một mẫu thiết lập (hay "Mặc định" = null): chỉ giọng kể, chất lượng, model, "bắt đầu ngay" của nháp đổi theo
    function pickTemplate(template) {
        const before = Templates.templateChoices(draft)
        const next = applyTo(draft, template)
        const changed = Templates.changedChoices(draft, next)
        draft = next
        // Áp mẫu ghi đè giọng / chất lượng / chờ duyệt bạn vừa chọn: nói đã đổi gì và cho trả lại
        if (changed.length) {
            Api.toast(S.s_da_ap_4cdf7062 + (template ? S.s_mau_81b2d539 + template.name + "”" : S.s_lua_chon_mac_dinh_2b7a4461) + S.s_doi_b9166fa9 + changed.join(", "),
                      {duration: 8000, action: {label: S.s_hoan_tac_e72ff675, run: function() { root.draft = Object.assign({}, root.draft, before) }}})
        }
    }
    property bool templateBusy: false
    // Một thao tác lên danh sách mẫu (POST /api/book-templates); done(ok, message). Máy tính trả lại cả tuỳ chọn.
    function templateOp(op, done) {
        if (templateBusy) return
        templateBusy = true
        request("POST", "/api/book-templates", op, function(status, data) {
            root.templateBusy = false
            const ok = status >= 200 && status < 300
            if (ok) {
                root.prefs = data
                if (root.store && !root.store.peer) Api.preferences = Object.assign({}, Api.preferences, data)
            } else if (status === 404 || status === 409) root.loadPrefs()
            if (done) done(ok, ok ? "" : (data && (data.message || data.error)) || S.s_chua_lam_duoc_luc_nay_2e7cacde)
        })
    }

    // ---- chọn nguồn ----
    function setPaths(paths) {
        update({paths: paths, excluded: [], keepMatter: [], limit: null, volumeStarts: null, titleEdited: paths.length ? draft.titleEdited : false})
    }
    function addFiles(paths) { update({paths: draft.paths.concat(paths), volumeStarts: null}) }
    // File / thư mục vừa chọn ở máy này: máy chủ có hộp chọn file của mình thì dùng đường dẫn; không thì gửi chương lên máy tính
    function picked(paths, append) {
        if (!paths.length) return
        if (!browser) { if (append) addFiles(paths); else setPaths(paths); return }
        upload(DesktopApi.sourceFiles(paths), append)
    }
    function removeChapter(path) {
        update({excluded: draft.excluded.concat([path])})
        Api.toast(S.s_da_bo_4874210f + Logic.sourceName(path), {action: {label: S.s_hoan_tac_e72ff675, run: function() { root.update({excluded: root.draft.excluded.filter(function(item) { return item !== path })}) }}})
    }
    function keepMatter(path, on) { update(Logic.keepMatterState(draft, path, on)) }

    // ---- gửi chương lên máy tính ----
    property var sendJob: null
    function upload(list, append) {
        if (!list.length || uploading) return
        const plan = Upload.planUpload(list, Upload.batchName(new Date(), Math.random().toString(36).slice(2, 6)))
        const notice = Upload.planNotice(plan)
        if (!plan.groups.length) {
            Api.notice = S.s_khong_co_file_truyen_nao_de_gui_1e4764a1 + (notice || S.s_chon_cac_file_txt_moi_file_mot_chuong_hay_ab6662ed)
            return
        }
        if (notice) Api.notice = S.s_co_file_khong_gui_52410790 + notice
        stopping = false
        sendJob = {plan: plan, append: append, group: 0, file: 0, folder: "", result: {paths: [], sent: 0, total: Upload.planFileCount(plan), cancelled: false, error: ""},
                   progress: {files: 0, totalFiles: Upload.planFileCount(plan), bytes: 0, totalBytes: plan.bytes}}
        uploading = sendJob.progress
        sendNext()
    }
    function sendNext() {
        const job = sendJob
        if (!job) return
        if (stopping) { finishUpload(job, true); return }
        const group = job.plan.groups[job.group]
        if (!group) { finishUpload(job, false); return }
        if (job.file >= group.files.length) { closeGroup(job, group); job.group++; job.file = 0; job.folder = ""; sendNext(); return }
        const picked = group.files[job.file]
        const data = DesktopApi.fileBase64(picked.local)
        request("POST", "/api/sources/upload", {folder: group.folder, name: picked.name, data: data}, function(status, reply) {
            if (root.sendJob !== job) return
            if (status < 200 || status >= 300 || !reply) {
                job.result.error = root.store ? root.store.errorText(status, reply) : S.s_chua_gui_duoc_d4832c85
                root.closeGroup(job, group)
                root.finishUpload(job, false)
                return
            }
            job.folder = reply.folder
            if (group.loose) job.result.paths.push(reply.path)
            job.file++
            job.result.sent++
            job.progress = Object.assign({}, job.progress, {files: job.progress.files + 1, bytes: job.progress.bytes + picked.size})
            root.uploading = job.progress
            root.sendNext()
        })
    }
    // Nhóm thư mục dừng giữa chừng vẫn trỏ tới thư mục chứa các file đã tới nơi
    function closeGroup(job, group) { if (!group.loose && job.folder) job.result.paths.push(job.folder) }
    function finishUpload(job, cancelled) {
        const group = job.plan.groups[job.group]
        if (cancelled && group && job.file < group.files.length) closeGroup(job, group)
        job.result.cancelled = cancelled
        sendJob = null
        uploading = null
        stopping = false
        const result = job.result
        // File đã tới máy tính thì giữ (huỷ hay hỏng giữa chừng cũng vậy)
        if (result.paths.length) { if (job.append) addFiles(result.paths); else setPaths(result.paths) }
        if (result.error) Api.notice = S.s_khong_gui_het_cac_chuong_9f410c03 + result.error + " " + Upload.sendSummary(result)
        else if (result.cancelled) Api.notice = result.sent ? S.s_da_dung_gui_da4bd94f + Upload.sendSummary(result) : S.s_da_huy_gui_d2e596a4
    }
    function cancelUpload() { stopping = true }
    Component.onDestruction: stopping = true

    // ---- tách một file cả truyện thành các chương ----
    function splitSource(path, done) {
        request("POST", "/api/sources/split", {path: path, title: String(draft.title).trim()}, function(status, data) {
            if (status < 200 || status >= 300 || !data) { root.fail(S.s_chua_tach_duoc_7d64588d, status, data); if (done) done(); return }
            const folder = data.folder
            // File đã chọn thẳng: thư mục chương thay chỗ nó. File nằm trong một thư mục đã chọn: thêm thư mục chương, bỏ file cả truyện khỏi danh sách
            const replaced = root.draft.paths.some(function(item) { return Logic.samePath(item, path) })
            // Tên sách người dùng đã có / đã gõ ở lại: thư mục chương mang tên FILE, không được đè lên nó khi quét lại
            const keepTitle = String(root.draft.title).trim() ? {titleEdited: true} : {}
            const plan = root.scan ? (root.scan.files.filter(function(file) { return Logic.samePath(file.path, path) })[0] || {}).split : undefined
            const chapters = plan ? Logic.splitOutcome(plan, root.draft.title).chapters : 0
            root.update(Object.assign(replaced
                ? {paths: root.draft.paths.map(function(item) { return Logic.samePath(item, path) ? folder : item }), excluded: [], keepMatter: [], limit: null, volumeStarts: null}
                : {paths: root.draft.paths.concat([folder]), excluded: root.draft.excluded.concat([path]), limit: null, volumeStarts: null}, keepTitle))
            Api.notice = chapters ? S.s_da_tach_thanh_df60df1d + Studio.formatNumber(chapters) + S.s_chuong_9e6a01dc : S.s_da_tach_thanh_cac_chuong_1e1bb231
            if (done) done()
        })
    }

    // ---- tạo sách ----
    function submit() {
        // Đang đọc lại nguồn (vừa thêm / bớt file): `scan` còn là của danh sách cũ - đợi, đừng tạo sách thiếu chương vừa chọn
        if (reading) return
        if (!scan || !scan.files.length || !String(draft.title).trim() || submitting) return
        submitting = true
        const mine = draft
        const body = Logic.createBody({draft: mine, files: scan.files, volumeStarts: volumeStarts, povChapters: povChapters, auto: autoNarrator, remote: remote, noStudio: noStudio, credits: credits})
        request("POST", "/api/books", body, function(status, data) {
            root.submitting = false
            if (status < 200 || status >= 300 || !data) { root.fail(S.s_chua_tao_duoc_sach_2d0ce411, status, data); return }
            const text = Logic.createdText(data, mine, root.noStudio)
            Api.notice = text[1] ? text[0] + "\n" + text[1] : text[0]
            if (data.replaceError) Api.toast(S.s_ban_cu_van_con_trong_du_an_43fe501c + data.replaceError)
            root.reset()
            if (root.store) root.store.refresh(data.id)
            root.created(data.id)
        })
    }
}
