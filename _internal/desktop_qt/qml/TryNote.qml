import QtQuick
import ABook

// Dòng dưới nút "Nghe thử" (note của useTryReading): máy đang đọc thử / đang phát / đã nghe xong / bị từ chối - luôn nói MỘT điều. Bị từ chối vì chưa có Studio thì kèm nút
// dẫn tới chỗ cài. Khép / mở tại chỗ; chữ cuối ở lại trong lúc khép.
Collapse {
    id: root
    property var reading: null
    property string shown: ""
    property bool warns: false
    open: !!reading && reading.note !== ""
    Connections {
        target: root.reading
        ignoreUnknownSignals: true
        function onNoteChanged() { if (root.reading.note !== "") { root.shown = root.reading.note; root.warns = root.reading.warns } }
    }
    Item {
        width: root.width
        height: line.height + (offer.visible ? offer.height + 4 : 0) + 6
        Text {
            id: line
            objectName: "tryNote"
            y: 6
            width: parent.width
            text: root.shown
            color: root.warns ? Theme.warning : Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
            Accessible.role: Accessible.StaticText
        }
        Button {
            id: offer
            objectName: "tryStudio"
            visible: !!root.reading && root.reading.offersStudio
            y: line.y + line.height + 4
            size: "sm"
            kind: "ghost"
            icon: "download"
            text: root.reading ? root.reading.work.store.studioState.action : ""
            onClicked: if (Nav.stack) Nav.stack.show(2)
        }
    }
}
