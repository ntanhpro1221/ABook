import "UiStrings.js" as S
import QtQuick
import ABook
import "ScriptLogic.js" as Script
import "DecisionLogic.js" as D

// Dữ liệu và lệnh của tab "Kịch bản" (ScriptTab.tsx): mục lục (/casting), MỘT chương (/casting/<id>), nhịp hỏi nhẹ /casting/stamp 6 giây khi tab đang
// hiện (hai cửa sổ cùng sửa một sách: đổi thì chương tải lại), và bốn lệnh của bản web - gán người nói, "Duyệt N câu", thu lại câu, sửa cách đọc câu.
// Mọi lệnh đổi ngay trên câu (bản lạc quan), lỗi thì trả câu về như trước; ghi xong có "Hoàn tác" 15 giây và Ctrl+Z (ngăn `undos`).
// Đi qua StudioStore nên Studio của máy khác tự đi đường /api/peers/<mã>/studio.
QtObject {
    id: root
    property var store: null
    property var work: null                     // WorkStore của dự án: Hoàn tác, lời báo hai máy cùng sửa, số việc
    property string bookId: ""
    property bool wanted: false                 // tab đang hiện
    property int chapterId: 0
    property var undos: []                      // Ctrl+Z: mỗi mục trả false khi lần ấy đã hoàn tác bằng nút trên lời báo
    property bool confirming: false
    property bool retaking: false

    function path(rest) { return "/api/books/" + bookId + rest }
    property StudioQuery contents: StudioQuery { store: root.store; path: root.bookId ? root.path("/casting") : ""; wanted: root.wanted }
    property StudioQuery script: StudioQuery { store: root.store; path: root.bookId && root.chapterId ? root.path("/casting/" + root.chapterId) : ""; wanted: root.wanted }
    property StudioQuery stamp: StudioQuery {
        store: root.store
        path: root.bookId ? root.path("/casting/stamp") : ""
        wanted: root.wanted && root.contents.data !== null
        interval: Script.STAMP_MS
        property var last: null
        onLoaded: data => {
            if (last !== null && last !== data.stamp) root.refresh()
            last = data.stamp
        }
    }
    readonly property var chapters: contents.data ? contents.data.chapters || [] : []
    // Chương đang xem đã về (đổi chương thì dữ liệu chương trước không hiện)
    readonly property var data: script.data && script.data.chapterId === chapterId ? script.data : null

    property Connections decisions: Connections {
        target: root.work
        function onDecided() { root.contents.invalidate(); root.script.invalidate() }
    }

    // invalidate ["casting"] + ["work"] của bản web
    function refresh() {
        contents.invalidate(); script.invalidate()
        if (work) { work.work.invalidate(); work.workCounted.invalidate() }
    }
    function refreshBook() { refresh(); if (store) store.loadBook() }
    function say(text, options) { Api.toast(text, options || {}) }
    function sayError(title, message) { say(title + "\n" + message) }
    function warnElsewhere(count, was, takeTheirs) {
        const note = D.elsewhereNote(count, was)
        Api.toast(note.title + "\n" + note.description, {id: "edited-elsewhere", duration: 20000,
            action: takeTheirs ? {label: S.s_lay_cua_may_kia_37d97780, run: takeTheirs} : null})
    }
    // Bản lạc quan trên chương đang xem; trả hàm đặt lại đúng bản trước
    function optimistic(change) {
        const previous = script.data
        if (previous) script.setData(Object.assign({}, previous, {lines: previous.lines.map(change)}))
        return function() { if (previous) root.script.setData(previous) }
    }
    function push(undo) { undos = undos.slice(-19).concat([undo]) }
    // Ctrl+Z: lần đã hoàn tác bằng nút trên lời báo thì bỏ qua, lấy lần trước nữa; hết thì nói ra thay vì im lặng
    function undoLast() {
        let undone = false
        const stack = undos.slice()
        while (!undone && stack.length) undone = stack.pop()()
        undos = stack
        if (!undone) say(S.s_khong_con_gi_de_hoan_tac_6b0854e7)
    }
    // Nút trên lời báo và Ctrl+Z dùng CHUNG một lần hoàn tác - bấm cả hai không hoàn tác hai lần
    function once(action) {
        let used = false
        return function() {
            if (used) return false
            used = true
            action.run()
            return true
        }
    }
    function quietly(method, rest, body, done) {
        store.request(method, path(rest), body, function(status, data) {
            if (store.ok(status)) done(data || {}, "")
            else done(null, store.errorText(status, data))
        })
    }

    // ---- gán người nói (useAssign) ----
    function assign(lines, person) {
        const value = person.value, label = person.label
        const refs = lines.map(Script.ref)
        const known = {}
        for (const line of lines) known[line.stableId] = line.wish ? line.wish.value : ""
        const ids = refs.map(item => item.stableId)
        const restore = optimistic(item => ids.indexOf(item.stableId) >= 0 ? Object.assign({}, item, {wish: {value: value, label: label, state: value === item.current ? "applied" : "pending"}}) : item)
        quietly("POST", "/speaker", {lines: refs, speaker: value, newGender: person.newGender || "", seen: D.seenFor(lines, known)}, function(answer, error) {
            if (!answer) { restore(); root.sayError(S.s_chua_ghi_duoc_nguoi_noi_5ef0be83, error); root.refresh(); return }
            const keep = lines.every(item => value === item.current)
            const run = root.once(root.work.undoAction("speaker", [{lines: refs, requestedAt: answer.requestedAt, keep: keep}], Script.assignBack(lines)))
            root.push(run)
            const replaced = Object.entries(answer.elsewhere || {})
            if (replaced.length) root.warnElsewhere(replaced.length, replaced[0][1] ? Script.nameOf(root.script.data, replaced[0][1]) : "", run)
            root.say(Script.assignedText(answer.lines, label, lines[0], keep), {duration: D.UNDO_MS, action: {label: S.s_hoan_tac_e72ff675, run: run}})
            root.refresh()
        })
    }

    // ---- "Duyệt N câu" (useConfirmChapter): mỗi nhóm người nói một yêu cầu, giữ requestedAt của từng lần để một Hoàn tác lùi cả chương ----
    function confirm(lines) {
        if (confirming) return
        confirming = true
        const groups = Script.confirmGroups(lines)
        const made = []
        const elsewhere = {}
        let count = 0
        function finish(error) {
            root.confirming = false
            root.refresh()
            if (error) {
                root.sayError(S.s_chua_xac_nhan_duoc_0804addb, count > 0 ? S.s_moi_xac_nhan_duoc_992971dc + count + S.s_cau_con_lai_chua_ghi_632b6cf5 + error + S.s_ban_bam_xac_nhan_lai_nhung_cau_da_ghi_se_k_0831b23f : error)
                return
            }
            const run = root.once(root.work.undoAction("speaker", made, count + S.s_cau_tro_lai_cho_duyet_829b356e))
            root.push(run)
            const replaced = Object.values(elsewhere)
            if (replaced.length) root.warnElsewhere(replaced.length, replaced[0] ? Script.nameOf(root.script.data, replaced[0]) : "", run)
            root.say(S.s_da_xac_nhan_c0b382d5 + count + S.s_cau_la_dung_7a9d958e, {duration: D.UNDO_MS, action: {label: S.s_hoan_tac_e72ff675, run: run}})
        }
        function next(i) {
            if (i >= groups.length) { finish(""); return }
            const group = groups[i]
            const refs = group.lines.map(Script.ref)
            const seen = {}
            for (const line of group.lines) seen[line.stableId] = line.wish ? line.wish.value : ""
            root.quietly("POST", "/speaker", {speaker: group.speaker, lines: refs, seen: seen}, function(answer, error) {
                if (!answer) { finish(error); return }
                Object.assign(elsewhere, answer.elsewhere || {})
                count += answer.lines
                made.push({lines: refs, requestedAt: answer.requestedAt, keep: true})
                next(i + 1)
            })
        }
        next(0)
    }

    // ---- thu lại câu (useRetake): POST /review verdict redo, một lần bấm một mốc; chỉ câu ĐÃ THU ----
    function reviewBody(verdict, lines) {
        const seen = {}
        for (const line of lines) seen[line.stableId] = line.verdict || ""
        return {verdict: verdict, chapterId: chapterId, lines: lines.map(line => ({stableId: line.stableId})), seen: seen}
    }
    function warnReview(answer) {
        const replaced = Object.entries(answer.elsewhere || {})
        if (!replaced.length) return false
        const chapter = chapterId
        warnElsewhere(replaced.length, D.verdictWord(replaced[0][1]), function() {
            let left = replaced.length, failed = ""
            for (const entry of replaced) {
                root.quietly("POST", "/review", {verdict: entry[1] || null, stableId: entry[0], chapterId: chapter}, function(done, error) {
                    if (!done && !failed) failed = error
                    if (--left === 0) { if (failed) root.sayError(S.s_chua_lay_lai_duoc_2e01d8a8, failed); root.refreshBook() }
                })
            }
        })
        return true
    }
    function retake(lines) {
        const ids = lines.map(line => line.stableId)
        const restore = optimistic(item => ids.indexOf(item.stableId) >= 0 ? Object.assign({}, item, {retake: "pending", verdict: "redo"}) : item)
        retaking = true
        quietly("POST", "/review", reviewBody("redo", lines), function(answer, error) {
            root.retaking = false
            if (!answer) { restore(); root.sayError(S.s_chua_ghi_duoc_9fa87a7d, error); root.refreshBook(); return }
            root.warnReview(answer)
            const run = root.once({run: function() {
                root.quietly("POST", "/review", root.reviewBody(null, lines), function(done, failure) {
                    if (done) root.say(lines.length > 1 ? S.s_da_hoan_tac_733b86c1 + lines.length + S.s_cau_khong_phai_thu_lai_nua_50819817 : S.s_da_hoan_tac_cau_nay_khong_phai_thu_lai_nua_5ba9e5c0)
                    else root.sayError(S.s_chua_hoan_tac_duoc_164b754b, failure)
                    root.refreshBook()
                })
            }})
            root.push(run)
            root.say(lines.length > 1 ? S.s_da_ghi_thu_lai_4303c66d + lines.length + S.s_cau_b07e1008 : S.s_da_ghi_thu_lai_cau_nay_9c9b1e4b, {duration: D.UNDO_MS, action: {label: S.s_hoan_tac_e72ff675, run: run}})
            root.refreshBook()
        })
    }
    function cancelRetake(lines) {
        const ids = lines.map(line => line.stableId)
        const restore = optimistic(item => ids.indexOf(item.stableId) >= 0 ? Object.assign({}, item, {retake: null, verdict: null}) : item)
        quietly("POST", "/review", reviewBody(null, lines), function(answer, error) {
            if (!answer) { restore(); root.sayError(S.s_chua_bo_duoc_638141d7, error); root.refreshBook(); return }
            root.warnReview(answer)
            root.say(S.s_da_bo_yeu_cau_thu_lai_c5881de5)
            root.refreshBook()
        })
    }

    // ---- sửa cách đọc một câu (useLineFix + postLineFix): người nói MỚI cần hai bước - /line trước, /speaker sau; bước sau hỏng thì rút bước đầu ----
    function postLineFix(line, change, done) {
        const ref = Script.ref(line)
        const rest = {}
        for (const key in change) if (key !== "newGender" && key !== "speaker") rest[key] = change[key]
        const seen = Script.seenDelivery(line.lineWish)
        if (!change.newGender) {
            const body = Object.assign({}, ref, rest, change.speaker ? {speaker: change.speaker} : {}, {seen: seen})
            quietly("POST", "/line", body, done)
            return
        }
        quietly("POST", "/line", Object.assign({}, ref, rest, {seen: seen}), function(made, error) {
            if (!made) { done(null, error); return }
            root.quietly("POST", "/speaker", {lines: [ref], speaker: change.speaker, newGender: change.newGender}, function(person, failure) {
                if (person) { done(Object.assign({}, made, {speakerAt: person.requestedAt}), ""); return }
                if (!made.requestedAt) { done(null, failure); return }
                root.quietly("POST", "/line", {stableId: ref.stableId, withdraw: true, requestedAt: made.requestedAt}, function() { done(null, failure) })
            })
        })
    }
    function fixLine(line, change) {
        const wish = {kind: change.kind || "", emotion: change.emotion || "", intensity: change.intensity !== undefined ? change.intensity : null, state: "pending"}
        if (change.spoken !== undefined) wish.spoken = change.spoken
        const restore = optimistic(item => item.stableId === line.stableId ? Object.assign({}, item, {lineWish: wish}) : item)
        postLineFix(line, change, function(answer, error) {
            if (!answer) { restore(); root.sayError(S.s_chua_ghi_duoc_9fa87a7d, error); root.refresh(); return }
            const elsewhere = answer.elsewhere
            if (elsewhere) {
                // "Lấy của máy kia": ghi lại những gì máy kia đã đặt (cách đọc câu không có Hoàn tác riêng); máy kia đã bỏ hết thì chỉ báo.
                const theirs = Script.theirDelivery(elsewhere.delivery)
                root.warnElsewhere(1, elsewhere.delivery ? Script.deliveryWords(elsewhere.delivery) : "", theirs ? function() {
                    root.quietly("POST", "/line", Object.assign({stableId: line.stableId, textSha256: line.textSha256}, theirs), function(done, failure) {
                        if (!done) root.sayError(S.s_chua_lay_lai_duoc_2e01d8a8, failure)
                        root.refresh()
                    })
                } : null)
            }
            const ref = Script.ref(line)
            const steps = []
            if (answer.speakerAt) steps.push({endpoint: "speaker", decision: {lines: [ref], requestedAt: answer.speakerAt}})
            steps.push({endpoint: "line", decision: {stableId: ref.stableId, requestedAt: answer.requestedAt}})
            const action = answer.requestedAt ? root.work.undoSteps(steps, S.s_cau_nay_tro_lai_nhu_truoc_khi_sua_cach_doc_77690b99) : null
            root.say(S.s_da_ghi_cach_doc_cau_nay_0db96b25, {duration: D.UNDO_MS, action: action})
            root.refresh()
        })
    }
}
