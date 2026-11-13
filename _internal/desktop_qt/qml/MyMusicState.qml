import "UiStrings.js" as S
import QtQuick
import ABook

// Ba trạng thái của vùng danh sách "Nhạc của tôi" (MotionRegion của MyMusicSection): đang tải (ContentSkeleton 2 hàng), lỗi tải (InlineError) và
// chưa có bài nào (EmptyState + nút thêm). Mỗi trạng thái mở / khép tại chỗ; không có gì thì vùng cao 0.
Column {
    id: root
    property string state: "ready"      // "loading" | "error" | "empty" | "ready"
    property bool adding: false
    // Studio (MyMusic của studio/MusicTab.tsx) mời "Thêm nhạc của bạn" + nút chính "Nhập nhạc"; Cài đặt giữ câu của mình
    property string emptyTitle: S.s_chua_co_bai_nao_c1c708be
    property string addText: S.s_them_nhac_cua_ban_dbd7d8c4
    property string addKind: "ghost"
    signal retry()
    signal add()

    // ---- đang tải: hai hàng khung chờ (ô 40 + hai vạch 12), nhấp nháy nhẹ ----
    Collapse {
        width: parent.width
        open: root.state === "loading"
        Column {
            id: skeleton
            width: parent.width
            spacing: 16
            Accessible.role: Accessible.StaticText
            Accessible.name: S.s_dang_tai_nhac_rieng_144f69a2
            property real pulse: 1
            SequentialAnimation on pulse {
                running: root.state === "loading" && Nav.uiVisible && !Theme.reduceMotion
                loops: Animation.Infinite
                NumberAnimation { to: Theme.skeletonLow; duration: Theme.skeletonHalf; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1; duration: Theme.skeletonHalf; easing.type: Easing.InOutSine }
            }
            Repeater {
                model: 2
                Item {
                    width: skeleton.width
                    height: 40
                    opacity: skeleton.pulse
                    Rectangle { width: 40; height: 40; radius: Theme.radiusControl; color: Theme.line }
                    Rectangle { x: 52; y: 6; width: (parent.width - 52) * 0.75; height: 12; radius: Theme.radiusControl; color: Theme.line }
                    Rectangle { x: 52; y: 26; width: (parent.width - 52) * 0.5; height: 12; radius: Theme.radiusControl; color: Theme.line }
                }
            }
        }
    }

    // ---- lỗi tải ----
    InlineError {
        objectName: "myMusicError"
        width: parent.width
        open: root.state === "error"
        message: S.s_ban_hay_thu_tai_lai_nhac_cua_ban_f18be139
        onRetry: root.retry()
    }

    // ---- chưa có bài nào ----
    Collapse {
        width: parent.width
        open: root.state === "empty"
        Column {
            width: parent.width
            topPadding: 24
            bottomPadding: 24
            spacing: 0
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 56; height: 56
                radius: Theme.radiusCover
                color: Theme.accentSoft
                Icon { anchors.centerIn: parent; name: "eighth-note"; size: 28; color: Theme.accentText }
            }
            Item { width: 1; height: 16 }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: root.emptyTitle
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBody
                font.weight: Theme.weightMedium
            }
            Item { width: 1; height: 20 }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.addText; icon: "upload"; kind: root.addKind
                busy: root.adding
                onActivated: root.add()
            }
        }
    }
}
