import "UiStrings.js" as S
import QtQuick
import ABook
import "MusicLibraryLogic.js" as Logic

// Bài đi kèm sách (BundledTrackSheet của ui/src/music/BundledTrack.tsx): chỉ những gì book.json mang - tên, người sáng tác, câu "đi kèm sách"
// (không nghe thử, không lưu) và, khi đoạn đầu tiên dùng bài có cảm xúc cảnh (`mood` của GET /api/books/<id>/music/library), "Vì sao bài này"
// ở mức có dữ liệu: ba cảm xúc mạnh nhất của đoạn (bài không có điểm cảm xúc để so).
Modal {
    id: root
    objectName: "musicBundledDetail"
    property var track: null
    property var meta: null                 // /api/music/library/meta (nhãn)
    readonly property var mood: track && track.mood ? track.mood : []
    title: track ? track.title || S.s_bai_nay_d9683a01 : ""
    description: track ? track.creator || "" : ""
    panelWidth: 560

    function show(next) {
        track = next
        open = true
    }

    Column {
        width: root.bodyWidth
        spacing: Theme.s16
        MusicArt {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 160; height: 160
            track: root.track || ({})
        }
        Text {
            objectName: "musicBundledNote"
            width: parent.width
            text: S.s_bundled_track_note
            wrapMode: Text.Wrap
            color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
        }
        Column {
            id: why
            objectName: "musicBundledWhy"
            Reveal { shown: root.mood.length > 0 }
            width: parent.width
            spacing: Theme.s8
            Text { text: S.s_vi_sao_bai_nay_f681e004; color: Theme.text; font.pixelSize: Theme.sizeBody; font.weight: Theme.weightMedium }
            Text {
                objectName: "musicBundledMood"
                width: parent.width; wrapMode: Text.Wrap
                text: root.mood.length ? S.s_bundled_scene_mood(Logic.labelOf(root.meta ? root.meta.emotions : [], root.mood[0].id)) : ""
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
            Repeater {
                model: root.mood
                delegate: Item {
                    required property var modelData
                    objectName: "musicBundledEmotion"
                    width: why.width
                    height: Math.max(24, moodLabel.implicitHeight)
                    Text { id: moodLabel; width: 120; anchors.verticalCenter: parent.verticalCenter; text: Logic.labelOf(root.meta ? root.meta.emotions : [], modelData.id); color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
                    LevelBar {
                        x: 128; width: parent.width - 128 - Math.max(52, moodScore.implicitWidth + 8); height: 6
                        anchors.verticalCenter: parent.verticalCenter
                        score: modelData.score; ink: Theme.text3; label: moodLabel.text + ": " + S.s_doan_nay_82d01522
                    }
                    ClockLabel {
                        id: moodScore
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        text: S.s_percent(Logic.percent(modelData.score)); color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
                    }
                }
            }
        }
    }
}
