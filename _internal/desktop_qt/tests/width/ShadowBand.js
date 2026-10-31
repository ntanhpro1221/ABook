.pragma library

// Máy dò bóng bậc thang (Lead soát 0.4.151: bóng hộp thoại là các Rectangle đen mờ chồng nhau, thành dải có bậc): đi từ mép
// khung ra ngoài trên nền phẳng, độ tối so với nền xa phải GIẢM DẦN (không tăng lại quá 1 mức vì làm tròn) và không có bước nào
// nhảy quá maxStep mức (0-255) giữa hai px kề nhau. Bóng Gauss thật dốc nhất ở mép khung: ~1 mức/px với shadow-float.

function luminance(image, x, y) {
    const c = image.pixel(Math.round(x), Math.round(y))
    return (c.r + c.g + c.b) / 3 * 255
}

// Độ tối dọc tia từ (x, y) theo hướng (dx, dy), `length` px; nền lấy ở cuối tia (ngoài hẳn bóng).
function band(image, x, y, dx, dy, length) {
    const base = luminance(image, x + dx * (length + 8), y + dy * (length + 8))
    const out = []
    for (let i = 0; i < length; ++i) out.push(base - luminance(image, x + dx * i, y + dy * i))
    return out
}

// Trả về chuỗi rỗng nếu dải mượt, không thì lý do.
function problem(values, maxStep, minPeak) {
    const peak = Math.max.apply(null, values)
    if (peak < minPeak) return "không thấy bóng (tối nhất " + peak.toFixed(1) + " < " + minPeak + ")"
    for (let i = 1; i < values.length; ++i) {
        const step = values[i - 1] - values[i]
        if (step < -1) return "tối lại ở px " + i + " (" + values[i - 1].toFixed(1) + " -> " + values[i].toFixed(1) + ")"
        if (step > maxStep) return "bậc " + step.toFixed(1) + " mức ở px " + i + " (tối đa " + maxStep + ")"
    }
    return ""
}

// Hai tia của một khung: xuống từ giữa mép dưới, sang trái từ giữa mép trái. rect theo toạ độ ảnh.
function verdict(image, rect, length, maxStep, minPeak) {
    const down = band(image, rect.x + rect.width / 2, rect.y + rect.height + 1, 0, 1, length)
    const left = band(image, rect.x - 2, rect.y + rect.height / 2, -1, 0, length)
    const below = problem(down, maxStep, minPeak), side = problem(left, maxStep, 0)
    return below === "" && side === "" ? "" : "dưới " + (below || "ổn") + "; trái " + (side || "ổn")
                                              + " | dưới " + JSON.stringify(down.slice(0, 16).map(Math.round))
}

function check(test, image, rect, length, maxStep, minPeak, what) {
    const why = verdict(image, rect, length, maxStep, minPeak)
    test.verify(why === "", what + ": " + why)
}
