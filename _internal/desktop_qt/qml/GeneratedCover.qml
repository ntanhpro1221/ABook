import QtQuick
import ABook
import "TextWrap.js" as TextWrap
import "UiStrings.js" as S

// Bìa vẽ từ tên khi sách chưa có ảnh: cặp màu cố định băm từ tên (cùng tên, cùng bìa), như ui/src/shared/cover.ts.
// Bảng màu lấy từ Theme.coverPalettes (sinh từ cover.ts); phần băm và tách "Tập N" là bản QML của coverStyle / splitTitle.
Rectangle {
    id: root
    property string title: ""
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

    gradient: Gradient {
        GradientStop { position: 0; color: root.palette[0] }
        GradientStop { position: 1; color: root.palette[1] }
    }

    // Chữ trên bìa nhỏ (coverLabel của cover.ts, CoverArt.label của điện thoại): số tập nếu là sách trong một bộ ("16"),
    // không thì chữ cái đầu của hai chữ có nghĩa.
    readonly property string label: {
        const volume = parts[1].match(/(\d+)/)
        if (volume) return volume[1]
        // Chữ đệm không lấy chữ cái: "the" / "and" của tên tiếng Anh (mẫu, không phải chữ hiện) và các chữ đệm tiếng Việt.
        const stop = [S.s_cua_56cf0ad4, S.s_va_befa210d, S.s_nhung_767e74d8, S.s_cac_d6e0786e, S.s_mot_0231bfca]
        return parts[0].split(/\s+/).filter(word => word.length > 2 && !/^(?:the|and)$/i.test(word) && stop.indexOf(word.toLowerCase()) < 0)
            .slice(0, 2).map(word => word.charAt(0).toUpperCase()).join("")
    }
    // Bìa nhỏ (ảnh đại diện trong bảng, < 64 px): chỉ nhãn ngắn ở giữa, như web xs/sm và `small` của điện thoại - tên dài 26 dòng
    // trong ô 40 px tràn khỏi bìa (soát R8 15-11).
    readonly property bool compact: width < 64
    Text {
        Reveal { shown: root.compact }
        anchors.centerIn: parent
        text: root.label
        color: Theme.coverInk
        font.pixelSize: Math.round(root.width * 0.34)
        font.weight: Theme.weightBold
    }
    // Tên sách in trên bìa: thu cỡ chữ cho vừa khung, chừa chỗ cho nhãn "Tập N" nếu có.
    Text {
        Reveal { shown: !root.compact }
        readonly property real pad: Math.max(8, root.width * 0.08)
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
        Reveal { shown: root.width >= 88 && root.parts[1] !== "" }
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
