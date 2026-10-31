import QtQuick
import ABook

// Icon đứng trước / sau một Text anh em, ngay giữa DÒNG ĐẦU của Text ấy: chữ gãy bao nhiêu dòng, lineHeight bao nhiêu cũng vậy. Qt đặt chữ
// ở ĐỈNH mỗi ô dòng và cao đúng một dòng tự nhiên của phông (lineHeight tỉ lệ hay cố định đều dồn phần dư xuống dưới - đo 31-10), nên tâm
// dòng đầu = đỉnh chữ + nửa dòng phông. Thay mọi `y: 3` đặt tay cạnh câu; máy dò IconText bắt lệch quá 2 px. `line` phải cùng cha với icon.
Icon {
    id: root
    property Item line
    FontMetrics { id: metrics; font: root.line ? root.line.font : Qt.font({}) }
    y: line ? line.y + line.topPadding + (metrics.height - size) / 2 : 0
}
