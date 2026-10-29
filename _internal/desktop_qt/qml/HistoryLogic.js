.pragma library
.import "CastLogic.js" as Cast
.import "EditBookLogic.js" as Edit

// Phần thuần của tab "Lịch sử" ở trang sách (HistoryTab của listen/BookScreen.tsx): ngày, giờ, gom lượt nghe theo ngày, tổng 7 ngày qua,
// "chương đã gỡ". Chữ giữ đúng từng chữ của bản web. `now` (mili giây) truyền vào để thử được; không truyền thì giờ máy.

var DAY = 86400
var WEEKDAYS = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"]

function startOfDay(date) { return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() }

// "Hôm nay", "Hôm qua", hay "Thứ Ba, 28/10" (toLocaleDateString("vi-VN", {weekday: "long", day: "numeric", month: "numeric"}))
function dayLabel(epoch, now) {
    const date = new Date(epoch * 1000)
    const today = new Date(now === undefined ? Date.now() : now)
    const days = Math.round((startOfDay(today) - startOfDay(date)) / 86400000)
    if (days === 0) return "Hôm nay"
    if (days === 1) return "Hôm qua"
    return WEEKDAYS[date.getDay()] + ", " + date.getDate() + "/" + (date.getMonth() + 1)
}

// "13:57" (toLocaleTimeString("vi-VN", {hour: "2-digit", minute: "2-digit"}))
function clockOf(epoch) {
    const date = new Date(epoch * 1000)
    return String(date.getHours()).padStart(2, "0") + ":" + String(date.getMinutes()).padStart(2, "0")
}

// Cùng phút thì một mốc giờ, không "13:57-13:57"
function timeRange(item) {
    const from = clockOf(item.startedAt), to = clockOf(item.endedAt)
    return from === to ? from : from + "-" + to
}

function formatClock(seconds) { return Edit.formatClock(seconds) }
function formatLength(seconds) { return Cast.formatLength(seconds) }

// Dòng chính của một lượt nghe: "13:57-14:20 · 23 phút"
function headline(item) { return timeRange(item) + " · " + formatLength(item.listened) }

function titleOf(chapters, chapterId) {
    const found = (chapters || []).filter(chapter => chapter.id === chapterId)[0]
    return found ? found.title : "chương đã gỡ"
}

// "Chương 3 12:04 → Chương 4 0:20"
function where(item, chapters) {
    return titleOf(chapters, item.from.chapterId) + " " + formatClock(item.from.seconds) + " → " + titleOf(chapters, item.to.chapterId) + " " + formatClock(item.to.seconds)
}

// Nút nhảy tới CUỐI phiên nghe ấy
function resumeLabel(item) { const at = formatClock(item.to.seconds); return "Nghe tiếp từ " + at }

// Số giây nghe trong 7 ngày qua
function weekListened(sessions, now) {
    const seconds = (now === undefined ? Date.now() : now) / 1000
    return (sessions || []).filter(item => seconds - item.startedAt < 7 * DAY).reduce((sum, item) => sum + item.listened, 0)
}

// Mới nhất trước, gom theo nhãn ngày giữ thứ tự gặp: [{day, items}]
function groupByDay(sessions, now) {
    const groups = []
    const byDay = {}
    for (const item of (sessions || []).slice().reverse()) {
        const key = dayLabel(item.startedAt, now)
        if (!byDay[key]) { byDay[key] = {day: key, items: []}; groups.push(byDay[key]) }
        byDay[key].items.push(item)
    }
    return groups
}

function groupSummary(group) { return group.items.length + " lượt nghe" }
