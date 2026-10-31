import QtQuick
import ABook

// Hàng chọn khung giờ của "Lịch đêm" (nửa dưới của desktop/SleepSchedule.tsx): "[Từ] đến [Đến] hẹn [N phút]", mở / khép tại chỗ khi công tắc đổi
// (MotionPresence): chiều cao tween + vạch chia 1 px đi cùng. Giờ mỗi 15 phút (TimeSelect: giờ đã lưu lệch vẫn có trong danh sách), phút hẹn 15 / 30 / 45 / 60.
// Đang chờ máy chủ nhận (`locked`) thì ba ô mờ đi và không đổi được.
Item {
    id: root
    objectName: "sleepWindow"
    property var schedule: null         // {from, to, minutes} hay null
    property bool locked: false
    signal changed(var value)
    // Khép lại thì vẫn vẽ lịch cuối cùng cho tới khi khép xong (bản web: MotionPresence giữ con cuối)
    property var last: ({from: "22:00", to: "06:00", minutes: 30})
    onScheduleChanged: if (schedule) last = schedule
    implicitHeight: fold.height
    height: implicitHeight
    visible: fold.visible

    function times(value) {
        const list = []
        for (let hour = 0; hour < 24; ++hour)
            for (const minute of ["00", "15", "30", "45"]) list.push((hour < 10 ? "0" : "") + hour + ":" + minute)
        if (list.indexOf(value) < 0) { list.push(value); list.sort() }
        return list.map(time => ({value: time, label: time}))
    }
    readonly property var minuteOptions: [15, 30, 45, 60].map(minutes => ({value: minutes, label: minutes + " phút"}))

    Collapse {
        id: fold
        width: root.width
        open: Boolean(root.schedule)
        Item {
            width: parent.width
            height: flow.height + 24 + 1
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            Flow {
                id: flow
                y: 1 + 12
                width: parent.width
                spacing: 8
                Select {
                    tabular: true; inline: true; label: "Từ"; enabled: !root.locked
                    options: root.times(root.last.from); value: root.last.from
                    onPicked: value => root.changed({from: value, to: root.last.to, minutes: root.last.minutes})
                }
                Item { width: toWord.implicitWidth; height: 40; Text { id: toWord; anchors.verticalCenter: parent.verticalCenter; text: "đến"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall } }
                Select {
                    tabular: true; inline: true; label: "Đến"; enabled: !root.locked
                    options: root.times(root.last.to); value: root.last.to
                    onPicked: value => root.changed({from: root.last.from, to: value, minutes: root.last.minutes})
                }
                Item { width: forWord.implicitWidth; height: 40; Text { id: forWord; anchors.verticalCenter: parent.verticalCenter; text: "hẹn"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall } }
                Select {
                    inline: true; label: "Số phút hẹn"; enabled: !root.locked
                    options: root.minuteOptions; value: root.last.minutes
                    onPicked: value => root.changed({from: root.last.from, to: root.last.to, minutes: Number(value)})
                }
            }
        }
    }
}
