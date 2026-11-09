.import "UiStrings.js" as S
.pragma library
.import "DecisionLogic.js" as D
.import "StudioLogic.js" as Studio

// Hộp "Việc cần duyệt" (studio/WorkInbox.tsx, workText.ts, workFocus.ts, minorGroups.ts, precast.isOpenWork): loại thẻ, tiêu đề thẻ đã quyết, lời mở đầu, chia thẻ thành
// nhóm, bộ lọc, phân trang, "Giữ cả nhóm", tiêu điểm sau khi quyết. Chữ chép từng chữ của bản web; ở đây không có gì dính tới giao diện.

// Thứ tự loại việc = thứ tự khoá của KIND_LABEL bản web (thanh lọc liệt kê theo thứ tự này)
var KINDS = ["speaker", "caller", "turn", "pronunciation", "gender", "vocative", "alias", "bracket", "shared-voice", "unnamed", "audio", "narrator", "voice-wish", "snap", "teller-voice", "teller-thought", "refused"]
var KIND_LABEL = {
    "speaker": S.s_ai_noi_cau_nay_0e00a5c7,
    "caller": S.s_nguoi_goi_ngoai_khung_03677986,
    "turn": S.s_luot_doi_dap_a2c055e0,
    "pronunciation": S.s_cach_doc_ten_1c46e75d,
    "gender": S.s_nam_hay_nu_0167dbc6,
    "vocative": S.s_goi_hay_noi_305521d7,
    "alias": S.s_mot_nguoi_hai_ten_9293d8ab,
    "bracket": S.s_loi_trong_c682376b,
    "shared-voice": S.s_chung_giong_a58df5cc,
    "unnamed": S.s_vai_phu_khong_ten_6395f0d2,
    "audio": S.s_ban_thu_loi_753aaed5,
    "narrator": S.s_nguoi_ke_cua_doan_b218398e,
    "voice-wish": S.s_giong_chua_doi_duoc_2617419d,
    "snap": S.s_ten_viet_khac_f05542f3,
    "teller-voice": S.s_giong_loi_dan_f8f4ea1e,
    "teller-thought": S.s_noi_tam_nguoi_ke_0c360f80,
    "refused": S.s_yeu_cau_chua_duoc_3c62dd70
}
function kindLabel(kind) { return KIND_LABEL[kind] || kind }
var PAGE = 40
// Nhiều hơn ngần này lựa chọn thì phần còn lại gom vào “Người khác…”
var MAX_CHIPS = 6
var GENERIC_PEOPLE = [S.s_nguoi_ke_fd36cd15, S.s_nguoi_ke_doc_tat_ca_97e4f69d, S.s_vai_phu_khong_ten_6395f0d2]
// Thẻ vai phụ cả cuốn hiện ngần này câu đầu; "Xem cả N câu" mở hết để bỏ chọn - nhóm lớn thì từng trang PICK_PAGE câu
var PICK_PREVIEW = 3
var PICK_PAGE = 100
// "Giữ như máy đang làm" cho cả loại thẻ đang lọc chỉ có ở các loại này
var BULK_KINDS = ["pronunciation", "speaker", "caller", "turn", "vocative", "unnamed"]

// Việc còn chờ người duyệt: chưa quyết, và quyết thì có tác dụng ngay (precast.isOpenWork, cùng phép đếm với work_items.open_count)
function isOpenWork(item) { return !item.requested && !item.redoOnly }

// ---- workText.ts ----
function narratorDecidedTitle(current, answer) {
    if (answer === S.s_giu_nguyen_1b550a12) return current ? S.s_doan_nay_van_do_01c8f28f + current + S.s_ke_8a00bf95 : S.s_doan_nay_van_ke_o_ngoi_thu_ba_ad31af6d
    if (answer === S.s_doi_nguoi_ke_ddc42796) return S.s_doan_nay_khong_phai_1fbdf8e0 + current + S.s_ke_8a00bf95
    const name = answer.replace(/^Người kể:\s*/, "").trim()
    return S.s_doan_nay_do_0366d95f + (name || answer) + S.s_ke_8a00bf95
}
function narratorButtons(current, heading) {
    const keep = current ? S.s_giu_d3777f80 + current + S.s_la_nguoi_ke_c2c99d76 : S.s_giu_nguyen_ngoi_thu_ba_e1160b2a
    if (!heading) return {accept: S.s_khong_phai_adb16acb + current + S.s_ke_doan_ke_ngoi_thu_ba_79a90be7, keep: keep, accepted: S.s_doi_nguoi_ke_ddc42796}
    return heading.label
        ? {accept: heading.label + S.s_ke_8a00bf95, keep: keep, accepted: S.s_nguoi_ke_97bd6976 + heading.label}
        : {accept: S.s_ke_ngoi_thu_ba_3ba8b1e4, keep: keep, accepted: S.s_doi_nguoi_ke_ddc42796}
}
// Thẻ đã quyết nói KẾT QUẢ thay vì lặp câu hỏi; null = giữ tiêu đề
function decidedTitle(item) {
    const answer = item.requested
    if (!answer) return null
    if (item.kind === "pronunciation" && item.surface) {
        return answer === item.current ? S.s_giu_c1b6fb18 + item.surface + S.s_doc_la_4c516fb0 + answer + "”" : "“" + item.surface + S.s_se_doc_la_7a286c54 + answer + "”"
    }
    if (item.voiceChoices && item.voiceChoices.length) {
        const found = item.voiceChoices.find(function(choice) { return choice.label === answer || choice.done === answer })
        return found && found.done !== undefined ? found.done : null
    }
    if (item.kind === "alias") return "“" + (item.subject !== undefined && item.subject !== null ? item.subject : item.current) + S.s_la_8e7bd753 + D.midSentence(answer)
    if (item.kind === "narrator") return narratorDecidedTitle(item.current, answer)
    if (item.lines && item.lines.length) return (item.lines.length > 1 ? item.lines.length + S.s_cau_nay_499089cc : S.s_cau_nay_ee66e104) + S.s_cua_ae306eb2 + D.midSentence(answer)
    return null
}
function cardTitle(item) { const decided = decidedTitle(item); return decided !== null ? decided : item.title }
function inboxLead(book) {
    const first = book.running && book.paused ? S.s_sach_dang_tam_dung_sua_ap_khi_lam_tiep_12a374a4
        : book.running ? S.s_may_dang_chay_tiep_sua_ap_o_chuong_sau_5482c856
        : book.phase === "done" ? S.s_sua_xong_bam_ap_dung_thay_doi_43042cc6
        : S.s_sach_dang_dung_sua_ap_khi_lam_tiep_9778f9fd
    return S.s_uu_tien_viec_tren_6f839f4c + first
}
// Chữ ký tự: chữ cái có hoa / thường (kể cả tiếng Việt), chữ số, hay chữ Nhật - Hàn - Trung
function isWordChar(ch) {
    if (!ch) return false
    return ch.toLowerCase() !== ch.toUpperCase() || (ch >= "0" && ch <= "9") || ch.charCodeAt(0) >= 0x3040
}
// Câu lời kể chia thành mảnh thường / mảnh tô (`mark`) ở mỗi chỗ có một trong `names`: nguyên chữ, không phân biệt hoa thường, tên dài trước
function markNames(text, names) {
    const seen = {}
    const forms = []
    for (const name of names || []) {
        const form = String(name).trim()
        if (form && !seen[form]) { seen[form] = true; forms.push(form.toLowerCase()) }
    }
    forms.sort(function(a, b) { return b.length - a.length })
    const lower = text.toLowerCase()
    if (!forms.length || lower.length !== text.length) return [{text: text, mark: false}]
    const parts = []
    let last = 0
    let i = 0
    while (i < text.length) {
        let hit = 0
        if (!isWordChar(text.charAt(i - 1))) {
            for (const form of forms) {
                if (lower.startsWith(form, i) && !isWordChar(text.charAt(i + form.length))) { hit = form.length; break }
            }
        }
        if (hit) {
            if (i > last) parts.push({text: text.slice(last, i), mark: false})
            parts.push({text: text.slice(i, i + hit), mark: true})
            i += hit
            last = i
        } else i++
    }
    if (last < text.length || !parts.length) parts.push({text: text.slice(last), mark: false})
    return parts
}
// Màu của Theme thành chữ cho CSS của Text.RichText (Qt đọc rgba(), không đọc #aarrggbb)
function cssColor(color) {
    const rgb = Math.round(color.r * 255) + "," + Math.round(color.g * 255) + "," + Math.round(color.b * 255)
    return color.a >= 1 ? "rgb(" + rgb + ")" : "rgba(" + rgb + "," + Math.round(color.a * 1000) / 1000 + ")"
}
function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;") }
// Câu ví dụ của thẻ thành HTML ngắn cho Text.RichText: tên ứng viên tô nền nhạt, đậm, màu nhấn
function exampleHtml(example, markBg, markInk) {
    if (!example.names || !example.names.length) return esc(example.text)
    return markNames(example.text, example.names).map(function(part) {
        return part.mark ? "<span style=\"background-color:" + markBg + "; color:" + markInk + "; font-weight:600\">" + esc(part.text) + "</span>" : esc(part.text)
    }).join("")
}
// Dòng nhỏ trên câu: "Chương 1 · câu 3 · máy gán: X · lời kể · sẽ đổi · chưa thu". `html`: ra HTML cho Text.RichText ("sẽ đổi" đậm màu `ink`).
function exampleMeta(example, willChange, html, ink) {
    const head = example.chapterTitle + "\u00a0·\u00a0" + (example.seq === 0 ? S.s_tieu_de_chuong_4f8f59f4 : S.s_cau_ac0b3a5b + example.seq)
        + (example.speaker ? S.s_u00a0_u00a0may_gan_2f1c964c + example.speaker : "")
        + (example.narration ? S.s_u00a0_u00a0loi_ke_824055ab : "")
    const change = willChange ? (html ? "<span style=\"color:" + ink + S.s_font_weight_600_nbsp_nbsp_se_doi_span_b8ad82a9 : S.s_nbsp_nbsp_se_doi_b770bb5a) : ""
    return (html ? esc(head) : head) + change + (!example.hasAudio ? S.s_u00a0_u00a0chua_thu_42d33ed7 : "")
}

// ---- minorGroups.ts ----
// Câu bỏ chọn là tập `dropped` dạng {stableId: true}
function pickedLines(lines, dropped) { return lines.filter(function(line) { return !dropped[line.stableId] }) }
function toggleLine(dropped, stableId) {
    const next = Object.assign({}, dropped)
    if (next[stableId]) delete next[stableId]; else next[stableId] = true
    return next
}
function keepRequests(item) {
    if (item.keepGroups && item.keepGroups.length) return item.keepGroups.filter(function(group) { return group.lines.length > 0 })
    if (item.lines && item.lines.length && item.currentValue) return [{lines: item.lines, speaker: item.currentValue}]
    return []
}
function pickNote(picked, total) {
    if (picked === total) return S.s_dang_chon_ca_5533ba66 + total + S.s_cau_b07e1008
    if (picked === 0) return S.s_chua_chon_cau_nao_trong_98e427e2 + total + S.s_cau_b07e1008
    return S.s_dang_chon_b79eb4ba + picked + "/" + total + S.s_cau_b07e1008
}
// Thẻ nhóm lớn chỉ mang vài câu đầu (`examplesTotal` là tổng); "Xem thêm" lấy từng trang (GET /work/examples). Trả câu đã có, tổng, và đường hỏi trang kế ("" = đã đủ).
function examplesPage(bookId, key, first, more, total, page) {
    const loaded = more.length > 0 ? first.concat(more) : first
    const all = Math.max(total || 0, loaded.length)
    const next = loaded.length < all ? "/api/books/" + bookId + "/work/examples?key=" + encodeURIComponent(key) + "&offset=" + loaded.length + "&limit=" + page : ""
    return {loaded: loaded, total: all, next: next}
}
function moreText(shown, total) { return S.s_xem_them_dang_hien_6f8f1101 + Studio.formatNumber(shown) + "/" + Studio.formatNumber(total) + S.s_cau_70a7137f }

// ---- Chọn người nói trên thẻ ----
// Chip hiện thẳng / chip gom vào “Người khác…”: chừa MAX_CHIPS đầu, lựa chọn đã ghi và người chung chung
function isAnswer(item, choice) { return !!item.requested && (choice.name === item.requested || choice.label === item.requested) }
function shownChoices(item) {
    return (item.choices || []).filter(function(choice, index) { return index < MAX_CHIPS || isAnswer(item, choice) || GENERIC_PEOPLE.indexOf(choice.label) >= 0 })
}
function moreChoices(item) {
    const shown = shownChoices(item)
    return (item.choices || []).filter(function(choice) { return shown.indexOf(choice) < 0 })
}
// Gợi ý tên bằng chính tên trong sách
function sampleName(item) {
    for (const choice of item.choices || []) {
        const text = choice.name !== undefined && choice.name !== null ? choice.name : choice.label
        if (text && GENERIC_PEOPLE.indexOf(text) < 0 && !/^(Tất cả là|Giữ) /.test(text)) return text
    }
    return ""
}
// Chip được gạch chân (lựa chọn đã ghi, hay máy đề xuất ở chip đầu)
function chipMarked(item, choice, index) {
    if (item.requested) return isAnswer(item, choice)
    return index === 0 && item.kind !== "unnamed" && item.suggested !== false
}
function keepButtonLabel(item) { return item.keepLabel || (item.kind === "unnamed" ? S.s_dung_la_vai_phu_7f821afe : S.s_giu_d3777f80 + item.current) }
// Tên người từ mã của họ, theo các lựa chọn của thẻ (báo "trước đó đang là …")
function personOf(item, value) {
    if (value === item.currentValue) return item.current
    const choice = (item.choices || []).find(function(option) { return option.value === value })
    return choice ? (choice.name !== undefined && choice.name !== null ? choice.name : choice.label) : value
}
function speakerBack(item, which) {
    if (item.requested) return S.s_tro_lai_quyet_dinh_truoc_33162bcb + which + S.s_cua_ae306eb2 + D.midSentence(item.requested) + "."
    if (item.pick) return D.sentence(which) + S.s_tro_lai_cho_duyet_31d037fd
    return D.sentence(which) + S.s_lai_la_cua_e26113c4 + D.midSentence(item.current) + "."
}
function speakerToast(item, recorded, speaker) {
    const which = recorded > 1 ? recorded + S.s_cau_nay_499089cc : S.s_cau_nay_c70feb8f
    if (speaker === item.currentValue) return item.keepLabel ? S.s_da_ghi_85094402 + item.keepLabel : S.s_giu_nguyen_360918a5 + which + S.s_cua_ae306eb2 + D.midSentence(item.current)
    const choice = (item.choices || []).find(function(option) { return option.value === speaker })
    const label = choice ? (choice.name !== undefined && choice.name !== null ? choice.name : choice.label) : speaker
    return S.s_da_ghi_85094402 + which + S.s_cua_ae306eb2 + D.midSentence(label)
}
function speakerAppliedLine(item, pending) {
    if (item.kind === "alias") return S.s_da_ghi_a2accbdb + (item.subject !== undefined && item.subject !== null ? item.subject : item.current) + S.s_la_8e7bd753 + D.midSentence(item.requested) + S.s_ca_cuon_va_cac_phan_sau_73506133
    const n = item.lines ? item.lines.length : 1
    return S.s_da_ghi_85094402 + (n > 1 ? n + S.s_cau_nay_499089cc : S.s_cau_nay_c70feb8f) + S.s_cua_ae306eb2 + D.midSentence(item.requested) + " - " + pending + "."
}
function scopeNote(item) {
    return item.scopeLabels
        ? item.scopeLabels[0] + S.s_theo_chuong_fe0e612d + item.scopeLabels[1] + S.s_theo_ca_sach_va_cac_phan_sau_aaf91813
        : S.s_cau_xen_ke_chi_doi_cau_danh_dau_ca_chuoi_d_8b814b90
}

// ---- Thẻ giọng / giới ----
function voiceHeard(item) { return item.current === S.s_giong_nam_4ab78f43 || item.current === S.s_giong_nu_cd860480 ? item.current.toLowerCase() : S.s_giong_dang_co_3b2ea3dd }
function voiceBack(item) {
    if (item.kind === "gender" && item.subject) {
        return item.requested ? S.s_tro_lai_quyet_dinh_truoc_33162bcb + item.subject + S.s_la_873f17ce + item.requested.toLowerCase() + "."
            : item.subject + S.s_lai_de_may_quyet_van_doc_bang_b242963d + voiceHeard(item) + "."
    }
    if (item.requested) return S.s_tro_lai_quyet_dinh_truoc_33162bcb + item.requested + "."
    return item.kind === "shared-voice" ? S.s_hai_nguoi_lai_dung_chung_giong_nhu_truoc_7486498c : S.s_the_hoi_lai_nhu_truoc_khi_bam_7ad3829e
}
function voiceChoiceMarked(item, choice) { return item.requested ? (choice.done === item.requested || choice.label === item.requested) : !!choice.recommended }

// ---- Thẻ cách đọc tên ----
function pronunciationBack(item) {
    return item.requested ? S.s_tro_lai_quyet_dinh_truoc_23b8f1db + item.surface + S.s_doc_la_4c516fb0 + item.requested + "”." : "“" + item.surface + S.s_lai_doc_la_fbb29ef1 + item.current + "”."
}
function pronunciationAppliedLine(item, pending) {
    return item.requested === item.current ? S.s_giu_f2a9d747 + item.requested + S.s_khong_can_ap_dung_9dc28408 : S.s_da_ghi_70e429d4 + item.requested + "” - " + pending + "."
}

// ---- Nhóm thẻ của hộp ----
// Số thay đổi đang chờ áp dụng trong các thẻ đã quyết: hai thẻ cùng quyết một câu là MỘT thay đổi; “Giữ” cách đang đọc là đã quyết mà không có gì chờ áp dụng.
function waitingChanges(decided) {
    const changes = {}
    for (const item of decided) {
        if (item.requested === item.current) continue
        const ids = item.lines ? item.lines.map(function(line) { return line.stableId }).sort() : []
        changes[ids.length ? "lines:" + ids.join(",") : "key:" + item.key] = true
    }
    return Object.keys(changes).length
}
// Chia việc của máy chủ thành các nhóm hộp hiển thị. `inPrecast`: {khoá: true} của thẻ đang nằm ở "Duyệt trước khi thu" (không hiện lại ở đây).
function groups(items, inPrecast, kind) {
    const precast = inPrecast || {}
    const undecided = items.filter(isOpenWork)
    const later = items.filter(function(item) { return !item.requested && item.redoOnly })
    const open = undecided.filter(function(item) { return !precast[item.key] })
    const answered = items.filter(function(item) { return item.requested })
    const redo = answered.filter(function(item) { return item.redoOnly })
    const decided = answered.filter(function(item) { return !item.redoOnly })
    const counts = {}
    for (const item of open) counts[item.kind] = (counts[item.kind] || 0) + 1
    const kinds = KINDS.filter(function(value) { return counts[value] })
    const active = kind !== "all" && !counts[kind] ? "all" : kind
    return {
        open: open, atReview: undecided.length - open.length, later: later, redo: redo, decided: decided, waiting: waitingChanges(decided),
        counts: counts, kinds: kinds, active: active,
        filtered: open.filter(function(item) { return active === "all" || item.kind === active })
    }
}
function decidedSummary(decided, waiting) {
    return waiting === decided.length ? S.s_da_quyet_cho_ap_dung_u00a0_u00a0_443dcc0a + decided.length + S.s_viec_1c50ca93 : S.s_da_quyet_u00a0_u00a0_17e896ba + decided.length + S.s_viec_1b4fd320 + waiting + S.s_thay_doi_cho_ap_dung_5e697cb8
}
function endLine(group, hint) {
    return group.later.length > 0
        ? S.s_het_viec_sua_duoc_ngay_nhung_viec_ben_duoi_2b4551c3
        : S.s_moi_viec_da_co_quyet_dinh_d64ce55d + (group.decided.length > 0 ? " - " + hint : "") + "."
}
function precastLine(count) { return count + S.s_viec_cua_cac_chuong_dau_dang_cho_o_duyet_t_ffc8b06a }
function filterOptions(group) {
    const options = [{value: "all", label: S.s_tat_ca_u00a0_u00a0_85c386de + group.open.length}]
    for (const value of group.kinds) options.push({value: value, label: KIND_LABEL[value] + "\u00a0·\u00a0" + group.counts[value]})
    return options
}
function bulkKeepable(kind, items) {
    return items.filter(function(item) { return kind === "pronunciation" ? !!item.surface : keepRequests(item).length > 0 })
}
function bulkTitle(kind, count) { return S.s_giu_ca_4b7c5467 + count + S.s_the_e2579785 + KIND_LABEL[kind] + "”?" }
function bulkDescription(kind) { return kind === "pronunciation" ? S.s_giu_cach_doc_ten_khong_thu_lai_co_the_hoan_175ec7d0 : S.s_giu_nguoi_noi_khong_thu_lai_co_the_hoan_ta_602c8451 }

// ---- workFocus.ts ----
// Thẻ nhận tiêu điểm sau khi danh sách đổi và tiêu điểm vừa mất. before / after: {open: [khoá], decided: [khoá]}; focused: khoá thẻ chứa tiêu điểm lần gần nhất (null = ở nút "Hoàn tác" của thông báo).
// Trả khoá thẻ, "end" (hết thẻ) hay null (không làm gì).
function focusAfterChange(before, after, focused) {
    if (focused === null) {
        const back = after.open.filter(function(key) { return before.open.indexOf(key) < 0 })
        const returned = back.find(function(key) { return before.decided.indexOf(key) >= 0 })
        if (returned !== undefined) return returned
        if (after.decided.length < before.decided.length && back.length) return back[0]
        return null
    }
    const list = before.open.indexOf(focused) >= 0 ? "open" : before.decided.indexOf(focused) >= 0 ? "decided" : null
    if (!list) return null
    const now = after[list]
    if (now.indexOf(focused) >= 0) return focused
    if (now.length) return now[Math.min(before[list].indexOf(focused), now.length - 1)]
    return list === "decided" && after.open.indexOf(focused) >= 0 ? focused : "end"
}
