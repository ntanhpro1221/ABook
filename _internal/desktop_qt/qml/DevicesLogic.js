.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size

// Phần chữ và logic thuần của Cài đặt › Thiết bị, chép từ bản web để hai nền tảng nói CÙNG một câu: shared/format.ts (formatRelative,
// formatDate, formatFingerprint; formatSize ở SizeFormat.js), shared/connectionRoute.ts, desktop/computerRoutes.ts, shared/unpair.ts, shared/diagnostics.ts.

function pad2(value) { return String(value).padStart(2, "0") }

function formatDate(epochSeconds) {
    const date = new Date(epochSeconds * 1000)
    return date.getDate() + "/" + (date.getMonth() + 1) + "/" + date.getFullYear()
}

function formatRelative(epochSeconds, nowSeconds) {
    if (!epochSeconds) return ""
    const now = nowSeconds === undefined ? Date.now() / 1000 : nowSeconds
    const delta = now - epochSeconds
    if (delta < 60) return S.s_vua_xong_b46f7a2b
    if (delta < 3600) return Math.floor(delta / 60) + S.s_phut_truoc_d6b7b9dc
    if (delta < 86400) return Math.floor(delta / 3600) + S.s_gio_truoc_44858c63
    const days = Math.floor(delta / 86400)
    if (days === 1) return S.s_hom_qua_20142adc
    if (days < 7) return days + S.s_ngay_truoc_24f1e46c
    return formatDate(epochSeconds)
}

// Vân tay chứng chỉ: nhóm 4 ký tự, hoa - "AB12 CD34 ..."
function formatFingerprint(value) {
    const hex = String(value || "").replace(/\s+/g, "").toUpperCase()
    return hex.replace(/(.{4})(?=.)/g, "$1 ")
}

// Thoát ký tự cho chữ rich text (tên máy, địa chỉ do người dùng / máy kia đặt)
function esc(text) {
    return String(text === undefined || text === null ? "" : text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;")
}

// ---- Địa chỉ của máy này (Where của PhoneSync.tsx): trong nhà và khi ở ngoài (mạng riêng ảo), chữ đậm vừa. Trả về HTML. ----
function whereHtml(sync, scheme, ink) {
    const addresses = sync.addresses || []
    const awayList = sync.awayAddresses || []
    const away = addresses.filter(address => awayList.indexOf(address) >= 0)
    const home = addresses.filter(address => away.indexOf(address) < 0)
    const open = "<span style='font-weight:500;color:" + ink + "'>"
    const show = list => open + list.map(address => esc((scheme ? "https://" : "") + address + ":" + sync.port)).join(S.s_span_hoac_79a0db31 + open) + "</span>"
    let html = ""
    if (home.length > 0) html += show(home)
    if (home.length > 0 && away.length > 0) html += S.s_trong_nha_hoac_de6d3fe2
    if (away.length > 0) html += show(away) + S.s_khi_o_ngoai_thiet_bi_kia_vao_cung_mang_rie_d9eb417b
    return html
}

// ---- Đường nối của máy đã ghép ----
function isBluetoothHost(host) { return String(host || "").toLowerCase().indexOf("bt:") === 0 }
function bluetoothAddress(computer) {
    return (isBluetoothHost(computer.host) ? String(computer.host).slice(3) : (computer.bt || "")).toUpperCase()
}
function deviceKindLabel(kind) { return kind === "phone" ? S.s_dien_thoai_2f73f175 : S.s_may_tinh_8eafc226 }

function connectionRoute(address) {
    if (!address) return S.s_chua_ket_noi_f3743a06
    const lower = String(address).toLowerCase()
    if (address === "bluetooth" || lower.indexOf("bt:") === 0) return S.s_dang_noi_qua_bluetooth_fb6ba9e5
    const host = address.charAt(0) === "[" ? address.slice(1, address.indexOf("]")) : address.split(":")[0]
    const parts = host.split(".").map(Number)
    if (parts.length === 4 && parts.every(part => Number.isInteger(part) && part >= 0 && part <= 255)) {
        const a = parts[0], b = parts[1]
        if (a === 100 && b >= 64 && b <= 127) return S.s_dang_noi_qua_tailscale_7de36f5d
        if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return S.s_dang_noi_qua_wi_fi_nha_ebf18485
    }
    return S.s_dang_noi_qua_mang_807811f3
}

function wakingLine(computer, nowSeconds) {
    const now = nowSeconds === undefined ? Date.now() / 1000 : nowSeconds
    const until = computer.waking && computer.waking.until !== undefined ? computer.waking.until : now
    const left = Math.max(0, until - now)
    const rest = left >= 90 ? Math.round(left / 60) + S.s_phut_cf728a6a : Math.max(1, Math.round(left)) + S.s_giay_9f6b3e22
    const what = computer.kind === "computer"
        ? S.s_may_kia_chua_tra_loi_mo_abook_tren_may_ay_0c068d6a
        : S.s_dien_thoai_dang_ngu_mo_abook_tren_dien_tho_15b25e58
    return what + S.s_u00a0_u00a0cho_them_toi_da_07c292ab + rest
}

// ---- Bỏ ghép (shared/unpair.ts) ----
function unpairDone(device) { return S.s_da_bo_ghep_0977f068 + device }

// `self`: "điện thoại" | "máy tính"; trả null khi không còn gì để mất - gỡ như thường.
function unpairCopy(device, self, unsent, reachable) {
    const edited = !!unsent && unsent.changes > 0 && (unsent.books || []).length > 0
    const cache = unsent && unsent.cache && unsent.cache.books > 0 ? unsent.cache : null
    if (!unsent || (!edited && !cache)) return null
    const lines = []
    if (cache) {
        const downloaded = cache.bytes > 0 ? S.s_va_231e8fb6 + (cache.bytes < Math.pow(1024, 2) ? S.s_duoi_1_mb_b59395ae : Size.formatSize(cache.bytes)) + S.s_da_tai_ve_80dabcac + self + S.s_nay_se_bi_xoa_99dfc8c2 : ""
        lines.push(cache.books + S.s_cuon_cua_4d2892a0 + device + S.s_se_roi_thu_vien_ec7e0d78 + downloaded + ".")
        if (cache.places > 0) lines.push(S.s_cho_nghe_cua_a4f044c0 + cache.places + S.s_cuon_van_giu_ghep_lai_dung_0c995a07 + device + S.s_la_nghe_tiep_duoc_20b1ca29)
    }
    let send = null
    const up = unsent.reachable === undefined || unsent.reachable === null ? reachable : unsent.reachable
    if (edited) {
        const names = unsent.books.slice(0, 3).map(book => "“" + book.title + "”")
        const rest = unsent.books.length - names.length
        lines.push(unsent.books.length + S.s_cuon_co_53d19033 + unsent.changes + S.s_thay_doi_chua_gui_ve_e4b95e8c + device + S.s_se_mat_f9df113f + names.join(", ") + (rest > 0 ? S.s_va_79e3d3b1 + rest + S.s_cuon_khac_d0f2513f : "") + ".")
        if (!unsent.sendable) {
            lines.push(device + S.s_khong_nhan_phan_sua_nhung_thay_doi_nay_chi_564e323c + self + S.s_nay_cc6b00f9)
        } else if (up) {
            send = S.s_gui_truoc_roi_bo_ghep_99e6d1f1
        } else {
            send = S.s_thu_gui_truoc_roi_bo_ghep_f12544da
            lines.push(device + S.s_dang_tat_hay_khac_mang_luc_nay_nen_chua_gu_6b9e0bbc)
        }
    }
    return {title: S.s_bo_ghep_9139fc92 + device + "?", lines: lines, send: send, sendPrimary: edited && up, discard: edited ? S.s_van_bo_ghep_bo_thay_doi_64cb2e74 : S.s_bo_ghep_64f921f9, cancel: S.s_giu_lai_3c3ba2db}
}

// ---- Chẩn đoán điện thoại (shared/diagnostics.ts) ----
function yes(value) { return value ? S.s_co_8e3aafe8 : S.s_khong_0ec84c3f }
function when(millis) {
    const date = new Date(millis)
    return pad2(date.getDate()) + "/" + pad2(date.getMonth() + 1) + "/" + date.getFullYear() + " " + pad2(date.getHours()) + ":" + pad2(date.getMinutes())
}
function failed(part) {
    if (!part || typeof part !== "object" || Array.isArray(part)) return null
    if (typeof part.error !== "string" || !part.error.trim()) return null
    if (!part.collectionFailed && ["bookId", "bookTitle", "playing", "position"].some(key => key in part)) return null
    return S.s_khong_doc_duoc_20e38587
}

function workProgressRows(report) {
    if (!Array.isArray(report.work)) return []
    const phases = {
        download: S.s_dang_tai_1fd8b1ef, downloading: S.s_dang_tai_1fd8b1ef, fetch: S.s_dang_tai_1fd8b1ef, voice: S.s_dang_tao_giong_doc_799156a0,
        encode: S.s_dang_ghep_am_thanh_9153c306, music: S.s_dang_tron_nhac_e4d467d5, "music-fetch": S.s_dang_tai_nhac_nen_98212286,
        peaks: S.s_dang_kiem_dinh_am_0858dcd2, reencode: S.s_dang_ma_hoa_lai_266e95f8, verify: S.s_dang_kiem_tra_3c8395d9, done: S.s_da_xong_fce9b751,
        prepare: S.s_dang_chuan_bi_d4a83411, "package": S.s_dang_dong_goi_f7c98bff, "export": S.s_dang_xuat_67231e8c
    }
    const states = {RUNNING: S.s_dang_chay_01527862, ENQUEUED: S.s_dang_cho_ed662259, FAILED: S.s_hong_284f6108, CANCELLED: S.s_da_dung_caf33d01, SUCCEEDED: S.s_da_xong_fce9b751, BLOCKED: S.s_dang_cho_dieu_kien_a44f208b}
    const kinds = {BookDownloadWorker: S.s_tai_sach_3c83e586, Mp3ExportWorker: S.s_xuat_mp3_60946614, M4bExportWorker: S.s_xuat_m4b_4a708187, ListenExportWorker: S.s_xuat_sach_noi_219fb12a}
    const count = value => value !== undefined && String(value).trim() !== "" && isFinite(Number(value)) && Number(value) >= 0 ? value : undefined
    const rows = []
    report.work.forEach(function(job, index) {
        const progress = job.progress || {}
        const done = count(progress.done)
        const total = count(progress.total)
        const phase = progress.phase ? String(progress.phase).trim() : ""
        if (done === undefined && total === undefined && !phase) return
        const title = (job.tags || []).map(tag => kinds[tag]).find(Boolean) || S.s_viec_nen_364c2b5d
        rows.push({label: S.s_viec_34de8b11 + (index + 1), value: [title, states[job.state] || S.s_chua_ro_trang_thai_8f3e99b0,
            done !== undefined && total !== undefined ? done + "/" + total : done !== undefined ? S.s_da_lam_5fe22366 + done : total !== undefined ? S.s_tong_37dd36d0 + total : "",
            phase ? "Pha: " + (phases[phase] || phase) : ""].filter(Boolean).join("\u00a0·\u00a0")})
    })
    return rows
}

function failureDetails(report) {
    const rows = []
    Object.keys(report).forEach(function(label) {
        const part = report[label]
        const error = part && typeof part === "object" && !Array.isArray(part) ? part.error : undefined
        if (typeof error === "string" && error.trim()) rows.push({label: label, value: error.trim()})
    })
    return rows
}

function summaryRows(report) {
    const rows = []
    const add = function(label, part, value) {
        if (part === undefined || part === null) return
        const problem = failed(part)
        if (problem) { rows.push({label: label, value: problem}); return }
        const text = value()
        if (text) rows.push({label: label, value: text})
    }
    add(S.s_ban_abook_046fa27d, report.app, function() {
        const app = report.app
        return [(app.versionName === undefined ? "?" : app.versionName) + (app.versionCode !== undefined ? " (" + app.versionCode + ")" : ""), app.debug ? S.s_ban_thu_3095d3e2 : ""].filter(Boolean).join("\u00a0·\u00a0")
    })
    add(S.s_dien_thoai_8185f4c9, report.device, function() {
        const device = report.device
        return [device.manufacturer, device.model].filter(Boolean).join(" ") + "\u00a0·\u00a0Android " + (device.release === undefined ? "?" : device.release) + (device.sdk ? " (API " + device.sdk + ")" : "")
    })
    add(S.s_gio_tren_may_6a6cdf95, report.time, function() {
        const time = report.time
        return time.epochMillis ? when(time.epochMillis) + (time.timezone ? "\u00a0·\u00a0" + time.timezone : "") : null
    })
    add(S.s_copy_ff1cee744146, report.battery, function() {
        const battery = report.battery
        return (typeof battery.percent === "number" ? battery.percent + "%" : S.s_khong_ro_e5605c9b) + (battery.charging ? S.s_u00a0_u00a0dang_sac_71741c4f : "")
    })
    add(S.s_mang_4b4e6369, report.network, function() {
        const net = report.network
        if (!net.connected) return S.s_chua_co_mang_c903ca13
        const ways = [net.wifi && S.s_wi_fi_337253f2, net.cellular && S.s_di_dong_541aae75, net.vpn && "VPN", net.ethernet && S.s_day_mang_56c3cabb, net.bluetooth && S.s_bluetooth_8bb29098].filter(Boolean)
        return [ways.join(" + ") || S.s_co_mang_23deb37d, net.validated ? "" : S.s_chua_ra_duoc_internet_43c4be0b, net.metered ? S.s_tinh_cuoc_707dc43c : ""].filter(Boolean).join("\u00a0·\u00a0")
    })
    add(S.s_cho_trong_a5fb7e34, report.storage, function() {
        const storage = report.storage
        return typeof storage.freeBytes === "number" ? Size.formatSize(storage.freeBytes) + (storage.totalBytes ? " / " + Size.formatSize(storage.totalBytes) : "") : null
    })
    add(S.s_thong_bao_a9b656f5, report.notifications, function() { return report.notifications.enabled ? S.s_dang_bat_a2be6d6c : S.s_dang_tat_6d495acb })
    add(S.s_chay_nen_4553c5f8, report.power, function() {
        const power = report.power
        return [S.s_mien_toi_uu_pin_a80cbc7b + yes(power.ignoringBatteryOptimizations), power.backgroundRestricted ? S.s_bi_han_che_chay_nen_d4b2a7df : "", power.powerSave ? S.s_dang_tiet_kiem_pin_287c6ba6 : ""].filter(Boolean).join("\u00a0·\u00a0")
    })
    add(S.s_dang_nghe_9310d8cf, report.playback, function() {
        const playback = report.playback
        if (!playback.bookTitle) return S.s_chua_mo_cuon_nao_1220ce65
        const place = typeof playback.position === "number" ? "\u00a0·\u00a0" + Math.floor(playback.position / 60) + S.s_phut_756e57f3 + Math.floor(playback.position % 60) + S.s_giay_9f6b3e22 : ""
        return playback.bookTitle + (playback.chapterId !== undefined ? S.s_u00a0_u00a0chuong_1785bbaa + playback.chapterId : "") + place + "\u00a0·\u00a0" + (playback.playing ? S.s_dang_phat_e3baf7da : S.s_tam_dung_eea0842f) + (playback.error && String(playback.error).trim() ? S.s_u00a0_u00a0co_loi_phat_5f4669f3 : "")
    })
    add(S.s_viec_nen_364c2b5d, report.work, function() {
        const work = Array.isArray(report.work) ? report.work : []
        if (!work.length) return S.s_khong_co_viec_nao_2e68f374
        const count = state => work.filter(job => job.state === state).length
        return [count("RUNNING") + S.s_dang_chay_a06941aa, count("ENQUEUED") + S.s_dang_cho_d8b24eaf, count("FAILED") ? count("FAILED") + S.s_hong_a0eccf93 : "", count("CANCELLED") ? count("CANCELLED") + S.s_da_dung_dc56868c : ""].filter(Boolean).join("\u00a0·\u00a0")
    })
    add(S.s_cho_may_khac_nghe_thu_vien_65b8bfae, report.share, function() {
        const share = report.share
        return share.running ? S.s_dang_bat_u00a0_u00a0_259152ff + (share.pairedDevices || 0) + S.s_may_da_ghep_b4494738 : S.s_dang_tat_6d495acb + (share.lastError ? " (" + share.lastError + ")" : "")
    })
    add(S.s_lan_tat_gan_nhat_3fae581d, report.exitReasons, function() {
        const last = Array.isArray(report.exitReasons) ? report.exitReasons[0] : undefined
        return last ? last.reason + (last.timestamp ? "\u00a0·\u00a0" + when(last.timestamp) : "") : null
    })
    add(S.s_lan_vang_dee6eb16, report.crashes, function() { return Array.isArray(report.crashes) && report.crashes.length ? report.crashes.length + S.s_lan_duoc_ghi_lai_348aa239 : null })
    add(S.s_phuc_hoi_du_lieu_7dde2059, report.dataRecovery, function() {
        const recovery = report.dataRecovery
        const kinds = {recovered: S.s_da_giu_ban_cu_698af56c, "saving-blocked": S.s_dang_chan_luu_e91d5596, "notice-read-error": S.s_chua_doc_duoc_canh_bao_ea2b6021, warning: S.s_canh_bao_9e63a91e}
        const notes = (recovery.notices || []).map(notice =>
            [kinds[notice.kind || ""] || S.s_canh_bao_9e63a91e, notice.at ? when(notice.at) : "", notice.preservedFile, notice.pending ? S.s_chua_luu_canh_bao_bdc85d89 : ""].filter(Boolean).join("\u00a0·\u00a0"))
        return [recovery.savingBlocked ? S.s_app_dang_chan_luu_de_giu_du_lieu_cua_ban_cd56418e : ""].concat(notes).filter(Boolean).join("; ") || S.s_chua_co_canh_bao_45795006
    })
    return rows
}

function logLines(report, key) {
    const part = report[key || "log"]
    return Array.isArray(part) ? part : []
}
function emptyLogNote(report, key) { return failed(report[key || "log"]) || S.s_chua_co_dong_nao_88732bb0 }

// Lời hướng dẫn kèm lời báo lỗi chẩn đoán (UNREACHABLE_HELP): 404 / 409 là lỗi nói rõ rồi, không kèm.
var UNREACHABLE_HELP = S.s_tren_dien_thoai_cai_dat_thiet_bi_dien_thoa_210864ae
