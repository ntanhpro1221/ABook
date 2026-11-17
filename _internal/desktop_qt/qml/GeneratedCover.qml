import QtQuick
import ABook
import "TextWrap.js" as TextWrap
import "UiStrings.js" as S

// Bìa vẽ từ tên khi sách chưa có ảnh: cặp màu cố định băm từ tên (cùng tên, cùng bìa), như ui/src/shared/cover.ts.
// Bảng màu lấy từ Theme.coverPalettes (sinh từ cover.ts); phần băm và tách "Tập N" là bản QML của coverStyle / splitTitle.
Rectangle {
    id: root
    property string title: ""
    // Bìa nhỏ trong hàng danh sách (hàng quyển): chỉ một nhãn ngắn ở giữa - số tập hay hai chữ cái đầu - như BookCover size "sm" của web
    // (chữ 17 px đậm, màu điểm của bảng màu) và `small` của Android.
    property bool initials: false
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
        return m ? [m[1].trim(), (m[2] + " " + m[3]).trim()] : [title.trim(), ""]
    }
    // coverLabel của cover.ts: số tập nếu có, không thì chữ cái đầu của tối đa hai từ dài hơn 2 chữ, bỏ từ nối.
    readonly property var stopWords: ["the", "and", S.s_cua_56cf0ad4, S.s_va_befa210d, S.s_nhung_767e74d8, S.s_cac_d6e0786e, S.s_mot_0231bfca]
    readonly property string label: {
        const volume = parts[1].match(/(\d+)/)
        if (volume) return volume[1]
        return parts[0].split(/\s+/).filter(word => word.length > 2 && stopWords.indexOf(word.toLowerCase()) < 0)
            .slice(0, 2).map(word => word[0].toUpperCase()).join("")
    }

    gradient: Gradient {
        GradientStop { position: 0; color: root.palette[0] }
        GradientStop { position: 1; color: root.palette[1] }
    }

    // Tên sách in trên bìa: thu cỡ chữ cho vừa khung (không cắt, không '...'), chừa chỗ cho nhãn "Tập N" nếu có.
    // Bìa nhỏ (ảnh đại diện trong bảng, < 64 px): chỉ còn tên sách, nhãn "Tập N" đã có ngay trên dòng tên
    readonly property bool compact: width < 64
    Text {
        objectName: "coverInitials"
        visible: root.initials
        anchors.centerIn: parent
        text: root.label
        color: root.palette[2]
        font.pixelSize: 17
        font.weight: Theme.weightBold
    }
    Text {
        visible: !root.initials
        readonly property real pad: root.compact ? 4 : Math.max(8, root.width * 0.08)
        x: pad
        y: pad
        width: root.width - 2 * pad
        height: root.height - 2 * pad - (tagBox.visible ? tagBox.height + 8 : 0)
        verticalAlignment: Text.AlignTop
        text: TextWrap.pretty(root.parts[0])
        color: Theme.coverInk
        wrapMode: Text.Wrap
        fontSizeMode: Text.Fit
        minimumPixelSize: 9
        lineHeight: 1.1
        font.pixelSize: Math.max(11, Math.min(19, root.width * 0.1))
        font.weight: Theme.weightBold
    }
    Rectangle {
        id: tagBox
        Reveal { shown: !root.initials && !root.compact && root.parts[1] !== "" }
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Math.max(8, root.width * 0.08)
        width: tag.implicitWidth + 12
        height: tag.implicitHeight + 6
        radius: Theme.radiusControl
        color: Theme.coverTag
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
