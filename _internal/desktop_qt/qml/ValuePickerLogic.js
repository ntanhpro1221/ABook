.import "UiStrings.js" as S
.import "UiNumber.js" as UiNumber
.pragma library

// Bộ chọn giá trị số - phần tính toán. MỘT hợp đồng cho ba nền (tests/fixtures/value_picker/cases.json): web shared/valuePickerLogic.ts,
// Android ui/components/ValuePickerLogic.kt. Luật DESIGN mục 6 "Chọn giá trị": mọi giá trị số = chip tiêu biểu + chọn tự do
// (kéo thước, -/+ một bước, gõ số). tst_value_picker.qml chạy đúng các ca của file chung và so bảng `specs` với `SPECS` dưới đây.

// Nấc hút: giá trị tiêu biểu "rộng" thêm chừng này bước khi kéo - đủ để dừng đúng nấc mà không nuốt bước kề.
var SNAP_STEPS = 0.75
// PageUp / PageDown đổi chừng này bước.
var PAGE_STEPS = 10

// Miền của một giá trị: biên, bước, giá trị tiêu biểu (chip một chạm, nấc hút khi kéo), thang của thước (mốc [vị trí 0..1, giá trị]).
var SPECS = {
    sleepMinutes: { min: 1, max: 240, step: 1, typical: [5, 15, 30, 45, 60, 90] },
    sleepChapters: { min: 1, max: 10, step: 1, typical: [1, 2, 3] },
    speed: { min: 0.5, max: 3, step: 0.05, typical: [0.8, 1, 1.25, 1.5, 2], scale: [[0, 0.5], [0.12, 0.8], [0.3, 1], [0.48, 1.25], [0.66, 1.5], [0.84, 2], [1, 3]] },
    readSize: { min: 12, max: 40, step: 1, typical: [16, 18, 20, 22, 24] },
    readLeading: { min: 1.2, max: 2.4, step: 0.05, typical: [1.5, 1.7, 1.9] },
    sleepFadeSeconds: { min: 5, max: 120, step: 5, typical: [10, 30, 60] },
    sleepExtendMinutes: { min: 1, max: 60, step: 1, typical: [5, 10, 15, 30] },
    scheduleMinutes: { min: 5, max: 240, step: 5, typical: [15, 30, 45, 60, 90] },
    voice: { min: 0, max: 200, step: 5, typical: [50, 100, 150, 200] },
    pitch: { min: -6, max: 6, step: 0.5, typical: [-2, 0, 2] },
    balance: { min: -100, max: 100, step: 1, typical: [-50, 0, 50] },
    silenceDb: { min: -80, max: -45, step: 1, typical: [-70, -60, -50] },
    silenceSeconds: { min: 2, max: 10, step: 0.5, typical: [3, 5] },
    keepSeconds: { min: 1.5, max: 3, step: 0.1, typical: [1.5, 2] }
}

function decimalsOf(step) {
    var text = String(step)
    var dot = text.indexOf(".")
    return dot < 0 ? 0 : text.length - dot - 1
}

function roundTo(value, decimals) {
    var factor = Math.pow(10, decimals)
    var result = Math.round(value * factor) / factor
    return result === 0 ? 0 : result   // bỏ -0
}

// Kẹp vào biên rồi về lưới min + n*step.
function quantize(spec, value) {
    var decimals = Math.max(decimalsOf(spec.step), decimalsOf(spec.min))
    var clamped = Math.min(spec.max, Math.max(spec.min, value))
    var result = roundTo(spec.min + Math.round((clamped - spec.min) / spec.step) * spec.step, decimals)
    if (result > spec.max) result = roundTo(result - spec.step, decimals)
    return result
}

function clampValue(spec, value) {
    return { value: quantize(spec, value), clamped: value < spec.min || value > spec.max }
}

function stepValue(spec, value, steps) {
    return quantize(spec, quantize(spec, value) + steps * spec.step)
}

function scaleOf(spec) {
    var crowded = spec.typical.some(function(v, i) { return i > 0 && (v - spec.typical[i - 1]) / (spec.max - spec.min) < 0.12 })
    if (!spec.scale && (spec.min > 0 && spec.max / spec.min >= 8 || crowded) && spec.typical.length > 1) {
        var inner = spec.typical.filter(function(v) { return v > spec.min && v < spec.max })
        var first = spec.typical[0] === spec.min ? 0.9 / inner.length : 0.1
        return [[0, spec.min]].concat(inner.map(function(v, i) { return [first + (0.9 - first) * i / Math.max(1, inner.length - 1), v] }), [[1, spec.max]])
    }
    return spec.scale || [[0, spec.min], [1, spec.max]]
}

// Labels under the ruler are captions of its detents: label i is centred on detent i, so the track inset grows until
// every label stays inside the ruler (never under the -/+ buttons). `aligned` false = the labels cannot sit under their
// detents without touching (`gap`) - then the ruler draws no detents and the labels fall back to rows.
function tickLabels(fractions, widths, total, minInset, gap) {
    var EPSILON = 1e-6
    var inset = minInset
    for (var i = 0; i < fractions.length; i++) {
        var f = fractions[i], half = widths[i] / 2
        if (f < 0.5) inset = Math.max(inset, (half - f * total) / (1 - 2 * f))
        if (f > 0.5) inset = Math.max(inset, (half - (1 - f) * total) / (2 * f - 1))
    }
    var width = total - 2 * inset
    var aligned = width > 0
    for (var j = 0; j < fractions.length; j++) {
        var c = inset + fractions[j] * width
        if (c - widths[j] / 2 < -EPSILON || c + widths[j] / 2 > total + EPSILON) aligned = false
        if (j > 0 && c - (inset + fractions[j - 1] * width) + EPSILON < (widths[j] + widths[j - 1]) / 2 + gap) aligned = false
    }
    return { inset: inset, aligned: aligned }
}

// Narrowest ruler whose labels still sit under their detents (hosts size popovers with it); 0 when nothing fits below 2000.
function minAlignedWidth(fractions, widths, minInset, gap) {
    if (!tickLabels(fractions, widths, 2000, minInset, gap).aligned) return 0
    var lo = 0, hi = 2000
    while (hi - lo > 0.5) {
        var mid = (lo + hi) / 2
        if (tickLabels(fractions, widths, mid, minInset, gap).aligned) hi = mid; else lo = mid
    }
    return Math.ceil(hi)
}

function chipRows(widths, available, gap) {
    for (var rows = 1; rows <= widths.length; rows++) {
        var groups = [], start = 0, fits = true
        for (var row = 0; row < rows; row++) {
            var count = Math.floor(widths.length / rows) + (row < widths.length % rows ? 1 : 0)
            var group = [], total = gap * (count - 1)
            for (var i = 0; i < count; i++) { group.push(start); total += widths[start++] }
            if (total > available) fits = false
            groups.push(group)
        }
        if (fits) return groups
    }
    return widths.map(function(_, i) { return [i] })
}

// Giá trị thô (chưa về lưới) ở vị trí `fraction` của thước.
function rawAt(spec, fraction) {
    var scale = scaleOf(spec)
    var f = Math.min(1, Math.max(0, fraction))
    for (var i = 1; i < scale.length; i++) {
        var f0 = scale[i - 1][0], v0 = scale[i - 1][1], f1 = scale[i][0], v1 = scale[i][1]
        if (f <= f1 || i === scale.length - 1) return v0 + ((f - f0) / (f1 - f0)) * (v1 - v0)
    }
    return spec.max
}

// Giá trị khi kéo tới `fraction`: hút về giá trị tiêu biểu gần (nấc), không thì về lưới.
function fromFraction(spec, fraction) {
    var raw = rawAt(spec, fraction)
    var nearest = null
    for (var i = 0; i < spec.typical.length; i++)
        if (nearest === null || Math.abs(spec.typical[i] - raw) < Math.abs(nearest - raw)) nearest = spec.typical[i]
    if (nearest !== null && Math.abs(nearest - raw) <= SNAP_STEPS * spec.step) return nearest
    return quantize(spec, raw)
}

// Vị trí 0..1 của `value` trên thước.
function toFraction(spec, value) {
    var scale = scaleOf(spec)
    var v = Math.min(spec.max, Math.max(spec.min, value))
    for (var i = 1; i < scale.length; i++) {
        var f0 = scale[i - 1][0], v0 = scale[i - 1][1], f1 = scale[i][0], v1 = scale[i][1]
        if (v <= v1 || i === scale.length - 1) return f0 + ((v - v0) / (v1 - v0)) * (f1 - f0)
    }
    return 1
}

// Chữ người gõ: null khi không ra số (giữ giá trị cũ).
function parseValue(spec, text) {
    var cleaned = String(text).replace(/[^0-9,.-]/g, "").replace(/,/g, ".")
    if (!cleaned) return null
    var parsed = Number(cleaned)
    if (!isFinite(parsed)) return null
    return clampValue(spec, parsed)
}

function chipIndex(spec, value) {
    for (var i = 0; i < spec.typical.length; i++)
        if (Math.abs(spec.typical[i] - value) < spec.step / 2) return i
    return -1
}

// Rung / tiếng nấc: vừa tới một giá trị tiêu biểu.
function isDetent(spec, previous, next) {
    return next !== previous && chipIndex(spec, next) >= 0
}

// Số kiểu Việt: "1,35", "1,5", "1".
function formatNumber(spec, value) {
    return UiNumber.decimal(roundTo(value, decimalsOf(spec.step)), decimalsOf(spec.step))
}

// Bản kẹp trần thấp hơn ("Giữ khoảng nghỉ" không quá "Dài tối thiểu").
function capped(spec, top) {
    var max = Math.min(spec.max, top)
    return { min: spec.min, max: max, step: spec.step, typical: spec.typical.filter(function(v) { return v <= max }), scale: spec.scale }
}

// Số giây kiểu người đọc: "45 giây", tròn phút thì "1 phút", "2 phút".
function secondsLabel(seconds) {
    return seconds >= 60 && seconds % 60 === 0 ? S.s_0_phut_2596d212(seconds / 60) : S.s_0_giay_daac30d3(seconds)
}

function minutesLabel(minutes) {
    return S.s_0_phut_2596d212(minutes)
}
