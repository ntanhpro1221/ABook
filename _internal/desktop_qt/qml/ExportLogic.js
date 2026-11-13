.import "UiStrings.js" as S
.pragma library
.import "StudioLogic.js" as Studio
.import "SizeFormat.js" as Size
.import "CastLogic.js" as Cast

// Phần thuần của hộp "Xuất" (ui/src/studio/ExportBook.tsx, exportText.ts, projectPacking.ts, bookFilePacking.ts, WordTimings.tsx và phần jobView / copy của
// desktop/bookFileExport.ts, listenExport.ts): chữ và quy tắc chép từng chữ để hai nền tảng nói cùng một câu; HTTP và giao diện nằm ở ExportBook.qml.

// ---- kiểu bản xuất ----
var KINDS = [
    {value: "mp3", title: S.s_thu_muc_mp3_2eea06d7, detail: S.s_moi_chuong_mot_file_co_ten_va_bia_97cf9d56, icon: "folder-down"},
    {value: "abook", title: "File .abook", detail: S.s_mot_file_chua_ca_sach_mo_bang_abook_c88beb23, icon: "file-audio"},
    {value: "m4b", title: S.s_sach_noi_m4b_01d29e1d, detail: S.s_mot_file_co_muc_luc_chuong_cho_app_sach_no_a73ffb74, icon: "book-audio"},
    {value: "abookproj", title: S.s_ca_du_an_abookproj_ff1824d8, detail: S.s_ca_du_an_va_audio_de_sao_luu_hay_lam_tiep_e5b95d4c, icon: "folder-archive"}
]
// [tiêu đề hộp chọn thư mục, đang làm, lỗi]
var SAVING = {
    mp3: [S.s_chon_noi_luu_2965936c, S.s_dang_xuat_mp3_99b61b74, S.s_chua_xuat_duoc_mp3_1550e65a],
    abook: [S.s_chon_noi_luu_2965936c, S.s_dang_dong_goi_sach_ac7bab85, S.s_chua_xuat_duoc_file_sach_43236ec7],
    m4b: [S.s_chon_noi_luu_2965936c, S.s_dang_lam_file_m4b_4a95b4ac, S.s_chua_xuat_duoc_m4b_5a39de4c],
    abookproj: [S.s_chon_noi_luu_2965936c, S.s_dang_dong_goi_du_an_59bb0a50, S.s_chua_goi_duoc_du_an_fd3612d5]
}
/** Thẻ nhớ / USB định dạng FAT32 không chứa nổi file lớn hơn 4 GiB. */
var FAT32_LIMIT = 4 * 1024 * 1024 * 1024
var MUSIC_MIX_HINT = S.s_nhac_duoc_tron_thang_vao_file_khong_tat_ri_e1608133
function scopeOptions(parts) { return [{value: "part", label: S.s_phan_nay_20fb3a86}, {value: "series", label: S.s_ca_bo_d0840d1d + parts + S.s_phan_64af5c84}] }
var LAYOUTS = [{value: "single", label: S.s_mot_file_774a88e2}, {value: "perPart", label: S.s_moi_phan_mot_file_055af8d9}]

/** Studio từ xa (máy khác) không gói dự án: file nằm ở máy tính, việc của người ngồi trước nó. */
function kindsFor(remote) { return remote ? KINDS.filter(function(item) { return item.value !== "abookproj" }) : KINDS }
function kindInfo(kind) { return KINDS.filter(function(item) { return item.value === kind })[0] || KINDS[0] }
/** Truy vấn chọn trạng thái tải nhạc / Huỷ của đúng kiểu xuất ở máy chủ (server.py `_music_key`); `.abook` không cần. */
function musicKind(kind) { return kind === "abookproj" ? "?kind=projectfile" : "" }

// ---- exportText.ts ----
/** Chương chờ thu lại theo sửa của người nghe: bản xuất mang bản thu CŨ của chúng. `null` khi không có chương nào chờ. */
function redoExportNote(redo, abook) {
    if (redo <= 0) return null
    const name = abook ? S.s_ten_giong_ghi_trong_sach_co_the_da_la_gion_73247fe9 : ""
    return redo + S.s_chuong_dang_cho_thu_lai_theo_sua_cua_ban_s_075516f2 + name + "."
}

// ---- projectPacking.ts ----
var PACK_SPAN = {prepare: [0, 0.02], listen: [0.02, 0.38], views: [0.38, 0.42], hash: [0.42, 0.72], write: [0.72, 1]}
/** File sách `.abook` (bookfile.pack): gom chương là gần hết thời gian, rồi ghi gói. */
var BOOK_FILE_SPAN = {prepare: [0, 0.02], listen: [0.02, 0.85], views: [0.85, 0.85], hash: [0.85, 0.85], write: [0.85, 1]}
/** {title: "Đang đóng gói (12/400 chương)…", fraction: 0-1 hay null khi chưa có mẫu số} */
function packView(job, spans) {
    spans = spans || PACK_SPAN
    const base = S.s_dang_dong_goi_5561df87
    if (!job || !job.phase || job.state !== "running") return {title: base + "…", fraction: null}
    const span = spans[job.phase]
    const total = job.total || 0
    const done = Math.min(job.done || 0, total)
    const inner = total > 0 ? done / total : 0
    const fraction = span[0] + (span[1] - span[0]) * inner
    if (job.phase === "listen" && total > 0) return {title: base + " (" + done + "/" + total + S.s_chuong_be1b3067, fraction: fraction}
    if ((job.phase === "hash" || job.phase === "write") && total > 0) return {title: base + " (" + Size.formatSize(done) + "/" + Size.formatSize(total) + ")…", fraction: fraction}
    return {title: base + "…", fraction: job.phase === "prepare" ? null : span[0]}
}
var PACK_KNOWN = [
    {pattern: /No space left|ENOSPC|disk full|WinError 112|not enough space|disk quota/i, summary: S.s_o_dia_het_cho_trong_giai_phong_dung_luong_4f636c99},
    {pattern: /PermissionError|WinError 5\b|WinError 32|Access is denied|being used by another process|Errno 13/i,
     summary: S.s_chua_ghi_duoc_vao_thu_muc_da_chon_dang_bi_87fb8bb6}
]
/** Lỗi thô của máy chủ -> câu cho người nghe + nguyên văn cho "Chi tiết". Lỗi đã viết bằng tiếng Việt giữ nguyên, không có Chi tiết. */
function packError(raw) {
    const detail = String(raw).trim()
    for (const known of PACK_KNOWN) if (known.pattern.test(detail)) return {summary: known.summary, detail: detail}
    if (/[ạảãàáâấầẩẫậắằẳẵặẹẻẽèéêếềểễệỉĩịọỏõòóôốồổỗộớờởỡợụủũùúưứừửữựỳỷỹýđ]/i.test(detail)) return {summary: detail, detail: ""}
    return {summary: S.s_chua_goi_duoc_du_an_4eb38947, detail: detail}
}
/** Gói bị huỷ (máy chủ trả "cancelled"): người dùng bấm Huỷ. */
var CANCELLED = "cancelled"

// ---- bookFilePacking.ts ----
/** Bắt đầu một việc xuất nền rồi theo nó; theo lại việc cũ (`attach`) thì không tạo lượt mới. `request(method, path, body, done(status, data))`
 *  là đường HTTP của Studio; `follow(done)` theo job tới khi xong. `done(error, result, data)`. */
function startJob(request, path, body, follow, attach, done) {
    if (attach) { follow(done); return }
    request("POST", path, body, function(status, data) {
        if (status < 200 || status >= 300) { done(data && (data.message || data.error) || S.s_chua_xuat_duoc_file_sach_43236ec7, null, data); return }
        follow(done)
    })
}
/** Xuất file sách `.abook` (bookFilePacking.ts): cùng đường với mọi kiểu xuất, đường là `bookfile-job`. */
function packBookFile(request, bookId, body, follow, attach, done) {
    startJob(request, "/api/books/" + bookId + "/bookfile-job", body, follow, attach, done)
}

// ---- định dạng chữ chung ----
function fileName(path) { const parts = String(path).replace(/[\\/]+$/, "").split(/[\\/]/); return parts[parts.length - 1] || String(path) }
/** Studio từ xa: file xuất nằm trên máy tính, không về máy đang xem. `detail`: phần còn lại của dòng ("5 MB", "6 file"). */
function exportedOnComputer(computer, name, detail) {
    const where = computer && computer !== S.s_may_tinh_8eafc226 ? S.s_da_xuat_vao_may_tinh_8f7e925f + computer : S.s_da_xuat_vao_may_tinh_d121586e
    return [name ? where + ": " + name : where, detail || ""].filter(Boolean).join("\u00a0·\u00a0")
}
function spokenDuration(seconds) {
    const minutes = Math.round(seconds / 60)
    if (minutes < 1) return S.s_duoi_1_phut_a1dd4f60
    if (minutes < 60) return S.s_khoang_934859d7 + minutes + S.s_phut_cf728a6a
    const hours = Math.floor(minutes / 60), rest = minutes % 60
    return S.s_khoang_934859d7 + hours + S.s_gio_9e4dcadb + (rest ? " " + rest + S.s_phut_cf728a6a : "")
}
/** "Chỗ lưu" nói trước khi bấm "Xuất": có hộp chọn thư mục thì tự chọn, không thì vào thư mục "Đã xuất" của thư viện. */
function savePlace(opts) {
    if (opts.dialogs) return S.s_bam_nut_ben_duoi_roi_chon_thu_muc_de_luu_e266290b
    if (opts.remote) return S.s_se_luu_vao_thu_muc_da_xuat_trong_thu_vien_bf91ff65 + (opts.computer && opts.computer !== S.s_may_tinh_8eafc226 ? " " + opts.computer : "")
        + S.s_file_nam_o_may_tinh_khong_tai_ve_may_nay_2e312a52
    const root = opts.libraryRoot || ""
    return root ? S.s_se_luu_vao_thu_muc_da_xuat_trong_thu_vien_433a32a2 + root + (root.indexOf("\\") >= 0 ? "\\" : "/") + S.s_da_xuat_d801674e : S.s_se_luu_vao_thu_muc_da_xuat_trong_thu_vien_a78ada3d
}

// ---- cái hộp tính ra: bao nhiêu chương, cảnh báo gì, nút có bấm được không ----
/** Truyện nhiều phần: xuất riêng phần đang xem hay cả bộ. M4B: mỗi phần một file riêng, như menu Thư viện; dự án nằm trong MỘT file. */
function isWholeSeries(scope, parts, kind) { return scope === "series" && parts > 1 && kind !== "abookproj" && kind !== "m4b" }
/** Mọi con số và lời cảnh báo của hộp cho một cuốn. ctx: {kind, scope, layout, parts, changedOnly, changed: [id], bytes} */
function plan(book, ctx) {
    const chapters = book.chapters || {}
    const missing = chapters.missingAudio || 0
    const ready = Math.max(0, (chapters.completed || 0) - missing)
    const total = chapters.total || 0
    const wholeSeries = isWholeSeries(ctx.scope, ctx.parts, ctx.kind)
    const oneFile = ctx.kind === "abook" && (!wholeSeries || ctx.layout === "single")
    // Dự án chỉ có chữ: `.abook` vẫn xuất được (gói mang chữ các chương); MP3 / M4B thì cần audio.
    const textOnly = ctx.kind === "abook" && !wholeSeries && !ready && total > 0
    const changed = ctx.changed || []
    const selectedCount = ctx.kind === "mp3" && !wholeSeries && ctx.changedOnly && changed.length ? changed.length : ready
    const whole = ctx.kind === "abookproj"
    const countText = whole ? "" : wholeSeries ? ctx.parts + S.s_phan_20f71101 : selectedCount + S.s_chuong_9e6a01dc
    const bytes = ctx.bytes || 0
    const warnings = (whole
        ? [book.running && S.s_du_an_dang_chay_goi_khi_no_da_chay_xong_ho_b4407187]
        : [
            textOnly && S.s_chua_chuong_nao_co_audio_file_abook_chi_ma_322233bb + Studio.formatNumber(total) + S.s_chuong_doc_duoc_chua_nghe_duoc_co_audio_ro_2fc6f16d,
            !wholeSeries && !textOnly && ready < total && Studio.formatNumber(ready) + "/" + Studio.formatNumber(total) + S.s_chuong_co_audio_39747288 + (missing ? " (" + missing + S.s_chuong_mat_file_901e1001 : "") + (ctx.kind === "abook" ? S.s_chon_xuat_mot_phan_de_xuat_khi_thieu_chuon_286cd8c0 : S.s_khong_co_trong_ban_xuat_2fda2fce),
            wholeSeries && (ctx.kind === "abook" ? S.s_file_sach_can_du_chuong_chon_xuat_mot_phan_95692f80 : S.s_phan_nao_chua_co_chuong_xong_se_bi_bo_qua_4d9cf695),
            !wholeSeries && book.running && (ctx.kind === "abook" ? S.s_sach_dang_chay_file_sach_can_du_chuong_hoa_d628b896 : S.s_sach_dang_chay_ban_xuat_chi_gom_cac_chuong_8941cd4a),
            !wholeSeries && redoExportNote(chapters.redo || 0, ctx.kind === "abook"),
            oneFile && bytes > FAT32_LIMIT && S.s_file_nay_se_lon_hon_4_gb_the_nho_hay_usb_d_3b80695c + (wholeSeries ? S.s_chon_moi_phan_mot_file_neu_dinh_chep_vao_d_812841f9 : "")
        ]).filter(Boolean)
    return {
        missing: missing, ready: ready, total: total, wholeSeries: wholeSeries, oneFile: oneFile, textOnly: textOnly, selectedCount: selectedCount, countText: countText,
        whole: whole, warnings: warnings,
        description: wholeSeries ? S.s_cac_chuong_nghe_duoc_cua_ca_ac3a8b52 + ctx.parts + S.s_phan_se_vao_ban_xuat_e4279c20 : Studio.formatNumber(selectedCount) + S.s_chuong_se_vao_ban_xuat_6c4d6c7e,
        // Gói dự án chờ sách chạy xong; còn lại cần chương có audio (hoặc bản chỉ chữ / cả bộ)
        blocked: whole ? Boolean(book.running) : (!wholeSeries && !ready && !textOnly)
    }
}
/** Bản xuất đã cũ (export-history): những lần xuất mà chương đã đổi sau đó; và các chương MP3 đã đổi. */
function staleOf(history) { return (history || []).filter(function(item) { return item.changed && item.changed.length > 0 }) }
function changedChapters(stale) {
    const out = []
    for (const item of stale) if (item.kind === "mp3") for (const id of item.changed) if (out.indexOf(id) < 0) out.push(id)
    return out
}
function staleAction(item) { return item.kind === "m4b" ? S.s_xuat_lai_m4b_07ad2a50 : item.kind === "mp3" ? S.s_xuat_chuong_doi_7eb1033d : S.s_xuat_file_sach_02b848a2 }
/** Ô "Kèm nhạc nền": theo công tắc Nhạc nền của cuốn cho tới khi người dùng tự tích / bỏ tích; cuốn không có kế hoạch nhạc: luôn tắt. */
function musicChecked(state, chosen, bookId) {
    if (!state || !state.available) return false
    return chosen && chosen.bookId === bookId ? chosen.on : Boolean(state.enabled)
}
function ffmpegPercent(status) { return status.total > 0 ? Math.min(100, Math.round(100 * status.done / status.total)) : 0 }

// ---- kết quả ----
/** Xong: {title, detail, folder, note}; `kind`: "abook" | "abookproj". Studio từ xa: máy chủ chỉ trả TÊN file / thư mục - nói file nằm ở máy tính nào. */
function finishedOf(kind, result, opts) {
    const lost = result.missingSources ? result.missingSources.length : 0
    const skippedNote = result.skipped && result.skipped.length ? S.s_chua_co_chuong_nao_nen_bo_qua_09add84f + result.skipped.map(function(part) { return S.s_phan_a17569d5 + part.part }).join(", ") : ""
    const skipped = skippedNote ? "\u00a0·\u00a0" + skippedNote : ""
    const lostNote = lost ? lost + S.s_file_nguon_chuong_da_bi_doi_hay_xoa_nen_kh_7f896e29 : ""
    // `file` chỉ có khi cả bộ (hay một phần) nằm trong MỘT file; cả bộ mỗi phần một file thì có `parts` mà không có `file`.
    const single = typeof result.file === "string"
    const title = result.parts
        ? (single ? S.s_da_xuat_ca_bo_88641f8a + result.parts.length + S.s_phan_trong_mot_file_sach_226c22b8 : S.s_da_xuat_11ce3b72 + result.parts.length + S.s_file_sach_679b88e4)
        : kind === "abook" ? S.s_da_xuat_file_sach_242afa05 : S.s_da_goi_du_an_9908b445
    const perPart = Boolean(result.parts && kind === "abook" && !single)
    const size = Size.formatSize(result.size || 0)
    const placeText = perPart ? result.folder + S.s_u00a0_u00a0moi_phan_mot_file_abook_rieng_b2aec5df : single ? result.file + "\u00a0·\u00a0" + size : result.folder
    const detail = (opts.remote
        ? exportedOnComputer(opts.computer, perPart ? "" : single ? fileName(result.file) : fileName(result.folder || ""),
                             [perPart ? S.s_moi_phan_mot_file_abook_rieng_e768e635 : "", single ? size : ""].filter(Boolean).join("\u00a0·\u00a0"))
        : placeText) + skipped + (lostNote ? "\u00a0·\u00a0" + lostNote : "") + (result.coverage ? "\u00a0·\u00a0" + result.coverage : "")
    return {title: title, detail: detail, folder: result.folder || "", note: [skippedNote, lostNote, result.coverage].filter(Boolean).join("\u00a0·\u00a0"), remoteTitle: exportedOnComputer(opts.computer, "")}
}

// ---- việc nền (MP3, M4B): bookFileExport.ts jobView ----
var MP3_COPY = {busy: S.s_dang_xuat_mp3_99b61b74, done: S.s_da_xuat_mp3_c93fc100, failed: S.s_chua_xuat_duoc_mp3_1550e65a, stopped: S.s_da_dung_xuat_ab8ac9d1, stoppedNote: S.s_cac_chuong_da_ghi_do_duoc_xoa_55c0187f,
                stopping: S.s_dung_ngay_sau_buoc_dang_lam_thu_muc_mp3_do_47cdbf95}
var M4B_COPY = {busy: S.s_dang_lam_file_m4b_4a95b4ac, done: S.s_da_xuat_m4b_76947b3a, failed: S.s_chua_xuat_duoc_m4b_5a39de4c, stopped: S.s_da_dung_xuat_ab8ac9d1, stoppedNote: S.s_chua_co_file_m4b_nao_duoc_ghi_341f690c,
                stopping: S.s_dung_ngay_sau_buoc_dang_lam_khong_ghi_file_52bd285a}
function copyOf(kind) { return kind === "m4b" ? M4B_COPY : MP3_COPY }

function packingText(chapters, elapsed) { return chapters + S.s_chuong_u00a0_u00a0da_1d092915 + Studio.formatClock(elapsed) }
/** Việc tự báo tiến độ: chữ + phần trăm 0-1; không báo thì null. */
function reportedProgress(job) {
    if (job.phase === "music-fetch" && job.total) {
        const done = job.done || 0
        return {fraction: done / job.total, text: S.s_dang_tai_nhac_nen_1c775caa + Math.min(done + 1, job.total) + "/" + job.total + S.s_bai_43a258fa}
    }
    if (job.phase === "peaks") return {fraction: 1, text: S.s_dang_kiem_dinh_am_fddf3cc5}
    const again = job.peakOver ? S.s_ma_hoa_lai_vi_05c99ac8 + job.peakOver + S.s_chuong_vuot_dinh_luot_28b6d6b9 + (job.peakRound || 1) + ")" : ""
    if (job.phase === "reencode") return {fraction: 1, text: again}
    if (job.chapter === undefined || !job.chapters) return null
    const where = S.s_chuong_aad5968e + job.chapter + "/" + job.chapters
    if (job.phase === "encode") return {fraction: 1, text: again ? again + "\u00a0·\u00a0" + where : S.s_dang_ghep_file_am_thanh_u00a0_u00a0_b7dd79db + where}
    if (job.phase === "chapters") return {fraction: (job.chapter - 1) / job.chapters, text: S.s_dang_ghi_chuong_0f8f1baa + job.chapter + "/" + job.chapters}
    if (job.phase === "music") {
        const text = S.s_dang_tron_nhac_chuong_7df81aba + job.chapter + "/" + job.chapters
        return {fraction: job.percent !== undefined ? job.percent / 100 : (job.chapter - 1) / job.chapters, text: again ? again + "\u00a0·\u00a0" + text : text}
    }
    const parts = [where, (job.percent || 0) + "%"]
    if (job.waiting === "listening") parts.push(S.s_nhuong_cho_chuong_dang_nghe_93babd54)
    else if (job.waiting === "network") parts.push(S.s_dang_cho_mang_4e41560e)
    else if (job.secondsLeft !== undefined && job.secondsLeft !== null) parts.push(S.s_con_c697bae9 + spokenDuration(job.secondsLeft))
    return {fraction: (job.percent || 0) / 100, text: parts.join("\u00a0·\u00a0")}
}
function missingChaptersNote(result) {
    if (result.chapters === undefined || result.chaptersTotal === undefined || result.chapters >= result.chaptersTotal) return ""
    return result.chapters + "/" + result.chaptersTotal + S.s_chuong_chuong_chua_xong_khong_co_trong_fil_6761474b
}
function musicMissingNote(result) { return result.musicMissing ? result.musicMissing + S.s_doan_thieu_nhac_vi_chua_tai_duoc_bai_b1268efd : "" }
function skippedPartsNote(result) {
    return result.skipped && result.skipped.length ? S.s_chua_co_chuong_nao_nen_bo_qua_09add84f + result.skipped.map(function(part) { return S.s_phan_a17569d5 + part.part }).join(", ") : ""
}
/** Thông báo cho trạng thái hiện có của một việc nền MP3 / M4B: {kind: none|loading|success|error|info, title, description, note, progress}. */
function jobView(job, chapters, copy) {
    if (job.state === "running") {
        const elapsed = job.elapsed || 0
        const reported = reportedProgress(job)
        if (reported) return {kind: "loading", title: copy.busy, description: reported.text, progress: reported.fraction}
        return {kind: "loading", title: copy.busy, description: chapters ? packingText(chapters, elapsed) : S.s_da_8c3d7ec0 + Studio.formatClock(elapsed)}
    }
    if (job.state === "cancelled") return copy.stopped ? {kind: "info", title: copy.stopped, description: copy.stoppedNote || ""} : {kind: "none"}
    if (job.state === "done" && job.result) {
        const file = job.result.file, folder = job.result.folder
        const count = job.result.files !== undefined ? job.result.files : (job.result.parts ? job.result.parts.length : undefined)
        const partsNote = !file && job.result.files !== undefined && job.result.parts ? job.result.parts.length + S.s_phan_20f71101 : ""
        const skipped = skippedPartsNote(job.result)
        const lacks = [missingChaptersNote(job.result), musicMissingNote(job.result), job.result.coverBroken ? S.s_anh_bia_cua_sach_bi_hong_nen_dung_bia_ve_t_782534c3 : ""].filter(Boolean)
        const details = [partsNote, !file && count ? count + " file" : "", skipped, job.result.size ? Size.formatSize(job.result.size) : ""].concat(lacks).filter(Boolean)
        const place = file || folder || ""
        const view = {kind: "success", title: copy.done, description: [fileName(place)].concat(details).filter(Boolean).join("\u00a0·\u00a0"), place: place, folder: folder || ""}
        if (skipped || lacks.length) view.note = [skipped].concat(lacks).filter(Boolean).join("\u00a0·\u00a0")
        return view
    }
    if (job.state === "error") return {kind: "error", title: copy.failed, description: job.error || ""}
    return {kind: "none"}
}

// ---- WordTimings.tsx ----
/** Dòng dưới "Chữ sáng": đang làm bao nhiêu %, đã xong chưa, đã có bao nhiêu câu. */
function wordTimingsNote(data) {
    const lines = data && data.lines || 0, aligned = data && data.words || 0
    const finished = Boolean(data && data.state === "done" && data.file)
    let note = S.s_them_chu_sang_theo_giong_doc_chay_nen_vai_161ec74e
    if (data && data.state === "running") note = S.s_dang_them_chu_sang_0_7874b215(data.total ? Math.round(((data.done || 0) / data.total) * 100) : 0)
    else if (data && data.state === "error") note = data.error || S.s_chua_them_duoc_chu_sang_a019d5cb
    else if (finished) note = S.s_xong_file_sach_cua_du_an_da_duoc_lam_lai_k_a150d813
    else if (lines > 0) note = Studio.formatNumber(aligned) + "/" + Studio.formatNumber(lines) + S.s_cau_da_co_chu_sang_theo_giong_doc_b229c30a
    return note
}
/** Nút "Thêm chữ sáng" tắt khi sách đang chạy hay mọi câu đã có chữ sáng. */
function wordTimingsDisabled(data, running) {
    const lines = data && data.lines || 0, aligned = data && data.words || 0
    const finished = Boolean(data && data.state === "done" && data.file)
    return Boolean(running) || (lines > 0 && aligned === lines && !finished)
}

// ---- ApplyChanges.tsx ----
/** Nút bỏ một dòng nói rõ nó bỏ gì ("Bỏ cách đọc “Lucien”"): mọi nút cùng nhãn thì trình đọc màn hình không phân biệt được dòng nào. */
function dropLabel(item) {
    if (item.kind === "pronunciation") {
        const surface = /^“([^”]+)”/.exec(item.label || "")
        if (surface) return S.s_bo_cach_doc_18836ac6 + surface[1] + "”"
    }
    const verbs = {pronunciation: S.s_bo_cach_doc_98ceb6ae, speaker: S.s_bo_doi_nguoi_noi_4787bbf3, line: S.s_bo_sua_cach_doc_cau_2b4e183f, voice: S.s_bo_doi_giong_d165cd63, retake: S.s_bo_thu_lai_ed903b0f}
    return (verbs[item.kind] || S.s_bo_e07d3f4d) + ": " + item.label
}
function pendingKey(item) { return item.section + ":" + item.key }
function pendingLines(item) { return item.lines ? Studio.formatNumber(item.lines) + S.s_cau_thu_lai_65b7ea54 : S.s_chua_thu_khong_ton_gi_d0da00cf }
/** Hộp "Áp dụng": đang chạy (`running` "busy" | "checkpoint") thì máy tự áp ở ranh giới chương kế nên không có nút "Áp dụng". */
function applyHeading(count, running) { return running ? count + S.s_thay_doi_dang_cho_ap_9ec08d2e : S.s_ap_dung_0_thay_doi_b7955e0a(count) }
function applyDescription(running) {
    return running ? S.s_tu_ap_o_chuong_ke_tiep_chi_bo_duoc_viec_ch_6f3e60e9
                   : S.s_may_chi_thu_lai_nhung_cau_bi_anh_huong_roi_67af5454
}
function applyClose(running) { return running ? S.s_dong_5d54c2a1 : S.s_de_sau_9be0a7ab }
function shownChapters(chapters) { return chapters.slice(0, 4).join(", ") + (chapters.length > 4 ? S.s_va_231e8fb6 + (chapters.length - 4) + S.s_chuong_khac_c77ef8b9 : "") }
/** Dòng cuối hộp "Áp dụng": thu lại bao nhiêu câu ở chương nào, mất bao lâu (data = /pending-changes). */
function applySummary(data) {
    if (!data.lines) return S.s_chi_ghi_thay_doi_khong_thu_lai_cau_nao_ad9ef853
    return S.s_thu_lai_bceb80c2 + Studio.formatNumber(data.lines) + S.s_cau_o_b6fbfb19 + data.chapters.length + S.s_chuong_1c106b8b + shownChapters(data.chapters) + ")"
        + (data.seconds > 0 ? " - " + Cast.estimateText(data.seconds, data.measured) : "") + "."
}

// ---- việc xuất nền: đường, nhịp hỏi, lời ----
var JOB_SEGMENT = {mp3: "mp3-job", m4b: "m4b-job", abook: "bookfile-job", abookproj: "projectfile-job"}
/** Đường của việc nền theo kiểu xuất của hộp (khớp `url` / `cancel` của ExportBookFileJob.tsx). */
function jobPath(kind, bookId) { return "/api/books/" + bookId + "/" + JOB_SEGMENT[kind] }
/** Kiểu của hộp theo khoá `/api/export-jobs` (bookfile -> abook, projectfile -> abookproj). */
function kindOfJob(name) { return {mp3: "mp3", m4b: "m4b", bookfile: "abook", projectfile: "abookproj"}[name] || "" }
/** Mã các kiểu đang chạy của một cuốn trong trả lời của GET /api/export-jobs: kiểu của hộp đầu tiên đang chạy, hay "". */
function runningKind(all, bookId) {
    for (const name of ["projectfile", "bookfile", "mp3", "m4b"]) {
        const hit = (all && all[name] || []).filter(function(job) { return job.bookId === bookId && job.state === "running" })
        if (hit.length) return kindOfJob(name)
    }
    return ""
}
/** Thân yêu cầu bắt đầu: MP3 / M4B mang `music`, `series`, `chapterIds`; `.abook` mang `series` và `single`; dự án chỉ cần `target`. */
function startBody(kind, ctx) {
    const body = {target: ctx.target || ""}
    if (kind === "mp3" || kind === "m4b") {
        if (ctx.mixes) body.music = true
        if (kind === "mp3" && ctx.wholeSeries) body.series = true
        if (kind === "mp3" && !ctx.wholeSeries && ctx.changedOnly && ctx.changedIds.length) body.chapterIds = ctx.changedIds
    } else if (kind === "abook") {
        if (ctx.partial) body.partial = true
        body.series = Boolean(ctx.wholeSeries)
        if (ctx.wholeSeries) body.single = ctx.layout === "single"
    }
    return body
}
/** Một nhịp hỏi việc nền: {state: "running"} | {state: "done", result} | {state: "cancelled"} | {state: "error", error}. (followPackJob của projectPacking.ts) */
function followStep(job, failure) {
    if (job.state === "done" && job.result) return {state: "done", result: job.result}
    if (job.state === "cancelled") return {state: "cancelled"}
    if (job.state !== "running") return {state: "error", error: job.error || failure || S.s_chua_goi_duoc_du_an_4eb38947}
    return {state: "running"}
}
/** Lời lúc đang xuất: {title, note, fraction (-1 = chưa có mẫu số)}. ctx: {chapters, countText, downloading: {done, total} hay null, cancelling} */
function busyView(kind, job, ctx) {
    let title = SAVING[kind][1], fraction = -1
    if (kind === "mp3" || kind === "m4b") {
        const view = jobView(job, ctx.chapters, copyOf(kind))
        if (view.kind === "loading") { title = view.description || view.title; if (view.progress !== undefined) fraction = view.progress }
    } else {
        const shown = packView(job, kind === "abook" ? BOOK_FILE_SPAN : PACK_SPAN)
        title = shown.title
        if (shown.fraction !== null) fraction = shown.fraction
    }
    const downloading = ctx.downloading && ctx.downloading.total > 0 ? ctx.downloading : null
    if (downloading) { title = S.s_dang_tai_nhac_nen_a3480994 + downloading.done + "/" + downloading.total + ")"; fraction = -1 }
    if (ctx.cancelling) title = S.s_dang_huy_c25a0214
    const lead = downloading ? S.s_tai_nhac_con_thieu_d1ac2c2f : ctx.countText ? ctx.countText + "; " : ""
    return {title: title, note: lead + S.s_dong_hop_van_xuat_nen_va_bao_khi_xong_604904f6, fraction: fraction}
}
/** Bản xuất xong: {title, detail, folder, note} - `.abook` / dự án theo finishedOf, MP3 / M4B theo jobView. */
function finishedFor(kind, result, opts) {
    if (kind === "abook" || kind === "abookproj") return finishedOf(kind, result, opts)
    const view = jobView({state: "done", result: result}, opts.chapters || 0, copyOf(kind))
    return {title: opts.remote ? exportedOnComputer(opts.computer, "") : view.title, detail: view.description, folder: view.folder || "", note: view.note || ""}
}
/** Việc hỏng: {title, description}; dự án qua packError (câu cho người nghe + nguyên văn sau một dòng trống). */
function failureOf(kind, raw) {
    if (kind === "abookproj") {
        const shown = packError(raw)
        return {title: SAVING[kind][2], description: shown.detail ? shown.summary + "\n" + shown.detail : shown.summary}
    }
    return {title: SAVING[kind][2], description: String(raw)}
}
/** Sách đang chạy: "checkpoint" (đã tạm dừng ở checkpoint), "busy" (đang làm) hay "" (đứng yên). Như `running=` của ApplyChangesDialog ở ProjectScreen.tsx. */
function applyRunning(book) {
    if (!book || !book.running) return ""
    return book.paused && book.status === "paused" ? "checkpoint" : "busy"
}
