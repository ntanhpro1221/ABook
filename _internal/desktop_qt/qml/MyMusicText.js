.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size

// Chữ và phép tính thuần của "Nhạc của tôi" (studio/musicLocal.ts, studio/musicImport.ts, shared/format.ts, listen/prepareAhead.ts của bản web), giữ nguyên lời.

var LOCAL_PREFIX = "local:"
var MY_MUSIC_INTRO = S.s_them_nhac_lam_nen_bai_da_chon_di_cung_file_eefa0e8d
var MY_MUSIC_HELP = S.s_nhac_duoc_chep_vao_kho_may_nay_dung_doi_ba_00b59983
var CANCELLED_NOTE = S.s_da_huy_lan_tai_sau_lam_tiep_tu_cho_dung_a3bd5f77
var RETRYING_NOTE = S.s_mang_chap_chon_dang_thu_lai_e0ce6cbb

// "m:ss" hay "h:mm:ss" (formatClock của shared/format.ts)
function formatClock(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0
    var whole = Math.floor(seconds)
    var hours = Math.floor(whole / 3600)
    var minutes = Math.floor((whole % 3600) / 60)
    var secs = whole % 60
    var mm = hours ? String(minutes).padStart(2, "0") : String(minutes)
    return (hours ? hours + ":" : "") + mm + ":" + String(secs).padStart(2, "0")
}

function modulePercent(module) {
    return module.total > 0 ? Math.min(100, Math.floor((module.done / module.total) * 100)) : 0
}

// Câu báo về mô-đun "Phân tích nhạc", nói bằng điều người nghe cần biết.
function moduleLabel(module) {
    if (module.state === "error") return module.error
    if (module.state === "downloading") return module.retrying ? RETRYING_NOTE + S.s_phan_tich_nhac_02745c2c + modulePercent(module) + "%)" : S.s_dang_tai_phan_tich_nhac_16da0da4 + Size.formatSize(module.total) + S.s_mot_lan_ca40e942 + modulePercent(module) + "%"
    if (module.analysing) return S.s_dang_phan_tich_nhac_da_them_a2a6a13b
    if (module.state === "unsupported") return module.reason ? S.s_may_nay_chua_phan_tich_duoc_nhac_5c389226 + module.reason + "." : S.s_may_nay_chua_phan_tich_duoc_nhac_15442fa6
    if (module.state === "outdated" && module.stopped)
        return S.s_phan_tich_nhac_dang_tat_tai_lai_c41e0d4b + Size.formatSize(module.outdatedBytes !== undefined ? module.outdatedBytes : module.total) + S.s_van_ghim_tay_duoc_1802e446
    if (module.state === "outdated") return (module.cancelled ? CANCELLED_NOTE + " " : "") + S.s_co_ban_moi_76a8cd88 + Size.formatSize(module.outdatedBytes !== undefined ? module.outdatedBytes : module.total) + S.s_ban_hien_tai_van_dung_duoc_85e16d72
    if (module.state === "ready") {
        if (module.restart) return S.s_phan_tich_nhac_da_cap_nhat_mo_lai_abook_de_0fe3cd00
        if ((module.stale || 0) > 0) return module.stale + S.s_bai_dung_phan_tich_cu_co_the_phan_tich_lai_80822b32
        return ""
    }
    return (module.cancelled ? CANCELLED_NOTE + " " : "") + S.s_may_tu_chon_nhac_hop_tung_doan_8c88a607     // dung lượng chỉ ở nút "Tải (… MB)"
}

// Có mời bật "Đo cảm xúc nhạc chính xác hơn" không: máy đủ sức, và đã có bộ phân tích nhạc.
function preciseOffered(module) {
    return Boolean(module && module.precise && module.precise.state !== "unavailable" && module.ready)
}
function preciseBusy(precise) {
    return Boolean(precise && (precise.state === "downloading" || precise.working))
}
function preciseLabel(precise) {
    var size = Size.formatSize(precise.bytes)
    if (precise.state === "downloading") {
        var percent = precise.total > 0 ? Math.min(100, Math.floor((precise.done / precise.total) * 100)) : 0
        return S.s_dang_tai_bo_do_cam_xuc_chinh_xac_hon_992a8222 + size + S.s_mot_lan_ca40e942 + percent + "%"
    }
    if (precise.state === "error") return precise.error
    if (precise.state === "missing") return S.s_da_bat_nhung_chua_tai_xong_bai_moi_them_ta_467bc3b6
    if (precise.state === "ready") {
        if (precise.working) {
            return precise.pending > 0
                ? S.s_dang_nghe_ky_6963a9b6 + precise.pending + S.s_bai_ban_da_them_bai_chua_toi_luot_van_dung_34b5c4c6
                : S.s_dang_nghe_ky_bai_vua_them_9d3cd7fd
        }
        return S.s_dang_bat_bai_moi_them_se_duoc_nghe_ky_ngam_66f8653c
    }
    var how = precise.present ? S.s_chay_67d64a17 : S.s_tai_them_76c4650b + size + S.s_mot_lan_sau_do_chay_236c7a4d
    return (precise.cancelled ? CANCELLED_NOTE + " " : "") + S.s_may_nghe_ky_hon_tung_bai_ban_them_de_chon_b1ad40b1 + how + S.s_ngam_vai_giay_moi_bai_khong_can_mang_32f1dd9a
}

function localDigest(link) {
    var digest = String(link).indexOf(LOCAL_PREFIX) === 0 ? String(link).slice(LOCAL_PREFIX.length) : ""
    return /^[0-9a-f]{40}$/.test(digest) ? digest : null
}

function hasVocals(track) { return track.analysed && track.vocalsLikely === true }

// Công tắc "Tự chọn" của một bài (công tắc `auto`, music_local.py): bật = máy được tự chọn bài này. Mặc định máy tự chọn bài thường, bỏ qua bài có lời.
var AUTO_PICK_LABEL = S.s_tu_chon_90506961
var UNANALYSED = S.s_chua_phan_tich_5c1c27fb
function autoOn(track) { return track.auto === "on" || (track.auto !== "off" && !hasVocals(track)) }
// Giá trị `auto` gửi đi khi gạt công tắc: trùng mặc định thì về mặc định (null).
function autoNext(track) {
    var on = !autoOn(track)
    return on === !hasVocals(track) ? null : (on ? "on" : "off")
}
// Nhãn ngắn cạnh công tắc - điều công tắc không nói: bài chưa phân tích (máy chưa tự chọn được), bài có lời.
function trackNote(track) { return !track.analysed ? UNANALYSED : hasVocals(track) ? S.s_co_loi_4b381f10 : "" }
// Dòng phụ của một bài trong "Đổi bài" (không có công tắc ở đó): có lời, đã tắt tự chọn, hợp đoạn này / chưa phân tích.
function mineNote(item) {
    var notes = [hasVocals(item) ? S.s_co_loi_4b381f10 : null, item.auto === "off" ? S.s_khong_tu_chon_02ae1742 : null, item.analysed ? (item.fits ? S.s_hop_khong_khi_doan_nay_44c3025b : null) : UNANALYSED]
    return notes.filter(function(note) { return !!note }).join("\u00a0·\u00a0")
}

// Gộp kết quả của nhiều lượt nhập (mỗi file một lượt): danh sách bài và mô-đun lấy của lượt cuối.
function mergeImports(results) {
    var last = results[results.length - 1]
    var merged = {tracks: last ? last.tracks : [], analyzer: last ? last.analyzer : false, added: [], existing: [], failed: []}
    if (last && last.module) merged.module = last.module
    for (var i = 0; i < results.length; ++i) {
        merged.added = merged.added.concat(results[i].added || [])
        merged.existing = merged.existing.concat(results[i].existing || [])
        merged.failed = merged.failed.concat(results[i].failed || [])
    }
    return merged
}

// Câu báo sau khi nhập: bao nhiêu bài đã vào, bao nhiêu đã có sẵn, file nào không nhập được. Trả {kind, title, description}.
function importSummary(result) {
    var added = result.added || [], existing = result.existing || [], failed = result.failed || []
    var parts = []
    if (added.length) parts.push(added.length + S.s_bai_moi_76603364)
    if (existing.length) parts.push(existing.length + S.s_bai_da_co_tu_truoc_2e0cbfb6)
    if (!added.length && !existing.length)
        return {kind: "error", title: S.s_chua_them_duoc_nhac_5565bc66, description: failed.join("\n")}
    var unanalysed = added.filter(function(track) { return !track.analysed }).length
    var notes = []
    if (failed.length) notes.push(failed.join("\n"))
    if (unanalysed) notes.push(unanalysed + S.s_bai_chua_phan_tich_may_chua_tu_chon_ban_gh_924e5ac5)
    return {kind: failed.length ? "warning" : "success", title: S.s_da_them_f09915c7 + parts.join(", "), description: notes.join("\n")}
}

// Lời báo của web (toast(title, {description})) thành một chuỗi của Api.notice: tên ở dòng đầu, lý do ở dòng sau.
function toast(title, description) {
    return description ? title + "\n" + description : title
}

// ---- Bộ nhớ (listen/prepareAhead.ts) ----
function storageLabel(usage) {
    return usage.total > 0 ? S.s_ban_doc_da_lam_chiem_69c5507d + Size.formatSize(usage.total) + S.s_tren_may_nay_606511e4 : S.s_chua_co_ban_doc_da_luu_18fe660f
}
function clearStorageQuestion(usage) {
    return S.s_don_a1fe57bd + Size.formatSize(usage.total) + S.s_ban_doc_da_lam_cua_moi_cuon_may_se_doc_lai_e7218cf6
}

// ---- Cập nhật (desktop/updateCheck.ts) ----
var UPDATE_CHECK_WAIT_MS = 45000
// Lời hiện dưới nút kiểm tra; `found` không cần lời (mục "bản mới đã có" hiện thay); vỏ im là lỗi mạng. Trả {tone, text} hay null.
function checkLine(detail, current) {
    if (detail && detail.state === "found") return null
    if (detail && detail.state === "latest") return {tone: "ok", text: S.s_abook_1c37d334 + (current ? " " + current : "") + S.s_la_ban_moi_nhat_2c45dd9f}
    return {tone: "error", text: (detail && detail.message) || S.s_chua_thay_tra_loi_tu_trang_phat_hanh_ban_k_437de1e1}
}

// ---- Thành phần bên thứ ba (shared/thirdParty.ts) ----
var MAINTAINER_SECTION = S.s_ghi_chu_cho_nguoi_bao_tri_c8670b77
// Tách Markdown của THIRD_PARTY.md thành các mục theo tiêu đề `##`; phần mở đầu là mục không tên; mục của người bảo trì bị bỏ.
function parseThirdParty(markdown) {
    var sections = [{title: "", items: []}]
    var open = null
    var lines = String(markdown).replace(/\r/g, "").split("\n")
    for (var i = 0; i < lines.length; ++i) {
        var line = lines[i].trim()
        if (!line) { open = null; continue }
        if (line.indexOf("# ") === 0) continue
        if (line.indexOf("## ") === 0) { sections.push({title: line.slice(3).trim(), items: []}); open = null; continue }
        var section = sections[sections.length - 1]
        var bullet = /^[-*] /.test(line)
        if (bullet || !open) {
            open = {text: bullet ? line.slice(2) : line, bullet: bullet}
            section.items.push(open)
        } else {
            open.text += " " + line
        }
    }
    return sections.filter(function(s) { return s.items.length && s.title.indexOf(MAINTAINER_SECTION) !== 0 })
}
function escapeHtml(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;")
}
// Chữ đậm `**...**` và mã `...` của Markdown thành HTML của Text (RichText); còn lại để nguyên. `strong`: màu chữ đậm; `codeBack`: nền mã.
function inlineHtml(text, strong, codeBack) {
    var parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/)
    var out = ""
    for (var i = 0; i < parts.length; ++i) {
        var part = parts[i]
        if (part.indexOf("**") === 0 && part.slice(-2) === "**" && part.length > 4)
            out += "<span style=\"font-weight:600; color:" + strong + "\">" + escapeHtml(part.slice(2, -2)) + "</span>"
        else if (part.charAt(0) === "`" && part.slice(-1) === "`" && part.length > 2)
            out += "<span style=\"font-family:monospace; background-color:" + codeBack + "\">&nbsp;" + escapeHtml(part.slice(1, -1)) + "&nbsp;</span>"
        else
            out += escapeHtml(part)
    }
    return out
}
