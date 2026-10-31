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
    if (delta < 60) return "vừa xong"
    if (delta < 3600) return Math.floor(delta / 60) + " phút trước"
    if (delta < 86400) return Math.floor(delta / 3600) + " giờ trước"
    const days = Math.floor(delta / 86400)
    if (days === 1) return "hôm qua"
    if (days < 7) return days + " ngày trước"
    return formatDate(epochSeconds)
}

// Vân tay chứng chỉ: nhóm 4 ký tự, hoa - "AB12 CD34 ..."
function formatFingerprint(value) {
    const hex = String(value || "").replace(/\s+/g, "").toUpperCase()
    return hex.replace(/(.{4})(?=.)/g, "$1 ")
}

// Thoát ký tự cho chữ rich text (tên máy, địa chỉ do người dùng / máy kia đặt)
function esc(text) {
    return String(text === undefined || text === null ? "" : text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

// ---- Địa chỉ của máy này (Where của PhoneSync.tsx): trong nhà và khi ở ngoài (mạng riêng ảo), chữ đậm vừa. Trả về HTML. ----
function whereHtml(sync, scheme, ink) {
    const addresses = sync.addresses || []
    const awayList = sync.awayAddresses || []
    const away = addresses.filter(address => awayList.indexOf(address) >= 0)
    const home = addresses.filter(address => away.indexOf(address) < 0)
    const open = "<span style='font-weight:500;color:" + ink + "'>"
    const show = list => open + list.map(address => esc((scheme ? "https://" : "") + address + ":" + sync.port)).join("</span> hoặc " + open) + "</span>"
    let html = ""
    if (home.length > 0) html += show(home)
    if (home.length > 0 && away.length > 0) html += " trong nhà, hoặc "
    if (away.length > 0) html += show(away) + " khi ở ngoài (thiết bị kia vào cùng mạng riêng ảo)"
    return html
}

// ---- Đường nối của máy đã ghép ----
function isBluetoothHost(host) { return String(host || "").toLowerCase().indexOf("bt:") === 0 }
function bluetoothAddress(computer) {
    return (isBluetoothHost(computer.host) ? String(computer.host).slice(3) : (computer.bt || "")).toUpperCase()
}
function deviceKindLabel(kind) { return kind === "phone" ? "điện thoại" : "máy tính" }

function connectionRoute(address) {
    if (!address) return "Chưa kết nối"
    const lower = String(address).toLowerCase()
    if (address === "bluetooth" || lower.indexOf("bt:") === 0) return "Đang nối qua Bluetooth"
    const host = address.charAt(0) === "[" ? address.slice(1, address.indexOf("]")) : address.split(":")[0]
    const parts = host.split(".").map(Number)
    if (parts.length === 4 && parts.every(part => Number.isInteger(part) && part >= 0 && part <= 255)) {
        const a = parts[0], b = parts[1]
        if (a === 100 && b >= 64 && b <= 127) return "Đang nối qua Tailscale"
        if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return "Đang nối qua Wi-Fi nhà"
    }
    return "Đang nối qua mạng"
}

function wakingLine(computer, nowSeconds) {
    const now = nowSeconds === undefined ? Date.now() / 1000 : nowSeconds
    const until = computer.waking && computer.waking.until !== undefined ? computer.waking.until : now
    const left = Math.max(0, until - now)
    const rest = left >= 90 ? Math.round(left / 60) + " phút" : Math.max(1, Math.round(left)) + " giây"
    const what = computer.kind === "computer"
        ? "Máy kia chưa trả lời - mở ABook trên máy ấy"
        : "Điện thoại đang ngủ - mở ABook trên điện thoại để trả lời ngay"
    return what + " · chờ thêm tối đa " + rest
}

// ---- Bỏ ghép (shared/unpair.ts) ----
function unpairDone(device) { return "Đã bỏ ghép " + device }

// `self`: "điện thoại" | "máy tính"; trả null khi không còn gì để mất - gỡ như thường.
function unpairCopy(device, self, unsent, reachable) {
    const edited = !!unsent && unsent.changes > 0 && (unsent.books || []).length > 0
    const cache = unsent && unsent.cache && unsent.cache.books > 0 ? unsent.cache : null
    if (!unsent || (!edited && !cache)) return null
    const lines = []
    if (cache) {
        const downloaded = cache.bytes > 0 ? ", và " + (cache.bytes < Math.pow(1024, 2) ? "dưới 1 MB" : Size.formatSize(cache.bytes)) + " đã tải về " + self + " này sẽ bị xoá" : ""
        lines.push(cache.books + " cuốn của " + device + " sẽ rời Thư viện" + downloaded + ".")
        if (cache.places > 0) lines.push("Chỗ nghe của " + cache.places + " cuốn vẫn giữ - ghép lại đúng " + device + " là nghe tiếp được.")
    }
    let send = null
    const up = unsent.reachable === undefined || unsent.reachable === null ? reachable : unsent.reachable
    if (edited) {
        const names = unsent.books.slice(0, 3).map(book => "“" + book.title + "”")
        const rest = unsent.books.length - names.length
        lines.push(unsent.books.length + " cuốn có " + unsent.changes + " thay đổi chưa gửi về " + device + " sẽ mất: " + names.join(", ") + (rest > 0 ? " và " + rest + " cuốn khác" : "") + ".")
        if (!unsent.sendable) {
            lines.push(device + " không nhận phần sửa - những thay đổi này chỉ có trên " + self + " này.")
        } else if (up) {
            send = "Gửi trước rồi bỏ ghép"
        } else {
            send = "Thử gửi trước rồi bỏ ghép"
            lines.push(device + " đang tắt hay khác mạng lúc này nên chưa gửi được - mở máy ấy rồi gửi, hay bỏ thay đổi.")
        }
    }
    return {title: "Bỏ ghép " + device + "?", lines: lines, send: send, sendPrimary: edited && up, discard: edited ? "Vẫn bỏ ghép, bỏ thay đổi" : "Bỏ ghép", cancel: "Giữ lại"}
}

// ---- Chẩn đoán điện thoại (shared/diagnostics.ts) ----
function yes(value) { return value ? "có" : "không" }
function when(millis) {
    const date = new Date(millis)
    return pad2(date.getDate()) + "/" + pad2(date.getMonth() + 1) + "/" + date.getFullYear() + " " + pad2(date.getHours()) + ":" + pad2(date.getMinutes())
}
function failed(part) {
    if (!part || typeof part !== "object" || Array.isArray(part)) return null
    if (typeof part.error !== "string" || !part.error.trim()) return null
    if (!part.collectionFailed && ["bookId", "bookTitle", "playing", "position"].some(key => key in part)) return null
    return "không đọc được"
}

function workProgressRows(report) {
    if (!Array.isArray(report.work)) return []
    const phases = {
        download: "đang tải", downloading: "đang tải", fetch: "đang tải", voice: "đang tạo giọng đọc",
        encode: "đang ghép âm thanh", music: "đang trộn nhạc", "music-fetch": "đang tải nhạc nền",
        peaks: "đang kiểm đỉnh âm", reencode: "đang mã hoá lại", verify: "đang kiểm tra", done: "đã xong",
        prepare: "đang chuẩn bị", "package": "đang đóng gói", "export": "đang xuất"
    }
    const states = {RUNNING: "đang chạy", ENQUEUED: "đang chờ", FAILED: "hỏng", CANCELLED: "đã dừng", SUCCEEDED: "đã xong", BLOCKED: "đang chờ điều kiện"}
    const kinds = {BookDownloadWorker: "Tải sách", Mp3ExportWorker: "Xuất MP3", M4bExportWorker: "Xuất M4B", ListenExportWorker: "Xuất sách nói"}
    const count = value => value !== undefined && String(value).trim() !== "" && isFinite(Number(value)) && Number(value) >= 0 ? value : undefined
    const rows = []
    report.work.forEach(function(job, index) {
        const progress = job.progress || {}
        const done = count(progress.done)
        const total = count(progress.total)
        const phase = progress.phase ? String(progress.phase).trim() : ""
        if (done === undefined && total === undefined && !phase) return
        const title = (job.tags || []).map(tag => kinds[tag]).find(Boolean) || "Việc nền"
        rows.push({label: "Việc " + (index + 1), value: [title, states[job.state] || "chưa rõ trạng thái",
            done !== undefined && total !== undefined ? done + "/" + total : done !== undefined ? "đã làm " + done : total !== undefined ? "tổng " + total : "",
            phase ? "Pha: " + (phases[phase] || phase) : ""].filter(Boolean).join(" · ")})
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
    add("Bản ABook", report.app, function() {
        const app = report.app
        return [(app.versionName === undefined ? "?" : app.versionName) + (app.versionCode !== undefined ? " (" + app.versionCode + ")" : ""), app.debug ? "bản thử" : ""].filter(Boolean).join(" · ")
    })
    add("Điện thoại", report.device, function() {
        const device = report.device
        return [device.manufacturer, device.model].filter(Boolean).join(" ") + " · Android " + (device.release === undefined ? "?" : device.release) + (device.sdk ? " (API " + device.sdk + ")" : "")
    })
    add("Giờ trên máy", report.time, function() {
        const time = report.time
        return time.epochMillis ? when(time.epochMillis) + (time.timezone ? " · " + time.timezone : "") : null
    })
    add("Pin", report.battery, function() {
        const battery = report.battery
        return (typeof battery.percent === "number" ? battery.percent + "%" : "không rõ") + (battery.charging ? " · đang sạc" : "")
    })
    add("Mạng", report.network, function() {
        const net = report.network
        if (!net.connected) return "chưa có mạng"
        const ways = [net.wifi && "Wi-Fi", net.cellular && "di động", net.vpn && "VPN", net.ethernet && "dây mạng", net.bluetooth && "Bluetooth"].filter(Boolean)
        return [ways.join(" + ") || "có mạng", net.validated ? "" : "chưa ra được Internet", net.metered ? "tính cước" : ""].filter(Boolean).join(" · ")
    })
    add("Chỗ trống", report.storage, function() {
        const storage = report.storage
        return typeof storage.freeBytes === "number" ? Size.formatSize(storage.freeBytes) + (storage.totalBytes ? " / " + Size.formatSize(storage.totalBytes) : "") : null
    })
    add("Thông báo", report.notifications, function() { return report.notifications.enabled ? "đang bật" : "đang tắt" })
    add("Chạy nền", report.power, function() {
        const power = report.power
        return ["miễn tối ưu pin: " + yes(power.ignoringBatteryOptimizations), power.backgroundRestricted ? "bị hạn chế chạy nền" : "", power.powerSave ? "đang tiết kiệm pin" : ""].filter(Boolean).join(" · ")
    })
    add("Đang nghe", report.playback, function() {
        const playback = report.playback
        if (!playback.bookTitle) return "chưa mở cuốn nào"
        const place = typeof playback.position === "number" ? " · " + Math.floor(playback.position / 60) + " phút " + Math.floor(playback.position % 60) + " giây" : ""
        return playback.bookTitle + (playback.chapterId !== undefined ? " · chương " + playback.chapterId : "") + place + " · " + (playback.playing ? "đang phát" : "tạm dừng") + (playback.error && String(playback.error).trim() ? " · có lỗi phát" : "")
    })
    add("Việc nền", report.work, function() {
        const work = Array.isArray(report.work) ? report.work : []
        if (!work.length) return "không có việc nào"
        const count = state => work.filter(job => job.state === state).length
        return [count("RUNNING") + " đang chạy", count("ENQUEUED") + " đang chờ", count("FAILED") ? count("FAILED") + " hỏng" : "", count("CANCELLED") ? count("CANCELLED") + " đã dừng" : ""].filter(Boolean).join(" · ")
    })
    add("Cho máy khác nghe thư viện", report.share, function() {
        const share = report.share
        return share.running ? "đang bật · " + (share.pairedDevices || 0) + " máy đã ghép" : "đang tắt" + (share.lastError ? " (" + share.lastError + ")" : "")
    })
    add("Lần tắt gần nhất", report.exitReasons, function() {
        const last = Array.isArray(report.exitReasons) ? report.exitReasons[0] : undefined
        return last ? last.reason + (last.timestamp ? " · " + when(last.timestamp) : "") : null
    })
    add("Lần văng", report.crashes, function() { return Array.isArray(report.crashes) && report.crashes.length ? report.crashes.length + " lần được ghi lại" : null })
    add("Phục hồi dữ liệu", report.dataRecovery, function() {
        const recovery = report.dataRecovery
        const kinds = {recovered: "đã giữ bản cũ", "saving-blocked": "đang chặn lưu", "notice-read-error": "chưa đọc được cảnh báo", warning: "cảnh báo"}
        const notes = (recovery.notices || []).map(notice =>
            [kinds[notice.kind || ""] || "cảnh báo", notice.at ? when(notice.at) : "", notice.preservedFile, notice.pending ? "chưa lưu cảnh báo" : ""].filter(Boolean).join(" · "))
        return [recovery.savingBlocked ? "App đang chặn lưu để giữ dữ liệu của bạn" : ""].concat(notes).filter(Boolean).join("; ") || "chưa có cảnh báo"
    })
    return rows
}

function logLines(report, key) {
    const part = report[key || "log"]
    return Array.isArray(part) ? part : []
}
function emptyLogNote(report, key) { return failed(report[key || "log"]) || "Chưa có dòng nào." }

// Lời hướng dẫn kèm lời báo lỗi chẩn đoán (UNREACHABLE_HELP): 404 / 409 là lỗi nói rõ rồi, không kèm.
var UNREACHABLE_HELP = "Trên điện thoại: Cài đặt › Thiết bị › Điện thoại này › bật “Chia sẻ thư viện”. Cùng Wi-Fi hay Tailscale."
