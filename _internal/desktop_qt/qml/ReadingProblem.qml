import QtQuick
import ABook

// Lời từ chối một cách đọc, ngay dưới ô nhập (ReadingProblem.tsx). Máy chủ có bản viết lại đúng chính tả ("Hên-kơ" -> "Hên-cơ") thì mời dùng bằng một cú bấm.
// Khép / mở tại chỗ bằng Collapse; giữ chữ cuối trong lúc khép để chữ không biến mất trước khung.
Collapse {
    id: root
    property string problem: ""
    property string suggestion: ""
    property string shownProblem: ""
    property string shownSuggestion: ""
    signal used(string spoken)
    open: problem !== ""
    onProblemChanged: if (problem !== "") { shownProblem = problem; shownSuggestion = suggestion }
    onSuggestionChanged: if (problem !== "") shownSuggestion = suggestion
    Item {
        width: root.width
        height: col.height + 6
        Column {
            id: col
            y: 6
            width: parent.width
            spacing: 6
            Text {
                objectName: "readingProblem"
                width: parent.width
                text: root.shownProblem
                color: Theme.danger
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                Accessible.role: Accessible.AlertMessage
                Accessible.name: text
            }
            Button {
                objectName: "readingSuggestion"
                visible: root.shownSuggestion !== ""
                size: "sm"
                kind: "ghost"
                text: "Dùng “" + root.shownSuggestion + "”"
                onClicked: root.used(root.shownSuggestion)
            }
        }
    }
}
