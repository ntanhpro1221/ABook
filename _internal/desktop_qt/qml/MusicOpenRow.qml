import "UiStrings.js" as S
import QtQuick
import ABook

// Lối sang màn "Nhạc" ở những chỗ từng chứa "Nhạc của tôi" (Studio › Nhạc nền, Cài đặt › Nghe, Nhạc nền của sách) - như OpenMusicRow của web:
// nhạc là nội dung, quản lý ở một chỗ (docs/DESIGN.md §7 "Nhạc"). Màn Nhạc là mục thứ tư của ngăn xếp gốc (Main.qml roots[3]).
DisclosureRow {
    id: root
    objectName: "openMusic"
    icon: "list-music"
    title: S.s_mo_nhac_c2f1b86b
    summary: S.s_nhac_cua_toi_f65b7ac6
    onClicked: if (Nav.stack) Nav.stack.show(3)
}
