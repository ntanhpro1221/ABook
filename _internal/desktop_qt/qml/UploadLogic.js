.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size

// Gửi chương lên máy tính khi Studio ở máy khác (ui/src/studio/upload.ts, phần thuần): máy đang xem không đưa được đường dẫn nào trên máy tính, nên nó gửi
// các chương TXT (hay file EPUB / DOCX / PDF) vào thư viện của máy tính (POST /api/sources/upload) từng file một rồi trả các thư mục để trình tạo sách đi
// tiếp như khi chọn thư mục. Gửi byte nguyên vẹn (base64): bảng mã do dây chuyền nhận, như với file trên máy.

/** Trần mỗi file của máy tính (webui/actions.MAX_SOURCE_UPLOAD). */
var UPLOAD_LIMIT = 40 * 1024 * 1024
var LIMIT_MB = UPLOAD_LIMIT / Math.pow(2, 20)
var ACCEPTED = /\.(txt|epub|docx|pdf)$/i

/** So tên theo thứ tự tự nhiên (2 đứng trước 10), không phân biệt hoa thường. */
function naturalCompare(a, b) {
    const left = String(a).toLowerCase().split(/(\d+)/), right = String(b).toLowerCase().split(/(\d+)/)
    for (let i = 0; i < Math.min(left.length, right.length); ++i) {
        if (left[i] === right[i]) continue
        if (i % 2 === 1) return Number(left[i]) - Number(right[i]) || (left[i] < right[i] ? -1 : 1)
        return left[i] < right[i] ? -1 : 1
    }
    return left.length - right.length
}
function byName(a, b) { return naturalCompare(a.name, b.name) }

/** "Tải lên 05-10-2026 18h22 ab12": mỗi lần gửi một thư mục riêng. */
function batchName(now, tag) {
    function two(value) { return value < 10 ? "0" + value : String(value) }
    return S.s_tai_len_e3c941d6 + two(now.getDate()) + "-" + two(now.getMonth() + 1) + "-" + now.getFullYear() + " " + two(now.getHours()) + "h" + two(now.getMinutes()) + " " + tag
}

/**
 * Những gì sẽ gửi, theo đúng cách trình tạo sách đọc một đường dẫn: file lẻ vào thư mục của lần gửi; chọn cả thư mục thì chỉ lấy file nằm ngay trong nó
 * (tên thư mục còn nguyên - máy gợi ý nó làm tên sách); nếu nó chỉ có thư mục con thì mỗi thư mục con thành một tập. `files`: [{name, size, path}],
 * `path` = "Truyện/Tập 1/001.txt" khi chọn cả thư mục, "" khi là file lẻ.
 */
function planUpload(files, batch) {
    const plan = {groups: [], rejected: [], tooBig: [], ignored: 0, bytes: 0}
    const loose = []
    const roots = {}
    const rootOrder = []
    for (const file of files) {
        const parts = String(file.path || "").split("/").filter(Boolean)
        const inFolder = parts.length > 1
        if (!ACCEPTED.test(file.name) || parts.length > 3) {
            if (inFolder) plan.ignored += 1
            else plan.rejected.push(file.name)
            continue
        }
        if (file.size > UPLOAD_LIMIT) { plan.tooBig.push(file.name); continue }
        if (!inFolder) { loose.push(file); continue }
        if (!roots[parts[0]]) { roots[parts[0]] = {top: [], subs: {}, subOrder: []}; rootOrder.push(parts[0]) }
        const root = roots[parts[0]]
        if (parts.length === 2) root.top.push(file)
        else {
            if (!root.subs[parts[1]]) { root.subs[parts[1]] = []; root.subOrder.push(parts[1]) }
            root.subs[parts[1]].push(file)
        }
    }
    if (loose.length) plan.groups.push({folder: batch, files: loose.sort(byName), loose: true})
    rootOrder.sort(naturalCompare)
    for (const name of rootOrder) {
        const root = roots[name]
        if (root.top.length) {
            plan.groups.push({folder: batch + "/" + name, files: root.top.sort(byName), loose: false})
            for (const sub of root.subOrder) plan.ignored += root.subs[sub].length
            continue
        }
        for (const sub of root.subOrder.sort(naturalCompare)) plan.groups.push({folder: batch + "/" + name + "/" + sub, files: root.subs[sub].sort(byName), loose: false})
    }
    plan.bytes = plan.groups.reduce(function(sum, group) { return sum + group.files.reduce(function(total, file) { return total + file.size }, 0) }, 0)
    return plan
}
function listed(names) {
    const shown = names.slice(0, 3).map(function(name) { return "“" + name + "”" }).join(", ")
    return names.length > 3 ? shown + S.s_va_79e3d3b1 + (names.length - 3) + S.s_file_khac_c25fd437 : shown
}
/** Lời nhắc về những file không gửi (nói ra, không bỏ âm thầm), hay "" khi không bỏ file nào. */
function planNotice(plan) {
    const lines = [
        plan.rejected.length ? listed(plan.rejected) + S.s_khong_phai_file_truyen_chi_nhan_txt_epub_d_064d09e9 : "",
        plan.tooBig.length ? listed(plan.tooBig) + S.s_lon_hon_5354650d + LIMIT_MB + S.s_mb_nen_khong_gui_qua_mang_duoc_ban_hay_tac_835a3c8c : ""
    ].filter(Boolean)
    return lines.join(" ")
}
function planFileCount(plan) { return plan.groups.reduce(function(sum, group) { return sum + group.files.length }, 0) }
/** "Đang gửi 3/12 file · 1,2 MB / 4,5 MB". */
function progressLabel(progress) {
    return S.s_dang_gui_231b5be2 + progress.files + "/" + progress.totalFiles + " file\u00a0·\u00a0" + Size.formatSize(progress.bytes) + " / " + Size.formatSize(progress.totalBytes)
}
/** "Đã gửi 3/12 file, giữ lại; 9 file chưa gửi." - nói rõ gì đã tới máy tính khi dừng giữa chừng. */
function sendSummary(result) {
    if (!result.sent) return S.s_chua_gui_file_nao_17f3f72a
    const rest = result.total - result.sent
    return S.s_da_gui_b15ba101 + result.sent + "/" + result.total + S.s_file_giu_lai_2e9078e4 + (rest > 0 ? "; " + rest + S.s_file_chua_gui_81d25852 : "") + "."
}
