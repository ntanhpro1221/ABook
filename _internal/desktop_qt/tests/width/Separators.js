.pragma library

// Máy dò dấu ngăn ở mép dòng (Lead soát 0.4.151, cột tiến độ Studio: "·" mở đầu dòng 2; soát gallery 01-11: "Thành Phố Sương Mù ·"
// treo cuối dòng ở thanh bên). Như luật LINE BREAK của web, dấu ngăn "·" không bao giờ đứng đầu hay cuối dòng: chuỗi ghép dùng
// "\u00a0·\u00a0" (dấu dính cả hai mảnh), tên sách / chữ tự do qua TextWrap.keepDots. Bốn dạng lỗi trên mọi cảnh đã dựng:
// (1)/(2) một Text xuống dòng mà dòng thứ 2 trở đi mở đầu bằng "·", hay một dòng trước dòng cuối kết thúc bằng "·" (đọc các dòng Qt
// đã dàn qua `probe`, tức qtVisualReady.lines);
// (3) một Text bắt đầu bằng "·" đứng đầu hàng của Flow (Flow là chuỗi khúc không gãy, dấu ngăn phải đi cuối khúc trước);
// (4) một khúc Flow kết thúc bằng "·" mà khúc sau bị đẩy xuống hàng mới (dấu treo cuối hàng; FlowDetail dắt dấu ở đầu khúc sau và bỏ
// dấu khi khúc ấy mở hàng).

function shown(item) { return item.visible && item.opacity > 0.01 && item.width > 0 && item.height > 0 }
function opensWithDot(text) { return String(text).replace(/^[\s\u00a0\u2028]+/, "").charAt(0) === "·" }
function closesWithDot(text) { const t = String(text).replace(/[\s\u00a0\u2028]+$/, ""); return t.charAt(t.length - 1) === "·" }
function label(item) { return item.objectName || String(item.text).slice(0, 60) }

function scan(root, probe) {
    const hits = []
    function walk(item) {
        if (!shown(item)) return
        if (typeof item.text === "string" && item.paintedWidth !== undefined && item.text.indexOf("·") >= 0) {
            const lines = probe.lines(item)
            for (let k = 0; k < lines.length; ++k) {
                if (k > 0 && opensWithDot(lines[k].text)) hits.push({rule: "dot-starts-line", text: label(item), line: k + 1})
                if (k < lines.length - 1 && closesWithDot(lines[k].text)) hits.push({rule: "dot-ends-line", text: label(item), line: k + 1})
            }
            // khúc thứ hai trở đi mà nằm ở mép trái Flow = Flow đã xuống hàng ngay trước dấu ngăn
            if (item.parent && /^QQuickFlow(_|\()/.test(String(item.parent)) && item.x < 1 && opensWithDot(item.text)
                    && item.parent.children.indexOf(item) > 0)
                hits.push({rule: "dot-starts-flow-row", text: label(item)})
            // khúc kết thúc bằng dấu mà khúc hiện sau nó nằm ở hàng dưới = dấu treo cuối hàng
            if (item.parent && /^QQuickFlow(_|\()/.test(String(item.parent)) && closesWithDot(item.text)) {
                const siblings = item.parent.children.filter(shown)
                const next = siblings[siblings.indexOf(item) + 1]
                if (next && next.y > item.y + item.height / 2) hits.push({rule: "dot-ends-flow-row", text: label(item)})
            }
        }
        for (const child of item.children || []) walk(child)
    }
    walk(root)
    return hits
}

function assertClean(test, root, probe) {
    const hits = scan(root, probe)
    if (hits.length) console.log("SEPARATOR_HITS " + JSON.stringify(hits))
    test.verify(hits.length === 0, "dấu ngăn đứng đầu hay cuối dòng: " + JSON.stringify(hits))
}
