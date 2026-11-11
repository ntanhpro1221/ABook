// One rounded contour around the line rectangles, matching Compose and web.
function sentenceOutline(rects) {
    const lines = rects.filter(r => r.width > 0 && r.height > 0)
    if (!lines.length) return ""
    const points = [[lines[0].x - 4, lines[0].y]]
    lines.forEach((r, i) => points.push([r.x + r.width + 4, r.y], [r.x + r.width + 4, i + 1 < lines.length ? lines[i + 1].y : r.y + r.height]))
    const last = lines[lines.length - 1]
    points.push([last.x - 4, last.y + last.height])
    for (let i = lines.length - 1; i > 0; i--) points.push([lines[i].x - 4, lines[i].y], [lines[i - 1].x - 4, lines[i].y])
    const distinct = points.filter((p, i) => i === 0 || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1])
    const vertices = distinct.filter((p, i, a) => {
        const prev = a[(i + a.length - 1) % a.length], next = a[(i + 1) % a.length]
        return !((prev[0] === p[0] && next[0] === p[0]) || (prev[1] === p[1] && next[1] === p[1]))
    })
    const corners = vertices.map((p, i, a) => {
        const prev = a[(i + a.length - 1) % a.length], next = a[(i + 1) % a.length]
        const before = Math.hypot(prev[0] - p[0], prev[1] - p[1]), after = Math.hypot(next[0] - p[0], next[1] - p[1])
        const r = Math.min(8, before / 2, after / 2)
        return [p[0] + (prev[0] - p[0]) / before * r, p[1] + (prev[1] - p[1]) / before * r, p[0], p[1], p[0] + (next[0] - p[0]) / after * r, p[1] + (next[1] - p[1]) / after * r]
    })
    const end = corners[corners.length - 1]
    return "M" + end[4] + "," + end[5] + " " + corners.map(c => "L" + c[0] + "," + c[1] + " Q" + c[2] + "," + c[3] + " " + c[4] + "," + c[5]).join(" ") + " Z"
}
