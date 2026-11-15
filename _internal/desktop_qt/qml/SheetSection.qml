import "TextWrap.js" as TextWrap
import QtQuick
import ABook

// Flat groups shared by player sheets.
Column {
    id: root
    property string title: ""
    property bool first: false
    default property alias content: body.data
    width: parent.width
    topPadding: first ? 0 : Theme.s16
    spacing: Theme.s8
    Text { width: parent.width; text: TextWrap.keepDots(root.title); color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium; wrapMode: Text.Wrap }
    Column { id: body; width: parent.width; spacing: Theme.s8 }
}
