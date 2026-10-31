.pragma library

// Máy dò chữ mồ côi (Lead soát 0.4.151 lượt 2: "Bạn hãy thử tải lại tiến / độ." ở thanh bên 232 px). Câu xuống dòng thì dòng cuối
// không được chỉ còn một từ ngắn (<= 4 ký tự, không kể dấu câu) trong khi dòng trên dài. Đọc các dòng Qt đã dàn qua `probe`
// (qtVisualReady.lines); dòng cuối mở đầu một đoạn (xuống dòng cứng, khối RichText mới) thì không tính. Từ nối bằng NBSP là một từ.

const SHORT = 4
const LONG = 12

function shown(item) { return item.visible && item.opacity > 0.01 && item.width > 0 && item.height > 0 }
function trimmed(text) { return String(text).replace(/^[\s\u2028]+|[\s\u2028]+$/g, "") }
function label(item) { return item.objectName || String(item.text).slice(0, 60) }
// Nơi đặt chữ: các kiểu QML có tên từ chữ lên (bỏ kiểu nền QQuick*), để tìm ra thành phần cần sửa
function where(item) {
    const names = []
    for (let at = item; at && names.length < 4; at = at.parent) {
        const name = String(at).replace(/(_QMLTYPE_\d+|_QML_\d+)?\(0x[0-9a-fA-F]+.*$/, "")
        if (!/^QQuick/.test(name) && names[names.length - 1] !== name) names.push(name)
    }
    return names.join("<")
}

function orphan(lines) {
    if (lines.length < 2) return null
    const last = lines[lines.length - 1], before = lines[lines.length - 2]
    if (last.block !== before.block || /[\n\u2028]\s*$/.test(before.text)) return null    // đoạn mới, không phải phần đuôi gãy xuống
    const word = trimmed(last.text)
    if (word === "" || /\s/.test(word.replace(/\u00a0/g, ""))) return null                 // còn từ hai từ trở lên
    const core = word.replace(/^[(“"'«]+|[.,;:!?…)”"'»]+$/g, "")
    if (core.length === 0 || core.length > SHORT || trimmed(before.text).length < LONG) return null
    // Phần trước chỉ một từ: không còn chỗ ngắt nào để dời (TextWrap.pretty cũng để nguyên) - không phải lỗi sửa được
    if (trimmed(lines.slice(0, -1).map(line => line.text).join("")).indexOf(" ") < 0) return null
    return word
}

function scan(root, probe) {
    const hits = []
    function walk(item) {
        if (!shown(item)) return
        // Chỉ chữ hiển thị (Text): ô nhập là chữ người dùng gõ
        if (typeof item.text === "string" && item.paintedWidth !== undefined && item.lineCount > 1 && item.cursorPosition === undefined) {
            const word = orphan(probe.lines(item))
            if (word !== null) hits.push({rule: "orphan", text: label(item), last: word, at: where(item)})
        }
        for (const child of item.children || []) walk(child)
    }
    walk(root)
    return hits
}

function assertClean(test, root, probe) {
    const hits = scan(root, probe)
    if (hits.length) console.log("ORPHAN_HITS " + JSON.stringify(hits))
    test.verify(hits.length === 0, "chữ mồ côi ở dòng cuối: " + JSON.stringify(hits))
}

function report(root, probe) {
    const hits = scan(root, probe)
    if (hits.length) console.log("ORPHAN_HITS " + JSON.stringify(hits))
}
