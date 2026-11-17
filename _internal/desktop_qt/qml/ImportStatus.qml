import "UiStrings.js" as S
import QtQuick
import ABook

// Lượt thêm sách của máy chủ khi hộp "Thêm sách" đã đóng (Api.importJobs, import_jobs.py) - ImportNotice ở thanh bên của web, thông báo của điện thoại:
// đang chạy thì vạch nhạc nhảy + "Đang thêm sách" + tên file; lỗi hay dở (app đóng giữa chừng) thì lý do, "Thử lại" và "Đóng". Hàng vào / ra bằng Collapse.
Column {
    id: root
    spacing: Theme.s4
    Repeater {
        model: Api.importRows
        delegate: Item {
            id: row
            required property var modelData
            readonly property bool running: modelData.state === "running"
            width: root.width
            height: Math.max(Theme.hit, texts.implicitHeight + 8)
            // Hàng mới hiện dần, không bật cứng (khối cả cụm đã gấp / mở bằng Collapse ở thanh bên)
            opacity: 0
            Component.onCompleted: opacity = 1
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionMedium } }
            Accessible.role: Accessible.StaticText
            Accessible.name: title.text + ". " + note.text
            Item {
                id: mark
                width: 16; height: 16
                anchors.verticalCenter: parent.verticalCenter
                Vu {
                    anchors.centerIn: parent
                    width: 12; height: 10; barWidth: 2; gap: 1
                    color: Theme.accent
                    opacity: row.running ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
                Icon {
                    anchors.centerIn: parent
                    name: "circle-alert"; size: 14; color: Theme.danger
                    opacity: row.running ? 0 : 1
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
            }
            Column {
                id: texts
                x: mark.width + Theme.s12
                width: parent.width - x - (row.running ? 0 : actions.width + Theme.s4)
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    id: title
                    width: parent.width
                    text: row.running ? S.s_import_running_title : S.s_chua_them_duoc_sach_b327e086
                    color: Theme.text
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Font.Medium
                    wrapMode: Text.Wrap
                }
                Text {
                    id: note
                    width: parent.width
                    text: row.modelData.state === "interrupted" ? S.s_import_interrupted
                        : row.modelData.state === "failed" && row.modelData.problem ? row.modelData.problem : row.modelData.name
                    color: Theme.text2
                    font.pixelSize: Theme.sizeCaption
                    wrapMode: Text.Wrap
                }
            }
            Row {
                id: actions
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                opacity: row.running ? 0 : 1
                enabled: !row.running
                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                IconButton { width: Theme.hit; height: Theme.hit; icon: "rotate-ccw"; iconSize: 16; tip: S.s_thu_lai_c58d068c; onActivated: Api.retryImport(row.modelData.id) }
                IconButton { width: Theme.hit; height: Theme.hit; icon: "x"; iconSize: 16; tip: S.s_dong_5d54c2a1; onActivated: Api.dismissImport(row.modelData.id) }
            }
        }
    }
}
