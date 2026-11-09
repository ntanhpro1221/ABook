import "UiStrings.js" as S
import QtQuick
import ABook
import "PrecastLogic.js" as P

// Công tắc "Duyệt trước khi thu" của một cuốn (PrecastWaitSwitch của PrecastReview.tsx): ở trang dự án (trước mốc phân tích xong) và trên màn duyệt.
// Bật: dừng sau phân tích để bạn duyệt rồi bấm “Thu âm”. Đổi bằng PUT /precast {wait}; lỗi thì lời báo "Chưa đổi được".
Item {
    id: root
    objectName: "precastWait"
    property var store: null
    property var book: null
    property bool saving: false
    width: parent ? parent.width : 400
    height: row.implicitHeight

    SettingRow {
        id: row
        objectName: "precastWaitRow"
        width: parent.width
        label: S.s_duyet_truoc_khi_thu_74c121d0
        hint: root.book ? P.waitHint(root.book) : ""
        Switch {
            objectName: "precastWaitSwitch"
            label: S.s_duyet_truoc_khi_thu_74c121d0
            checked: !!root.book && !!root.book.precast && Boolean(root.book.precast.wait)
            enabled: !root.saving && !!root.store
            onToggled: value => {
                root.saving = true
                root.store.setPrecastWait(root.book.id, value, function() { root.saving = false })
            }
        }
    }
}
