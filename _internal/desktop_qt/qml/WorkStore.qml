import QtQuick
import ABook
import "DecisionLogic.js" as D
import "WorkLogic.js" as W
import "NameLogic.js" as N

// Việc "cần bạn" của MỘT cuốn: hộp Việc cần duyệt, Cần nghe lại, Cách đọc tên, yêu cầu từ điện thoại (WorkInbox / ReviewQueue / NameReadings / PhoneEdits của bản web). Mọi lời gọi đi
// qua StudioStore nên Studio của máy khác tự đi đường /api/peers/<mã>/studio. Ba con số cho nhãn tab (useWorkCount, useReviewCount, useInboxCount) hỏi nhẹ; danh sách
// đầy đủ chỉ tải khi tab của nó đang mở (`workWanted`, `namesWanted`), không hỏi định kỳ khi cửa sổ ẩn. Mỗi quyết định ghi xong thì `after()` làm mới mọi chỗ nó chạm tới
// (refreshAfterDecision) và hiện lời báo kèm "Hoàn tác" 15 giây qua Api.toast.
QtObject {
    id: root
    property var store: null
    property var book: null
    property string bookId: ""
    property bool workWanted: false
    property bool namesWanted: false
    property bool counting: true                // màn dự án đang thấy: ba con số của nhãn tab được hỏi định kỳ
    readonly property bool live: !!book && (Boolean(book.running) || Boolean(book.starting)) && !book.paused
    readonly property int producing: live ? 15000 : 0

    function path(rest) { return "/api/books/" + bookId + rest }

    // ---- nguồn dữ liệu ----
    property StudioQuery work: StudioQuery { store: root.store; path: root.bookId ? root.path("/work") : ""; wanted: root.workWanted && root.bookId !== ""; interval: root.producing }
    property StudioQuery workCounted: StudioQuery { store: root.store; path: root.bookId ? root.path("/work?count=1") : ""; wanted: root.counting && !root.workWanted && root.bookId !== ""; interval: root.producing }
    property StudioQuery reviewCounted: StudioQuery { store: root.store; path: root.bookId ? root.path("/review") : ""; wanted: root.counting && root.bookId !== ""; interval: root.producing }
    property StudioQuery inbox: StudioQuery { store: root.store; path: root.bookId ? root.path("/edits-inbox") : ""; wanted: root.counting && root.bookId !== ""; interval: 15000 }
    property StudioQuery names: StudioQuery { store: root.store; path: root.bookId ? root.path("/pronunciations") : ""; wanted: root.namesWanted && root.bookId !== "" }
    property StudioQuery offer: StudioQuery { store: root.store; path: root.bookId ? root.path("/shared-readings") : ""; wanted: root.namesWanted && root.bookId !== "" }
    property StudioQuery shared: StudioQuery { store: root.store; path: "/api/readings"; wanted: root.namesWanted && root.bookId !== "" }

    // ---- ba con số của nhãn tab ----
    // Việc đã quyết (chờ áp dụng) không còn là việc cần làm: danh sách đang mở thì đếm từ chính nó, không thì chỉ hỏi con số (?count=1)
    readonly property int workOpen: workWanted && work.data ? work.data.items.filter(W.isOpenWork).length : (workCounted.data ? workCounted.data.count : 0)
    readonly property int reviewCount: reviewCounted.data ? reviewCounted.data.pending || 0 : 0
    readonly property int inboxCount: inbox.data ? inbox.data.waiting || 0 : 0
    readonly property int workCount: workOpen + inboxCount
    readonly property bool analyzed: !book || (book.segments.total > 0 && book.segments.analyzed === book.segments.total)
    readonly property string pendingNote: D.pendingNote(book)

    // ---- lời gọi ----
    function post(rest, body, done) { return store.request("POST", path(rest), body, done) }
    function ok(status) { return store.ok(status) }
    function say(title, description, options) { Api.toast(description ? title + "\n" + description : title, options || {}) }
    function fail(title, status, data) { say(title, store.errorText(status, data)) }
    function kept(duration, action) { return {duration: duration, action: action} }
    function suggestionOf(data) { return data && typeof data.suggestion === "string" ? data.suggestion : "" }

    // refreshAfterDecision: làm mới mọi chỗ một quyết định của người nghe chạm tới
    function after() {
        work.invalidate(); workCounted.invalidate()
        names.invalidate(); offer.invalidate(); shared.invalidate()
        if (store) { store.loadBook(); if (store.libraryWanted) store.loadLibrary() }
    }
    // "Cần thu lại" là một yêu cầu cho dây chuyền: trang dự án đếm nó vào nút "Áp dụng thay đổi"
    function afterReview() {
        reviewCounted.invalidate()
        if (store) { store.loadBook(); if (store.libraryWanted) store.loadLibrary() }
    }

    // ---- Hoàn tác (undoAction / undoSteps): gửi lại đúng lần bấm với `withdraw`, nói thật điều đã xảy ra ----
    function undoSteps(steps, message) {
        return {label: "Hoàn tác", run: function() {
            let done = 0, restored = false, sent = false
            function next(i) {
                if (i >= steps.length) { Api.toast(D.undoText(restored, sent, message)); root.after(); return }
                root.store.request("POST", root.path("/" + steps[i].endpoint), Object.assign({}, steps[i].decision, {withdraw: true}), function(status, data) {
                    if (!root.ok(status)) {
                        root.fail(done > 0 ? "Mới hoàn tác được " + done + "/" + steps.length + " việc" : "Không hoàn tác được", status, data)
                        root.after()
                        return
                    }
                    restored = restored || Boolean(data && data.restored)
                    sent = sent || Boolean(data && data.sent === true)
                    done++
                    next(i + 1)
                })
            }
            next(0)
        }}
    }
    function undoAction(endpoint, decisions, message) {
        return undoSteps(decisions.map(function(decision) { return {endpoint: endpoint, decision: decision} }), message)
    }
    // Hai máy (hay hai cửa sổ) cùng sửa một chỗ: báo và hỏi giữ của mình hay lấy của máy kia. Chỉ có một chỗ cho lời báo nên lời này thế lời "Đã ghi" (cũng có nút lấy lại).
    function warnElsewhere(count, was, takeTheirs) {
        const note = D.elsewhereNote(count, was)
        Api.toast(note.title + "\n" + note.description, {duration: 20000, action: takeTheirs ? {label: "Lấy của máy kia", run: takeTheirs} : null})
    }
    function undoDecision(item) { undoAction(item.undo.endpoint, item.undo.decisions, "Việc này trở lại chờ bạn duyệt.").run() }

    // ---- thẻ cách đọc tên (PronunciationFix) ----
    // done(vấn đề, gợi ý): vấn đề rỗng = ổn. Lỗi chỉ nằm dưới ô nhập, không thêm lời báo.
    function savePronunciationCard(item, spokenForm, done) {
        post("/pronunciation", {surface: item.surface, spokenForm: spokenForm, seen: item.requested || ""}, function(status, data) {
            if (!ok(status)) { done(store.errorText(status, data), suggestionOf(data)); return }
            after()
            const keep = data.spokenForm === item.current
            const action = undoAction("pronunciation", [{surface: item.surface, requestedAt: data.requestedAt, previous: item.current, keep: keep}], W.pronunciationBack(item))
            if (data.elsewhere && data.elsewhere.spokenForm !== undefined) warnElsewhere(1, data.elsewhere.spokenForm ? "“" + data.elsewhere.spokenForm + "”" : "", action.run)
            else say(keep ? "Giữ cách đọc “" + data.spokenForm + "”" : "Đã ghi: “" + item.surface + "” đọc là “" + data.spokenForm + "”", "", kept(D.UNDO_MS, action))
            done("", "")
        })
    }

    // ---- thẻ người nói (SpeakerFix) ----
    function saveSpeaker(item, lines, scope, request, done) {
        const body = {lines: lines, speaker: request.speaker, newGender: request.newGender || "", seen: D.seenFor(lines || [], item.seen)}
        if (item.kind === "alias" && request.speaker !== item.currentValue) body.alias = item.currentValue
        if (item.kind === "bracket" && scope === "all") body.bracketRule = true
        post("/speaker", body, function(status, data) {
            if (!ok(status)) { fail("Chưa ghi được người nói", status, data); done(false); return }
            after()
            const which = data.lines > 1 ? data.lines + " câu này" : "câu này"
            const keep = request.speaker === item.currentValue
            // Quy ước 『』 cả cuốn còn ghi ở cấp cuốn cho các phần sau - hoàn tác chỉ lùi được phần câu, nên không mời
            const undo = data.alias && item.kind === "bracket" ? null : undoAction("speaker", [{lines: lines, requestedAt: data.requestedAt, keep: keep}], W.speakerBack(item, which))
            const replaced = Object.keys(data.elsewhere || {}).map(function(key) { return data.elsewhere[key] })
            if (replaced.length) warnElsewhere(replaced.length, replaced[0] ? W.personOf(item, replaced[0]) : "", undo ? undo.run : null)
            else say(W.speakerToast(item, data.lines, request.speaker), "", undo ? kept(D.UNDO_MS, undo) : {})
            done(true)
        })
    }
    // Thẻ nhóm giữ nguyên: mỗi vai giữ người của nó - vài yêu cầu, một nút hoàn tác cho cả nhóm
    function keepAllSpeakers(item, requests, done) {
        const made = []
        const replaced = []
        function next(i) {
            if (i >= requests.length) {
                after()
                const action = undoAction("speaker", made, "Thẻ hỏi lại như trước khi bấm.")
                if (replaced.length) warnElsewhere(replaced.length, replaced[0] ? W.personOf(item, replaced[0]) : "", action.run)
                else say("Đã ghi: " + (item.keepLabel || "Giữ nguyên"), "", kept(D.UNDO_MS, action))
                done(true)
                return
            }
            const request = requests[i]
            post("/speaker", Object.assign({}, request, {seen: D.seenFor(request.lines, item.seen)}), function(status, data) {
                if (!ok(status)) { after(); fail("Chưa ghi được", status, data); done(false); return }
                for (const key of Object.keys(data.elsewhere || {})) replaced.push(data.elsewhere[key])
                made.push({lines: request.lines, requestedAt: data.requestedAt, keep: true})
                next(i + 1)
            })
        }
        next(0)
    }

    // ---- thẻ người kể của đoạn (NarratorFix) ----
    function saveNarrator(item, request, done) {
        const section = item.narratorSection
        const where = {chapterIndex: section.chapterIndex, fromSeq: section.fromSeq, toSeq: section.toSeq}
        post("/narrator-section", Object.assign({}, where, request), function(status, data) {
            if (!ok(status)) { fail("Chưa ghi được người kể", status, data); done(false); return }
            after()
            const back = item.requested ? "Trở lại quyết định trước: " + item.requested + "." : "Thẻ hỏi lại như trước khi bấm."
            const text = data.action === "keep" ? (item.current ? "Giữ nguyên: đoạn này vẫn do " + item.current + " kể" : "Giữ nguyên: đoạn này vẫn kể ở ngôi thứ ba")
                : data.narrator ? "Đã ghi: đoạn này do " + (section.heading && section.heading.narrator === data.narrator ? section.heading.label : data.narrator) + " kể"
                : "Đã ghi: đoạn này không phải " + item.current + " kể"
            say(text, "", kept(D.UNDO_MS, undoAction("narrator-section", [where], back)))
            done(true)
        })
    }

    // ---- thẻ "Yêu cầu chưa được" ----
    function dropRefused(item, done) {
        post("/pending-changes/withdraw", {section: item.refused.section, key: item.refused.key, requestedAt: item.refused.requestedAt}, function(status, data) {
            if (!ok(status)) { fail("Chưa bỏ được", status, data); done(false); return }
            after()
            say("Đã bỏ yêu cầu này")
            done(true)
        })
    }

    // ---- thẻ giọng / giới (VoiceFix) ----
    function saveVoice(item, requests, label, keep, done) {
        const made = []
        function next(i) {
            if (i >= requests.length) {
                after()
                const decisions = made.map(function(decision) { return Object.assign({}, decision, {keep: keep}) })
                say("Đã ghi: " + label, "", kept(D.UNDO_MS, undoAction("voice", decisions, W.voiceBack(item))))
                done(true)
                return
            }
            post("/voice", requests[i], function(status, data) {
                if (!ok(status)) { fail("Chưa ghi được", status, data); done(false); return }
                made.push({character: requests[i].character, requestedAt: data.requestedAt})
                next(i + 1)
            })
        }
        next(0)
    }

    // ---- "Giữ như máy đang làm" cho cả loại thẻ đang lọc (BulkKeep) ----
    function bulkKeep(kind, keepable, done) {
        const pronunciation = kind === "pronunciation"
        const decisions = []
        const replaced = []
        let finished = 0
        function end(error) {
            after()
            if (error) say("Mới giữ được " + finished + "/" + keepable.length + " thẻ", error)
            else {
                const action = undoAction(pronunciation ? "pronunciation" : "speaker", decisions, finished + " thẻ trở lại chờ duyệt.")
                if (replaced.length) warnElsewhere(replaced.length, replaced[0], action.run)
                else say("Đã giữ như máy đang làm cho " + finished + " thẻ", "", kept(D.UNDO_MS, action))
            }
            done()
        }
        function card(i) {
            if (i >= keepable.length) { end(""); return }
            const item = keepable[i]
            if (pronunciation) {
                post("/pronunciation", {surface: item.surface, spokenForm: item.current, seen: item.requested || ""}, function(status, data) {
                    if (!ok(status)) { end(store.errorText(status, data)); return }
                    if (data.elsewhere && data.elsewhere.spokenForm !== undefined) replaced.push(data.elsewhere.spokenForm ? "“" + data.elsewhere.spokenForm + "”" : "")
                    decisions.push({surface: item.surface, requestedAt: data.requestedAt, previous: item.current, keep: true})
                    finished++
                    card(i + 1)
                })
            } else {
                const requests = W.keepRequests(item)
                let step = 0
                const run = function() {
                    if (step >= requests.length) { finished++; card(i + 1); return }
                    const request = requests[step]
                    post("/speaker", Object.assign({}, request, {seen: D.seenFor(request.lines, item.seen)}), function(status, data) {
                        if (!ok(status)) { end(store.errorText(status, data)); return }
                        for (const key of Object.keys(data.elsewhere || {})) replaced.push(data.elsewhere[key] ? W.personOf(item, data.elsewhere[key]) : "")
                        decisions.push({lines: request.lines, requestedAt: data.requestedAt, keep: true})
                        step++
                        run()
                    })
                }
                run()
            }
        }
        card(0)
    }

    // Câu của thẻ vai phụ cả cuốn tải thêm theo trang (GET /work/examples)
    function loadExamples(url, done) {
        store.request("GET", url, null, function(status, data) {
            if (!ok(status) || !data) { fail("Chưa tải thêm được câu", status, data); done(null); return }
            done(data)
        })
    }

    // ---- Cần nghe lại (ReviewQueue): phán quyết Ổn / Cần thu lại (null = bỏ phán quyết) ----
    // `seen`: phán quyết màn này đang thấy cho câu - máy / cửa sổ khác vừa quyết khác thì hỏi giữ của mình hay lấy của máy kia. Ghi xong hay hỏng, danh sách đều hỏi lại (reviewChanged).
    signal reviewChanged()
    function saveVerdict(item, value, done) {
        const base = {stableId: item.stableId, chapterId: item.chapterId, audioSha256: item.audioSha256}
        const seen = {}
        seen[item.stableId] = item.verdict || ""
        post("/review", Object.assign({}, base, {verdict: value, seen: seen}), function(status, data) {
            if (!ok(status)) fail("Chưa ghi được phán quyết nghe", status, data)
            else {
                const theirs = data && data.elsewhere ? data.elsewhere[item.stableId] : undefined
                if (theirs !== undefined) warnElsewhere(1, D.verdictWord(theirs), function() {
                    post("/review", Object.assign({}, base, {verdict: theirs || null}), function() { root.afterReview(); root.reviewChanged() })
                })
            }
            afterReview()
            reviewChanged()
            if (done) done(ok(status))
        })
    }

    // ---- Cách đọc tên (NameReadings → EditReading) ----
    function saveName(item, spokenForm, everywhere, done) {
        const previous = names.data
        if (previous) names.setData(N.withReading(previous, item, spokenForm))
        const body = {surface: item.surface, spokenForm: spokenForm, seen: N.seenSpoken(item)}
        if (everywhere) body.everywhere = true
        post("/pronunciation", body, function(status, data) {
            if (!ok(status)) {
                if (previous) names.setData(previous)
                done(store.errorText(status, data), suggestionOf(data))
                return
            }
            after()
            if (everywhere) shared.invalidate()
            const saved = data.spokenForm
            const keep = saved === item.spoken
            const decision = {surface: item.surface, requestedAt: data.requestedAt, previous: item.spoken, keep: keep}
            if (everywhere) decision.shared = saved
            const undo = undoAction("pronunciation", [decision], N.savedBack(item, everywhere))
            if (data.elsewhere && data.elsewhere.spokenForm !== undefined) {
                // "Lấy của máy kia": bỏ lần ghi này - yêu cầu nó thay (của máy kia) trở lại
                const back = undoAction("pronunciation", [{surface: item.surface, requestedAt: data.requestedAt, keep: false}], "“" + item.surface + "” trở lại cách đọc máy kia đã ghi.")
                warnElsewhere(1, data.elsewhere.spokenForm ? "“" + data.elsewhere.spokenForm + "”" : "", back.run)
            } else say(N.savedToast(item, saved), "", kept(D.UNDO_MS, undo))
            done("", "")
        })
    }
    // "Dùng N cách đọc chung" (SharedReadingsOffer)
    function applyShared(done) {
        post("/shared-readings", null, function(status, data) {
            if (!ok(status)) { fail("Chưa dùng được cách đọc chung", status, data); done(false); return }
            after()
            offer.invalidate()
            say("Đã dùng " + (data.applied ? data.applied.length : 0) + " cách đọc chung")
            done(true)
        })
    }

    // ---- Yêu cầu thiết bị (PhoneEdits) ----
    function decide(verb, device, item, done) {
        const body = {device: device.id}
        if (item) body.items = [item.id]
        post("/edits-inbox/" + verb, body, function(status, data) {
            if (!ok(status)) { fail("Chưa làm được", status, data); done(false); return }
            if (verb === "apply") {
                const made = data.requests || 0
                const skipped = data.skipped || 0
                const held = data.held || 0
                const dropped = (data.dropped || []).map(function(row) { return row.label })
                say(made ? "Đã ghi " + made + " việc vào “Áp dụng thay đổi”" : "Không có việc nào ghi được", skipped || held ? N.applyNote(skipped, held, dropped) : "")
            } else if (verb === "restore") say("Đã khôi phục")
            else say("Đã bỏ qua", "", kept(D.UNDO_MS, {label: "Khôi phục", run: function() { root.decide("restore", device, item, function() {}) }}))
            after()
            inbox.invalidate()
            reviewCounted.invalidate()
            done(true)
        })
    }
}
