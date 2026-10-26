import QtQuick
import ABook

// Hộp "Phím tắt" (ShortcutsHost của listen/Shortcuts.tsx): mở bằng phím "?" ở mọi màn (trừ khi đang gõ chữ), cùng danh sách với Cài đặt › Giao diện.
Modal {
    id: root
    objectName: "shortcutsDialog"
    property bool letters: true
    title: "Phím tắt"
    description: "Dùng được ở mọi màn hình, trừ khi đang gõ chữ."
    LookShortcuts { width: Math.min(parent.width, 448); letters: root.letters; inSettings: false }
}
