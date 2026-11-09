.import "UiStrings.js" as S
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
    sleepMinutes: { min: 1, max: 240, step: 1, typical: [5, 10, 15, 30, 45, 60, 90], scale: [[0, 1], [0.5, 60], [0.75, 120], [1, 240]] },
    sleepChapters: { min: 1, max: 10, step: 1, typical: [1, 2, 3] },
    speed: { min: 0.5, max: 3, step: 0.05, typical: [0.8, 1, 1.25, 1.5, 2], scale: [[0, 0.5], [0.6, 1.5], [1, 3]] },
    readSize: { min: 12, max: 40, step: 1, typical: [16, 18, 20, 22, 24] },
    readLeading: { min: 1.2, max: 2.4, step: 0.05, typical: [1.5, 1.7, 1.9] },
    sleepFadeSeconds: { min: 5, max: 120, step: 5, typical: [10, 30, 60] },
    sleepExtendMinutes: { min: 1, max: 60, step: 1, typical: [5, 10, 15, 30] },
    scheduleMinutes: { min: 5, max: 240, step: 5, typical: [15, 30, 45, 60, 90] },
    volume: { min: 0, max: 100, step: 1, typical: [25, 50, 75, 100] },
    boost: { min: 0, max: 12, step: 1, typical: [0, 3, 6] },
    pitch: { min: -6, max: 6, step: 0.5, typical: [-2, 0, 2] },
    balance: { min: -100, max: 100, step: 1, typical: [-50, 0, 50] },
    silenceDb: { min: -80, max: -45, step: 1, typical: [-70, -60, -50] },
    silenceSeconds: { min: 2, max: 10, step: 0.5, typical: [3, 5] },
    keepSeconds: { min: 1.5, max: 3, step: 0.1, typical: [1.5, 2] },
    eqBand: { min: -12, max: 12, step: 1, typical: [-6, 0, 6] },
    bass: { min: 0, max: 12, step: 1, typical: [0, 4, 8] }
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
    return spec.scale || [[0, spec.min], [1, spec.max]]
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
    var decimals = decimalsOf(spec.step)
    var text = roundTo(value, decimals).toFixed(decimals)
    if (text.indexOf(".") >= 0) text = text.replace(/0+$/, "").replace(/\.$/, "")
    return text.replace(".", ",")
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
