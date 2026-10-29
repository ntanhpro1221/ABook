.pragma library

// Số và dung lượng kiểu Việt cho MỌI nhãn cỡ file của bản Qt (Cài đặt, Studio, giọng, nhạc, gửi sách): chép shared/format.ts formatSize của bản
// web - hệ 1024, dấu chấm ngăn nghìn, dấu phẩy thập phân (Intl vi-VN). Không file nào tự tính MB / GB riêng.

function groupThousands(whole) { return String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ".") }
// tối đa một chữ số thập phân, bỏ ",0" (Intl maximumFractionDigits: 1)
function decimal1(value) {
    const rounded = Math.round(value * 10) / 10
    const whole = Math.floor(rounded)
    const tenth = Math.round((rounded - whole) * 10)
    return groupThousands(whole) + (tenth ? "," + tenth : "")
}

// "850 MB", "3,2 GB"; dưới 10 MB một chữ số thập phân ("0,5 MB"), dưới 0,1 MB tính KB (ít nhất 1)
function formatSize(bytes) {
    if (bytes >= Math.pow(1024, 3)) return decimal1(bytes / Math.pow(1024, 3)) + " GB"
    const megabytes = bytes / Math.pow(1024, 2)
    if (megabytes < 0.1) return Math.max(1, Math.round(bytes / 1024)) + " KB"
    if (megabytes < 10) return decimal1(megabytes) + " MB"
    return groupThousands(Math.round(megabytes)) + " MB"
}
