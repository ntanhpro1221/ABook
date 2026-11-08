import "UiStrings.js" as S
import QtQuick
import ABook

// Hộp "Phím tắt" (ShortcutsHost của listen/Shortcuts.tsx): mở bằng phím "?" ở mọi màn (trừ khi đang gõ chữ), cùng danh sách với Cài đặt › Giao diện.
Modal {
    id: root
    objectName: "shortcutsDialog"
    property bool letters: true
    title: S.s_phim_tat_7baaed2f
    description: S.s_dung_duoc_o_moi_man_hinh_tru_khi_dang_go_c_6452e52d
    LookShortcuts { width: Math.min(parent.width, 448); letters: root.letters; inSettings: false }
}
