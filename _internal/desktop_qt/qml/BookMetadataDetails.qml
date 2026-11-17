import QtQuick
import ABook
import "UiStrings.js" as S

Column {
    id: root
    property var book: ({})
    property bool expanded: false
    readonly property string summary: book.summary || ""
    readonly property var characters: Array.from(summary)
    width: parent ? parent.width : 320
    spacing: Theme.s8
    Repeater {
        model: [
            {label: S.s_tac_gia_0ec4731b, value: root.book.author || ""},
            {label: S.s_bookmeta_illustrator, value: root.book.illustrator || ""},
            {label: S.s_bookmeta_alt_titles, value: (root.book.altTitles || []).join("; ")}
        ]
        Text {
            id: metadataLine
            Reveal { target: metadataLine; shown: modelData.value !== "" }
            required property var modelData
            width: root.width
            text: modelData.label + " " + modelData.value
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            font.family: Theme.family
            wrapMode: Text.Wrap
        }
    }
    Flow {
        id: genresRow
        Reveal { target: genresRow; shown: (root.book.genres || []).length > 0 }
        width: root.width
        spacing: Theme.s8
        Repeater {
            model: root.book.genres || []
            Rectangle {
                required property string modelData
                implicitWidth: Math.min(root.width, genre.implicitWidth + Theme.s16)
                implicitHeight: genre.implicitHeight + Theme.s8
                color: Theme.sunken
                radius: Theme.radiusControl
                Text { id: genre; width: Math.min(root.width - Theme.s16, implicitWidth); anchors.centerIn: parent; text: modelData; color: Theme.text2; font.family: Theme.family; font.pixelSize: Theme.sizeCaption; wrapMode: Text.Wrap }
            }
        }
    }
    Text {
        id: summaryHeading
        Reveal { target: summaryHeading; shown: root.summary !== "" }
        text: S.s_tom_tat_b4bb3064
        color: Theme.text
        font.family: Theme.family
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightMedium
    }
    Item {
        id: summaryRegion
        Reveal { target: summaryRegion; shown: root.summary !== "" }
        objectName: "bookSummaryRegion"
        width: root.width
        height: root.expanded ? summaryText.implicitHeight : summaryPreview.implicitHeight
        clip: true
        Behavior on height { NumberAnimation { duration: Theme.reduceMotion ? 0 : root.expanded ? Theme.motionMedium : Theme.motionMediumOut; easing.type: Easing.BezierSpline; easing.bezierCurve: root.expanded ? Theme.easeStandard : Theme.easeAccelerate } }
        Text { id: summaryText; width: parent.width; text: root.summary; color: Theme.text2; font.family: Theme.family; font.pixelSize: Theme.sizeBodySmall; lineHeight: 1.5; wrapMode: Text.Wrap }
    }
    Text { id: summaryPreview; visible: false; width: root.width; text: root.summary; font: summaryText.font; lineHeight: 1.5; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
    InlineActionRow {
        id: summaryToggle
        Reveal { target: summaryToggle; shown: summaryText.implicitHeight > summaryPreview.implicitHeight }
        width: root.width
        text: root.expanded ? S.s_thu_gon_1f6bf2c3 : S.s_xem_them_e0ac1b1e
        icon: root.expanded ? "chevron-up" : "chevron-down"
        onClicked: root.expanded = !root.expanded
    }
}
