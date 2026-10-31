.pragma library

// Máy dò dấu ngăn đầu dòng (Lead soát 0.4.151, cột tiến độ Studio: "·" mở đầu dòng 2). Gãy dòng không bao giờ để dấu ngăn "·" đứng đầu
// dòng: chuỗi ghép dùng "\u00a0· " (dấu ngăn dính mảnh trước, chỉ gãy SAU dấu). Hai dạng lỗi trên mọi cảnh đã dựng:
// (1) một Text xuống dòng mà dòng thứ 2 trở đi mở đầu bằng "·" (đọc các dòng Qt đã dàn qua `probe`, tức qtVisualReady.lines);
// (2) một Text bắt đầu bằng "·" đứng đầu hàng của Flow (Flow là chuỗi khúc không gãy, dấu ngăn phải đi cuối khúc trước).

function shown(item) { return item.visible && item.opacity > 0.01 && item.width > 0 && item.height > 0 }
function opensWithDot(text) { return String(text).replace(/^[\s\u00a0\u2028]+/, "").charAt(0) === "·" }
function label(item) { return item.objectName || String(item.text).slice(0, 60) }

function scan(root, probe) {
    const hits = []
    function walk(item) {
        if (!shown(item)) return
        if (typeof item.text === "string" && item.paintedWidth !== undefined && item.text.indexOf("·") >= 0) {
            const lines = probe.lines(item)
            for (let k = 1; k < lines.length; ++k)
                if (opensWithDot(lines[k].text)) hits.push({rule: "dot-starts-line", text: label(item), line: k + 1})
            // khúc thứ hai trở đi mà nằm ở mép trái Flow = Flow đã xuống hàng ngay trước dấu ngăn
            if (item.parent && /^QQuickFlow(_|\()/.test(String(item.parent)) && item.x < 1 && opensWithDot(item.text)
                    && item.parent.children.indexOf(item) > 0)
                hits.push({rule: "dot-starts-flow-row", text: label(item)})
        }
        for (const child of item.children || []) walk(child)
    }
    walk(root)
    return hits
}

function assertClean(test, root, probe) {
    const hits = scan(root, probe)
    if (hits.length) console.log("SEPARATOR_HITS " + JSON.stringify(hits))
    test.verify(hits.length === 0, "dấu ngăn đứng đầu dòng: " + JSON.stringify(hits))
}
