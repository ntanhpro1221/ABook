import QtQuick
import ABook

// Bìa vẽ từ tên khi sách chưa có ảnh: cặp màu cố định băm từ tên (cùng tên, cùng bìa), như ui/src/shared/cover.ts.
// Bảng màu lấy từ Theme.coverPalettes (sinh từ cover.ts); phần băm và tách "Tập N" là bản QML của coverStyle / splitTitle.
Rectangle {
    id: root
    property string title: ""
    property int part: 0            // thứ tự phần thật ("Làm tiếp cuốn này"): phần đã đổi tên vẫn mang "Phần N"
    property bool small: false      // bìa ô nhỏ (size "sm" của BookCover): chỉ chữ tắt / số tập giữa bìa (coverLabel)
    radius: Theme.radiusCover

    // FNV-1a như cover.ts hash(); Math.imul có trong QML JS.
    function hash(text) {
        let value = 2166136261
        for (let i = 0; i < text.length; i += 1) {
            value ^= text.charCodeAt(i)
            value = Math.imul(value, 16777619)
        }
        return value >>> 0
    }
    readonly property var palette: Theme.coverPalettes[hash(title.trim().toLowerCase()) % Theme.coverPalettes.length]
    readonly property var parts: {
        const m = title.match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(.+)$/i)
        if (m) return [m[1].trim(), (m[2] + " " + m[3]).trim()]
        return part > 1 ? [title.trim(), "Phần " + part] : [title.trim(), ""]
    }
    // cover.ts coverLabel: số tập nếu là sách trong một bộ, không thì hai chữ cái đầu
    readonly property string label: {
        const volume = parts[1].match(/(\d+)/)
        if (volume) return volume[1]
        const stop = ["the", "and", "của", "và", "những", "các", "một"]
        return parts[0].split(/\s+/).filter(w => w.length > 2 && stop.indexOf(w.toLowerCase()) < 0).slice(0, 2).map(w => w[0].toUpperCase()).join("")
    }

    gradient: Gradient {
        GradientStop { position: 0; color: root.palette[0] }
        GradientStop { position: 1; color: root.palette[1] }
    }

    // Tên sách in trên bìa: thu cỡ chữ cho vừa khung (không cắt, không '...'), chừa chỗ cho nhãn "Tập N" nếu có.
    Text {
        objectName: "coverSmallLabel"
        visible: root.small
        anchors.centerIn: parent
        text: root.label
        color: root.palette[2]
        font.pixelSize: 17
        font.weight: Theme.weightBold
    }
    Text {
        visible: !root.small
        readonly property real pad: Math.max(8, root.width * 0.08)
        x: pad
        y: pad
        width: root.width - 2 * pad
        height: root.height - 2 * pad - (tagBox.visible ? tagBox.height + 8 : 0)
        verticalAlignment: Text.AlignTop
        text: root.parts[0]
        color: "#ffffff"
        wrapMode: Text.Wrap
        fontSizeMode: Text.Fit
        minimumPixelSize: 9
        lineHeight: 1.1
        font.pixelSize: Math.max(11, Math.min(19, root.width * 0.1))
        font.weight: Theme.weightBold
    }
    Rectangle {
        id: tagBox
        visible: !root.small && root.parts[1] !== ""
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Math.max(8, root.width * 0.08)
        width: tag.implicitWidth + 12
        height: tag.implicitHeight + 6
        radius: Theme.radiusControl
        color: "#47000000"
        Text {
            id: tag
            anchors.centerIn: parent
            text: root.parts[1].toUpperCase()
            color: root.palette[2]
            font.pixelSize: Math.max(10, Math.min(13, root.width * 0.07))
            font.weight: Theme.weightMedium
        }
    }
}
