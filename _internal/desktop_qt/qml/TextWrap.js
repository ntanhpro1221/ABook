.pragma library

// = text-wrap: pretty của bản web (styles.css: body, trừ mặt đọc chương): câu gãy dòng không để một từ ngắn rớt xuống dòng cuối
// một mình ("tải lại tiến / độ."). Qt không có thuộc tính ấy, nên từ cuối (<= 4 ký tự, không kể dấu câu) được nối với từ trước
// bằng NBSP - PlainText và StyledText qua `&nbsp;` đều giữ, hai từ xuống dòng cùng nhau. Mỗi dòng cứng xét riêng. Chỉ đổi chữ
// đem vẽ, không đổi chữ gốc (máy dò Orphans.js bắt chỗ còn sót). Như CSS, không bao giờ xoá chỗ ngắt cuối cùng: phần trước phải
// còn một dấu cách thường (>= 3 từ) - "Hồ Vy" ghép NBSP thì khung hẹp không còn chỗ xuống dòng, chữ tràn hay bẻ giữa từ.

const SHORT = 4

// = installKeepDots của bản web (DotJoin.tsx): dấu ngăn " · " có sẵn trong chữ tự do (tên sách "Thành Phố Sương Mù · Tập 2", tên chương)
// không bao giờ đứng đầu hay cuối dòng - khoảng trắng thường hai bên dấu thành NBSP. Chuỗi app tự ghép đã viết "\u00a0·\u00a0"; hàm này cho chữ
// đến từ dữ liệu. Cùng độ dài, chỉ đổi chữ đem vẽ (máy dò Separators.js bắt chỗ còn sót; lint test_qt_layout_lints.py bắt Text xuống dòng
// đọc tên / tiêu đề mà không qua đây).
function keepDots(text) {
    return String(text == null ? "" : text).replace(/ (?=·[ \u00a0])/g, "\u00a0").replace(/([ \u00a0]·) /g, "$1\u00a0")   // hai lượt thay lookbehind
}

function pretty(text) {
    return String(keepDots(text)).split("\n").map(function(line) {
        const tail = /^(.*\S) ([^\s\u00a0]+)(\s*)$/.exec(line)
        if (!tail || tail[1].indexOf(" ") < 0 || tail[2].replace(/^[(“"'«]+|[.,;:!?…)”"'»]+$/g, "").length > SHORT) return line
        return tail[1] + "\u00a0" + tail[2] + tail[3]
    }).join("\n")
}
