.pragma library
.import "CastLogic.js" as Cast

// Công tắc B "Nhân vật tự kể" (studio/tellerMode.ts, TellerModeSwitch.tsx, NarratorNote của ProjectScreen.tsx; webui/teller_mode.py): chữ và phép tính cái giá, chép từng chữ.

var TITLE = "Nhân vật tự kể"
// Câu thay cho nút đổi ở nơi không đổi được (điện thoại mở file dự án)
var ELSEWHERE = "Đổi ở máy tính có Studio (cần thu lại)."
// Sách đang chạy: Tạm dừng chưa đủ (máy vẫn giữ sách), phải “Dừng”
var BUSY_NOTE = "Dừng sau phân tích để đổi, rồi Tiếp tục; Tạm dừng chưa đủ."

function hint(on) {
    return on ? "Nhân vật xưng “tôi” đọc cả lời kể bằng giọng mình." : "Giọng dẫn đọc lời kể; nhân vật chỉ đọc lời thoại."
}
// Có cần hỏi lại trước khi đổi không: chỉ khi đã có câu thu sẽ bị bỏ
function needsConfirm(view) { return Boolean(view && view.castLocked && view.plan && view.plan.recorded > 0) }
// Cái giá của lần đổi, nói như người nghe thấy
function costText(plan, turningOn) {
    if (!plan || !plan.lines) return turningOn ? "Chưa có câu lời kể nào cần đổi giọng." : "Không còn câu nào để trả lại giọng dẫn."
    const who = plan.tellers && plan.tellers.length ? plan.tellers.join(", ") : "người kể"
    const what = turningOn
        ? Cast.formatNumber(plan.lines) + " câu lời kể sẽ đọc bằng giọng của " + who
        : Cast.formatNumber(plan.lines) + " câu lời kể sẽ trở về giọng dẫn"
    if (!plan.recorded) return what + ". Chưa câu nào trong số đó được thu nên không phải thu lại gì."
    return what + ". " + Cast.formatNumber(plan.recorded) + " bản thu hiện có của những câu ấy sẽ bị bỏ và thu lại, " + Cast.estimateText(plan.seconds, plan.measured) + ". Bản thu cũ không lấy lại được."
}
function confirmTitle(asking) { return asking === "teller" ? "Bật giọng tự kể?" : "Dùng giọng dẫn?" }
function confirmAction(asking) { return asking === "teller" ? "Bật và thu lại" : "Tắt và thu lại" }
// Lời báo sau khi đổi xong: chỉ nhắc thu lại khi có bản thu bị bỏ
function savedNote(view, recorded) {
    if (!(view.castLocked && view.mode === "teller" && view.applied)) return ""
    return recorded > 0 ? "Đã đổi - bấm “Tiếp tục” để thu lại những câu đổi giọng" : "Đã đổi - những câu đổi giọng sẽ được thu bằng giọng mới"
}

// NarratorNote: dưới hàng "Người kể chuyện" của tab Nhân vật. Cuốn chưa chạy: đổi qua "Sửa thiết lập"; đã phân vai: nút ở hàng ấy; đang phân tích: nói khi nào đổi được.
function narratorNote(book) {
    if (book.phase === "idle") return {text: "Giọng kể chọn lúc tạo sách, đổi được vì cuốn này chưa bắt đầu chạy.", link: "Đổi giọng kể"}
    if (book.castLocked) return {text: "Đổi giọng kể không phải tạo lại sách: câu kể đã thu sẽ được thu lại bằng giọng mới.", link: ""}
    return {text: "Đổi được giọng kể khi máy phân vai xong (ngay sau bước phân tích truyện).", link: ""}
}
