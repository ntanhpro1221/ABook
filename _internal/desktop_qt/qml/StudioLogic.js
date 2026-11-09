.import "UiStrings.js" as S
.pragma library
.import "LibraryLogic.js" as LibraryLogic
.import "PeerStudio.js" as Peer

// Phần thuần của Studio (danh sách dự án + trang dự án): chữ và quy tắc chép nguyên từ ui/src/studio (data.ts, stopText.ts, errorText.ts, polling.ts,
// projectGroups.ts, ProjectScreen.tsx, ProjectsScreen.tsx) và ui/src/shared/format.ts, để hai nền tảng nói cùng một câu.

// ---- shared/format.ts ----
function formatNumber(value) {
    const whole = String(Math.round(value))
    return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".")
}
function formatPercent(fraction) {
    const value = Math.max(0, Math.min(1, fraction)) * 100
    if (value > 0 && value < 1) return "<1%"
    if (value < 100 && value > 99) return "99%"
    return Math.floor(value) + "%"
}
function formatLength(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return S.s_0_phut_66a3b36a
    const minutes = Math.round(seconds / 60)
    if (minutes < 1) return S.s_duoi_1_phut_a1dd4f60
    const hours = Math.floor(minutes / 60)
    const rest = minutes % 60
    if (!hours) return minutes + S.s_phut_cf728a6a
    return rest ? hours + S.s_gio_fbaccc8e + rest + S.s_phut_cf728a6a : hours + S.s_gio_9e4dcadb
}
function formatEta(seconds, fraction) {
    if (seconds < 90) return fraction === undefined || fraction >= 0.85 ? S.s_sap_xong_7d5cfa0f : S.s_con_duoi_2_phut_41c172a6
    return S.s_con_khoang_f88c6a5c + formatLength(seconds)
}
// Thời gian còn lại của một cuốn đang chạy theo bước máy đang ước, hay null khi chưa có tốc độ. `short`: gọn cho cột hẹp của bảng.
function etaOf(book, short) {
    if (!book.eta) return null
    function say(step, left) { return short ? step + " " + left.replace(/^còn khoảng /, S.s_con_c697bae9) : "pha " + step + " " + left }
    if (book.eta.phase === "speaker") {
        const pass = book.speakerPass
        return say(short ? S.s_do_nguoi_noi_1365941c : S.s_xac_dinh_nguoi_noi_a6f340f9, formatEta(book.eta.seconds, pass && pass.total ? pass.done / pass.total : undefined))
    }
    const synthesis = book.eta.phase === "synthesis"
    const left = formatEta(book.eta.seconds, synthesis ? book.progress.synthesis : book.progress.analysis)
    return say(synthesis ? S.s_thu_am_1382b7bf : S.s_phan_tich_70311eb1, left)
}
function formatDate(epochSeconds) {
    const date = new Date(epochSeconds * 1000)
    return date.getDate() + "/" + (date.getMonth() + 1) + "/" + date.getFullYear()
}
function two(value) { return value < 10 ? "0" + value : String(value) }
function formatTime(epochSeconds, nowMs) {
    const date = new Date(epochSeconds * 1000)
    const today = new Date(nowMs === undefined ? Date.now() : nowMs)
    const time = two(date.getHours()) + ":" + two(date.getMinutes())
    return date.toDateString() === today.toDateString() ? time : time + "\u00a0·\u00a0" + date.getDate() + "/" + (date.getMonth() + 1)
}
function formatRelative(epochSeconds, nowMs) {
    if (!epochSeconds) return ""
    const delta = (nowMs === undefined ? Date.now() : nowMs) / 1000 - epochSeconds
    if (delta < 60) return S.s_vua_xong_b46f7a2b
    if (delta < 3600) return Math.floor(delta / 60) + S.s_phut_truoc_d6b7b9dc
    if (delta < 86400) return Math.floor(delta / 3600) + S.s_gio_truoc_44858c63
    const days = Math.floor(delta / 86400)
    if (days === 1) return S.s_hom_qua_20142adc
    if (days < 7) return days + S.s_ngay_truoc_24f1e46c
    return formatDate(epochSeconds)
}
// Mốc thời gian nói kiểu người: "hôm nay 14:02", "tối qua 23:41", "hôm qua 09:15", "3 ngày trước" (formatWhen của shared/format.ts)
function formatWhen(epochSeconds, nowMs) {
    if (!epochSeconds) return ""
    const date = new Date(epochSeconds * 1000)
    const now = nowMs === undefined ? Date.now() : nowMs
    const today = new Date(now)
    const days = Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() - new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) / 86400000)
    const time = two(date.getHours()) + ":" + two(date.getMinutes())
    if (days <= 0) return now / 1000 - epochSeconds < 60 ? S.s_vua_xong_b46f7a2b : S.s_hom_nay_bccb739b + time
    if (days === 1) return date.getHours() >= 18 ? S.s_toi_qua_aa87cbc4 + time : S.s_hom_qua_48c4bf51 + time
    if (days < 7) return days + S.s_ngay_truoc_24f1e46c
    return formatDate(epochSeconds)
}
// Cách đọc để HIỆN: chữ đầu mỗi từ viết hoa ("rên-ta-rô" -> "Rên-ta-rô"); dữ liệu giữ nguyên cách đọc đã lưu (shownReading của shared/format.ts)
function shownReading(spoken) {
    return String(spoken).replace(/(^|\s)(\S)/g, function(match, gap, letter) {
        return letter.toLowerCase() === letter && letter.toUpperCase() !== letter ? gap + letter.toUpperCase() : match
    })
}

// ---- data.ts: trạng thái ----
function phaseTone(phase, running) {
    if (phase === "done") return "success"
    if (phase === "error") return "danger"
    if (running) return "accent"
    if (phase === "analysis" || phase === "casting" || phase === "synthesis" || phase === "stopped") return "warning"
    return "muted"
}
function queueLabel(position) { return position <= 1 ? S.s_sap_toi_luot_4fcc9331 : S.s_con_71d0e2b2 + (position - 1) + S.s_viec_truoc_af0a3410 }
// Nhãn + màu + "đang chạy" của trạng thái một dự án: MỘT nơi cho đầu trang dự án và bảng dự án.
function projectStatus(book) {
    const running = Boolean(book.running || book.starting)
    return {
        label: book.queuePosition ? queueLabel(book.queuePosition) : book.starting ? S.s_dang_khoi_dong_e7a9b0e5 : book.precast && book.precast.held ? S.s_cho_ban_duyet_dd9175be : book.statusLabel || "",
        tone: book.queuePosition || book.paused || book.stopping ? "warning" : phaseTone(book.phase, running),
        live: running && !book.paused && !book.stopping
    }
}
function isLive(book) { return Boolean(book.running || book.starting) }

// ---- polling.ts ----
var BACKOFF_CAP_MS = 120000
// Nhịp hỏi kế tiếp (ms), hay 0 = thôi hỏi: 404 / chỉ-nghe dừng hẳn; lỗi khác gấp đôi theo số lần lỗi liên tiếp tới trần.
function pollDelay(base, errorStatus, errorCount) {
    if (errorStatus === 404 || errorStatus === "listenOnly") return 0
    if (!errorCount || base === 0) return base
    return Math.min(base * Math.pow(2, Math.min(errorCount, 8)), BACKOFF_CAP_MS)
}
var LIVE_MS = 2000
var IDLE_MS = 15000
function libraryInterval(books) { return (books || []).some(isLive) ? 5000 : IDLE_MS }
function bookInterval(book) { return book && isLive(book) ? LIVE_MS * 1.5 : IDLE_MS }
function failureText(status, message) {
    if (status === 0) return S.s_mat_ket_noi_toi_abook_1d2b48ae
    return message || S.s_sach_co_the_da_bi_chuyen_hoac_xoa_e69fbf8d
}
// Trang dự án khi lần hỏi gần nhất hỏng: sách đã mất -> "gone"; đã có bản cũ -> "stale"; chưa từng có -> "error"; không lỗi -> "".
function bookFailure(hasData, errorStatus) {
    if (errorStatus === 404) return "gone"
    if (hasData && errorStatus !== null && errorStatus !== undefined) return "stale"
    if (!hasData) return "error"
    return ""
}

// ---- projectGroups.ts: gom phần của một cuốn, đưa nhóm đang chạy lên đầu ----
function unitOfGroup(group) {
    if (group.key.indexOf("chain:") === 0) return S.s_phan_87a88dd0
    for (const book of group.books) {
        const match = String(book.title).match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b/i)
        if (match) { const word = match[2].toLowerCase(); return word === S.s_quyen_99cc1029 || word === S.s_phan_87a88dd0 ? word : S.s_tap_f6dd4977 }
    }
    return S.s_tap_f6dd4977
}
function groupParts(books) {
    const groups = LibraryLogic.sections(books.map(function(b) { return Object.assign({}, b, {bookId: b.id}) }))
    return groups.map(function(group) {
        if (group.books.length < 2 || group.key.indexOf("book:") === 0) return {kind: "book", book: group.books[0]}
        return {kind: "series", name: group.title, unit: unitOfGroup(group), books: group.books}
    })
}
function entryBooks(entry) { return entry.kind === "book" ? [entry.book] : entry.books }
function splitLive(entries) {
    const live = entries.filter(function(entry) { return entryBooks(entry).some(isLive) })
    return {live: live, rest: entries.filter(function(entry) { return live.indexOf(entry) < 0 })}
}
// Hàng phẳng của bảng: dòng tên nhóm (cuốn nhiều phần) rồi các phần của nó, hay một dự án lẻ. `key` ổn định cho mô hình cập nhật tại chỗ.
function tableRows(books) {
    const split = splitLive(groupParts(books))
    const rows = []
    for (const entry of split.live.concat(split.rest)) {
        if (entry.kind === "book") rows.push({key: "book:" + entry.book.id, kind: "book", id: entry.book.id, book: entry.book, grouped: false})
        else {
            rows.push({key: "series:" + entry.name, kind: "group", name: entry.name, unit: entry.unit, count: entry.books.length,
                       label: entry.name + "\u00a0·\u00a0" + entry.books.length + " " + entry.unit})
            for (const book of entry.books) rows.push({key: "book:" + book.id, kind: "book", id: book.id, book: book, grouped: true})
        }
    }
    return rows
}

// Cột của bảng (COLUMNS của ProjectsScreen.tsx): `width` là bề ngang cả hàng, đã gồm đệm 12 hai bên. Khổ "wide": 40 · tên · 230 · 190 · 100;
// "mid": 40 · tên · 190 · 170 · 36 (chỗ "…"); "stacked": 40 · tên · 36, trạng thái và tiến độ xếp dưới tên.
function tableColumns(width, kind) {
    const pad = 12, gap = 16, inner = width - 2 * pad
    const wide = kind === "wide", stacked = kind === "stacked"
    const statusW = wide ? 230 : 190, progressW = wide ? 190 : 170, updatedW = wide ? 100 : 0, moreW = 36
    const nameX = pad + 40 + gap
    const nameW = Math.max(80, stacked ? inner - 40 - gap - moreW - 4
                                        : inner - 40 - statusW - progressW - (wide ? updatedW : moreW) - 4 * gap)
    const statusX = nameX + nameW + gap
    const progressX = statusX + statusW + gap
    return {nameX: nameX, nameW: nameW, statusX: statusX, statusW: statusW, progressX: progressX, progressW: progressW,
            updatedX: progressX + progressW + gap, updatedW: updatedW}
}
// Khổ của bảng theo bề ngang của khung chữ (màn hẹp: trạng thái và tiến độ dưới tên)
function tableKind(bodyWidth) { return bodyWidth >= 1000 ? "wide" : bodyWidth >= 700 ? "mid" : "stacked" }

// ---- ProjectsScreen.tsx: nội dung một hàng ----
function rowSubtitle(book) {
    const settings = book.settings || {}
    return [settings.narrator && S.s_giong_ke_255bd6e6 + settings.narrator, settings.profile !== "balanced" && settings.profileLabel].filter(Boolean).join("\u00a0·\u00a0")
}
function rowDetail(book) {
    if (!book.chapters) return ""
    const live = isLive(book)
    return book.phase !== "done" && book.eta && live ? etaOf(book, true) : book.chapters.completed + "/" + book.chapters.total + S.s_chuong_9e6a01dc
}
function rowNeeds(book) {
    if (!book.chapters) return []
    return [
        book.pendingChanges ? book.pendingChanges + S.s_thay_doi_cho_ap_e4e2c5a3 : book.phase === "done" && book.chapters.redo ? book.chapters.redo + S.s_chuong_cho_thu_lai_6920aaee : "",
        book.chapters.missingAudio ? book.chapters.missingAudio + S.s_chuong_mat_audio_a079e8e7 : ""
    ].filter(Boolean)
}
// Cột trạng thái: xong là mặc định, không đeo nhãn trên mọi hàng; chỉ dự án chưa xong mới có viên trạng thái.
function rowShowsPill(book) { return !(book.phase === "done" && !book.queuePosition) }
function rowUpdated(book) { return isLive(book) ? S.s_vua_xong_b46f7a2b : formatRelative(book.updatedAt) }
function brokenLine(book) { return (book.brokenKind === "busy" ? S.s_chua_mo_duoc_ffa5657d : S.s_chua_doc_duoc_2213ed66) + book.broken }
function projectsSubtitle(count) { return count ? count + S.s_du_an_72561792 : "\u00a0" }

// ---- stopText.ts ----
var ANALYSIS_CUT_COST = S.s_co_the_ra_mot_cuon_khac_nguoi_noi_o_doan_s_4a2e8f6b
var ANALYSIS_STOP_FACT = S.s_phan_da_phan_tich_duoc_giu_nguyen_nhung_la_7b0b4096
function stopAnalysisAdvice(book) {
    if (book.paused) return S.s_sach_dang_tam_dung_dung_yen_dung_cho_phan_7bfd81b4
    if (book.canPause) return S.s_can_nghi_thi_bam_tam_dung_sach_dung_yen_ro_0d5d0ddd
    return ""
}
function pauseNotice(paused, book, onBattery) {
    if (paused) return {
        title: S.s_dang_tam_dung_e40cc1b7,
        description: S.s_sach_dung_lai_sau_phan_dang_lam_do_luc_pha_330de94c,
        warn: false
    }
    if (book.paused) return {
        title: S.s_sach_van_dang_tam_dung_1d8dc8ed,
        description: book.paused === "battery" ? S.s_may_dang_chay_pin_nen_studio_van_giu_sach_13fd5894
                                                : S.s_sach_chua_lam_tiep_duoc_doi_vai_giay_roi_x_129b7133,
        warn: true
    }
    return {
        title: S.s_dang_lam_tiep_013b8524,
        description: onBattery ? S.s_sach_lam_tiep_ngay_tren_pin_cham_va_hao_pi_7d1a8968
                               : S.s_sach_lam_tiep_dung_cho_da_tam_dung_3d848ab8,
        warn: false
    }
}
function queueWaitNotice(waitsOn) {
    return waitsOn.paused === "battery"
        ? "“" + waitsOn.title + S.s_dang_tam_dung_vi_may_chay_pin_nen_cuon_nay_27a2cfc3
        : "“" + waitsOn.title + S.s_dang_tam_dung_nen_cuon_nay_chua_toi_luot_b_80e4ac97
}
// "Tiếp tục" phải hỏi trước: pha phân tích đã bị ngắt giữa chừng (AGENTS.md: dừng giữa pha phân tích là đổi quyển sách).
function asksBeforeResume(book) { return book.phase !== "done" && Boolean(book.analysisInterrupted) }
function stopTitle(book) { return book.phase === "analysis" ? S.s_dung_phan_tich_3fae0cc9 : S.s_dung_thu_am_c0b08972 }
function stopDescription(book) {
    if (book.phase === "analysis") return ""
    return book.paused ? S.s_tam_dung_van_giu_bo_nho_card_do_hoa_dung_h_5c49cc06
                       : S.s_moi_chuong_va_cau_da_xong_duoc_giu_nguyen_295ff27b
}
// Hộp Dừng lúc phân tích: hai đoạn cảnh báo (câu thứ hai nói nên để chạy hết bước này).
function stopWarning(book) {
    if (book.phase !== "analysis") return null
    const eta = etaOf(book)
    const advice = stopAnalysisAdvice(book)
    return {fact: ANALYSIS_STOP_FACT + " - " + ANALYSIS_CUT_COST + ".",
            advice: S.s_nen_de_chay_het_buoc_nay_55b34878 + (eta ? " (" + eta + ")" : "") + ". " + advice}
}
function resumeWarning(book) {
    return {fact: S.s_phan_tich_cua_4a395adb + book.title + S.s_da_dung_giua_chung_df1e44a8, cost: S.s_lam_tiep_tu_cho_ay_c42ae1b1 + ANALYSIS_CUT_COST + S.s_khac_voi_khi_phan_tich_lien_mot_mach_a389d2e0,
            advice: S.s_muon_chac_nhu_chay_lien_mach_lam_lai_phan_856b2309}
}

// ---- errorText.ts ----
var KNOWN_ERRORS = [
    {pattern: /out of memory|CUBLAS_STATUS_ALLOC_FAILED|CUDA error: .*memory|OutOfMemoryError|bad allocation/i,
     summary: S.s_card_do_hoa_het_bo_nho_3d3fdb50,
     hint: S.s_dong_cac_app_khac_dang_dung_card_do_hoa_tr_12ee0258},
    {pattern: /disk free (\d+(?:[.,]\d+)?) GB/i,
     summary: function(match) { return S.s_o_dia_chua_thu_vien_sach_chi_con_29f74a91 + match[1].replace(",", ".") + " GB." },
     hint: S.s_giai_phong_them_dung_luong_o_o_do_lam_sach_0ae5c6e8},
    {pattern: /model .* không sẵn sàng/i,
     summary: S.s_chua_dung_duoc_model_phan_tich_truyen_olla_8c2ead55,
     hint: S.s_bam_tiep_tuc_de_thu_lai_neu_van_loi_mo_oll_2d24bc66,
     studioHint: S.s_studio_tu_bat_ollama_rieng_cua_no_bam_tiep_cffd211a},
    {pattern: /ollama|11434|actively refused|Connection refused|ConnectionError|Max retries exceeded/i,
     summary: S.s_chua_ket_noi_duoc_ollama_phan_chay_mo_hinh_9408ea80,
     hint: S.s_mo_ollama_bieu_tuong_o_khay_he_thong_roi_b_e00df159,
     studioHint: S.s_studio_tu_bat_ollama_rieng_cua_no_nen_khon_10d2c374},
    {pattern: /No space left|ENOSPC|disk full|database or disk is full|WinError 112|not enough space|disk quota/i,
     summary: S.s_o_dia_het_cho_trong_3b736e41,
     hint: S.s_giai_phong_dung_luong_o_o_chua_thu_vien_sa_f1ab2981}
]
// Lỗi thô -> câu cho người nghe + việc nên làm + nguyên văn.
function friendlyError(raw, bundledStudio, redo, studioLostModel) {
    const detail = String(raw).trim()
    if (studioLostModel && /ollama|model|qwen/i.test(detail)) {
        return {summary: S.s_studio_mat_model_phan_tich_truyen_file_da_e8f0b483,
                hint: redo ? S.s_vao_du_an_bam_sua_studio_de_tai_lai_dung_p_a4f2e4e5
                           : S.s_vao_du_an_bam_sua_studio_de_tai_lai_dung_p_68884ea1, detail: detail}
    }
    function advice(hint) { return redo ? hint.replace(/([Bb])ấm Tiếp tục/g, S.s_1am_lam_lai_phan_tich_tu_dau_af1d00bc) : hint }
    for (const known of KNOWN_ERRORS) {
        const match = detail.match(known.pattern)
        if (match) return {summary: typeof known.summary === "function" ? known.summary(match) : known.summary,
                           hint: advice((bundledStudio && known.studioHint) || known.hint), detail: detail}
    }
    return {summary: S.s_co_loi_khi_lam_sach_469057f5, hint: advice(S.s_bam_tiep_tuc_de_thu_lai_neu_van_loi_mo_chi_c47f6ecc), detail: detail}
}
// RunEnd: lượt chạy gần nhất chết vì sự cố mà sổ không có lỗi nào để hiện
function runEndText(end, bundledStudio, redo, lostModel) {
    const detail = [end.detail, end.exitCode ? S.s_ma_thoat_ffd8844b + end.exitCode : ""].filter(Boolean).join(" - ")
    const shown = friendlyError(detail, bundledStudio, redo, lostModel)
    const summary = end.state === "lost" ? S.s_lan_chay_truoc_bi_ngat_dot_ngot_tien_trinh_48f760d3
        : shown.summary === S.s_co_loi_khi_lam_sach_469057f5 ? S.s_lan_chay_truoc_dung_vi_su_co_edbb6146 : shown.summary
    return {summary: summary, hint: shown.hint, detail: shown.detail}
}

// ---- ProjectScreen.tsx: nút chính ----
// MỘT nút chính theo trạng thái (DESIGN.md mục 7); null = lúc ấy không có việc gì để bấm. Mọi việc khác vào "…".
function primaryKind(book) {
    const listen = book.chapters.completed > 0 ? "listen" : null
    const redoWaiting = book.phase === "done" ? (book.chapters.redo || 0) : 0
    if (book.queuePosition) return listen
    if (book.starting) return "starting"
    if (book.running) {
        if (book.stopping) return "stopping"
        if (book.paused) return "unpause"
        return book.canPause ? "pause" : listen
    }
    if (book.phase === "idle") return "start"
    if (book.precast && book.precast.held && book.phase !== "done") return "record"
    if (asksBeforeResume(book)) return "reanalyze"
    if (book.phase !== "done") return "continue"
    if (book.pendingChanges) return "apply"
    if (redoWaiting > 0) return "continue"
    return "listen"
}
// Nhãn + biểu tượng + trạng thái bận của nút chính; `busy`: lệnh đang chạy ({pause, start}).
function primaryButton(book, busy) {
    const kind = primaryKind(book)
    if (!kind) return null
    busy = busy || {}
    const held = Boolean(book.precast && book.precast.held)
    const table = {
        starting: {label: S.s_dang_khoi_dong_e7a9b0e5, busy: true},
        stopping: {label: S.s_dang_dung_2fb8aa7c, busy: true},
        unpause: {label: held ? S.s_thu_am_db588c2e : S.s_tiep_tuc_87a7ae88, icon: held ? "mic-vocal" : "play", busy: Boolean(busy.pause)},
        pause: {label: S.s_tam_dung_67635815, icon: "pause", busy: Boolean(busy.pause)},
        start: {label: S.s_bat_dau_b3cacc46, icon: "wand-sparkles", busy: Boolean(busy.start)},
        record: {label: S.s_thu_am_db588c2e, icon: "mic-vocal", busy: Boolean(busy.start)},
        reanalyze: {label: S.s_phan_tich_lai_745c8437, icon: "rotate-ccw", busy: false},
        "continue": {label: S.s_tiep_tuc_87a7ae88, icon: "play", busy: Boolean(busy.start)},
        apply: {label: S.s_ap_dung_a5a429fc + (book.pendingChanges || 0) + S.s_thay_doi_28c1bfb5, icon: "refresh-cw", busy: Boolean(busy.start)},
        listen: {label: S.s_nghe_trong_thu_vien_c0d6771a, icon: "headphones", busy: false}
    }
    return Object.assign({kind: kind, enabled: kind !== "starting" && kind !== "stopping"}, table[kind])
}
// Các dòng nói thêm dưới hàng nút (hàng chờ, đang dừng, phân tích bị ngắt, chương chờ thu lại, tạm dừng vì pin).
function actionNotes(book, remote) {
    const kind = primaryKind(book)
    const live = Boolean(book.running)
    const notes = []
    const redoWaiting = book.phase === "done" ? (book.chapters.redo || 0) : 0
    const pending = book.segments.pending !== undefined && book.segments.pending !== null ? book.segments.pending : book.segments.total - book.segments.analyzed
    if (book.queuePosition) {
        notes.push(S.s_cho_luot_7ff91550 + book.queuePosition + S.s_tu_chay_khi_cuon_truoc_xong_b1556944 + (book.seedPending ? S.s_giu_giong_va_cach_doc_ten_993d1078 : "") + "."
                   + (book.queueWaitsOn ? " " + queueWaitNotice(book.queueWaitsOn) : ""))
    } else if (live && book.stopping) {
        notes.push(S.s_dung_o_checkpoint_ke_giu_phan_da_xong_co_t_37dd2329)
    } else if (kind === "reanalyze") {
        notes.push(S.s_phan_tich_da_dung_giua_chung_6971e0d3 + (book.segments.total ? S.s_con_fe156350 + formatNumber(pending) + "/" + formatNumber(book.segments.total) + S.s_cau_70a7137f : "")
                   + S.s_phan_tich_lai_de_giu_ket_qua_lien_mach_tie_bdf01f74 + ANALYSIS_CUT_COST + ".")
    } else if (redoWaiting > 0 && kind === "continue") {
        notes.push((redoWaiting === 1 ? S.s_1_chuong_dang_cho_thu_lai_b9da1ca4 : redoWaiting + S.s_chuong_dang_cho_thu_lai_a4fbdb2e) + S.s_theo_sua_cua_ban_ban_cu_van_nghe_duoc_cho_6adf5ab2)
    }
    if (live && book.paused === "battery") notes.push(S.s_studio_tam_dung_cam_sac_de_tiep_tuc_5704e36a)
    return notes
}
// Vì sao tạm dừng khi chạy pin, gập sau "Dùng pin" dưới lời tạm dừng (MoreInfo của Actions trong ProjectScreen.tsx); "" khi không chạy pin
function batteryInfo(book, remote) {
    if (!book.running || book.paused !== "battery") return ""
    return S.s_lam_sach_tren_pin_cham_va_hao_pin_bam_tiep_c6ccaf1c + (remote ? "." : S.s_hoac_doi_o_cai_dat_studio_2fab1ca2)
}

// ---- Tiến độ đầu trang và "Các bước" (HeaderProgress, ProductionPanel, stepStates của ProjectScreen.tsx) ----
// Dòng nói còn bao lâu của cả lượt làm sách (hay vì sao đang đứng); "" khi không có gì để nói. Giữ chờ duyệt (precast.held) cũng là `paused` nhưng là
// đợi người nghe; tạm dừng thường đã nói ở trạng thái đầu trang.
function progressNote(book) {
    const live = book.running || book.starting
    if (book.stopping) return S.s_dang_dung_cd5f369b
    if (book.paused) return book.precast && book.precast.held ? S.s_cho_ban_duyet_roi_bam_thu_am_5f91fe4f : ""
    const eta = etaOf(book)
    return eta !== null ? eta : live ? S.s_dang_uoc_tinh_thoi_gian_b3820c56 : ""
}
// Trạng thái ba bước Phân tích truyện / Phân vai / Thu âm và kiểm tra: done | active | paused | pending
function stepStates(book) {
    const live = (book.running || book.starting) && !book.paused && !book.stopping
    const now = live ? "active" : "paused"
    if (book.phase === "done") return ["done", "done", "done"]
    if (book.phase === "idle") return ["pending", "pending", "pending"]
    if (book.phase === "analysis") return [now, "pending", "pending"]
    if (book.phase === "casting") return ["done", now, "pending"]
    if (book.phase === "synthesis") return ["done", "done", now]
    // Đã dừng / lỗi: suy từ tiến độ
    if (book.progress.analysis < 1) return [now, "pending", "pending"]
    if (book.progress.synthesis <= 0) return ["done", now, "pending"]
    return ["done", "done", now]
}
var STEP_TITLES = [S.s_phan_tich_truyen_36344512, S.s_phan_vai_b490d45b, S.s_thu_am_va_kiem_tra_313021dd]
var STEP_ICONS = ["book-open-text", "users", "mic-vocal"]
// Dòng phụ của "Các bước": bước đang tới - cả khi đang tạm dừng (lý do dừng đã ở trên)
function stepSummary(book) {
    const current = stepStates(book).findIndex(function(state) { return state === "active" || state === "paused" })
    return current >= 0 ? STEP_TITLES[current] : (book.statusLabel || "")
}
function stepDetails(book) {
    const pass = book.speakerPass
    const read = S.s_doc_ca_truyen_de_nhan_ra_loi_thoai_ai_dang_46dad1fa
    return [pass && pass.active ? S.s_xac_dinh_nguoi_noi_tung_cau_670b5bd0 + pass.done + "/" + pass.total + S.s_chuong_1d138181
                                : book.settings && book.settings.analyzer ? read + " " + analyzerLabel(book.settings.analyzer) + "." : read,
            S.s_trao_cho_moi_nhan_vat_mot_giong_rieng_va_k_9788a813,
            S.s_doc_tung_cau_nghe_lai_bang_nhan_dang_giong_a58b69c7]
}
// Nhật ký làm sách không ghi được khi sách vẫn chạy; "" khi không có gì
function logLostLine(book) {
    if (!(book.running || book.starting) || !book.logLost) return ""
    return S.s_sach_van_dang_chay_binh_thuong_nhung_nhat_5dd24dc3 + book.logLost.lines + S.s_dong_da_bo_thuong_do_phan_mem_diet_virus_baf9004e
        + S.s_dong_bo_dam_may_giu_file_hoac_o_dia_gan_da_f67116d7
}
function studioMissingNote(studio, book, remote) {
    if (!studio || (studio.installed && !studio.outdated) || book.running) return ""
    const redoWaiting = book.phase === "done" ? (book.chapters.redo || 0) : 0
    if (!(book.phase !== "done" || Boolean(book.pendingChanges) || redoWaiting > 0)) return ""
    const repair = Boolean(studio.installed && studio.outdated && studio.damaged)
    const update = Boolean(studio.installed && studio.outdated)
    return S.s_may_nay_ee46aadd + (repair ? S.s_can_sua_16c9c3dd : update ? S.s_can_cap_nhat_8d5ac598 : S.s_chua_cai_bd3c52e9) + S.s_studio_nen_chua_lam_tiep_duoc_phan_phan_ti_7dcb6e58
}
function studioMissing(studio) {
    const update = Boolean(studio && studio.installed && studio.outdated)
    const repair = Boolean(update && studio.damaged)
    return {missing: Boolean(studio && (!studio.installed || studio.outdated)), update: update, repair: repair,
            action: repair ? S.s_sua_studio_2f99394d : update ? S.s_cap_nhat_studio_b3acc7e7 : S.s_cai_studio_5fdd3bd9}
}
function startRefusal(missing) {
    return {title: missing.repair ? S.s_can_sua_studio_a65aa0f0 : missing.update ? S.s_can_cap_nhat_studio_0018e420 : S.s_can_cai_studio_1599eed5, description: S.s_phan_tich_va_thu_am_chay_bang_studio_ea5c7b5c}
}

// ---- Menu "…" ----
function separator() { return {sep: true} }
function item(key, icon, text, extra) { return Object.assign({key: key, icon: icon, text: text}, extra || {}) }
// "Làm việc ở máy tính <tên>" (shared/peerStudio.ts onComputerLine)
function onComputerLine(verb, name) { return name && name !== S.s_may_tinh_8eafc226 ? verb + S.s_o_may_tinh_2d10bef7 + name : verb + S.s_o_may_tinh_4ed6fbac }
// Việc ít dùng của đầu trang dự án (đứng trên các mục đổi tên, làm tiếp, xoá).
function actionExtras(book, opts) {
    const kind = primaryKind(book)
    const live = Boolean(book.running)
    const out = []
    if (book.chapters.completed > 0 && kind !== "listen") out.push(item("listen", "headphones", S.s_nghe_trong_thu_vien_c0d6771a))
    if (asksBeforeResume(book) && !live && !book.starting && !book.queuePosition) out.push(item("resumeAnyway", "play", S.s_van_tiep_tuc_0f792959))
    if (live && !book.stopping) out.push(item("stop", "square", S.s_dung_385b27c6))
    if (live && book.pendingChanges) out.push(item("apply", "refresh-cw", book.pendingChanges + S.s_thay_doi_cho_ap_e4e2c5a3))
    if (book.queuePosition) out.push(item("leaveQueue", "square", S.s_bo_xep_hang_e797cd68))
    if (book.phase === "idle" && !live && !book.queuePosition) out.push(item("redo", "sliders-horizontal", S.s_sua_thiet_lap_96fa3435))
    if (book.chapters.completed > 0) out.push(item("export", "folder-down", S.s_xuat_e9ca2198))
    if (opts.next > 0) out.push(item("addChapters", "book-plus", S.s_them_3f5e8c43 + opts.next + S.s_chuong_9e6a01dc))
    if (!opts.remote) out.push(item("reveal", "folder-open", S.s_mo_thu_muc_4bf5b127))
    out.push(item("details", "info", S.s_chi_tiet_e762d926))
    return out
}
// "…" của một dự án: `extras` (đứng trên) rồi đổi tên, làm tiếp, xoá. `rename: false` cho dự án hỏng.
function projectMenu(book, opts) {
    opts = opts || {}
    const out = []
    const extras = opts.extras || []
    if (extras.length) { for (const e of extras) out.push(e); out.push(separator()) }
    if (opts.rename !== false) out.push(item("rename", "text-cursor-input", S.s_doi_ten_4cea1fd0))
    if (!book.broken) {
        const analyzed = ((book.segments && book.segments.analyzed) || 0) > 0
        out.push(item("continueBook", "book-plus", S.s_lam_tiep_cuon_nay_51fc8121, {disabled: !analyzed, hint: analyzed ? "" : S.s_chay_phan_nay_truoc_73213667}))
    }
    out.push(separator())
    if (opts.remote) out.push(item("onComputer", "monitor", onComputerLine(S.s_xoa_du_an_6b9e7c0b, opts.computer || S.s_may_tinh_8eafc226), {disabled: true}))
    else out.push(item("delete", "trash-2", S.s_xoa_du_an_3b65e276, {danger: true}))
    return out
}
function rowMenu(book, local, computer) {
    const extras = []
    if (book.broken) {
        if (book.backup) extras.push(item("restore", "history", S.s_khoi_phuc_ban_sao_d4b986fb))
        extras.push(item("reveal", "folder-open", S.s_mo_thu_muc_4bf5b127))
        return projectMenu(book, {rename: false, extras: extras, remote: !local, computer: computer})
    }
    if (local) extras.push(item("reveal", "folder-open", S.s_mo_thu_muc_4bf5b127))
    return projectMenu(book, {extras: extras, remote: !local, computer: computer})
}
// Đồng hồ "1:05:09" / "4:07" (shared/format.ts formatClock)
function formatClock(seconds) {
    const whole = Math.max(0, Math.floor(isFinite(seconds) ? seconds : 0)), h = Math.floor(whole / 3600), m = Math.floor((whole % 3600) / 60), sec = whole % 60
    return (h ? h + ":" : "") + (h ? two(m) : String(m)) + ":" + two(sec)
}
// Tên dễ đọc của model phân tích; khoá kỹ thuật chỉ dùng gửi máy chủ (analyzerLabel.ts)
function analyzerLabel(model) {
    const own = /^abook-analyzer:v(\d+)$/.exec(String(model).replace(/:latest$/, ""))
    return own ? S.s_bo_phan_tich_ban_a68c42e0 + own[1] : S.s_bo_phan_tich_tuy_chon_eed83d3d
}
// Giọng kể ở dòng thông tin đầu trang: đang chờ đổi thì giọng SẼ dùng + "(chờ áp dụng)" (analyzerLabel.ts narratorLabel)
function narratorLabel(settings) {
    if (settings.narratorPending) return S.s_giong_ke_255bd6e6 + settings.narratorPending + S.s_cho_ap_dung_31faa52d
    return settings.narrator ? S.s_giong_ke_255bd6e6 + settings.narrator : ""
}
function projectDetails(book) {
    const s = book.settings || {}
    return [
        narratorLabel(s),
        s.profileLabel || "",
        s.analyzer ? analyzerLabel(s.analyzer) : "",
        book.createdAt ? S.s_tao_2a1c4f55 + formatDate(book.createdAt) : "",
        book.position ? S.s_nghe_lan_cuoi_29e51e68 + formatRelative(book.position.at) + S.s_o_ce0ade07 + formatClock(book.position.seconds) : ""
    ].filter(Boolean)
}

// ---- Tab của trang dự án ----
var TAB_LABEL = {chapters: S.s_chuong_2d157977, precast: S.s_duyet_truoc_khi_thu_74c121d0, work: S.s_viec_can_duyet_5c0c3ce1, script: S.s_kich_ban_602e5f27, review: S.s_can_nghe_lai_d651f6ab, cast: S.s_nhan_vat_d4940c17, music: S.s_nhac_nen_271fb292, activity: S.s_nhat_ky_1e6c3c10}
var MAIN_TABS = ["chapters", "work", "review", "cast", "music"]
var ALL_TABS = ["chapters", "precast", "work", "script", "review", "cast", "music", "activity"]
function canReview(book) { return Boolean(book.precast && book.precast.ready) && book.phase !== "done" }
function moreTabs(precast) { return (precast ? ["precast"] : []).concat(["script", "activity"]) }
function tabOf(value) { return ALL_TABS.indexOf(value) >= 0 ? value : "chapters" }
// Nhãn nút "Thêm": nằm trong "Thêm" thì mang tên tab đang chọn.
function moreLabel(tab, precast) { return moreTabs(precast).indexOf(tab) >= 0 ? TAB_LABEL[tab] : S.s_them_dd92626f }
function moreCount(tab, precast, counts) {
    const more = moreTabs(precast)
    if (more.indexOf(tab) >= 0) return counts[tab] || 0
    return more.reduce(function(sum, key) { return sum + (counts[key] || 0) }, 0)
}
function tabPlaceholder(tab) { return S.s_muc_nay_chua_mo_trong_ban_nay_7f8e746e }

// ---- Chương ----
// Dấu nhỏ trên một hàng chương, hay null (chương xong / chờ tới lượt là mặc định, không đeo nhãn).
function chapterMark(chapter) {
    if (chapter.statusLabel === S.s_mat_file_audio_b2b0802b) return {label: chapter.statusLabel, tone: "warning"}
    if (chapter.status === "completed" && !chapter.redo) return null
    if (chapter.status === "pending" || chapter.status === "analyzed" || chapter.status === "synthesizing" || chapter.status === "verifying") return null
    return {label: chapter.statusLabel, tone: chapter.status === "failed" ? "danger" : chapter.status === "warning" ? "warning" : "muted"}
}
function chapterWorking(chapter) { return chapter.status === "synthesizing" || chapter.status === "verifying" }
function chapterRecorded(chapter) { return chapter.segments.total ? chapter.segments.finished / chapter.segments.total : 0 }
// Độ dài khi đã có audio, chưa thì số câu
function chapterLength(chapter) {
    return chapter.status === "completed" || chapter.redo ? formatLength(chapter.seconds) : chapter.segments.total ? formatNumber(chapter.segments.total) + S.s_cau_b07e1008 : ""
}
function chapterDone(chapter) { return chapter.completedAt ? formatRelative(chapter.completedAt) : "" }
function chapterWorkingText(chapter, running) { return (running ? "" : S.s_dung_o_f47312a8) + chapter.segments.finished + "/" + chapter.segments.total }

// ---- Nhật ký ----
function activityGroups(items) {
    const result = []
    for (const entry of items || []) {
        const day = formatDate(entry.at)
        const last = result[result.length - 1]
        if (last && last.day === day) last.items.push(entry)
        else result.push({day: day, items: [entry]})
    }
    return result
}
function activityTime(entry) { return formatTime(entry.at).split("\u00a0·\u00a0")[0] }

// ---- Đầu trang một dự án ----
// Dòng phụ dưới tên (DotJoin của ProjectScreen.tsx, sau viên trạng thái): số chương · độ dài · việc cần để ý. StyledText; `warn` là màu cảnh báo.
function metaLine(book, warn) {
    const parts = [(book.phase !== "done" && book.chapters.total ? book.chapters.completed + "/" + book.chapters.total : String(book.chapters.total)) + S.s_chuong_9e6a01dc]
    if (book.audioSeconds > 0) parts.push(formatLength(book.audioSeconds))
    if (book.chapters.missingAudio) parts.push("<font color=\"" + warn + "\"><b>" + book.chapters.missingAudio + S.s_chuong_mat_file_audio_b_font_4d0db657)
    if (book.chapters.redo) parts.push(book.chapters.redo + S.s_chuong_cho_thu_lai_6920aaee)
    return parts.join("\u00a0·\u00a0")
}
// Dải báo khi lần hỏi gần nhất hỏng mà vẫn còn bản cũ của sách
function staleLine(status, text) {
    return status === 0 ? S.s_mat_ket_noi_toi_abook_dang_thu_lai_07419d77 : S.s_chua_tai_lai_duoc_sach_01a64552 + failureText(status, text) + S.s_dang_thu_lai_20eefc5d
}
// Lỗi của lần làm sách cho người nghe: {summary, hint, detail} hay null. `studio`: máy này có Studio.
function bookProblem(book, studio, studioLostModel) {
    if (book.lastError && book.phase === "error") return friendlyError(book.lastError, studio, asksBeforeResume(book), studioLostModel)
    if (book.runEnd && !book.running && !book.starting) return runEndText(book.runEnd, studio, asksBeforeResume(book), studioLostModel)
    return null
}
var TAB_ICON = {precast: "headphones", script: "book-open-text", activity: "history"}
function moreItems(precast) {
    return moreTabs(precast).map(function(key) { return item(key, TAB_ICON[key], TAB_LABEL[key]) })
}
var LEVEL_TONE = {error: "danger", warning: "warning"}

// Tên thư mục cuối của một đường dẫn (folderName của shared/MissingLibrary.tsx)
function folderName(path) { return String(path).split(/[\\/]/).filter(Boolean).pop() || String(path) }

// ---- Chữ của hộp ----
function renameDescription() { return S.s_ten_moi_hien_o_thu_vien_dien_thoai_va_file_a0f15560 }
function deleteDescription() { return S.s_ca_thu_muc_du_an_vao_thung_rac_cua_windows_6f78dcf8 }
function peerPath(path, peer) { return Peer.throughPeer(path, peer) }
